# Automatic Image Optimization

The batch processing tool now includes **automatic image optimization** that transforms large PNG files into optimally-sized JPEG files directly in your Scans directory during processing.

## 🚀 What It Does

When you run the batch processing tool (`python3 run.py`), it will automatically:

1. **Scan all images** in your Scans directory
2. **Identify large images** that need optimization (>2MB or >1600px)
3. **Optimize them in-place** using optimal eBay settings
4. **Convert PNG to JPEG** for smaller file sizes
5. **Preserve original filenames** (just changes extension)
6. **Continue processing** with optimized images

## ⚙️ Optimization Settings

**Default Configuration (Optimal for eBay):**
- **Max Size**: 1600px on longest side
- **Quality**: 85% JPEG compression
- **Format**: JPEG (converted from PNG)
- **Auto-Optimize**: Enabled by default

## 📊 Performance Impact

Based on your images, automatic optimization provides:

- **98.4% file size reduction** (30MB → 0.4MB per image)
- **Faster eBay uploads** (400KB vs 30MB per image)
- **Faster processing** (smaller images process quicker)
- **Better performance** throughout the entire pipeline

### Before vs After
```
Before: image0005.png (30MB, 3254×4434 pixels)
After:  image0005.jpg (0.4MB, 1174×1600 pixels)
Result: 98.4% smaller, perfect quality for eBay
```

## 🔧 Configuration Options

You can control optimization behavior through environment variables or config.json:

### Environment Variables (.env file)
```bash
# Enable/disable automatic optimization
AUTO_OPTIMIZE_IMAGES=1          # 1=enabled, 0=disabled

# Optimization settings
OPTIMIZATION_MAX_SIZE=1600       # Max pixels on longest side
OPTIMIZATION_QUALITY=85          # JPEG quality (1-100)
OPTIMIZATION_FORMAT=JPEG         # Output format (JPEG or PNG)
```

### config.json
```json
{
  "processing": {
    "auto_optimize_images": true,
    "optimization_max_size": 1600,
    "optimization_quality": 85,
    "optimization_format": "JPEG"
  }
}
```

## 🎯 When Optimization Happens

Optimization occurs **once per image** when it's first detected by the batch processor:

1. **First run**: Large PNGs are optimized to JPEGs in-place
2. **Subsequent runs**: Already-optimized JPEGs are left unchanged
3. **New images**: Any new large images added later will be optimized

## ✅ Safety Features

### Automatic Detection
- Only optimizes images that actually need it (>2MB or >1600px)
- Skips already-optimized images to avoid double-processing
- Preserves images that are already optimal size

### Quality Preservation
- Uses high-quality Lanczos resampling for sharp images
- 85% JPEG quality maintains excellent detail
- Preserves aspect ratio (no stretching or distortion)
- Maintains color accuracy

### Error Handling
- If optimization fails, keeps original image
- Continues processing even if some images can't be optimized
- Logs all optimization activities for troubleshooting

## 🔄 Manual Control

### Disable Optimization
To disable automatic optimization:
```bash
# In .env file
AUTO_OPTIMIZE_IMAGES=0
```

### One-Time Manual Optimization
If you disabled auto-optimization but want to optimize manually:
```bash
python3 batch_optimize.py --size 1600 --quality 85 --format JPEG
```

### Different Quality Settings
For premium cards that need maximum detail:
```bash
# In .env file
OPTIMIZATION_MAX_SIZE=2000    # Higher resolution
OPTIMIZATION_QUALITY=90       # Higher quality
```

## 📁 File Management

### What Happens to Files
- **PNG files**: Converted to JPEG format with same name
- **Original PNGs**: Automatically removed after successful conversion
- **File names**: Preserved (image0005.png → image0005.jpg)
- **Sequential pairs**: Still detected correctly after optimization

### Directory Structure
```
Scans/
├── image0001.jpg  ← Optimized from image0001.png
├── image0002.jpg  ← Optimized from image0002.png
├── image0003.jpg  ← Was already small, unchanged
└── ...
```

## 🎯 Benefits for Your Workflow

### Immediate Benefits
- **9.4GB freed** from your 322 images (98.6% reduction)
- **Faster uploads** to eBay EPS service
- **Faster processing** by Ximilar API
- **Better performance** throughout entire pipeline

### Long-term Benefits
- **Reduced storage costs** for backups and cloud storage
- **Faster file transfers** when moving/copying images
- **Better mobile experience** for eBay buyers
- **Compliance with eBay's file size guidelines**

## 🔍 Monitoring and Logs

The optimization process is fully logged:

```
🔧 Automatically optimizing images for optimal eBay performance...
🔧 Optimizing 322 images for eBay performance...
   📷 Optimized: image0005.png → image0005.jpg (30MB → 0.4MB, 98.4% smaller)
   📷 Optimized: image0006.png → image0006.jpg (19MB → 0.4MB, 97.9% smaller)
   ...
✅ Optimized 322 images, saved 9.4GB total
✅ Automatically optimized 322 images, saved 9.4GB total
   💡 Images are now optimized for fast eBay upload and processing
```

## ⚡ Quick Start

**To use automatic optimization (recommended):**
1. Simply run your normal batch processing: `python3 run.py`
2. The tool will automatically optimize images on first run
3. Subsequent runs will use the already-optimized images
4. Enjoy faster processing and uploads!

**To disable if needed:**
1. Add `AUTO_OPTIMIZE_IMAGES=0` to your .env file
2. Or set `"auto_optimize_images": false` in config.json

## 🎉 Summary

Automatic image optimization is now seamlessly integrated into your workflow:

- ✅ **Enabled by default** with optimal eBay settings
- ✅ **98.4% file size reduction** maintaining excellent quality
- ✅ **Transparent operation** - works automatically during normal processing
- ✅ **Configurable** - can be customized or disabled if needed
- ✅ **Safe and reliable** - preserves originals until successful optimization

Your images are now perfectly optimized for eBay performance while maintaining the quality needed for accurate card identification and appealing listings!