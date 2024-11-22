"""Service for interacting with Copernicus/Sentinel data."""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
import logging
from functools import lru_cache
import pyproj
from shapely.geometry import box
import json

from ..config import (
    COPERNICUS_USER,
    COPERNICUS_PASSWORD,
    MAX_CLOUD_COVERAGE,
    TEMPORAL_WINDOW_DAYS,
    DATA_DIR
)

logger = logging.getLogger(__name__)

class SentinelService:
    """Service for handling Sentinel satellite data operations using Copernicus Dataspace API."""

    AUTH_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"
    COLLECTION_ID = "byoc-5460de54-082e-473a-b6ea-d5cbe3c17cca"  # Sentinel-2 L2A collection

    # Evalscript for RGB visualization with enhancements
    EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: ["B04","B03","B02", "dataMask"],
    output: { bands: 4 }
  };
}

// Contrast enhance / highlight compress
const maxR = 3.0; // max reflectance
const midR = 0.13;
const sat = 1.2;
const gamma = 1.8;
const scalefac = 10000;

function evaluatePixel(smp) {
  const rgbLin = satEnh(sAdj(smp.B04/scalefac), sAdj(smp.B03/scalefac), sAdj(smp.B02/scalefac));
  return [sRGB(rgbLin[0]), sRGB(rgbLin[1]), sRGB(rgbLin[2]), smp.dataMask];
}

function sAdj(a) {
  return adjGamma(adj(a, midR, 1, maxR));
}

const gOff = 0.01;
const gOffPow = Math.pow(gOff, gamma);
const gOffRange = Math.pow(1 + gOff, gamma) - gOffPow;

function adjGamma(b) {
  return (Math.pow((b + gOff), gamma) - gOffPow)/gOffRange;
}

// Saturation enhancement
function satEnh(r, g, b) {
  const avgS = (r + g + b) / 3.0 * (1 - sat);
  return [clip(avgS + r * sat), clip(avgS + g * sat), clip(avgS + b * sat)];
}

function clip(s) {
  return s < 0 ? 0 : s > 1 ? 1 : s;
}

//contrast enhancement with highlight compression
function adj(a, tx, ty, maxC) {
  var ar = clip(a / maxC, 0, 1);
  return ar * (ar * (tx/maxC + ty -1) - ty) / (ar * (2 * tx/maxC - 1) - tx/maxC);
}

const sRGB = (c) => c <= 0.0031308 ? (12.92 * c) : (1.055 * Math.pow(c, 0.41666666666) - 0.055);"""

    def __init__(self):
        """Initialize the Sentinel service."""
        if not all([COPERNICUS_USER, COPERNICUS_PASSWORD]):
            raise ValueError("Copernicus credentials not found in environment")
        
        self.session = requests.Session()
        self._refresh_token()
        
        # Create directory for Sentinel data
        self.data_dir = DATA_DIR / "sentinel"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _refresh_token(self) -> None:
        """Get a new access token and update session headers."""
        try:
            response = requests.post(
                self.AUTH_URL,
                data={
                    'grant_type': 'password',
                    'username': COPERNICUS_USER,
                    'password': COPERNICUS_PASSWORD,
                    'client_id': 'cdse-public'
                },
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            )
            response.raise_for_status()
            token_data = response.json()
            
            # Update session headers with the new token
            self.session.headers.update({
                'Authorization': f"Bearer {token_data['access_token']}",
                'Accept': 'application/json',
                'Origin': 'https://browser.dataspace.copernicus.eu',
                'Accept-CRS': 'EPSG:4326,EPSG:3857'
            })
            
            logger.debug("Successfully refreshed access token")
            
        except Exception as e:
            logger.error(f"Error getting access token: {str(e)}")
            raise

    @staticmethod
    @lru_cache(maxsize=None)
    def _create_transformer():
        """Create a cached coordinate transformer."""
        return pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)

    def _create_bbox(self, lon: float, lat: float, buffer_km: float = 0.3) -> Dict[str, Any]:
        """
        Create a bounding box around a point in EPSG:3857.
        
        Args:
            lon: Longitude of the point
            lat: Latitude of the point
            buffer_km: Buffer size in kilometers
            
        Returns:
            Dictionary with bbox in EPSG:3857 format
        """
        # Convert coordinates to Web Mercator for metric calculations
        transformer = self._create_transformer()
        x, y = transformer.transform(lon, lat)
        
        # Create buffer in meters
        buffer_m = buffer_km * 1000
        bbox = box(x - buffer_m, y - buffer_m, x + buffer_m, y + buffer_m)
        bounds = bbox.bounds
        
        return {
            "properties": {
                "crs": "http://www.opengis.net/def/crs/EPSG/0/3857"
            },
            "bbox": list(bounds)
        }

    def _handle_auth_error(self, response: requests.Response) -> bool:
        """
        Handle authentication errors by refreshing the token if needed.
        Returns True if the token was refreshed.
        """
        if response.status_code == 403:
            logger.debug("Got 403, refreshing token and retrying")
            self._refresh_token()
            return True
        return False

    def find_and_process_tiles(
        self,
        lon: float,
        lat: float,
        target_date: datetime,
        width: int = 512,
        height: int = 512
    ) -> Optional[Path]:
        """
        Find and process Sentinel tiles for a given location and date.
        
        Args:
            lon: Longitude of the point
            lat: Latitude of the point
            target_date: Target date for imagery
            width: Output image width
            height: Output image height
            
        Returns:
            Path to the processed image file
        """
        logger.info(f"Processing tiles for point ({lon}, {lat}) on {target_date.date()}")
        
        try:
            # Calculate date range using TEMPORAL_WINDOW_DAYS
            start_date = target_date - timedelta(days=TEMPORAL_WINDOW_DAYS)
            end_date = target_date + timedelta(days=TEMPORAL_WINDOW_DAYS)
            
            # Create request payload
            payload = {
                "input": {
                    "bounds": self._create_bbox(lon, lat),
                    "data": [{
                        "dataFilter": {
                            "timeRange": {
                                "from": start_date.strftime('%Y-%m-%dT00:00:00.000Z'),
                                "to": end_date.strftime('%Y-%m-%dT23:59:59.999Z')
                            },
                            "mosaickingOrder": "mostRecent",
                            "previewMode": "EXTENDED_PREVIEW"
                        },
                        "processing": {
                            "upsampling": "BICUBIC",
                            "downsampling": "NEAREST"
                        },
                        "type": self.COLLECTION_ID
                    }]
                },
                "output": {
                    "width": width,
                    "height": height,
                    "responses": [{
                        "identifier": "default",
                        "format": {
                            "type": "image/png"
                        }
                    }]
                },
                "evalscript": self.EVALSCRIPT
            }
            
            logger.debug(f"Processing request payload: {json.dumps(payload, indent=2)}")
            
            # Make the processing request with specific headers
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'image/png',
                'Cache-Control': 'no-cache'
            }
            
            response = self.session.post(
                self.PROCESS_URL,
                json=payload,
                headers=headers
            )
            
            # Retry once with fresh token if we get a 403
            if self._handle_auth_error(response):
                response = self.session.post(
                    self.PROCESS_URL,
                    json=payload,
                    headers=headers
                )
            
            response.raise_for_status()
            
            # Check if response is JSON (error) or binary (image)
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                error_data = response.json()
                logger.error(f"API returned error: {json.dumps(error_data, indent=2)}")
                return None
            
            if 'image/png' not in content_type:
                logger.error(f"Unexpected content type: {content_type}")
                return None
            
            # Save the processed image
            file_path = self.data_dir / f"sentinel_{target_date.strftime('%Y%m%d')}_{lon:.6f}_{lat:.6f}.png"
            
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Successfully saved processed image to {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error processing tiles: {str(e)}", exc_info=True)
            return None

    def process_feature(
        self,
        feature: Dict[str, Any],
        target_date: datetime
    ) -> Optional[Path]:
        """
        Process a GeoJSON feature to get Sentinel imagery.
        
        Args:
            feature: GeoJSON feature containing location data
            target_date: Target date for imagery
            
        Returns:
            Path to the processed image file
        """
        try:
            # Extract coordinates
            geometry = feature.get('geometry', {})
            if geometry.get('type') != 'Point':
                logger.warning("Feature geometry is not a point")
                return None
            
            coordinates = geometry.get('coordinates', [])
            if len(coordinates) < 2:
                logger.warning("Invalid coordinates in feature")
                return None
            
            lon, lat = coordinates
            
            # Process the tiles
            return self.find_and_process_tiles(lon, lat, target_date)
            
        except Exception as e:
            logger.error(f"Error processing feature: {str(e)}", exc_info=True)
            return None
