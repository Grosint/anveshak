#!/bin/bash
# Anveshak — Cloud-Agnostic VM Bootstrap Script
# Run once on a fresh Ubuntu 22.04+ VM with optional GPU.
# Works on: GCP, AWS, Azure, bare metal.
# Usage: sudo bash scripts/bootstrap-vm.sh
#
# Prerequisites:
#   - Ubuntu 22.04+ or Debian 12+
#   - Data disk attached at /dev/sdb (or set DATA_DISK below)
#   - Internet access for package downloads
#
# Lessons learned from production deploy 2026-06-29:
#   - docker.io not on Ubuntu 24.04 — use official Docker repo
#   - nvidia-container-toolkit needs separate NVIDIA repo
#   - nvidia-driver-550-server for headless VMs
#   - Bind mount permissions: models need 777, observability needs specific UIDs
#   - Ubuntu 24.04 uses 'ssh' not 'sshd' service name
set -euo pipefail

DATA_DISK="${DATA_DISK:-/dev/sdb}"
DATA_DIR="/data"

echo "=== Anveshak VM Bootstrap ==="
echo "Data disk: $DATA_DISK → $DATA_DIR"

# ─── Step 1: Mount data disk ─────────────────────────────────────────────────
echo "[1/9] Mounting data disk..."
if ! mountpoint -q "$DATA_DIR"; then
  if ! blkid "$DATA_DISK" > /dev/null 2>&1; then
    mkfs.ext4 -F "$DATA_DISK"
  fi
  mkdir -p "$DATA_DIR"
  mount "$DATA_DISK" "$DATA_DIR"
  if ! grep -q "$DATA_DISK" /etc/fstab; then
    echo "$DATA_DISK $DATA_DIR ext4 defaults,noatime,discard,nofail 0 2" >> /etc/fstab
  fi
fi
echo "  Mounted: $(df -h $DATA_DIR | tail -1 | awk '{print $2, "total,", $4, "free"}')"

# ─── Step 2: Install Docker (official repo) ──────────────────────────────────
echo "[2/9] Installing Docker..."
apt-get update -qq
apt-get install -y ca-certificates curl gnupg

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

CODENAME=$(. /etc/os-release && echo "$VERSION_CODENAME")
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $CODENAME stable" > /etc/apt/sources.list.d/docker.list

apt-get update -qq
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
usermod -aG docker "${SUDO_USER:-ubuntu}" || true
systemctl enable docker

# ─── Step 3: Install NVIDIA (if GPU present) ─────────────────────────────────
echo "[3/9] Checking for NVIDIA GPU..."
if lspci | grep -qi nvidia; then
  echo "  GPU detected. Installing drivers..."

  # Check if driver already installed (GCP pre-installs sometimes)
  if ! command -v nvidia-smi &> /dev/null; then
    apt-get install -y linux-headers-$(uname -r)
    apt-get install -y nvidia-driver-550-server || apt-get install -y nvidia-driver-550 || echo "  WARN: nvidia-driver install failed — may need reboot"
  else
    echo "  nvidia-smi already available: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'check after reboot')"
  fi

  # NVIDIA container toolkit (separate repo)
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg 2>/dev/null
  echo "deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://nvidia.github.io/libnvidia-container/stable/deb/amd64 /" > /etc/apt/sources.list.d/nvidia-container-toolkit.list
  apt-get update -qq
  apt-get install -y nvidia-container-toolkit
  nvidia-ctk runtime configure --runtime=docker

  GPU_RUNTIME='"default-runtime": "nvidia","runtimes": {"nvidia": {"path": "nvidia-container-runtime", "runtimeArgs": []}},'
else
  echo "  No GPU detected. Skipping NVIDIA drivers."
  GPU_RUNTIME=""
fi

# ─── Step 4: Configure Docker daemon ─────────────────────────────────────────
echo "[4/9] Configuring Docker daemon..."
mkdir -p "$DATA_DIR/docker"

cat > /etc/docker/daemon.json <<DAEMON_EOF
{
  "data-root": "$DATA_DIR/docker",
  "log-driver": "json-file",
  "log-opts": {"max-size": "50m", "max-file": "5"},
  "storage-driver": "overlay2",
  ${GPU_RUNTIME}
  "default-ulimits": {"nofile": {"Name": "nofile", "Hard": 65536, "Soft": 65536}},
  "live-restore": true,
  "userland-proxy": false
}
DAEMON_EOF

systemctl restart docker

# ─── Step 5: Install host packages ───────────────────────────────────────────
echo "[5/9] Installing host packages..."
apt-get install -y nginx certbot python3-certbot-nginx fail2ban unattended-upgrades jq htop tmux git make curl wget logrotate

# ─── Step 6: Create data directory structure ─────────────────────────────────
echo "[6/9] Creating data directories..."
mkdir -p "$DATA_DIR"/{postgres,redis,ollama,models,vision-models,media,reports,backups,logs,prometheus,loki,grafana}

# App data dirs — writable by container user (UID 1000) and init containers
chmod -R 777 "$DATA_DIR/models" "$DATA_DIR/vision-models"
chown -R 1000:1000 "$DATA_DIR/media" "$DATA_DIR/reports" "$DATA_DIR/backups"

# Observability dirs — each tool runs as specific UID inside container
chown -R 65534:65534 "$DATA_DIR/prometheus"   # prometheus runs as nobody
chown -R 10001:10001 "$DATA_DIR/loki"         # loki UID
chown -R 472:472 "$DATA_DIR/grafana"          # grafana UID

# ─── Step 7: Sysctl tuning ───────────────────────────────────────────────────
echo "[7/9] Applying sysctl tuning..."
cat > /etc/sysctl.d/99-anveshak.conf <<'SYSCTL_EOF'
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.core.netdev_max_backlog = 65535
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_intvl = 30
net.ipv4.tcp_keepalive_probes = 5
fs.file-max = 2097152
vm.overcommit_memory = 1
vm.swappiness = 10
SYSCTL_EOF
sysctl -p /etc/sysctl.d/99-anveshak.conf

# ─── Step 8: Create swap ─────────────────────────────────────────────────────
echo "[8/9] Creating swap..."
if [ ! -f "$DATA_DIR/swapfile" ]; then
  fallocate -l 8G "$DATA_DIR/swapfile"
  chmod 600 "$DATA_DIR/swapfile"
  mkswap "$DATA_DIR/swapfile"
  swapon "$DATA_DIR/swapfile"
  if ! grep -q "$DATA_DIR/swapfile" /etc/fstab; then
    echo "$DATA_DIR/swapfile none swap sw 0 0" >> /etc/fstab
  fi
fi

# ─── Step 9: Security hardening ──────────────────────────────────────────────
echo "[9/9] Hardening SSH and firewall..."
sed -i 's/#\?PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/#\?PermitRootLogin .*/PermitRootLogin no/' /etc/ssh/sshd_config
# Ubuntu 24.04 uses 'ssh', older uses 'sshd'
systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || true

systemctl enable fail2ban
systemctl start fail2ban

ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# ─── Done ────────────────────────────────────────────────────────────────────
echo ""
echo "=== Bootstrap Complete ==="
echo "Docker:  $(docker --version 2>/dev/null || echo 'check after relogin')"
if command -v nvidia-smi &> /dev/null; then
  echo "GPU:     $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo 'reboot needed')"
else
  echo "GPU:     none (CPU-only deployment)"
fi
echo "Data:    $(df -h $DATA_DIR | tail -1 | awk '{print $2, "total,", $4, "free"}')"
echo "Swap:    $(free -h | grep Swap | awk '{print $2}')"
echo ""
echo "Next steps:"
echo "  1. If NVIDIA driver was just installed: sudo reboot"
echo "  2. After reboot verify GPU: nvidia-smi"
echo "  3. Verify Docker GPU: docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi"
echo "  4. Clone repo: cd /data && git clone <repo-url> anveshak"
echo "  5. Configure: cd anveshak && cp .env.example .env && nano .env"
echo "  6. Build: docker compose -p anveshak --env-file .env -f infra/compose.yml -f infra/compose.prod.yml build"
echo "  7. Start: docker compose -p anveshak --env-file .env -f infra/compose.yml -f infra/compose.prod.yml up -d"
echo "  8. Migrate: docker compose ... exec api python -m alembic upgrade head"
echo "  9. Pull LLM: docker compose ... exec ollama ollama pull qwen2.5:14b"
echo "  10. Create admin user — see docs/prod_deployment.md"
