#!/bin/bash
# Script to update configuration structure after pulling changes

set -e

echo "🔧 Updating configuration structure..."

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

cd "$PROJECT_ROOT"

# Check if old config files exist and offer to migrate them
if [ -f "config.json" ] && [ ! -f "config/config.json" ]; then
    echo "📦 Found config.json in old location. Moving to config/ directory..."
    mv config.json config/config.json
fi

if [ -f ".env.template" ] && [ ! -f "config/.env.template" ]; then
    echo "📦 Found .env.template in old location. Moving to config/ directory..."
    mv .env.template config/.env.template
fi

if [ -f ".env.production.example" ] && [ ! -f "config/.env.production.example" ]; then
    echo "📦 Found .env.production.example in old location. Moving to config/ directory..."
    mv .env.production.example config/.env.production.example
fi

if [ -f "alembic.ini" ] && [ ! -f "config/alembic.ini" ]; then
    echo "📦 Found alembic.ini in old location. Moving to config/ directory..."
    mv alembic.ini config/alembic.ini
fi

if [ -f "pytest.ini" ] && [ ! -f "config/pytest.ini" ]; then
    echo "📦 Found pytest.ini in old location. Moving to config/ directory..."
    mv pytest.ini config/pytest.ini
fi

# Create symlinks for docker-compose files if they don't exist
if [ ! -L "docker-compose.yml" ]; then
    echo "🔗 Creating symlink for docker-compose.yml..."
    ln -sf config/docker/docker-compose.yml docker-compose.yml
fi

if [ ! -L "docker-compose.production.yml" ]; then
    echo "🔗 Creating symlink for docker-compose.production.yml..."
    ln -sf config/docker/docker-compose.production.yml docker-compose.production.yml
fi

echo "✅ Configuration structure updated successfully!"
echo ""
echo "📝 Note: If you have a local .env file, it should remain in the project root."
echo "   The config/ directory contains only templates and examples."