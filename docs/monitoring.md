# Monitoring Guide

## Stack Overview

| Component | Port | Purpose |
|-----------|------|---------|
| Prometheus | `:9090` | Metrics collection + storage (15d retention) |
| Grafana | `:3000` | Dashboard visualization (admin/admin) |
| Node Exporter | `:9100` | Host system metrics (CPU, memory, disk, network) |
| Backend `/metrics` | `:8000` | Application metrics (Prometheus format) |

## Quick Start

```bash
# Start with app stack
docker compose -f docker-compose.prod.yml up -d

# Access
# Grafana:    http://localhost:3000  (admin/admin)
# Prometheus: http://localhost:9090
```

Dashboards are auto-provisioned on first start — no manual import needed.

## Grafana Dashboards

### 1. System Overview

**File**: `monitoring/grafana/dashboards/system-overview.json`

Panels:
- CPU usage (user/system/iowait)
- Memory usage + available
- Disk I/O throughput
- Network traffic (rx/tx bytes)
- Container resource usage

**Use for**: Capacity planning, spotting resource exhaustion.

### 2. Data Pipeline

**File**: `monitoring/grafana/dashboards/data-pipeline.json`

Panels:
- SSI messages processed per second (by type: trade, quote, foreign, index, bar)
- Trade classification latency histogram
- Message processing errors
- Batch writer throughput + latency
- WebSocket broadcast rate per channel

**Use for**: Monitoring real-time data flow health, detecting SSI connection drops.

### 3. Alerts Dashboard

**File**: `monitoring/grafana/dashboards/alerts.json`

Panels:
- Alert count by type (VOLUME_SPIKE, PRICE_BREAKOUT, FOREIGN_ACCELERATION, BASIS_DIVERGENCE)
- Alert severity distribution (WARNING vs CRITICAL)
- Alert rate over time
- Top symbols triggering alerts

**Use for**: Market activity overview, validating alert thresholds.

### 4. Database Performance

**File**: `monitoring/grafana/dashboards/database.json`

Panels:
- Connection pool utilization (active/idle/total)
- Query latency (p50, p95, p99)
- Batch write throughput
- Table sizes (hypertable compression)
- Replication lag (if configured)

**Use for**: Database health, identifying slow queries, capacity planning.

## Prometheus Configuration

**File**: `monitoring/prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'stock-tracker-backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: /metrics

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
```

### Verify Targets

```bash
# Check all targets are UP
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool
```

Expected: both `stock-tracker-backend` and `node-exporter` show `"health": "up"`.

## Application Metrics

The backend exposes these Prometheus metrics at `GET /metrics`:

### Counters

| Metric | Labels | Description |
|--------|--------|-------------|
| `ssi_messages_total` | `channel` | SSI messages processed (trade, quote, foreign, index, bar) |
| `ws_messages_sent_total` | `channel` | WebSocket messages broadcast |
| `trade_classifications_total` | `type` | Trades classified (buy/sell/neutral) |
| `alerts_generated_total` | `type`, `severity` | Alerts triggered |
| `db_batch_writes_total` | `table` | Database batch inserts |

### Gauges

| Metric | Labels | Description |
|--------|--------|-------------|
| `ws_connections_active` | `channel` | Current WebSocket connections |
| `db_pool_size` | — | Current connection pool size |
| `db_pool_available` | — | Available pool connections |

### Histograms

| Metric | Labels | Description |
|--------|--------|-------------|
| `trade_classification_seconds` | — | Classification latency |
| `db_batch_write_seconds` | `table` | Batch write latency |
| `ws_broadcast_seconds` | `channel` | Broadcast latency |

## Useful PromQL Queries

### Message throughput
```promql
rate(ssi_messages_total[1m])
```

### Active WebSocket connections by channel
```promql
ws_connections_active
```

### Trade classification p99 latency
```promql
histogram_quantile(0.99, rate(trade_classification_seconds_bucket[5m]))
```

### Database pool utilization
```promql
1 - (db_pool_available / db_pool_size)
```

### Alert rate by type
```promql
rate(alerts_generated_total[5m])
```

### Error rate
```promql
rate(ssi_messages_total{type="error"}[5m]) / rate(ssi_messages_total[5m])
```

## Alerting (Grafana)

To add Grafana alerts on critical conditions:

1. Open any dashboard panel → Edit → Alert tab
2. Set condition, e.g. `ws_connections_active < 1 for 5m`
3. Configure notification channel (email, Slack, webhook)

Suggested alert rules:

| Rule | Condition | Severity |
|------|-----------|----------|
| SSI disconnected | `rate(ssi_messages_total[2m]) == 0` | Critical |
| High memory | `node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes < 0.1` | Warning |
| DB pool exhausted | `db_pool_available == 0 for 1m` | Critical |
| No WS clients | `ws_connections_active == 0 for 10m` | Info |
| High classification latency | `histogram_quantile(0.99, ...) > 0.005` | Warning |

## Data Retention

| Component | Retention | Storage |
|-----------|-----------|---------|
| Prometheus | 15 days | `prometheus-data` Docker volume |
| Grafana | Unlimited | `grafana-data` Docker volume |
| TimescaleDB | Configurable | `pgdata` Docker volume |

To change Prometheus retention, edit `docker-compose.prod.yml`:
```yaml
prometheus:
  command:
    - "--storage.tsdb.retention.time=30d"
```

## Backup

```bash
# Grafana dashboards (auto-provisioned from files, no backup needed)
# Dashboard JSONs in: monitoring/grafana/dashboards/

# Prometheus data
docker compose -f docker-compose.prod.yml exec prometheus \
  promtool tsdb dump /prometheus

# TimescaleDB
docker compose -f docker-compose.prod.yml exec timescaledb \
  pg_dump -U stock stock_tracker > backup.sql
```

## Customizing Dashboards

1. Edit dashboard in Grafana UI
2. Export JSON: Dashboard settings → JSON Model → Copy
3. Save to `monitoring/grafana/dashboards/<name>.json`
4. Restart Grafana to verify auto-provisioning works

Dashboard provisioning config: `monitoring/grafana/provisioning/dashboards/dashboards.yml`

Datasource provisioning: `monitoring/grafana/provisioning/datasources/prometheus.yml`
