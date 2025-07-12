# Directory Structure

> Last Updated: November 11, 2025

## Overview
The project has been reorganized with a proper directory structure for all assets and workflows.

## Main Directories

### `/assets/`
Central location for all static assets (images, data files, etc.)

- `/assets/images/` - All card images organized by game type
  - `/assets/images/pokemon/` - Pokemon TCG images
    - `/assets/images/pokemon/english/` - English card sets (base1, base2, etc.)
    - `/assets/images/pokemon/japanese/` - Japanese card sets organized by set name
  - `/assets/images/mtg/` - Magic: The Gathering images (future)

### `/input/`
User workspace for scanning cards
- Place scanned card images here for processing
- The application will automatically detect and process images from this directory

### `/output/`
Processing results and generated files
- `/output/scans/` - Processed scan results
- `/output/ultra_cache/` - Application cache
- `/output/manual_review/` - Cards requiring manual review
- Excel files and other exports are saved here

### `/src/`
Application source code
- `/src/web/` - Web interface
  - `/src/web/static/images` - Symlink to `/assets/images` for backward compatibility
  - `/src/web/templates/` - HTML templates

## Web Access
- Static files: `http://localhost:5000/static/<path>`
- Asset files: `http://localhost:5000/assets/<path>`

## Migration Notes
- All Japanese Pokemon cards have been moved from `japanese_pokemon_cards_complete/` to `/assets/images/pokemon/japanese/`
- All English Pokemon cards have been moved from `src/web/static/images/pokemon/` to `/assets/images/pokemon/english/`
- The old `Scans` folder functionality is now handled by the `/input/` directory
- All code has been updated to reference the new paths