# Phase 2: Domain + Cloudflare SSL

**Priority**: P0
**Est.**: 30 min
**Dependencies**: Phase 1 complete, domain owned

## Overview

Point domain to VPS via Cloudflare proxy → free SSL, DDoS protection, static asset caching. No Certbot needed.

## Steps

### 2.1 Cloudflare Setup

1. Add domain to [Cloudflare](https://dash.cloudflare.com) (free plan)
2. Update domain registrar nameservers to Cloudflare's
3. Add DNS records:

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | `@` | `VPS_IP` | Proxied (orange cloud) |
| A | `www` | `VPS_IP` | Proxied (orange cloud) |

4. SSL/TLS settings:
   - **Mode**: Full (not Full Strict — no origin cert needed)
   - **Always Use HTTPS**: ON
   - **Minimum TLS**: 1.2
   - **Auto Minify**: CSS + JS

5. Caching:
   - **Browser Cache TTL**: 4 hours
   - **Caching Level**: Standard

### 2.2 Update Nginx Config

Update `nginx/nginx.conf` to:
- Set `server_name` to actual domain
- Trust Cloudflare IPs for real client IP
- Add security headers

```nginx
# Changes needed in nginx/nginx.conf:

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;  # ← update

    # Trust Cloudflare proxy IPs for real client IP
    set_real_ip_from 173.245.48.0/20;
    set_real_ip_from 103.21.244.0/22;
    set_real_ip_from 103.22.200.0/22;
    set_real_ip_from 103.31.4.0/22;
    set_real_ip_from 141.101.64.0/18;
    set_real_ip_from 108.162.192.0/18;
    set_real_ip_from 190.93.240.0/20;
    set_real_ip_from 188.114.96.0/20;
    set_real_ip_from 197.234.240.0/22;
    set_real_ip_from 198.41.128.0/17;
    set_real_ip_from 162.158.0.0/15;
    set_real_ip_from 104.16.0.0/13;
    set_real_ip_from 104.24.0.0/14;
    set_real_ip_from 172.64.0.0/13;
    set_real_ip_from 131.0.72.0/22;
    real_ip_header CF-Connecting-IP;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # ... rest of existing location blocks unchanged ...
}
```

### 2.3 Update docker-compose.prod.yml

Remove external exposure of monitoring ports:

```yaml
# REMOVE these from prometheus and grafana:
#   ports:
#     - "9090:9090"   # prometheus — remove
#     - "3000:3000"   # grafana — remove

# Keep only expose (internal network):
prometheus:
  expose:
    - "9090"
  # ports removed

grafana:
  expose:
    - "3000"
  # ports removed
```

### 2.4 Update Backend CORS

In `.env` on VPS:
```bash
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### 2.5 Verify

```bash
# On VPS
cd /home/deploy/stock-tracker
docker compose -f docker-compose.prod.yml up -d --build

# Test
curl -I https://yourdomain.com         # Should 200 via Cloudflare
curl https://yourdomain.com/health      # {"status":"ok"}
```

## Cloudflare WebSocket Note

Cloudflare free plan supports WebSocket proxying. No special config needed — it detects `Upgrade: websocket` headers automatically.

## Success Criteria

- [ ] `https://yourdomain.com` loads dashboard
- [ ] SSL certificate valid (Cloudflare edge)
- [ ] WebSocket `/ws/market` connects via `wss://yourdomain.com/ws/market`
- [ ] Prometheus/Grafana NOT accessible from internet
- [ ] Security headers present in response
- [ ] Real client IPs logged (not Cloudflare IPs)
