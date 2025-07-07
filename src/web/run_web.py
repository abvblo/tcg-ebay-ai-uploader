"""Quick launcher for the Pokemon card search web app"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.app import app

if __name__ == '__main__':
    print("Starting Pokemon Card Search Web App...")
    print("Access the app at: http://localhost:5001")
    print("\nMake sure your PostgreSQL database is running with Pokemon card data.")
    print("Press Ctrl+C to stop the server.\n")
    
    app.run(debug=True, host='0.0.0.0', port=5001)