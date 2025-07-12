# Database Migrations Guide

This document explains how to use the Alembic migration system for the eBay TCG Batch Uploader database.

## Overview

The project uses Alembic for database migrations, allowing version-controlled schema changes and easy deployment across environments.

## Setup

### Initial Setup

1. **Configure Database Connection**
   ```bash
   cp .env.template .env
   # Edit .env with your database credentials
   ```

2. **Initialize Migration System**
   ```bash
   python src/database/migrations.py init
   ```

3. **Apply Initial Migrations**
   ```bash
   python src/database/migrations.py upgrade
   ```

## Migration Commands

### Using the Migration Manager (Recommended)

```bash
# Check current version
python src/database/migrations.py current

# View migration history
python src/database/migrations.py history

# Create new migration (auto-generated from model changes)
python src/database/migrations.py create -m "Add new feature"

# Apply all pending migrations
python src/database/migrations.py upgrade

# Rollback one migration
python src/database/migrations.py downgrade

# Verify all tables exist
python src/database/migrations.py verify
```

### Using Alembic Directly

```bash
# Navigate to project root
cd "/path/to/eBay TCG Batch Uploader"

# Create new migration
alembic revision -m "Description of changes" --autogenerate

# Apply migrations
alembic upgrade head

# Rollback to previous version
alembic downgrade -1

# View current version
alembic current

# View history
alembic history
```

## Migration Files

### Structure

Migrations are stored in `alembic/versions/` with the naming pattern:
```
{revision_id}_{slug}_description.py
```

### Current Migrations

1. **001_initial_schema** - Creates all base tables
   - Pokemon cards, sets, types, subtypes
   - Variations, price snapshots
   - Validation rules, corrections
   - All necessary indexes and constraints

2. **002_performance_indexes** - Adds performance optimizations
   - Composite indexes for common queries
   - Partial indexes for filtered searches
   - Text search indexes using trigrams
   - Foreign key lookup indexes

3. **003_audit_enhancements** - Adds tracking and audit features
   - Audit log table for change tracking
   - Identification results tracking
   - Batch upload management
   - Automatic timestamp triggers

## Creating New Migrations

### Auto-generate from Model Changes

1. Make changes to models in `src/database/models.py`
2. Generate migration:
   ```bash
   python src/database/migrations.py create -m "Describe your changes"
   ```
3. Review generated migration in `alembic/versions/`
4. Edit if necessary (auto-generation may miss some changes)
5. Apply migration:
   ```bash
   python src/database/migrations.py upgrade
   ```

### Manual Migration

1. Create empty migration:
   ```bash
   alembic revision -m "Manual migration description"
   ```
2. Edit the generated file to add upgrade/downgrade logic
3. Apply as usual

## Best Practices

### DO:
- Always review auto-generated migrations before applying
- Test migrations on a development database first
- Include both upgrade() and downgrade() implementations
- Use descriptive migration messages
- Add comments explaining complex changes
- Run `ANALYZE` after creating new indexes

### DON'T:
- Never edit existing migrations that have been applied
- Don't drop columns/tables without careful consideration
- Avoid making schema changes outside of migrations
- Don't use migrations for data changes (use separate scripts)

## Deployment

### Production Deployment

1. **Backup Database**
   ```bash
   pg_dump -U $DB_USER -d $DB_NAME > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Run Deployment Script**
   ```bash
   ./scripts/deployment/deploy.sh
   ```

3. **Verify Migration**
   ```bash
   python src/database/migrations.py current
   python src/database/migrations.py verify
   ```

### Rollback Procedure

If a migration fails:

1. **Rollback Migration**
   ```bash
   python src/database/migrations.py downgrade
   ```

2. **Restore from Backup** (if necessary)
   ```bash
   psql -U $DB_USER -d $DB_NAME < backup_file.sql
   ```

## Troubleshooting

### Common Issues

1. **"No module named 'src'"**
   - Ensure you're running commands from the project root
   - Check that PYTHONPATH includes the project directory

2. **"relation already exists"**
   - Database may be out of sync with migrations
   - Use `alembic stamp head` to mark current schema as up-to-date

3. **"Can't locate revision"**
   - Check alembic_version table: `SELECT * FROM alembic_version;`
   - Ensure all migration files are present in `alembic/versions/`

4. **Connection Errors**
   - Verify .env file has correct database credentials
   - Check PostgreSQL is running
   - Ensure database exists

### Reset Migrations (Development Only)

To completely reset migrations in development:

```bash
# Drop all tables (CAUTION: destroys all data)
psql -U $DB_USER -d $DB_NAME -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Re-run migrations
python src/database/migrations.py init
python src/database/migrations.py upgrade
```

## Environment-Specific Configuration

### Development
- Use local PostgreSQL instance
- Enable SQL echo for debugging: `echo=True` in engine config
- Keep migration files in version control

### Production
- Use connection pooling settings in DatabaseConfig
- Disable SQL echo
- Run migrations as part of deployment pipeline
- Always backup before migrations

## Integration with Application

The DatabaseService automatically runs pending migrations on startup:

```python
# In src/database/service.py
migration_manager = MigrationManager()
migration_manager.auto_upgrade()
```

This ensures the database is always up-to-date when the application starts.

## Future Considerations

- Consider partitioning for price_snapshots table as data grows
- May need to add table inheritance for card variations
- Consider read replicas for heavy query loads
- Implement migration testing in CI/CD pipeline