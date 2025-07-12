#!/usr/bin/env python3
"""Test runner script for eBay TCG Batch Uploader."""

import sys
import subprocess
import shlex
from pathlib import Path


def run_command(cmd):
    """Run a command and return the result."""
    try:
        # Convert command string to list for safe execution
        cmd_list = shlex.split(cmd)
        result = subprocess.run(cmd_list, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def main():
    """Main test runner function."""
    print("🧪 eBay TCG Batch Uploader - Test Runner")
    print("=" * 50)
    
    # Check if we're in the correct directory
    if not Path("tests").exists():
        print("❌ Error: tests directory not found. Please run from project root.")
        sys.exit(1)
    
    # Test categories
    test_categories = {
        "basic": {
            "description": "Basic functionality tests",
            "command": "python3 -m pytest tests/unit/test_basic.py -v",
            "required": True
        },
        "config": {
            "description": "Configuration tests",
            "command": "python3 -m pytest tests/unit/test_config.py -v",
            "required": True
        },
        "models": {
            "description": "Database model tests",
            "command": "python3 -m pytest tests/unit/test_database/test_models.py -v",
            "required": True
        },
        "integration": {
            "description": "Database integration tests",
            "command": "python3 -m pytest tests/integration/test_database_integration.py -v",
            "required": False
        },
        "web": {
            "description": "Web application tests",
            "command": "python3 -m pytest tests/unit/test_web/test_flask_app.py -v",
            "required": False
        },
        "all": {
            "description": "All available tests",
            "command": "python3 -m pytest tests/ --tb=short -x",
            "required": False
        }
    }
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        category = sys.argv[1]
        if category not in test_categories:
            print(f"❌ Unknown test category: {category}")
            print("Available categories:")
            for cat, info in test_categories.items():
                print(f"  - {cat}: {info['description']}")
            sys.exit(1)
        
        categories_to_run = [category]
    else:
        # Run required tests by default
        categories_to_run = [cat for cat, info in test_categories.items() if info["required"]]
    
    # Run tests
    total_passed = 0
    total_failed = 0
    
    for category in categories_to_run:
        info = test_categories[category]
        print(f"\n🔬 Running {category} tests: {info['description']}")
        print("-" * 50)
        
        success, stdout, stderr = run_command(info["command"])
        
        if success:
            print(f"✅ {category} tests passed!")
            total_passed += 1
        else:
            print(f"❌ {category} tests failed!")
            total_failed += 1
            
            # Show error details for failed tests
            if stderr:
                print(f"Error output:\n{stderr}")
    
    # Summary
    print("\n" + "=" * 50)
    print(f"📊 Test Summary:")
    print(f"✅ Passed: {total_passed}")
    print(f"❌ Failed: {total_failed}")
    
    if total_failed > 0:
        print("\n💡 To debug failed tests:")
        print("1. Run individual test categories: python3 run_tests.py <category>")
        print("2. Check test output for specific errors")
        print("3. Some tests may fail if source files don't exist yet - this is expected")
        sys.exit(1)
    else:
        print("\n🎉 All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()