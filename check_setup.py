#!/usr/bin/env python3
"""
Diagnostic script to check if the project is set up correctly
"""

import os
import sys
from pathlib import Path

def check_python_version():
    """Check Python version"""
    print("🐍 Python Version Check:")
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro} (OK)")
    else:
        print(f"   ❌ Python {version.major}.{version.minor}.{version.micro} (Need 3.8+)")
    print()

def check_directory_structure():
    """Check if all required directories exist"""
    print("📁 Directory Structure Check:")
    
    required_dirs = [
        "Scans",
        "output",
        "src",
        "src/api",
        "src/processing",
        "src/output",
        "src/utils"
    ]
    
    all_good = True
    for dir_path in required_dirs:
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            print(f"   ✅ {dir_path}/")
        else:
            print(f"   ❌ {dir_path}/ (missing)")
            all_good = False
    
    print()
    return all_good

def check_required_files():
    """Check if all required files exist"""
    print("📄 Required Files Check:")
    
    required_files = {
        "Root files": [
            "run.py",
            "requirements.txt",
            ".env"
        ],
        "Main source": [
            "src/main.py",
            "src/config.py",
            "src/cache.py",
            "src/models.py",
            "src/price_mappings.py"
        ],
        "API modules": [
            "src/api/__init__.py",
            "src/api/ximilar.py",
            "src/api/pokemon_tcg.py",
            "src/api/scryfall.py",
            "src/api/ebay_eps.py"
        ],
        "Processing modules": [
            "src/processing/__init__.py",
            "src/processing/card_identifier.py",
            "src/processing/group_detector.py",
            "src/processing/price_calculator.py"
        ],
        "Output modules": [
            "src/output/__init__.py",
            "src/output/excel_generator.py",
            "src/output/ebay_formatter.py"
        ],
        "Utils": [
            "src/utils/__init__.py",
            "src/utils/logger.py",
            "src/utils/metrics.py"
        ]
    }
    
    all_good = True
    for category, files in required_files.items():
        print(f"\n   {category}:")
        for file_path in files:
            if os.path.exists(file_path):
                print(f"      ✅ {file_path}")
            else:
                print(f"      ❌ {file_path} (missing)")
                all_good = False
    
    print()
    return all_good

def check_dependencies():
    """Check if required packages are installed"""
    print("📦 Dependencies Check:")
    
    required_packages = [
        "aiohttp",
        "aiofiles",
        "diskcache",
        "pandas",
        "openpyxl",
        "PIL",
        "tqdm",
        "tenacity",
        "openai",
        "dotenv"
    ]
    
    all_good = True
    for package in required_packages:
        try:
            if package == "PIL":
                __import__("PIL")
            elif package == "dotenv":
                __import__("dotenv")
            else:
                __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} (not installed)")
            all_good = False
    
    if not all_good:
        print("\n   Run: pip3 install -r requirements.txt")
    
    print()
    return all_good

def check_env_file():
    """Check .env file configuration"""
    print("🔑 Environment Configuration Check:")
    
    if not os.path.exists(".env"):
        print("   ❌ .env file not found!")
        print("   Create it by copying .env.example: cp .env.example .env")
        return False
    
    required_keys = [
        "XIMILAR_API_KEY",
        "POKEMON_TCG_API_KEY",
        "EBAY_APP_ID",
        "EBAY_DEV_ID",
        "EBAY_CERT_ID",
        "EBAY_USER_TOKEN"
    ]
    
    with open(".env", "r") as f:
        env_content = f.read()
    
    all_good = True
    for key in required_keys:
        if key in env_content:
            # Check if it's still a placeholder
            line = next((l for l in env_content.split("\n") if l.startswith(key)), "")
            if "your_" in line or "_here" in line:
                print(f"   ⚠️  {key} (placeholder - needs real value)")
                all_good = False
            else:
                print(f"   ✅ {key}")
        else:
            print(f"   ❌ {key} (missing)")
            all_good = False
    
    print()
    return all_good

def check_test_images():
    """Check if there are test images"""
    print("🖼️  Test Images Check:")
    
    image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff']
    scans_dir = Path("Scans")
    
    if not scans_dir.exists():
        print("   ❌ Scans directory doesn't exist")
        return False
    
    images = []
    for ext in image_extensions:
        images.extend(scans_dir.glob(f"*{ext}"))
        images.extend(scans_dir.glob(f"*{ext.upper()}"))
    
    if images:
        print(f"   ✅ Found {len(images)} image(s) in Scans/")
        for img in images[:5]:  # Show first 5
            print(f"      - {img.name}")
        if len(images) > 5:
            print(f"      ... and {len(images) - 5} more")
    else:
        print("   ⚠️  No images found in Scans/")
        print("   Add some card images to test the system")
    
    print()
    return True

def suggest_fixes(issues):
    """Suggest fixes for common issues"""
    if issues:
        print("🔧 Suggested Fixes:")
        print("=" * 50)
        
        if "dirs" in issues:
            print("\n1. Run the setup script to create directories:")
            print("   python3 setup_project.py")
            print("   OR")
            print("   bash setup.sh")
        
        if "files" in issues:
            print("\n2. Make sure all source files are in the project folder")
            print("   If files are in wrong locations, run setup_project.py")
        
        if "deps" in issues:
            print("\n3. Install missing dependencies:")
            print("   pip3 install -r requirements.txt")
        
        if "env" in issues:
            print("\n4. Configure your API keys:")
            print("   cp .env.example .env")
            print("   Then edit .env with your actual API keys")

def main():
    """Run all checks"""
    print("TCG eBay Batch Uploader - Diagnostic Check")
    print("=" * 50)
    print()
    
    issues = []
    
    # Run checks
    check_python_version()
    
    if not check_directory_structure():
        issues.append("dirs")
    
    if not check_required_files():
        issues.append("files")
    
    if not check_dependencies():
        issues.append("deps")
    
    if not check_env_file():
        issues.append("env")
    
    check_test_images()
    
    # Summary
    print("=" * 50)
    if not issues:
        print("✅ Everything looks good! You're ready to run:")
        print("   python3 run.py")
    else:
        print("❌ Some issues found:")
        suggest_fixes(issues)

if __name__ == "__main__":
    main()
