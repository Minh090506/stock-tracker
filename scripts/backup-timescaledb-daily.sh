#!/usr/bin/env bash
# Daily logical backup of the production TimescaleDB database.
#
# Dumps the whole database (including _timescaledb_internal) so compressed
# hypertable chunks are captured in their compressed form, keeping the dump
# small. Output is gzipped and rotated after RETENTION_DAYS.
#
# Storage is on-VPS only — protects against logical errors (bad migration,
# accidental DROP) but NOT VPS/disk loss. Add an off-site copy for that.
#
# Restore (into an empty DB) needs the TimescaleDB restore guards:
#   docker exec -i stock-timescaledb psql -U stock -d stock_tracker \
#     -c "SELECT timescaledb_pre_restore();"
#   gunzip -c BACKUP.sql.gz | docker exec -i stock-timescaledb \
#     psql -U stock -d stock_tracker
#   docker exec -i stock-timescaledb psql -U stock -d stock_tracker \
#     -c "SELECT timescaledb_post_restore();"
set -euo pipefail

BACKUP_DIR="/home/deploy/backups"
RETENTION_DAYS=7
CONTAINER="stock-timescaledb"
DB_USER="stock"
DB_NAME="stock_tracker"
TIMESTAMP="$(date +%Y%m%d-%H%M)"
OUT="$BACKUP_DIR/stock-tracker-${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"
echo "[backup $(date -Is)] start -> $OUT"

docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" \
    --no-owner --no-privileges \
    | gzip -6 > "$OUT"

# Reject a truncated/corrupt dump rather than silently keeping it.
if ! gzip -t "$OUT" 2>/dev/null; then
    echo "[backup] ERROR: dump failed gzip integrity check, removing"
    rm -f "$OUT"
    exit 1
fi

echo "[backup] ok: $(du -h "$OUT" | cut -f1)"

find "$BACKUP_DIR" -name 'stock-tracker-*.sql.gz' -mtime +"$RETENTION_DAYS" -delete
echo "[backup] retained (<= ${RETENTION_DAYS}d):"
ls -lh "$BACKUP_DIR"/stock-tracker-*.sql.gz 2>/dev/null || echo "  (none)"
