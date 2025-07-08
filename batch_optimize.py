#!/usr/bin/env python3
"""
Batch image optimization script for trading card images
Optimizes all images in the Scans directory
"""

import os
import shutil
from PIL import Image
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import argparse

def optimize_single_image(input_path, output_path, max_size=1600, quality=85, format_type='JPEG'):
    """Optimize a single image"""
    try:
        with Image.open(input_path) as img:
            # Calculate thumbnail size maintaining aspect ratio
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Convert to RGB if saving as JPEG and image has transparency
            if format_type == 'JPEG' and img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            # Save optimized image
            if format_type == 'JPEG':
                img.save(output_path, format='JPEG', quality=quality, optimize=True)
            else:
                img.save(output_path, format='PNG', optimize=True)
            
            return True
    except Exception as e:
        print(f"❌ Error processing {input_path}: {e}")
        return False

def batch_optimize_images(scans_dir, output_dir, backup_dir=None, max_size=1600, quality=85, format_type='JPEG'):
    """Batch optimize all images in scans directory"""
    
    scans_path = Path(scans_dir)
    output_path = Path(output_dir)
    
    if not scans_path.exists():
        print(f"❌ Scans directory not found: {scans_dir}")
        return
    
    # Create output directory
    output_path.mkdir(exist_ok=True)
    
    # Create backup directory if specified
    if backup_dir:
        backup_path = Path(backup_dir)
        backup_path.mkdir(exist_ok=True)
        print(f"📦 Backup directory: {backup_dir}")
    
    # Find all image files
    image_extensions = ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']
    image_files = []
    for ext in image_extensions:
        image_files.extend(scans_path.glob(f"*{ext}"))
        image_files.extend(scans_path.glob(f"*{ext.upper()}"))
    
    if not image_files:
        print(f"❌ No image files found in {scans_dir}")
        return
    
    print(f"🔍 Found {len(image_files)} image files")
    
    # Calculate total original size
    total_original_size = sum(f.stat().st_size for f in image_files)
    print(f"📊 Total original size: {total_original_size/(1024*1024*1024):.2f} GB")
    
    # Process images
    successful = 0
    total_optimized_size = 0
    
    # Determine output file extension
    output_ext = '.jpg' if format_type == 'JPEG' else '.png'
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        
        for img_file in image_files:
            # Create backup if requested
            if backup_dir:
                backup_file = backup_path / img_file.name
                if not backup_file.exists():
                    shutil.copy2(img_file, backup_file)
            
            # Determine output filename
            output_file = output_path / (img_file.stem + output_ext)
            
            # Submit optimization task
            future = executor.submit(
                optimize_single_image, 
                img_file, 
                output_file, 
                max_size, 
                quality, 
                format_type
            )
            futures.append((future, img_file, output_file))
        
        # Process results with progress bar
        for future, input_file, output_file in tqdm(futures, desc="Optimizing images"):
            if future.result():
                successful += 1
                if output_file.exists():
                    total_optimized_size += output_file.stat().st_size
    
    # Calculate savings
    compression_ratio = (total_original_size - total_optimized_size) / total_original_size * 100
    
    print(f"\n✅ OPTIMIZATION COMPLETE:")
    print(f"   📸 Processed: {successful}/{len(image_files)} images")
    print(f"   📊 Original size: {total_original_size/(1024*1024*1024):.2f} GB")
    print(f"   📊 Optimized size: {total_optimized_size/(1024*1024*1024):.2f} GB")
    print(f"   💾 Space saved: {(total_original_size-total_optimized_size)/(1024*1024*1024):.2f} GB ({compression_ratio:.1f}%)")
    print(f"   📁 Optimized images: {output_dir}")
    
    return successful == len(image_files)

def main():
    """Main function with command line arguments"""
    parser = argparse.ArgumentParser(description='Batch optimize trading card images')
    parser.add_argument('--input', default='Scans', help='Input directory (default: Scans)')
    parser.add_argument('--output', default='Scans_Optimized', help='Output directory (default: Scans_Optimized)')
    parser.add_argument('--backup', default='Scans_Backup', help='Backup directory (default: Scans_Backup)')
    parser.add_argument('--size', type=int, default=1600, help='Maximum size in pixels (default: 1600)')
    parser.add_argument('--quality', type=int, default=85, help='JPEG quality 1-100 (default: 85)')
    parser.add_argument('--format', choices=['JPEG', 'PNG'], default='JPEG', help='Output format (default: JPEG)')
    parser.add_argument('--no-backup', action='store_true', help='Skip creating backup')
    
    args = parser.parse_args()
    
    print("🖼️  TRADING CARD IMAGE BATCH OPTIMIZER")
    print("=" * 50)
    print(f"📁 Input directory: {args.input}")
    print(f"📁 Output directory: {args.output}")
    print(f"📏 Maximum size: {args.size}px")
    print(f"⚙️  Quality: {args.quality}%")
    print(f"📄 Format: {args.format}")
    
    if not args.no_backup:
        print(f"📦 Backup directory: {args.backup}")
    
    print()
    
    # Confirm before proceeding
    response = input("🤔 Proceed with optimization? (y/N): ")
    if response.lower() != 'y':
        print("❌ Optimization cancelled")
        return
    
    # Run optimization
    success = batch_optimize_images(
        scans_dir=args.input,
        output_dir=args.output,
        backup_dir=args.backup if not args.no_backup else None,
        max_size=args.size,
        quality=args.quality,
        format_type=args.format
    )
    
    if success:
        print("\n🎉 All images optimized successfully!")
        print("\n💡 NEXT STEPS:")
        print("   1. Review optimized images in the output directory")
        print("   2. Test with a few images to ensure quality is acceptable")
        print("   3. If satisfied, replace your Scans directory with optimized version")
        print("   4. Keep backups safe until you're confident in the results")
    else:
        print("\n⚠️  Some images failed to optimize. Check error messages above.")

if __name__ == "__main__":
    main()