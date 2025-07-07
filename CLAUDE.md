# eBay TCG Batch Uploader - CLAUDE.md

## Project Overview
eBay TCG batch uploader with Pokemon card database integration. Includes PostgreSQL database with 18,065+ Pokemon cards and Flask web UI for searching/filtering.

## Key Commands

### Start Web Application
```bash
cd "/Users/mateoallen/Library/CloudStorage/GoogleDrive-abovebelow.gg@gmail.com/My Drive/Project Folders/eBay TCG Batch Uploader"
python src/web/app.py
```
Access at: http://localhost:5001

### Database Access
```bash
psql -U mateo -d pokemon_cards
```

### Linting & Type Checking
```bash
# Python linting
pylint src/

# Type checking (if mypy is installed)
mypy src/
```

### Run Batch Upload Processing
```bash
python3 run.py
```

## Project Structure
- `src/database/` - Database models and import scripts
- `src/web/` - Flask application with templates and static files
- `src/web/static/images/pokemon/` - Card images by set
- `src/scrapers/` - Bulbapedia scraper for Unlimited edition images
- `src/processing/` - Card identification, pricing, and review systems
- `config.json` - eBay API configuration
- `.env` - Database credentials and API keys
- `Scans/` - Input folder for card images to process

## Recent Updates (July 2025)

### Fixed Issues
- ✅ Fixed `_check_alternatives_for_better_match` error in card_identifier.py
- ✅ Created Bulbapedia scraper for Unlimited edition images
- ✅ Successfully scraped 85/102 Base Set Unlimited images (83.3%)

### Known Issues
- PNG images in Scans folder not accepted by eBay EPS (format compatibility)
- Missing 17 Base Set cards (mostly trainers/energy) from Bulbapedia
- Some Bulbapedia images may still be 1st Edition despite filtering

### Scraper Results
- `base_set_unlimited_images/` - Contains 85 Base Set Unlimited cards
- `test_scraped_images/` - Test images (Charizard, Venusaur, Blastoise)
- Large files (>500KB) are high-quality scans, not necessarily 1st Edition

### Missing Base Set Cards
Trainers: Bill, Professor Oak, Gust of Wind, Super Energy Removal, etc.
Energy: All 7 basic energy cards (Fighting, Fire, Grass, Lightning, Psychic, Water, DCE)

## Important Notes
- Database has full Pokemon TCG API data imported
- Web UI supports filtering by Set, Type, Rarity, and Edition
- Bulbapedia scraper respects rate limits (3 second delay)
- Manual review system tracks low-confidence identifications
- Database URL: postgresql://mateo:pokemon@localhost:5432/pokemon_cards