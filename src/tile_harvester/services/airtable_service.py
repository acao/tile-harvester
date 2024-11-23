"""Service for interacting with Airtable."""
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from pyairtable import Api
import logging
import mimetypes
import base64

from ..config import (
    AIRTABLE_ACCESS_TOKEN,
    AIRTABLE_BASE_ID,
    AIRTABLE_TABLE_NAME
)

logger = logging.getLogger(__name__)

class AirtableService:
    """Service for handling Airtable operations."""

    def __init__(self):
        """Initialize the Airtable service."""
        if not all([AIRTABLE_ACCESS_TOKEN, AIRTABLE_BASE_ID]):
            raise ValueError("Airtable credentials not found in environment")
        
        self.api = Api(AIRTABLE_ACCESS_TOKEN)
        self.table = self.api.table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
        logger.info(f"Initialized AirtableService with base {AIRTABLE_BASE_ID}, table {AIRTABLE_TABLE_NAME}")

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
            'Province': properties.get('province'),
            'City': properties.get('city'),
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

    def _attach_image(self, record_id: str, image_path: Path, event_id: str, date_str: str = None) -> None:
        """
        Attach an image to an Airtable record.
        
        Args:
            record_id: ID of the Airtable record
            image_path: Path to the image file
            event_id: The UW prefixed ID from source data
            date_str: Date string for the image (optional)
        """
        logger.info(f"Attempting to attach image for record {record_id}")
        logger.debug(f"Image path: {image_path}")
        logger.debug(f"Event ID: {event_id}")

        if not image_path.exists():
            logger.error(f"Image file not found: {image_path}")
            return
        
        logger.info(f"Image file exists at {image_path}")
            
        try:
            # Create filename using UW ID and date if available
            if date_str:
                filename = f"{event_id}_{date_str}.jpg"
            else:
                filename = f"{event_id}.jpg"
            logger.debug(f"Generated filename: {filename}")

            # Read the image file and encode it
            with open(image_path, 'rb') as file:
                image_data = file.read()
                encoded_image = base64.b64encode(image_data).decode('utf-8')

            # Create the new attachment object according to Airtable's format
            new_attachment = [{
                'url': f'data:image/jpeg;base64,{encoded_image}',
                'filename': filename
            }]

            # Update the record with the new attachment
            # Note: We're not appending to existing attachments, but replacing them
            # This avoids potential issues with attachment object format
            self.table.update(record_id, {
                'Satellite Imagery': new_attachment
            })
                
            logger.info(f"Successfully updated record with image")
            
        except Exception as e:
            logger.error(f"Error attaching image {image_path}: {str(e)}", exc_info=True)

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
        # Get the UW ID from feature properties
        event_id = feature.get('properties', {}).get('id', '')
        logger.info(f"Creating record for event {event_id}")
        
        # Log the lengths of our data
        logger.info(f"Number of sentinel data entries: {len(sentinel_data) if sentinel_data else 0}")
        logger.info(f"Number of image paths: {len(image_paths) if image_paths else 0}")
        
        # Prepare and create the record
        record = self._prepare_record(feature, sentinel_data or [])
        logger.debug(f"Prepared record: {record}")
        
        result = self.table.create(record)
        record_id = result['id']
        logger.info(f"Created record with ID: {record_id}")
        
        # Attach images if we have any
        if image_paths:
            logger.info(f"Attaching {len(image_paths)} images to record")
            
            # If we have sentinel data, use it for dates
            if sentinel_data:
                for i in range(min(len(image_paths), len(sentinel_data))):
                    image_path = image_paths[i]
                    tile_data = sentinel_data[i]
                    date_str = tile_data['date'].strftime('%Y%m%d')
                    logger.debug(f"Processing image {i+1}: {image_path} for date {date_str}")
                    self._attach_image(record_id, image_path, event_id, date_str)
            else:
                # Just attach images without dates
                for i, image_path in enumerate(image_paths):
                    logger.debug(f"Processing image {i+1}: {image_path}")
                    self._attach_image(record_id, image_path, event_id)
        else:
            logger.warning("No images to attach")
        
        return record_id
