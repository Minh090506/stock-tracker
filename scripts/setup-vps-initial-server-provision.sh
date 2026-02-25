#!/usr/bin/env bash
# setup-vps-initial-server-provision.sh
# Run as root on a fresh Ubuntu 24.04 Hetzner VPS.
# Usage: ssh root@VPS_IP 'bash -s' < scripts/setup-vps-initial-server-provision.sh
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[setup]${NC} $*"; }
warn() { echo -e "${YELLOW}[setup]${NC} $*"; }
err()  { echo -e "${RED}[setup]${NC} $*" >&2; }

# ── Require root ──────────────────────────────────────────
if [ "$(id -u)" -ne 0 ]; then
    err "Must run as root"
    exit 1
fi

DEPLOY_USER="deploy"
APP_DIR="/home/$DEPLOY_USER/stock-tracker"
REPO_URL="${1:-}"

# ── 1. System update ─────────────────────────────────────
log "Updating system packages..."
apt-get update -qq && apt-get upgrade -y -qq

# ── 2. Create deploy user ────────────────────────────────
if id "$DEPLOY_USER" &>/dev/null; then
    warn "User '$DEPLOY_USER' already exists, skipping"
else
    log "Creating user '$DEPLOY_USER'..."
    adduser --disabled-password --gecos "" "$DEPLOY_USER"
    echo "$DEPLOY_USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$DEPLOY_USER
    chmod 440 /etc/sudoers.d/$DEPLOY_USER
fi

# Copy root SSH keys to deploy user
log "Copying SSH authorized_keys to $DEPLOY_USER..."
mkdir -p /home/$DEPLOY_USER/.ssh
cp /root/.ssh/authorized_keys /home/$DEPLOY_USER/.ssh/ 2>/dev/null || warn "No root authorized_keys found"
chown -R $DEPLOY_USER:$DEPLOY_USER /home/$DEPLOY_USER/.ssh
chmod 700 /home/$DEPLOY_USER/.ssh
chmod 600 /home/$DEPLOY_USER/.ssh/authorized_keys 2>/dev/null || true

# ── 3. SSH hardening ─────────────────────────────────────
log "Hardening SSH..."
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
# Ubuntu 24.04 uses ssh.service (not sshd.service)
systemctl restart ssh

# ── 4. Firewall (UFW) ────────────────────────────────────
log "Configuring firewall..."
apt-get install -y -qq ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment "SSH"
ufw allow 80/tcp comment "HTTP"
ufw allow 443/tcp comment "HTTPS"
echo "y" | ufw enable
ufw status

# ── 5. Install Docker ────────────────────────────────────
if command -v docker &>/dev/null; then
    warn "Docker already installed: $(docker --version)"
else
    log "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
fi
usermod -aG docker $DEPLOY_USER

# Verify docker compose
if docker compose version &>/dev/null; then
    log "Docker Compose: $(docker compose version --short)"
else
    err "Docker Compose not found!"
    exit 1
fi

# ── 6. Unattended security updates ───────────────────────
log "Enabling unattended security updates..."
apt-get install -y -qq unattended-upgrades
echo 'Unattended-Upgrade::Automatic-Reboot "false";' > /etc/apt/apt.conf.d/51custom-unattended
# DEBIAN_FRONTEND=noninteractive avoids interactive prompt when piping via SSH
DEBIAN_FRONTEND=noninteractive dpkg-reconfigure -plow unattended-upgrades 2>/dev/null || true

# ── 7. Create backup directory ────────────────────────────
mkdir -p /home/$DEPLOY_USER/backups
chown $DEPLOY_USER:$DEPLOY_USER /home/$DEPLOY_USER/backups

# ── 8. Clone repo (if URL provided) ──────────────────────
if [ -n "$REPO_URL" ]; then
    if [ -d "$APP_DIR" ]; then
        warn "App directory already exists: $APP_DIR"
    else
        log "Cloning repo..."
        sudo -u $DEPLOY_USER git clone "$REPO_URL" "$APP_DIR"
    fi
else
    warn "No repo URL provided. Clone manually:"
    warn "  sudo -u $DEPLOY_USER git clone <repo-url> $APP_DIR"
fi

# ── Done ──────────────────────────────────────────────────
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  VPS Setup Complete                              ║${NC}"
echo -e "${CYAN}╠══════════════════════════════════════════════════╣${NC}"
echo -e "${CYAN}║  User:      ${NC}deploy${CYAN}                               ║${NC}"
echo -e "${CYAN}║  Docker:    ${NC}$(docker --version | cut -d' ' -f3)${CYAN}                     ║${NC}"
echo -e "${CYAN}║  Firewall:  ${NC}UFW active (22, 80, 443)${CYAN}             ║${NC}"
echo -e "${CYAN}║  SSH:       ${NC}Root disabled, key-only${CYAN}              ║${NC}"
echo -e "${CYAN}╠══════════════════════════════════════════════════╣${NC}"
echo -e "${CYAN}║  Next steps:                                     ║${NC}"
echo -e "${CYAN}║  1. ${NC}ssh deploy@<VPS_IP>${CYAN}                          ║${NC}"
echo -e "${CYAN}║  2. ${NC}cd ~/stock-tracker${CYAN}                           ║${NC}"
echo -e "${CYAN}║  3. ${NC}cp .env.example .env && nano .env${CYAN}            ║${NC}"
echo -e "${CYAN}║  4. ${NC}docker compose -f docker-compose.prod.yml up -d --build${CYAN} ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
