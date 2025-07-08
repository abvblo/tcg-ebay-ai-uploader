# Product Requirements Document - eBay TCG Batch Uploader (Updated July 2025)

## Executive Summary

The eBay TCG Batch Uploader is a comprehensive solution for automating the process of identifying, pricing, and creating eBay listings for Trading Card Game (TCG) cards. The system has been significantly enhanced with advanced finish detection capabilities and automatic image optimization to maximize listing quality and search visibility.

## Key Features & Enhancements

### 🎯 Core Functionality
- **Automated Card Identification**: Uses Ximilar API for accurate card recognition
- **Intelligent Finish Detection**: Preserves specific finish types (Reverse Holo, Holo, Foil, etc.)
- **Database Integration**: PostgreSQL with 18,065+ Pokemon cards for validation
- **Automatic Image Optimization**: Converts large PNG files to optimal eBay formats
- **Batch Processing**: Handles multiple cards simultaneously with concurrent processing
- **eBay Listing Generation**: Creates optimized titles and descriptions for maximum search visibility

### 🔧 Recent Major Updates (July 2025)

#### 1. Enhanced Finish Detection System
**Problem Solved**: 37.3% of cards were missing finish information in listing titles despite accurate detection.

**Key Improvements**:
- **Ximilar Finish Preservation**: Modified `_determine_card_finish()` to preserve Ximilar's specific finish detection (especially "Reverse Holo")
- **Enhanced Title Generation**: Updated `_generate_fallback_title()` to include important finish terms like "Reverse Holo" and "Holo"
- **Duplication Prevention**: Added logic to prevent redundant finish terms (e.g., "Rare Holo Holo" → "Rare Holo")

**Impact**: 
- Butterfree now correctly displays as "Pokémon Butterfree 14/106 Great Encounters Rare Reverse Holo NM/LP" instead of "Pokémon Butterfree 14/106 Great Encounters Rare NM/LP"
- Significant improvement in search visibility for finish-specific terms

#### 2. Automatic Image Optimization
**Problem Solved**: PNG files in Scans directory were 30MB each, causing performance issues.

**Solution Implemented**:
- **Automatic Conversion**: PNG to JPEG with optimal eBay specifications
- **Optimal Sizing**: Resizes images to 1600px maximum dimension
- **Quality Optimization**: 85% JPEG quality for best size/quality balance
- **In-Place Processing**: Files are optimized directly in the input directory
- **Performance Gain**: 98.4% file size reduction (30MB → 500KB)

**Files Created**:
- `src/processing/image_optimizer.py`: New image optimization module
- Integration in `src/processing/group_detector.py`: Automatic optimization in processing pipeline

### 📊 Technical Architecture

#### Database Schema
- **PostgreSQL Database**: `pokemon_cards` with comprehensive card data
- **Connection**: `postgresql://mateo:pokemon@localhost:5432/pokemon_cards`
- **Data Source**: Pokemon TCG API with 18,065+ cards imported

#### Processing Pipeline
1. **Image Optimization**: Automatic conversion to optimal formats
2. **Card Detection**: Ximilar API identification with confidence scoring
3. **Finish Preservation**: Maintains specific finish types from detection
4. **Database Validation**: Cross-references with Pokemon TCG database
5. **eBay Formatting**: Optimized titles and descriptions generation
6. **Excel Export**: Structured output for review and bulk upload

#### Key Components
- **Card Identifier** (`src/processing/card_identifier.py`): Core identification logic
- **Image Optimizer** (`src/processing/image_optimizer.py`): Automatic image processing
- **Title Generator** (`src/api/openai_titles.py`): eBay-optimized title creation
- **Group Detector** (`src/processing/group_detector.py`): Batch processing orchestration
- **eBay Formatter** (`src/output/ebay_formatter.py`): Listing format optimization

### 🚀 Performance Improvements

#### Processing Speed
- **Concurrent Processing**: Uses `asyncio.gather()` for parallel operations
- **Batch Optimization**: Groups similar operations for efficiency
- **Timeout Handling**: Increased from 30s to 120s for large batches

#### Image Performance
- **File Size Reduction**: 30MB PNG → 500KB JPEG (98.4% reduction)
- **Optimal Dimensions**: 1600px maximum for eBay requirements
- **Quality Balance**: 85% JPEG quality maintains visual quality

#### Detection Accuracy
- **Finish Preservation**: Ximilar's 96.8% confidence "Reverse Holo" detection now preserved
- **Database Integration**: Maintains accuracy while preventing override of good detection
- **Title Quality**: Important finish terms included in searchable titles

### 🛠️ Configuration

#### Essential Settings
```json
{
  "processing": {
    "auto_optimize_images": true,
    "batch_size": 20,
    "timeout_seconds": 120,
    "preserve_ximilar_finish": true
  },
  "image_optimization": {
    "max_dimension": 1600,
    "jpeg_quality": 85,
    "format": "JPEG"
  }
}
```

#### Environment Variables
- `DATABASE_URL`: PostgreSQL connection string
- `XIMILAR_API_KEY`: Card identification API key
- `OPENAI_API_KEY`: Title optimization (optional)

### 📈 Quality Metrics

#### Before Updates
- **Missing Finish Info**: 37.3% of cards (69/185)
- **File Sizes**: 30MB PNG files
- **Detection Loss**: Ximilar's accurate detection overridden by database defaults

#### After Updates
- **Finish Preservation**: ✅ Ximilar's specific detection maintained
- **File Optimization**: ✅ 98.4% size reduction with maintained quality
- **Title Quality**: ✅ Important finish terms included in listings
- **Search Visibility**: ✅ Enhanced discoverability for finish-specific searches

### 🔍 Testing & Validation

#### Automated Testing
- **Unit Tests**: Individual component validation
- **Pipeline Tests**: End-to-end finish preservation
- **Integration Tests**: Database and API interactions

#### Test Results
```
✅ Input: 'Reverse Holo' → Output: 'Reverse Holo' (Preserved)
✅ Butterfree [Reverse Holo]: "Pokémon Butterfree 14/106 Great Encounters Rare Reverse Holo NM/LP"
✅ Charizard [Holo]: "Pokémon Charizard 4/102 Base Set Rare Holo NM/LP"
✅ Pikachu [Non-Holo]: "Pokémon Pikachu 25/102 Base Set NM/LP" (Correctly excluded)
```

### 🎯 Business Impact

#### Enhanced Listing Quality
- **Accurate Descriptions**: Finish information properly preserved and displayed
- **Search Optimization**: Titles include terms buyers actively search for
- **Professional Presentation**: Optimal image quality and sizing

#### Operational Efficiency
- **Automated Processing**: Reduced manual intervention required
- **File Management**: Automatic optimization prevents upload issues
- **Batch Capabilities**: Process multiple cards simultaneously

#### Market Positioning
- **Competitive Advantage**: More accurate and complete listings
- **Buyer Trust**: Detailed and accurate card descriptions
- **Search Visibility**: Better ranking in eBay search results

### 📋 Usage Instructions

#### 1. Setup
```bash
# Start PostgreSQL database
psql -U mateo -d pokemon_cards

# Start web application
cd "/Users/mateoallen/Library/CloudStorage/GoogleDrive-abovebelow.gg@gmail.com/My Drive/Project Folders/eBay TCG Batch Uploader"
python src/web/app.py
```

#### 2. Processing
```bash
# Place card images in Scans/ directory
# Run batch processing
python3 run.py
```

#### 3. Review & Export
- Access web interface at http://localhost:5001
- Review generated listings in Excel output
- Import to eBay for bulk upload

### 🔮 Future Enhancements

#### Planned Features
- **Multi-Game Support**: Expand beyond Pokemon to MTG, Yu-Gi-Oh
- **Advanced Pricing**: Dynamic market pricing integration
- **Condition Assessment**: Automated condition grading
- **Bulk Upload Integration**: Direct eBay API integration

#### Technical Improvements
- **Machine Learning**: Enhanced finish detection accuracy
- **Performance Optimization**: Further processing speed improvements
- **UI/UX**: Enhanced web interface for better user experience

### 📞 Support & Documentation

#### Key Commands
- **Web App**: `python src/web/app.py`
- **Database**: `psql -U mateo -d pokemon_cards`
- **Linting**: `pylint src/`
- **Processing**: `python3 run.py`

#### Documentation Files
- `CLAUDE.md`: Developer instructions and context
- `FINISH_DETECTION_FIXES.md`: Detailed fix documentation
- `test_finish_fixes.py`: Testing and validation scripts

This updated system represents a significant advancement in TCG listing automation, with particular focus on accuracy, efficiency, and market optimization. The enhanced finish detection and automatic image optimization features directly address the most critical pain points in the previous version while maintaining the robust foundation of the original system.