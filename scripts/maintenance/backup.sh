#!/bin/sh
# Database backup script

set -e

# Configuration
BACKUP_DIR="/backup"
RETENTION_DAYS=7
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="pokemon_cards_backup_${DATE}.sql.gz"

# Create backup directory if it doesn't exist
mkdir -p ${BACKUP_DIR}

echo "Starting database backup at $(date)"

# Perform the backup
pg_dump -h ${PGHOST} -U ${PGUSER} -d ${PGDATABASE} --no-password \
    --verbose --no-owner --no-acl \
    | gzip -9 > ${BACKUP_DIR}/${BACKUP_FILE}

# Check if backup was successful
if [ $? -eq 0 ]; then
    echo "Backup completed successfully: ${BACKUP_FILE}"
    
    # Get file size
    SIZE=$(ls -lh ${BACKUP_DIR}/${BACKUP_FILE} | awk '{print $5}')
    echo "Backup size: ${SIZE}"
    
    # Clean up old backups
    echo "Cleaning up backups older than ${RETENTION_DAYS} days"
    find ${BACKUP_DIR} -name "pokemon_cards_backup_*.sql.gz" -type f -mtime +${RETENTION_DAYS} -delete
    
    # List remaining backups
    echo "Current backups:"
    ls -lh ${BACKUP_DIR}/pokemon_cards_backup_*.sql.gz 2>/dev/null || echo "No backups found"
else
    echo "Backup failed!"
    exit 1
fi

echo "Backup process completed at $(date)"