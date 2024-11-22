# Tile Harvester

A Python tool for harvesting and analyzing satellite imagery for specific locations. This tool:

1. Retrieves and caches data from eyesonrussia.org's GeoJSON feed
2. Filters for Russian firing positions from a specified year
3. Fetches corresponding Sentinel-2 satellite imagery from Copernicus Data Hub
4. Creates Airtable records with the data and imagery for analysis

## Requirements

- Python 3.12 or higher
- Copernicus Data Hub account (https://scihub.copernicus.eu/)
- Airtable account and API key
- uv (modern Python packaging tools)

## Installation

1. Install uv if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone the repository:
```bash
git clone https://github.com/yourusername/tile-harvester.git
cd tile-harvester
```

3. Create a virtual environment and install dependencies:
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

The project uses a `uv.lock` file to ensure reproducible installations. This lock file is automatically maintained by uv.

## Configuration

1. Copy the `.env.template` file to `.env`:
```bash
cp .env.template .env
```

2. Edit `.env` and fill in your credentials:
```
# Copernicus Data Hub credentials
COPERNICUS_USER=your_username
COPERNICUS_PASSWORD=your_password

# Airtable credentials
AIRTABLE_API_KEY=your_api_key
AIRTABLE_BASE_ID=your_base_id
AIRTABLE_TABLE_NAME=Firing Positions  # Optional, defaults to "Firing Positions"
```

### Airtable Setup

Create a new base in Airtable with the following fields:

- Date (Date)
- Type (Single line text)
- Description (Long text)
- Source (Single line text)
- Longitude (Single line text)
- Latitude (Single line text)
- Original URL (URL)
- Status (Single select: Pending Review, Reviewed, etc.)
- Sentinel Data (Long text)
- Satellite Imagery (Attachment)

## Usage

Run the tile harvester:

```bash
python -m tile_harvester.main
```

By default, it will process firing positions from 2023. To specify a different year:

```python
from tile_harvester.main import TileHarvester

harvester = TileHarvester()
harvester.run(year=2022)  # Process positions from 2022
```

## Development

For development work:

1. Install development dependencies:
```bash
uv pip install -e ".[dev]"
```

2. Update dependencies (when pyproject.toml changes):
```bash
uv pip compile pyproject.toml -o uv.lock
uv pip sync uv.lock
```

## Data Flow

1. The tool fetches and caches the GeoJSON data from eyesonrussia.org
2. It filters the data for firing positions in the specified year
3. For each position:
   - Searches for the closest Sentinel-2 imagery (temporally)
   - Downloads the imagery tiles
   - Creates an Airtable record with the position data and imagery
4. Logs are saved in the `data/logs` directory

## Output

The tool creates:

- Cached GeoJSON data in `data/cache`
- Downloaded Sentinel imagery in `data/sentinel`
- Detailed logs in `data/logs`
- Airtable records with:
  - Position details (date, coordinates, description, etc.)
  - Links to Sentinel imagery
  - Uploaded satellite imagery tiles

## Error Handling

- All errors are logged to both console and log files
- The tool continues processing remaining positions if one fails
- Failed positions are logged for review

## Contributing

1. Fork the repository
2. Create a feature branch
3. Install development dependencies: `uv pip install -e ".[dev]"`
4. Make your changes
5. Run tests: `pytest`
6. Update dependencies if needed: `uv pip compile pyproject.toml -o uv.lock`
7. Commit your changes
8. Push to the branch
9. Create a Pull Request
