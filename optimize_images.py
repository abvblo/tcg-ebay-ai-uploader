#!/usr/bin/env python3
"""
Image optimization script for trading card images
Tests different sizes and compression settings to find optimal balance
"""

import os
from PIL import Image, ImageOps
from pathlib import Path
import tempfile

def test_image_optimization(input_image_path, output_dir):
    """Test different optimization settings on a sample image"""
    
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    # Open original image
    with Image.open(input_image_path) as img:
        original_size = os.path.getsize(input_image_path)
        print(f"Original: {img.size[0]}x{img.size[1]} pixels, {original_size/(1024*1024):.1f}MB")
        
        # Test configurations based on research
        test_configs = [
            # Format: (max_width, max_height, quality, format, description)
            (1600, 1600, 85, 'JPEG', 'eBay Recommended (1600px, JPEG 85%)'),
            (2000, 2000, 85, 'JPEG', 'E-commerce Optimal (2000px, JPEG 85%)'),
            (1200, 1200, 80, 'JPEG', 'Fast Loading (1200px, JPEG 80%)'),
            (1600, 1600, 95, 'JPEG', 'High Quality (1600px, JPEG 95%)'),
            (1600, 1600, None, 'PNG', 'PNG Compressed (1600px)'),
            (2400, 2400, 85, 'JPEG', 'Detail Preservation (2400px, JPEG 85%)'),
            (800, 800, 80, 'JPEG', 'Mobile Optimized (800px, JPEG 80%)')
        ]
        
        results = []
        
        for max_w, max_h, quality, fmt, desc in test_configs:
            # Calculate resize dimensions maintaining aspect ratio
            img_copy = img.copy()
            img_copy.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            
            # Save with different settings
            filename = f"test_{max_w}x{max_h}"
            if fmt == 'JPEG':
                filename += f"_q{quality}.jpg"
                if img_copy.mode in ('RGBA', 'LA'):
                    # Convert to RGB for JPEG
                    background = Image.new('RGB', img_copy.size, (255, 255, 255))
                    background.paste(img_copy, mask=img_copy.split()[-1] if img_copy.mode == 'RGBA' else None)
                    img_copy = background
                
                filepath = os.path.join(output_dir, filename)
                img_copy.save(filepath, format='JPEG', quality=quality, optimize=True)
            else:
                filename += ".png"
                filepath = os.path.join(output_dir, filename)
                img_copy.save(filepath, format='PNG', optimize=True)
            
            # Check file size
            new_size = os.path.getsize(filepath)
            compression_ratio = (original_size - new_size) / original_size * 100
            
            results.append({
                'config': desc,
                'dimensions': f"{img_copy.size[0]}x{img_copy.size[1]}",
                'file_size_mb': new_size / (1024 * 1024),
                'compression_ratio': compression_ratio,
                'filename': filename
            })
            
            print(f"{desc}: {img_copy.size[0]}x{img_copy.size[1]}, {new_size/(1024*1024):.1f}MB ({compression_ratio:.1f}% smaller)")
        
        return results

def analyze_card_image_requirements():
    """Analyze requirements specifically for trading card images"""
    print("\n=== TRADING CARD IMAGE OPTIMIZATION ANALYSIS ===\n")
    
    print("📏 STANDARD CARD DIMENSIONS:")
    print("  - Physical: 2.5\" x 3.5\" (63.5mm x 88.9mm)")
    print("  - At 300 DPI: 750 x 1050 pixels")
    print("  - At 600 DPI: 1500 x 2100 pixels")
    
    print("\n📋 EBAY REQUIREMENTS:")
    print("  - Minimum: 500px on longest side")
    print("  - Recommended: 1600px on longest side")
    print("  - Maximum: 9000px, 12MB file size")
    print("  - Optimal for zoom: 1600px+")
    
    print("\n💡 RECOMMENDATIONS FOR TRADING CARDS:")
    print("  - Resolution: 1600-2000px on longest side")
    print("  - Format: JPEG for smaller files, PNG for transparency")
    print("  - Quality: 80-90% JPEG compression")
    print("  - Target file size: Under 1MB for fast loading")
    print("  - Aspect ratio: Maintain original (roughly 3:4)")

def main():
    """Main optimization testing function"""
    
    # Get sample image from Scans directory
    scans_dir = Path("Scans")
    if not scans_dir.exists():
        print("❌ Scans directory not found")
        return
    
    # Find first PNG file
    png_files = list(scans_dir.glob("*.png"))
    if not png_files:
        print("❌ No PNG files found in Scans directory")
        return
    
    sample_image = png_files[0]
    print(f"🔍 Testing optimization on: {sample_image.name}")
    
    # Create output directory for tests
    output_dir = "image_optimization_tests"
    
    # Run analysis
    analyze_card_image_requirements()
    
    print(f"\n🧪 TESTING DIFFERENT OPTIMIZATION SETTINGS:\n")
    
    # Test optimization
    results = test_image_optimization(sample_image, output_dir)
    
    print(f"\n📊 OPTIMIZATION RESULTS SUMMARY:")
    print(f"{'Configuration':<35} {'Dimensions':<12} {'Size (MB)':<10} {'Reduction':<10}")
    print("-" * 70)
    
    for result in results:
        print(f"{result['config']:<35} {result['dimensions']:<12} {result['file_size_mb']:<10.1f} {result['compression_ratio']:<10.1f}%")
    
    print(f"\n✅ Test images saved to: {output_dir}/")
    print(f"📁 Review the test images to see quality vs file size trade-offs")
    
    # Recommendations
    print(f"\n🎯 RECOMMENDED SETTINGS:")
    print(f"  1. For high-quality listings: 1600px, JPEG 85% (~300-500KB)")
    print(f"  2. For fast loading: 1200px, JPEG 80% (~200-300KB)")
    print(f"  3. For premium cards: 2000px, JPEG 90% (~500KB-1MB)")

if __name__ == "__main__":
    main()