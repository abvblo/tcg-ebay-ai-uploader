# Scripts Directory

This directory contains all utility and maintenance scripts for the eBay TCG Batch Uploader project.

## Directory Structure

```
scripts/
├── database/           # Database-related scripts
│   └── migrate.py     # Database migration tool
├── deployment/        # Deployment and CI/CD scripts
│   └── deploy.sh      # Production deployment script
├── development/       # Development utilities
│   └── run_tests.py   # Test runner script
├── docker/           # Docker-related scripts
│   ├── docker-build.sh    # Docker image build script
│   ├── entrypoint.sh      # Docker container entrypoint
│   └── wait-for-it.sh     # Wait for services to be ready
└── maintenance/      # System maintenance scripts
    ├── backup.sh          # Database backup script
    ├── restore.sh         # Database restore script
    ├── update_config.sh   # Configuration update helper
    └── verify_security.py # Security verification script
```

## Usage

### Database Scripts

**Database Migration:**
```bash
python scripts/database/migrate.py          # Show current version
python scripts/database/migrate.py up       # Apply all pending migrations
python scripts/database/migrate.py down     # Rollback one migration
python scripts/database/migrate.py create "description"  # Create new migration
```

### Deployment Scripts

**Deploy to Production:**
```bash
./scripts/deployment/deploy.sh
```

### Development Scripts

**Run Tests:**
```bash
python scripts/development/run_tests.py     # Run all tests
python scripts/development/run_tests.py unit    # Run unit tests only
python scripts/development/run_tests.py integration  # Run integration tests only
```

### Docker Scripts

**Build Docker Image:**
```bash
./scripts/docker/docker-build.sh
```

### Maintenance Scripts

**Database Backup:**
```bash
./scripts/maintenance/backup.sh             # Create backup
./scripts/maintenance/restore.sh backup_file.sql  # Restore from backup
```

**Security Verification:**
```bash
python scripts/maintenance/verify_security.py
```

**Update Configuration:**
```bash
./scripts/maintenance/update_config.sh
```

## Notes

- All shell scripts should be executable: `chmod +x script.sh`
- Python scripts use the project's virtual environment
- Database scripts require proper database credentials in `.env`
- Docker scripts are used by docker-compose and CI/CD pipelines