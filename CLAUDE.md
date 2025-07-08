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

# Using Gemini CLI for Large Codebase Analysis

When analyzing large codebases or multiple files that might exceed context limits, use the Gemini CLI with its massive context window. Use `gemini -p` to leverage Google Gemini's large context capacity.

## File and Directory Inclusion Syntax

Use the `@` syntax to include files and directories in your Gemini prompts. The paths should be relative to WHERE you run the gemini command:

### Examples:

**Single file analysis:**
gemini -p "@src/main.py Explain this file's purpose and structure"

Multiple files:
gemini -p "@package.json @src/index.js Analyze the dependencies used in the code"

Entire directory:
gemini -p "@src/ Summarize the architecture of this codebase"

Multiple directories:
gemini -p "@src/ @tests/ Analyze test coverage for the source code"

Current directory and subdirectories:
gemini -p "@./ Give me an overview of this entire project"

# Or use --all_files flag:
gemini --all_files -p "Analyze the project structure and dependencies"

Implementation Verification Examples

Check if a feature is implemented:
gemini -p "@src/ @lib/ Has dark mode been implemented in this codebase? Show me the relevant files and functions"

Verify authentication implementation:
gemini -p "@src/ @middleware/ Is JWT authentication implemented? List all auth-related endpoints and middleware"

Check for specific patterns:
gemini -p "@src/ Are there any React hooks that handle WebSocket connections? List them with file paths"

Verify error handling:
gemini -p "@src/ @api/ Is proper error handling implemented for all API endpoints? Show examples of try-catch blocks"

Check for rate limiting:
gemini -p "@backend/ @middleware/ Is rate limiting implemented for the API? Show the implementation details"

Verify caching strategy:
gemini -p "@src/ @lib/ @services/ Is Redis caching implemented? List all cache-related functions and their usage"

Check for specific security measures:
gemini -p "@src/ @api/ Are SQL injection protections implemented? Show how user inputs are sanitized"

Verify test coverage for features:
gemini -p "@src/payment/ @tests/ Is the payment processing module fully tested? List all test cases"

When to Use Gemini CLI

Use gemini -p when:
- Analyzing entire codebases or large directories
- Comparing multiple large files
- Need to understand project-wide patterns or architecture
- Current context window is insufficient for the task
- Working with files totaling more than 100KB
- Verifying if specific features, patterns, or security measures are implemented
- Checking for the presence of certain coding patterns across the entire codebase

Important Notes

- Paths in @ syntax are relative to your current working directory when invoking gemini
- The CLI will include file contents directly in the context
- No need for --yolo flag for read-only analysis
- Gemini's context window can handle entire codebases that would overflow Claude's context
- When checking implementations, be specific about what you're looking for to get accurate results