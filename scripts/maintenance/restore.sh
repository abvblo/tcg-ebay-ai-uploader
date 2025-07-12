#!/bin/sh
# Database restore script

set -e

# Check if backup file is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <backup_file>"
    echo "Example: $0 /backup/pokemon_cards_backup_20250111_020000.sql.gz"
    exit 1
fi

BACKUP_FILE=$1

# Check if backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Error: Backup file '${BACKUP_FILE}' not found!"
    exit 1
fi

echo "Starting database restore from: ${BACKUP_FILE}"
echo "WARNING: This will overwrite the current database!"
echo "Press Ctrl+C to cancel, or wait 5 seconds to continue..."
sleep 5

# Drop and recreate database (optional, comment out if you want to preserve data)
echo "Preparing database..."
psql -h ${PGHOST} -U ${PGUSER} -d postgres --no-password <<EOF
DROP DATABASE IF EXISTS ${PGDATABASE};
CREATE DATABASE ${PGDATABASE};
EOF

# Restore the backup
echo "Restoring backup..."
gunzip -c ${BACKUP_FILE} | psql -h ${PGHOST} -U ${PGUSER} -d ${PGDATABASE} --no-password

if [ $? -eq 0 ]; then
    echo "Restore completed successfully!"
    
    # Run analyze to update statistics
    echo "Analyzing database..."
    psql -h ${PGHOST} -U ${PGUSER} -d ${PGDATABASE} --no-password -c "ANALYZE;"
    
    echo "Database restore completed at $(date)"
else
    echo "Restore failed!"
    exit 1
fi