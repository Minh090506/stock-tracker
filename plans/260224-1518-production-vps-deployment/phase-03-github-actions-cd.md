# Phase 3: GitHub Actions CD Pipeline

**Priority**: P1
**Est.**: 1 hour
**Dependencies**: Phase 1+2 complete

## Overview

Add deploy job to existing CI workflow. On push to master → tests pass → SSH into VPS → git pull → rebuild containers.

## Steps

### 3.1 Create SSH Deploy Key

```bash
# On local machine — generate deploy-only key
ssh-keygen -t ed25519 -C "github-deploy" -f ~/.ssh/stock-tracker-deploy

# Copy public key to VPS
ssh-copy-id -i ~/.ssh/stock-tracker-deploy.pub deploy@VPS_IP

# Test
ssh -i ~/.ssh/stock-tracker-deploy deploy@VPS_IP "echo ok"
```

### 3.2 Add GitHub Secrets

In GitHub repo → Settings → Secrets → Actions:

| Secret | Value |
|--------|-------|
| `VPS_HOST` | VPS IP address |
| `VPS_USER` | `deploy` |
| `VPS_SSH_KEY` | Contents of `~/.ssh/stock-tracker-deploy` (private key) |

### 3.3 Create Deploy Script on VPS

Create `scripts/deploy-vps-remote.sh` — runs ON the VPS during CD:

```bash
#!/usr/bin/env bash
# deploy-vps-remote.sh — Executed by GitHub Actions on VPS via SSH
set -euo pipefail

APP_DIR="/home/deploy/stock-tracker"
COMPOSE_FILE="docker-compose.prod.yml"

cd "$APP_DIR"

echo "[deploy] Pulling latest code..."
git fetch origin master
git reset --hard origin/master

echo "[deploy] Building and deploying..."
docker compose -f "$COMPOSE_FILE" up -d --build --remove-orphans

echo "[deploy] Waiting for health check..."
sleep 10
if curl -sf http://localhost/health > /dev/null; then
    echo "[deploy] Health check PASSED"
else
    echo "[deploy] Health check FAILED — rolling back"
    docker compose -f "$COMPOSE_FILE" logs --tail=50 backend
    exit 1
fi

echo "[deploy] Pruning old images..."
docker image prune -f

echo "[deploy] Deploy complete"
docker compose -f "$COMPOSE_FILE" ps
```

### 3.4 Update CI Workflow

Add `deploy` job to `.github/workflows/ci.yml`:

```yaml
  deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    needs: [backend, frontend, docker-build]
    if: github.ref == 'refs/heads/master' && github.event_name == 'push'

    steps:
      - name: Deploy to VPS
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: bash /home/deploy/stock-tracker/scripts/deploy-vps-remote.sh
```

### 3.5 Full CI/CD Flow

```
git push master
  → CI: backend tests (80% coverage)
  → CI: frontend build
  → CI: docker-build (verify images)
  → CD: SSH to VPS → git pull → docker compose up --build
  → CD: health check → pass/fail
```

### 3.6 Manual Deploy Option

For hotfixes or manual deploys:

```bash
# SSH to VPS directly
ssh deploy@VPS_IP
cd ~/stock-tracker
./scripts/deploy-vps-remote.sh
```

## Rollback Strategy

```bash
# On VPS — rollback to previous commit
ssh deploy@VPS_IP
cd ~/stock-tracker
git log --oneline -5          # Find previous good commit
git reset --hard <commit>
docker compose -f docker-compose.prod.yml up -d --build
```

## Success Criteria

- [ ] Push to master triggers full CI → CD pipeline
- [ ] Deploy job only runs after all tests pass
- [ ] Deploy job only runs on master push (not PRs)
- [ ] Health check validates deployment
- [ ] Failed health check logs backend errors
- [ ] Manual deploy still works via SSH
