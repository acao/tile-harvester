"""Main script for the tile harvester application."""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from .services.geojson_service import GeoJSONService
from .services.sentinel_service import SentinelService
from .services.airtable_service import AirtableService
from .config import DATA_DIR, LOG_LEVEL

# Set up logging with debug level
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TileHarvester:
    """Main class for coordinating the tile harvesting process."""

    def __init__(self):
        """Initialize the TileHarvester with its component services."""
        self.geojson_service = GeoJSONService()
        self.sentinel_service = SentinelService()
        self.airtable_service = AirtableService()
        
        # Create log directory
        self.log_dir = DATA_DIR / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _process_feature(
        self,
        feature: Dict[str, Any]
    ) -> Optional[str]:
        """
        Process a single feature through the pipeline.
        
        Args:
            feature: GeoJSON feature to process
            
        Returns:
            Airtable record ID if successful, None otherwise
        """
        try:
            # Extract coordinates and date
            lon, lat = self.geojson_service.extract_coordinates(feature)
            date_str = feature['properties'].get('verifiedDate')
            if not date_str:
                logger.warning(f"No date found for feature: {feature}")
                return None
                
            target_date = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d')
            
            logger.debug(f"Processing feature at ({lon}, {lat}) for date {target_date}")
            
            # Process Sentinel imagery
            image_path = self.sentinel_service.process_feature(feature, target_date)
            
            if not image_path:
                logger.warning(
                    f"No suitable Sentinel imagery found for position "
                    f"({lon}, {lat}) on {date_str}"
                )
                return None
            
            # Create Airtable record with processed image
            record_id = self.airtable_service.create_record(
                feature,
                [],  # No Sentinel metadata needed since we're using processed images
                [image_path]
            )
            
            logger.info(
                f"Successfully processed position ({lon}, {lat}) "
                f"on {date_str} - Airtable record: {record_id}"
            )
            
            return record_id
            
        except Exception as e:
            logger.error(f"Error processing feature: {str(e)}", exc_info=True)
            return None

    def run(self, year: int = 2023) -> None:
        """
        Run the tile harvesting process.
        
        Args:
            year: Year to filter positions for (default: 2023)
        """
        try:
            # Start logging to file
            log_file = self.log_dir / f"harvest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            logger.addHandler(file_handler)
            
            logger.info(f"Starting tile harvest for year {year}")
            
            # Get firing positions
            positions = self.geojson_service.get_firing_positions(year)
            logger.info(f"Found {len(positions)} firing positions to process")
            
            # Process each position
            successful = 0
            for idx, feature in enumerate(positions, 1):
                logger.info(f"Processing position {idx}/{len(positions)}")
                if self._process_feature(feature):
                    successful += 1
            
            logger.info(
                f"Tile harvest complete. Successfully processed "
                f"{successful}/{len(positions)} positions"
            )
            
        except Exception as e:
            logger.error(f"Error during tile harvest: {str(e)}", exc_info=True)
            raise
        finally:
            logger.removeHandler(file_handler)

def main():
    """Entry point for the tile harvester."""
    harvester = TileHarvester()
    harvester.run()

if __name__ == "__main__":
    main()
