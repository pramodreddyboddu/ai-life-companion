# Backup & Restore Runbook

## Targets
- **RPO**: 24 hours (nightly backups)
- **RTO**: 2 hours for critical services

## Postgres Backups
- Nightly `pg_dump` stored in cloud storage (e.g., S3 `s3://ai-companion-backups/db/YYYY-MM-DD.sql.gz`).
- Retention: 30 days.
- Job: `0 2 * * *` UTC on Render or external scheduler.
  ```bash
  pg_dump "$APP_DATABASE__URL" \
    | gzip \
    | aws s3 cp - s3://ai-companion-backups/db/$(date -u +\%F).sql.gz
  ```

## Redis Backups
- Enable Redis RDB snapshots (every 6 hours) and copy `dump.rdb` to storage nightly.
- Retention: 7 days.
- Job: `0 3 * * *` UTC.
  ```bash
  redis-cli save
  aws s3 cp /var/redis/dump.rdb s3://ai-companion-backups/redis/dump-$(date -u +\%F-%H).rdb
  ```

## Restore Steps (Staging Drill)
1. **Postgres**
   ```bash
   aws s3 cp s3://ai-companion-backups/db/<snapshot>.sql.gz - | gunzip \
     | psql "$APP_DATABASE__URL"
   ```
2. **Redis**
   ```bash
   aws s3 cp s3://ai-companion-backups/redis/<snapshot>.rdb dump.rdb
   redis-server --dbfilename dump.rdb --dir .
   ```
3. Update configs / secrets as needed.

## Validation
- Run `./scripts/smoke.sh` against staging.
- Verify reminders, chat, and calendar endpoints.

## Production Incident
- Halt traffic (maintenance mode).
- Restore DB + Redis from latest snapshot.
- Redeploy services.
- Notify stakeholders and log incident.
