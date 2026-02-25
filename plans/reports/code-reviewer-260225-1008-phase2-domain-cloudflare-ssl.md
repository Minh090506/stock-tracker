# Code Review: Phase 2 — Domain + Cloudflare SSL

**Date**: 2026-02-25
**Files**: `nginx/nginx.conf`, `docker-compose.prod.yml`
**Plan**: `plans/260224-1518-production-vps-deployment/phase-02-domain-cloudflare-ssl.md`

---

## Overall Assessment

Changes are correct and match the plan exactly. No blocking issues. Two minor gaps noted below.

---

## nginx/nginx.conf

### Positive

- All 15 Cloudflare IPv4 ranges present and match [Cloudflare's published list](https://www.cloudflare.com/ips-v4/) — correct.
- `real_ip_header CF-Connecting-IP` — correct header for Cloudflare proxy.
- Security headers use `always` directive — headers sent on all response codes including errors. Correct.
- `X-Frame-Options: SAMEORIGIN` — appropriate for a dashboard app.
- `Referrer-Policy: strict-origin-when-cross-origin` — good modern choice.
- `/metrics` uses exact-match `location = /metrics` — correct, avoids accidental prefix match.
- WebSocket `proxy_read_timeout 86400s` (24h) — appropriate for persistent SSI connections.
- Existing location blocks fully preserved.

### Issues

**Medium — `/metrics` endpoint publicly accessible**

The `/metrics` block proxies to backend but has no access restriction. With Cloudflare proxy in front, anyone can hit `https://yourdomain.com/metrics` and read Prometheus metrics (exposes internal app stats, scrape timings, endpoint labels).

Options (pick one):
```nginx
location = /metrics {
    # Option A: restrict by Cloudflare IP only (metrics called by Prometheus internally anyway)
    deny all;

    # Option B: allow only from internal network
    allow 172.0.0.0/8;
    deny all;
    proxy_pass http://backend;
    ...
}
```
Since Prometheus scrapes backend directly (container-to-container on `app-network`), this public `/metrics` route may not be needed at all. If it exists only for external scraping, block it; if internal-only, remove the location block.

**Low — Missing Cloudflare IPv6 ranges**

`set_real_ip_from` only covers IPv4. Cloudflare also routes via IPv6. Missing:
```nginx
set_real_ip_from 2400:cb00::/32;
set_real_ip_from 2606:4700::/32;
set_real_ip_from 2803:f800::/32;
set_real_ip_from 2405:b500::/32;
set_real_ip_from 2405:8100::/32;
set_real_ip_from 2a06:98c0::/29;
set_real_ip_from 2c0f:f248::/32;
```
Impact: real client IP not extracted for IPv6 Cloudflare connections — logs show Cloudflare IP instead of client IP.

**Low — `server_name` still placeholder**

`server_name yourdomain.com www.yourdomain.com` — expected placeholder, must be updated before deploy. Not a code issue, just a reminder.

**Low — No `Content-Security-Policy` header**

Plan doesn't require it but CSP would strengthen the security posture. Low priority for a monitoring dashboard with no user auth.

---

## docker-compose.prod.yml

### Positive

- Prometheus: `ports: "9090:9090"` → `expose: "9090"` — correct, internal only.
- Grafana: `ports: "3000:3000"` → `expose: "3000"` — correct, internal only.
- Both still reachable by Prometheus/Grafana internally on `app-network`.
- All other service definitions unchanged.
- `timescaledb` not exposed externally — already correct from Phase 1.

### Issues

None. Docker Compose syntax valid. The expose/ports change achieves the plan goal.

---

## Plan Completeness Check

| Step | Status |
|------|--------|
| 2.1 Cloudflare setup (DNS/SSL) | Manual — not code |
| 2.2 nginx: server_name + CF IPs + security headers | Done |
| 2.3 docker-compose: remove monitoring ports | Done |
| 2.4 Update CORS in `.env` on VPS | Manual — not code |
| 2.5 Verify | Manual — post-deploy |

Code changes cover all automatable steps. Manual steps (DNS, `.env` CORS update) remain for deployment time.

---

## Recommended Actions

1. **[Medium]** Restrict or remove public `/metrics` endpoint in nginx — block with `deny all` or remove if Prometheus scrapes backend directly (container-to-container).
2. **[Low]** Add Cloudflare IPv6 ranges to `set_real_ip_from` blocks before production deploy.
3. **[Reminder]** Replace `yourdomain.com` placeholder in `server_name` with actual domain before deploy.
4. **[Reminder]** Set `CORS_ORIGINS=https://yourdomain.com,...` in VPS `.env` (Step 2.4).

---

## Unresolved Questions

- Does the `/metrics` Nginx proxy route serve any purpose? Prometheus is configured to scrape `backend:8000/metrics` container-to-container — the public route appears unnecessary and should be removed.
- Is nginx compiled with `ngx_http_realip_module`? (`nginx:alpine` includes it by default — should be fine, but verify with `nginx -V` on the image.)
