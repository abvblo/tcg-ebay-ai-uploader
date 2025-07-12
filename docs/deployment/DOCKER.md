# Docker Deployment Guide for eBay TCG Batch Uploader

## Quick Start

### Development Setup

1. **Configure Environment Variables**
   ```bash
   cp .env.template .env
   # Edit .env with your actual credentials
   ```

2. **Build and Start Services**
   ```bash
   docker-compose up -d
   ```

3. **Access the Application**
   - Web UI: http://localhost:5001
   - PostgreSQL: localhost:5432
   - Redis: localhost:6379

4. **View Logs**
   ```bash
   docker-compose logs -f web
   ```

### Production Deployment

1. **Create Production Environment File**
   ```bash
   cp .env.template .env.production
   # Edit with production credentials
   # Add SECRET_KEY and REDIS_PASSWORD
   ```

2. **Build Production Image**
   ```bash
   docker build -t ebay-tcg-uploader:latest .
   ```

3. **Deploy with Production Configuration**
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.production.yml up -d
   ```

## Services Overview

### Core Services

- **web**: Flask application (port 5001)
- **postgres**: PostgreSQL database (port 5432)
- **redis**: Redis cache/rate limiting (port 6379)
- **batch-processor**: Background batch processing (profile: batch)

### Production-Only Services

- **nginx**: Reverse proxy and static file serving (ports 80/443)
- **backup**: Automated database backups (profile: backup)

## Common Commands

### Service Management
```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart a specific service
docker-compose restart web

# View service logs
docker-compose logs -f [service-name]

# Execute commands in containers
docker-compose exec web python src/web/app.py
docker-compose exec postgres psql -U $DB_USER -d $DB_NAME
```

### Database Operations
```bash
# Run migrations
docker-compose exec web python src/database/migrate.py

# Create database backup
docker-compose exec backup /scripts/backup.sh

# Restore from backup
docker-compose exec backup /scripts/restore.sh /backup/pokemon_cards_backup_20250111_020000.sql.gz

# Access PostgreSQL CLI
docker-compose exec postgres psql -U mateo -d pokemon_cards
```

### Batch Processing
```bash
# Run batch processor once
docker-compose run --rm batch-processor

# Start batch processor service
docker-compose --profile batch up -d batch-processor
```

### Maintenance
```bash
# Clean up unused images
docker system prune -a

# View disk usage
docker system df

# Backup volumes
docker run --rm -v ebay-tcg-batch-uploader_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_data_backup.tar.gz -C /data .
```

## Volume Management

### Persistent Volumes
- `postgres_data`: Database files
- `redis_data`: Redis persistence
- `uploads`: User uploaded files
- `static_files`: Static assets
- `postgres_backup`: Database backups

### Backup Strategy
1. Automated daily backups at 2 AM
2. Backups every 6 hours for critical data
3. 7-day retention policy
4. Compressed SQL dumps

## Security Considerations

1. **Environment Variables**
   - Never commit `.env` files
   - Use strong passwords
   - Rotate credentials regularly

2. **Network Security**
   - Services communicate on internal network
   - Only required ports exposed
   - Nginx handles SSL termination

3. **Container Security**
   - Non-root user (appuser)
   - Read-only root filesystem where possible
   - Security headers configured

4. **Rate Limiting**
   - General: 10 requests/second
   - API: 30 requests/second
   - Configurable in nginx.conf

## Troubleshooting

### Container Won't Start
```bash
# Check logs
docker-compose logs web

# Verify environment variables
docker-compose config

# Check container status
docker-compose ps
```

### Database Connection Issues
```bash
# Test database connection
docker-compose exec web python -c "from src.database import test_connection; test_connection()"

# Check if database is ready
docker-compose exec postgres pg_isready
```

### Permission Issues
```bash
# Fix file permissions
docker-compose exec web chown -R appuser:appuser /app/logs /app/uploads

# Reset volume permissions
docker run --rm -v ebay-tcg-batch-uploader_uploads:/data alpine chown -R 1000:1000 /data
```

## Performance Tuning

### PostgreSQL
- Adjust shared_buffers in production
- Configure work_mem for complex queries
- Enable query logging for optimization

### Redis
- Set appropriate maxmemory limit
- Configure eviction policy
- Monitor memory usage

### Application
- Use connection pooling
- Enable caching for static content
- Configure worker processes

## Monitoring

### Health Checks
- Web: http://localhost:5001/health
- Database: `pg_isready` command
- Redis: `redis-cli ping`

### Logs Location
- Application: `/app/logs/`
- Nginx: `/var/log/nginx/`
- PostgreSQL: Docker logs
- Backups: `/backup/backup.log`

## Scaling

### Horizontal Scaling
1. Use Docker Swarm or Kubernetes
2. Scale web service behind load balancer
3. Consider read replicas for database

### Vertical Scaling
1. Adjust resource limits in docker-compose
2. Increase container CPU/memory allocation
3. Optimize database queries

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [PostgreSQL Docker Image](https://hub.docker.com/_/postgres)
- [Redis Docker Image](https://hub.docker.com/_/redis)
- [Nginx Docker Image](https://hub.docker.com/_/nginx)