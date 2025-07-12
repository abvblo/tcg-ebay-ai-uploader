"""Quick launcher for the Pokemon card search web app"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.app import app

if __name__ == "__main__":
    print("Starting Pokemon Card Search Web App...")
    print("Access the app at: http://localhost:5001")
    print("\nMake sure your PostgreSQL database is running with Pokemon card data.")
    print("Press Ctrl+C to stop the server.\n")

    # Use localhost binding for development security
    # For production deployment, configure host via environment variable
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_PORT', '5001'))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    
    app.run(debug=debug, host=host, port=port)
