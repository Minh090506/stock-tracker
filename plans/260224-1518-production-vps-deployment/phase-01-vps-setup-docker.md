# Phase 1: VPS Setup & Docker

**Priority**: P0 — Foundation
**Est.**: 45 min (manual SSH work)
**Dependencies**: Hetzner account

## Overview

Provision Hetzner CX22, install Docker, clone repo, verify containers start.

## Steps

### 1.1 Provision Hetzner VPS

1. Go to [Hetzner Cloud Console](https://console.hetzner.cloud)
2. Create server:
   - **Type**: CX22 (2 vCPU, 4GB RAM, 40GB SSD) — EUR 3.99/mo
   - **OS**: Ubuntu 24.04
   - **Location**: Nuremberg or Falkenstein (cheapest)
   - **SSH Key**: Add your public key (`~/.ssh/id_ed25519.pub`)
   - **Name**: `stock-tracker`
3. Note the public IP → `VPS_IP`

### 1.2 Initial Server Setup

```bash
# SSH in
ssh root@VPS_IP

# Update system
apt update && apt upgrade -y

# Create deploy user (non-root)
adduser --disabled-password deploy
usermod -aG sudo deploy
echo "deploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/deploy

# Copy SSH key to deploy user
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh

# Disable root SSH login
sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart sshd
```

### 1.3 Install Docker

```bash
# As deploy user
ssh deploy@VPS_IP

# Install Docker (official method)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker deploy

# Logout and re-login for group to take effect
exit
ssh deploy@VPS_IP

# Verify
docker compose version
```

### 1.4 Firewall (UFW)

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (Cloudflare)
sudo ufw allow 443/tcp   # HTTPS (Cloudflare)
sudo ufw enable
```

> Prometheus (9090) and Grafana (3000) NOT exposed — access via SSH tunnel only.

### 1.5 Clone Repo & First Deploy

```bash
# Clone repo
cd /home/deploy
git clone https://github.com/YOUR_USER/stock-tracker.git
cd stock-tracker

# Create .env from example
cp .env.example .env
nano .env  # Fill SSI credentials, DB password, etc.

# Build and start
docker compose -f docker-compose.prod.yml up -d --build

# Verify
curl http://localhost/health
docker compose -f docker-compose.prod.yml ps
```

### 1.6 Access Monitoring (SSH Tunnel)

```bash
# From local machine — tunnel Grafana
ssh -L 3000:localhost:3000 deploy@VPS_IP
# Open http://localhost:3000 in browser
```

## Success Criteria

- [ ] VPS accessible via SSH as `deploy` user
- [ ] Docker + Docker Compose installed
- [ ] UFW firewall active (22, 80, 443 only)
- [ ] All 6 containers running and healthy
- [ ] `curl http://VPS_IP/health` returns `{"status":"ok"}`
- [ ] Root SSH disabled
