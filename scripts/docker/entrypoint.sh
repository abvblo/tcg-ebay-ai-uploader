#!/bin/bash
set -e

echo "Starting eBay TCG Batch Uploader..."

# Function to check if database is ready
check_db() {
    python -c "
import psycopg2
import os
import sys
import time

db_url = os.environ.get('DATABASE_URL', '')
if not db_url:
    print('DATABASE_URL not set')
    sys.exit(1)

# Parse DATABASE_URL
if db_url.startswith('postgresql://'):
    db_url = db_url.replace('postgresql://', '')
    
user_pass, host_db = db_url.split('@')
user, password = user_pass.split(':')
host_port, db = host_db.split('/')
host, port = host_port.split(':')

max_retries = 30
retry_count = 0

while retry_count < max_retries:
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=db,
            user=user,
            password=password
        )
        conn.close()
        print('Database is ready!')
        sys.exit(0)
    except Exception as e:
        retry_count += 1
        print(f'Database not ready yet... ({retry_count}/{max_retries})')
        time.sleep(2)

print('Database connection failed after maximum retries')
sys.exit(1)
"
}

# Wait for database if DATABASE_URL is set
if [ ! -z "$DATABASE_URL" ]; then
    echo "Waiting for database..."
    check_db
fi

# Run database migrations if they exist
if [ -f "/app/scripts/database/migrate.py" ]; then
    echo "Running database migrations..."
    python /app/scripts/database/migrate.py
fi

# Create necessary directories
mkdir -p /app/logs /app/cache /app/uploads /app/static

# Set proper permissions (if running as root, which we shouldn't be)
if [ "$(id -u)" = "0" ]; then
    chown -R appuser:appuser /app/logs /app/cache /app/uploads /app/static
fi

# Execute the main command
exec "$@"