"""Service for fetching and filtering GeoJSON data."""
import json
from datetime import datetime
import requests
from pathlib import Path
from typing import Dict, List, Any

from ..config import GEOJSON_URL, GEOJSON_CACHE_FILE

class GeoJSONService:
    """Service for handling GeoJSON data operations."""

    @staticmethod
    def fetch_and_cache() -> Path:
        """
        Fetch GeoJSON data from the URL and cache it locally.
        Returns the path to the cached file.
        """
        response = requests.get(GEOJSON_URL)
        response.raise_for_status()
        
        # Ensure the parent directory exists
        GEOJSON_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the data to cache
        with open(GEOJSON_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(response.json(), f)
        
        return GEOJSON_CACHE_FILE

    @staticmethod
    def load_cached_data() -> Dict[str, Any]:
        """Load the cached GeoJSON data."""
        if not GEOJSON_CACHE_FILE.exists():
            raise FileNotFoundError("Cached GeoJSON file not found. Run fetch_and_cache first.")
        
        with open(GEOJSON_CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def filter_firing_positions(data: Dict[str, Any], year: int = 2023) -> List[Dict[str, Any]]:
        """
        Filter GeoJSON features for Russian firing positions in the specified year.
        
        Args:
            data: The GeoJSON data dictionary
            year: The year to filter for (default: 2023)
            
        Returns:
            List of filtered features
        """
        filtered_features = []
        
        for feature in data.get('features', []):
            properties = feature.get('properties', {})
            
            # Extract and parse the date
            date_str = properties.get('verifiedDate')  # Changed from 'date' to 'verifiedDate'
            if not date_str:
                continue
                
            try:
                date = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d')
            except ValueError:
                continue
                
            # Check if the feature matches our criteria
            categories = properties.get('categories', [])
            if (date.year == year and 
                any(cat.lower() == 'russian firing positions' for cat in categories)):
                filtered_features.append(feature)
        
        return filtered_features

    @classmethod
    def get_firing_positions(cls, year: int = 2023) -> List[Dict[str, Any]]:
        """
        Main method to get filtered firing positions.
        Will fetch and cache data if needed.
        
        Args:
            year: The year to filter for (default: 2023)
            
        Returns:
            List of filtered features
        """
        if not GEOJSON_CACHE_FILE.exists():
            cls.fetch_and_cache()
            
        data = cls.load_cached_data()
        return cls.filter_firing_positions(data, year)

    @staticmethod
    def extract_coordinates(feature: Dict[str, Any]) -> tuple[float, float]:
        """
        Extract coordinates from a GeoJSON feature.
        
        Args:
            feature: A GeoJSON feature
            
        Returns:
            Tuple of (longitude, latitude)
        """
        geometry = feature.get('geometry', {})
        if geometry.get('type') == 'Point':
            coordinates = geometry.get('coordinates', [])
            if len(coordinates) >= 2:
                return coordinates[0], coordinates[1]
        raise ValueError("Invalid feature geometry")
