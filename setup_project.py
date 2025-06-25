#!/usr/bin/env python3
"""
Project Setup Script for TCG eBay Batch Uploader
This script organizes all files into the correct folder structure
"""

import os
import shutil
from pathlib import Path

def create_project_structure():
    """Create the complete project folder structure"""
    
    print("🚀 Setting up TCG eBay Batch Uploader project structure...")
    
    # Define the folder structure
    folders = [
        "Scans",
        "output",
        "output/ultra_cache",
        "output/ultra_cache/images",
        "output/ultra_cache/card_data",
        "output/ultra_cache/ebay_eps",
        "output/ultra_cache/titles",
        "src",
        "src/api",
        "src/processing",
        "src/output",
        "src/utils"
    ]
    
    # Create all folders
    for folder in folders:
        Path(folder).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created folder: {folder}")
    
    # Create __init__.py files in all Python packages
    init_locations = [
        "src/__init__.py",
        "src/api/__init__.py",
        "src/processing/__init__.py",
        "src/output/__init__.py",
        "src/utils/__init__.py"
    ]
    
    for init_file in init_locations:
        Path(init_file).touch()
        print(f"✅ Created: {init_file}")

def move_files_to_correct_locations():
    """Move Python files to their correct locations"""
    
    # Define where each file should go
    # Format: (filename, destination_path)
    file_mappings = [
        # Root level files (stay in root)
        ("run.py", "."),
        ("requirements.txt", "."),
        ("README.md", "."),
        (".env", "."),
        (".env.example", "."),
        (".gitignore", "."),
        
        # Main src files
        ("main.py", "src"),
        ("config.py", "src"),
        ("cache.py", "src"),
        ("models.py", "src"),
        ("price_mappings.py", "src"),
        
        # API files
        ("ximilar.py", "src/api"),
        ("pokemon_tcg.py", "src/api"),
        ("scryfall.py", "src/api"),
        ("ebay_eps.py", "src/api"),
        ("openai_titles.py", "src/api"),
        
        # Processing files
        ("card_identifier.py", "src/processing"),
        ("group_detector.py", "src/processing"),
        ("price_calculator.py", "src/processing"),
        ("image_processor.py", "src/processing"),
        
        # Output files
        ("excel_generator.py", "src/output"),
        ("ebay_formatter.py", "src/output"),
        
        # Utils files
        ("logger.py", "src/utils"),
        ("metrics.py", "src/utils"),
    ]
    
    print("\n📁 Moving files to correct locations...")
    
    for filename, destination in file_mappings:
        # Check if file exists in root
        if os.path.exists(filename) and destination != ".":
            dest_path = os.path.join(destination, filename)
            try:
                shutil.move(filename, dest_path)
                print(f"✅ Moved {filename} → {dest_path}")
            except Exception as e:
                if "already exists" in str(e):
                    print(f"⚠️  {filename} already in correct location")
                else:
                    print(f"❌ Error moving {filename}: {e}")
        elif destination == "." and os.path.exists(filename):
            print(f"✅ {filename} stays in root directory")

def create_gitignore():
    """Create or update .gitignore file"""
    
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Environment variables
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp
*.swo
.DS_Store

# Project specific
output/*.xlsx
output/*.log
output/ultra_cache/
Scans/*
!Scans/.gitkeep
*.log

# Config with secrets
config.json

# Temporary files
*.tmp
*.temp
*.bak
"""
    
    with open(".gitignore", "w") as f:
        f.write(gitignore_content)
    print("✅ Created .gitignore file")

def create_gitkeep_files():
    """Create .gitkeep files in empty directories"""
    
    gitkeep_locations = [
        "Scans/.gitkeep",
        "output/.gitkeep"
    ]
    
    for gitkeep in gitkeep_locations:
        Path(gitkeep).touch()
        print(f"✅ Created: {gitkeep}")

def clean_up_unnecessary_files():
    """Remove unnecessary files and folders"""
    
    unnecessary_items = [
        # Old cache folders that might exist
        "cache",
        "temp",
        ".cache",
        
        # Old config files
        "config.ini",
        "settings.json",
        
        # IDE files
        ".vscode",
        ".idea",
        
        # Mac system files
        ".DS_Store",
        
        # Python cache
        "__pycache__",
        "*.pyc",
        
        # Old output files
        "*.xlsx",
        "*.xls",
        "*.csv"
    ]
    
    print("\n🧹 Cleaning up unnecessary files...")
    
    for item in unnecessary_items:
        if "*" in item:
            # Handle wildcards
            import glob
            for file in glob.glob(item):
                try:
                    os.remove(file)
                    print(f"🗑️  Removed: {file}")
                except:
                    pass
        else:
            # Handle specific files/folders
            if os.path.exists(item):
                try:
                    if os.path.isdir(item):
                        shutil.rmtree(item)
                    else:
                        os.remove(item)
                    print(f"🗑️  Removed: {item}")
                except Exception as e:
                    print(f"⚠️  Could not remove {item}: {e}")

def verify_setup():
    """Verify the setup is complete"""
    
    print("\n🔍 Verifying setup...")
    
    required_files = [
        "run.py",
        "requirements.txt",
        ".env",
        "src/main.py",
        "src/config.py",
        "src/api/ximilar.py",
        "src/processing/card_identifier.py",
        "src/output/excel_generator.py"
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print("❌ Missing required files:")
        for file in missing_files:
            print(f"   - {file}")
        print("\n⚠️  Please ensure all source files are in the project directory before running setup.")
    else:
        print("✅ All required files are in place!")
    
    # Check if .env has API keys
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            env_content = f.read()
            if "your_" in env_content:
                print("⚠️  Don't forget to add your actual API keys to .env file!")
    
    print("\n✨ Setup complete!")
    print("\nNext steps:")
    print("1. Make sure your .env file has your actual API keys")
    print("2. Install dependencies: pip3 install -r requirements.txt")
    print("3. Place card images in the Scans/ folder")
    print("4. Run: python3 run.py")

def main():
    """Main setup function"""
    
    # Get confirmation from user
    print("TCG eBay Batch Uploader - Project Setup")
    print("=" * 50)
    print("This script will:")
    print("1. Create all necessary folders")
    print("2. Move files to correct locations")
    print("3. Create __init__.py files")
    print("4. Clean up unnecessary files")
    print("\nCurrent directory:", os.getcwd())
    
    response = input("\nContinue with setup? (y/n): ").lower()
    if response != 'y':
        print("Setup cancelled.")
        return
    
    # Run setup steps
    create_project_structure()
    move_files_to_correct_locations()
    create_gitignore()
    create_gitkeep_files()
    clean_up_unnecessary_files()
    verify_setup()

if __name__ == "__main__":
    main()
