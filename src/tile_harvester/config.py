"""Configuration management for the tile harvester."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"

# Create necessary directories
DATA_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

# API configurations
COPERNICUS_USER = os.getenv("COPERNICUS_USER")
COPERNICUS_PASSWORD = os.getenv("COPERNICUS_PASSWORD")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "Firing Positions")

# Data source
GEOJSON_URL = "https://eyesonrussia.org/events.geojson"
GEOJSON_CACHE_FILE = CACHE_DIR / "events.geojson"

# Sentinel search parameters
SENTINEL_PRODUCT_TYPE = "S2MSI2A"  # Changed to Level 1C for better availability
MAX_CLOUD_COVERAGE = 30  # Increased maximum cloud coverage percentage
TEMPORAL_WINDOW_DAYS = 7  # Increased temporal window to 30 days
