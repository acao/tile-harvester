"""Service for interacting with Airtable."""
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from airtable import Airtable
import base64

from ..config import (
    AIRTABLE_API_KEY,
    AIRTABLE_BASE_ID,
    AIRTABLE_TABLE_NAME
)

class AirtableService:
    """Service for handling Airtable operations."""

    def __init__(self):
        """Initialize the Airtable service."""
        if not all([AIRTABLE_API_KEY, AIRTABLE_BASE_ID]):
            raise ValueError("Airtable credentials not found in environment")
        
        self.table = Airtable(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME, AIRTABLE_API_KEY)

    def _prepare_record(
        self,
        feature: Dict[str, Any],
        sentinel_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Prepare a record for Airtable from a GeoJSON feature and Sentinel data.
        
        Args:
            feature: GeoJSON feature containing firing position data
            sentinel_data: List of associated Sentinel tile data
            
        Returns:
            Dictionary formatted for Airtable record creation
        """
        properties = feature.get('properties', {})
        geometry = feature.get('geometry', {})
        coordinates = geometry.get('coordinates', [])
        
        # Parse the ISO date
        date_str = properties.get('verifiedDate', '').split('T')[0] if properties.get('verifiedDate') else None
        
        record = {
            'Date': date_str,
            'ID': properties.get('id'),
            'Type': properties.get('type'),
            'Description': properties.get('description'),
            'Source': 'CIR',  # Default to CIR as per example
            'Longitude': str(coordinates[0]) if len(coordinates) > 0 else None,
            'Latitude': str(coordinates[1]) if len(coordinates) > 1 else None,
            'Original URL': properties.get('url'),
            'Geolocation URL': properties.get('geolocUrl'),
            'Status': properties.get('status', 'Pending Review'),
            'Country': properties.get('country'),
            'Province': properties.get('province'),
            'City': properties.get('city'),
            'Categories': ', '.join(properties.get('categories', [])),
            'Violence Level': properties.get('violenceLevel'),
            'Civilian Casualties': 'Yes' if properties.get('civCas') else 'No'
        }
        
        # Add Sentinel data
        if sentinel_data:
            sentinel_info = []
            for idx, tile in enumerate(sentinel_data, 1):
                sentinel_info.append(
                    f"Tile {idx}:\n"
                    f"Date: {tile['date'].strftime('%Y-%m-%d')}\n"
                    f"Cloud Coverage: {tile['cloud_coverage']}%\n"
                    f"Title: {tile['title']}\n"
                    f"Download: {tile['download_link']}"
                )
            record['Sentinel Data'] = '\n\n'.join(sentinel_info)
        
        return record

    def _attach_image(self, record_id: str, image_path: Path, title: str) -> None:
        """
        Attach an image to an Airtable record.
        
        Args:
            record_id: ID of the Airtable record
            image_path: Path to the image file
            title: Title for the attachment
        """
        if not image_path.exists():
            print(f"Warning: Image file not found: {image_path}")
            return
            
        try:
            with open(image_path, 'rb') as file:
                encoded_image = base64.b64encode(file.read()).decode('utf-8')
                
                self.table.update(record_id, {
                    'Satellite Imagery': [
                        {
                            'url': f'data:image/jpeg;base64,{encoded_image}',
                            'filename': title
                        }
                    ]
                })
        except Exception as e:
            print(f"Error attaching image {image_path}: {str(e)}")

    def create_record(
        self,
        feature: Dict[str, Any],
        sentinel_data: List[Dict[str, Any]],
        image_paths: List[Path]
    ) -> str:
        """
        Create a new record in Airtable with feature data and attachments.
        
        Args:
            feature: GeoJSON feature containing firing position data
            sentinel_data: List of associated Sentinel tile data
            image_paths: List of paths to Sentinel imagery files
            
        Returns:
            ID of the created record
        """
        # Prepare and create the record
        record = self._prepare_record(feature, sentinel_data)
        result = self.table.insert(record)
        record_id = result['id']
        
        # Attach images
        for image_path, tile_data in zip(image_paths, sentinel_data):
            title = f"Sentinel-2 {tile_data['date'].strftime('%Y-%m-%d')}"
            self._attach_image(record_id, image_path, title)
        
        return record_id
