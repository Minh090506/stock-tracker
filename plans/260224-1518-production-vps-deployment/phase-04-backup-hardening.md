# Phase 4: DB Backup + Production Hardening

**Priority**: P1
**Est.**: 1 hour
**Dependencies**: Phase 1 complete

## Overview

Daily TimescaleDB backup via cron + production security hardening.

## Steps

### 4.1 Database Backup Script

Create `scripts/backup-timescaledb-daily.sh` on VPS:

```bash
#!/usr/bin/env bash
# backup-timescaledb-daily.sh — Daily pg_dump of TimescaleDB
set -euo pipefail

BACKUP_DIR="/home/deploy/backups"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d-%H%M)
COMPOSE_FILE="/home/deploy/stock-tracker/docker-compose.prod.yml"

mkdir -p "$BACKUP_DIR"

echo "[backup] Starting backup: $TIMESTAMP"

# Dump via docker exec
docker compose -f "$COMPOSE_FILE" exec -T timescaledb \
    pg_dump -U "${POSTGRES_USER:-stock}" -d "${POSTGRES_DB:-stock_tracker}" \
    --no-owner --no-privileges \
    | gzip > "$BACKUP_DIR/stock-tracker-$TIMESTAMP.sql.gz"

SIZE=$(du -h "$BACKUP_DIR/stock-tracker-$TIMESTAMP.sql.gz" | cut -f1)
echo "[backup] Backup created: $SIZE"

# Cleanup old backups
find "$BACKUP_DIR" -name "stock-tracker-*.sql.gz" -mtime +$RETENTION_DAYS -delete
echo "[backup] Cleaned backups older than $RETENTION_DAYS days"

# List remaining
echo "[backup] Current backups:"
ls -lh "$BACKUP_DIR"/stock-tracker-*.sql.gz 2>/dev/null || echo "  (none)"
```

### 4.2 Cron Schedule

```bash
# On VPS as deploy user
crontab -e

# Add: Daily at 15:35 VN (08:35 UTC) — after market close
35 8 * * 1-5 /home/deploy/stock-tracker/scripts/backup-timescaledb-daily.sh >> /home/deploy/backups/backup.log 2>&1
```

> Market closes 15:00 VN. Backup at 15:35 captures full trading day.
> Only Mon-Fri (trading days).

### 4.3 Restore Procedure

```bash
# On VPS — restore from backup
gunzip -c /home/deploy/backups/stock-tracker-YYYYMMDD-HHMM.sql.gz | \
    docker compose -f docker-compose.prod.yml exec -T timescaledb \
    psql -U stock -d stock_tracker
```

### 4.4 Production Hardening

#### .env on VPS

```bash
# Strong DB password
POSTGRES_PASSWORD=<random-32-char-string>

# Disable debug
DEBUG=false
LOG_LEVEL=WARNING

# Restrict CORS
CORS_ORIGINS=https://yourdomain.com

# WS auth token (optional — set if you want to restrict WS access)
WS_AUTH_TOKEN=<random-token>

# Grafana admin password
GF_SECURITY_ADMIN_PASSWORD=<strong-password>
```

#### docker-compose.prod.yml Changes

```yaml
# 1. Pin TimescaleDB version (no :latest)
timescaledb:
  image: timescale/timescaledb:2.16.1-pg16  # ← pinned

# 2. Remove node-exporter (or fix for Linux)
# node-exporter works on Linux VPS (rslave supported), keep it

# 3. Remove monitoring port exposure (done in Phase 2)

# 4. Add restart policy validation — already has restart: unless-stopped ✓
```

#### SSH Hardening (already done in Phase 1)

- Root login disabled ✓
- Key-only auth (disable password)

```bash
# Disable password auth
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```

#### Auto-Updates (unattended-upgrades)

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades  # Select yes
```

### 4.5 Health Monitoring (Simple)

Add to crontab — alert if health check fails:

```bash
# Every 5 min — check health, log failures
*/5 * * * * curl -sf http://localhost/health > /dev/null || echo "[$(date)] HEALTH CHECK FAILED" >> /home/deploy/backups/health.log
```

> For real alerting: configure Grafana alerts to send to Telegram/email (future enhancement).

## Success Criteria

- [ ] Daily backup runs at 15:35 VN on weekdays
- [ ] Backups older than 7 days auto-deleted
- [ ] Restore procedure tested once
- [ ] TimescaleDB image version pinned
- [ ] Strong passwords in production .env
- [ ] Password SSH disabled
- [ ] Unattended security updates enabled
- [ ] Health check cron running every 5 min
- [ ] Monitoring ports (9090, 3000) not exposed to internet
