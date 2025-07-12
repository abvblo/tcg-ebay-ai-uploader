# Configuration Directory

This directory contains all configuration files for the eBay TCG Batch Uploader project.

## Structure

```
config/
├── .env.template           # Template for environment variables
├── .env.production.example # Example production environment configuration
├── config.json            # Main application configuration
├── config.example.json    # Example configuration file
├── alembic.ini           # Database migration configuration
├── pytest.ini            # Test configuration
└── docker/               # Docker-related configurations
    ├── Dockerfile
    ├── docker-compose.yml
    └── docker-compose.production.yml
```

## Files

### Environment Files
- `.env.template` - Template with placeholder values for all required environment variables
- `.env.production.example` - Example of production-ready environment configuration

### Application Configuration
- `config.json` - Main application configuration (API endpoints, processing settings, etc.)
- `config.example.json` - Example configuration with placeholder values

### Development/Testing
- `alembic.ini` - Configuration for Alembic database migrations
- `pytest.ini` - Configuration for pytest test runner

### Docker
- `docker/` - Contains all Docker-related configuration files
  - `Dockerfile` - Main application container definition
  - `docker-compose.yml` - Development environment orchestration
  - `docker-compose.production.yml` - Production environment orchestration

## Usage

1. Copy `.env.template` to the project root as `.env` and fill in your actual values
2. Copy `config.example.json` to `config.json` and update as needed
3. For Docker deployments, use the configurations in the `docker/` subdirectory

## Security Note

Never commit files containing actual credentials. Always use the template files and keep your actual configuration files in `.gitignore`.