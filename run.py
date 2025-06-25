#!/usr/bin/env python3
"""
TCG eBay Batch Uploader - Launch Script

This is the main entry point for the application.
Place this file in the root directory of your project.

Usage:
    python run.py
    
or make it executable:
    chmod +x run.py
    ./run.py
"""

import sys
import asyncio
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

# Import the main module from src directory
from src.main import main

if __name__ == "__main__":
    print("🚀 Starting TCG eBay Batch Uploader...")
    print("=" * 50)
    
    try:
        # Run the async main function
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Process interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)