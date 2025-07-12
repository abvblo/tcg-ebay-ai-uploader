#!/bin/bash
# Deployment script for eBay TCG Batch Uploader
# Includes database migration management

set -e  # Exit on error

echo "🚀 Starting deployment process..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

cd "$PROJECT_ROOT"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command_exists python3; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

if ! command_exists psql; then
    echo -e "${RED}Error: PostgreSQL client is not installed${NC}"
    exit 1
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}No .env file found. Creating from template...${NC}"
    cp config/.env.template .env
    echo -e "${RED}Please update .env with your actual credentials before continuing${NC}"
    exit 1
fi

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Validate critical environment variables
if [[ "$DB_USER" == "your_db_user_here" ]] || [[ "$DB_PASSWORD" == "your_db_password_here" ]]; then
    echo -e "${RED}Error: Database credentials not configured in .env${NC}"
    exit 1
fi

# Install/update dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip3 install -r requirements.txt

# Check database connection
echo -e "${YELLOW}Checking database connection...${NC}"
python3 -c "
import os
import psycopg2
try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        database=os.getenv('DB_NAME', 'pokemon_cards'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    conn.close()
    print('✅ Database connection successful')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo -e "${RED}Database connection failed. Please check your credentials.${NC}"
    exit 1
fi

# Run database migrations
echo -e "${YELLOW}Running database migrations...${NC}"
python3 src/database/migrations.py upgrade

# Verify database setup
echo -e "${YELLOW}Verifying database tables...${NC}"
python3 src/database/migrations.py verify

# Create necessary directories
echo -e "${YELLOW}Creating necessary directories...${NC}"
mkdir -p input
mkdir -p logs
mkdir -p cache
mkdir -p japanese_pokemon_cards
mkdir -p base_set_unlimited_images

# Set permissions
echo -e "${YELLOW}Setting permissions...${NC}"
chmod +x scripts/*.sh
chmod 755 input logs cache

# Run tests (optional)
if [ "$1" == "--with-tests" ]; then
    echo -e "${YELLOW}Running tests...${NC}"
    python3 -m pytest tests/ -v
fi

# Start the application (optional)
if [ "$1" == "--start" ]; then
    echo -e "${YELLOW}Starting web application...${NC}"
    python3 src/web/app.py &
    echo $! > app.pid
    echo -e "${GREEN}Application started with PID $(cat app.pid)${NC}"
fi

echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo ""
echo "Next steps:"
echo "1. Ensure your .env file has all correct API keys and credentials"
echo "2. Place card images in the 'input' directory"
echo "3. Run 'python3 src/web/app.py' to start the web interface"
echo "4. Or run 'python3 run.py' for batch processing"