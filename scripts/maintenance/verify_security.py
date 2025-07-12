#!/usr/bin/env python3
"""
Security verification script for the eBay TCG Batch Uploader
Tests that the application properly handles placeholder credentials
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def verify_gitignore():
    """Verify that sensitive files are properly ignored by git"""
    print("🔍 Verifying .gitignore configuration...")
    
    # Check if .gitignore exists
    gitignore_path = Path('.gitignore')
    if not gitignore_path.exists():
        print("❌ .gitignore file not found!")
        return False
    
    # Read .gitignore content
    with open(gitignore_path, 'r') as f:
        gitignore_content = f.read()
    
    # Check for required entries
    required_entries = ['.env', 'config/config.json', '*.key', '*.pem']
    missing_entries = []
    
    for entry in required_entries:
        if entry not in gitignore_content:
            missing_entries.append(entry)
    
    if missing_entries:
        print(f"❌ Missing entries in .gitignore: {missing_entries}")
        return False
    
    print("✅ .gitignore properly configured")
    return True

def verify_template_file():
    """Verify that .env.template exists and contains placeholder values"""
    print("🔍 Verifying .env.template...")
    
    template_path = Path('config/.env.template')
    if not template_path.exists():
        print("❌ .env.template file not found!")
        return False
    
    with open(template_path, 'r') as f:
        template_content = f.read()
    
    # Check for placeholder values
    placeholders = [
        'your_ximilar_api_key_here',
        'your_pokemon_tcg_api_key_here',
        'your_openai_api_key_here',
        'your_ebay_app_id_here'
    ]
    
    missing_placeholders = []
    for placeholder in placeholders:
        if placeholder not in template_content:
            missing_placeholders.append(placeholder)
    
    if missing_placeholders:
        print(f"❌ Missing placeholders in .env.template: {missing_placeholders}")
        return False
    
    print("✅ .env.template properly configured")
    return True

def verify_no_real_credentials():
    """Verify that no real credentials are present in tracked files"""
    print("🔍 Verifying no real credentials in tracked files...")
    
    # Check .env file
    env_path = Path('.env')
    if env_path.exists():
        with open(env_path, 'r') as f:
            env_content = f.read()
        
        # Look for patterns that might indicate real credentials
        suspicious_patterns = [
            'sk-proj-',  # OpenAI API key pattern
            'PRD-',      # eBay production key pattern
            'v^1.1#',    # eBay token pattern
        ]
        
        for pattern in suspicious_patterns:
            if pattern in env_content:
                print(f"❌ Suspicious pattern found in .env: {pattern}")
                return False
    
    # Check config.json
    config_path = Path('config/config.json')
    if config_path.exists():
        with open(config_path, 'r') as f:
            config_content = f.read()
        
        for pattern in suspicious_patterns:
            if pattern in config_content:
                print(f"❌ Suspicious pattern found in config.json: {pattern}")
                return False
    
    print("✅ No real credentials found in tracked files")
    return True

def verify_config_validation():
    """Verify that config.py properly validates credentials"""
    print("🔍 Verifying config validation...")
    
    try:
        from config import Config
        
        # This should fail because we have placeholder values
        try:
            config = Config()
            print("❌ Config loaded with placeholder values - this should fail!")
            return False
        except ValueError as e:
            if "SECURITY" in str(e):
                print("✅ Config properly rejects placeholder values")
                return True
            else:
                print(f"❌ Config failed for wrong reason: {e}")
                return False
    except ImportError as e:
        print(f"❌ Could not import config module: {e}")
        return False

def main():
    """Run all security verification tests"""
    print("🔐 Running security verification tests...")
    print("="*50)
    
    tests = [
        verify_gitignore,
        verify_template_file,
        verify_no_real_credentials,
        verify_config_validation
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            failed += 1
        print()
    
    print("="*50)
    print(f"✅ Tests passed: {passed}")
    print(f"❌ Tests failed: {failed}")
    
    if failed == 0:
        print("🎉 All security tests passed!")
        return True
    else:
        print("⚠️  Some security tests failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)