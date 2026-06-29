#!/bin/bash
# Anveshak — GCP VM Bootstrap Script
# Run once after SSH into a fresh Ubuntu 24.04 VM with T4 GPU.
# Usage: sudo bash scripts/bootstrap-vm.sh
set -euo pipefail

echo "=== Anveshak VM Bootstrap ==="

# --- System packages ---
echo "[1/8] Installing system packages..."
apt-get update
apt-get install -y \
  docker.io docker-compose-plugin \
  nginx certbot python3-certbot-nginx \
  fail2ban unattended-upgrades \
  jq htop tmux git make curl wget \
  logrotate

# --- NVIDIA drivers + container toolkit ---
echo "[2/8] Installing NVIDIA drivers..."
apt-get install -y nvidia-driver-550 nvidia-container-toolkit

# --- Docker setup ---
echo "[3/8] Configuring Docker..."
usermod -aG docker "$SUDO_USER" || true
systemctl enable docker

# Configure Docker daemon
cat <<'EOF' > /etc/docker/daemon.json
{
  "data-root": "/data/docker",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "5"
  },
  "storage-driver": "overlay2",
  "default-runtime": "nvidia",
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime",
      "runtimeArgs": []
    }
  },
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 65536,
      "Soft": 65536
    }
  },
  "live-restore": true,
  "userland-proxy": false
}
EOF

nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

# --- Mount data disk ---
echo "[4/8] Mounting data disk..."
if ! mountpoint -q /data; then
  if ! blkid /dev/sdb; then
    mkfs.ext4 -F /dev/sdb
  fi
  mkdir -p /data
  mount /dev/sdb /data
  if ! grep -q '/dev/sdb' /etc/fstab; then
    echo '/dev/sdb /data ext4 defaults,noatime,discard,nofail 0 2' >> /etc/fstab
  fi
fi

# --- Data directory structure ---
echo "[5/8] Creating data directories..."
mkdir -p /data/{docker,postgres,redis,ollama,models,vision-models,media,reports,backups,logs,prometheus,loki,grafana}
chown -R 1000:1000 /data/media /data/reports /data/models /data/vision-models /data/backups

# --- Sysctl tuning ---
echo "[6/8] Applying sysctl tuning..."
cat <<'EOF' > /etc/sysctl.d/99-anveshak.conf
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.core.netdev_max_backlog = 65535
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_intvl = 30
net.ipv4.tcp_keepalive_probes = 5
fs.file-max = 2097152
vm.overcommit_memory = 1
vm.swappiness = 10
vm.nr_hugepages = 0
EOF
sysctl -p /etc/sysctl.d/99-anveshak.conf

# --- Swap ---
echo "[7/8] Creating swap..."
if [ ! -f /data/swapfile ]; then
  fallocate -l 8G /data/swapfile
  chmod 600 /data/swapfile
  mkswap /data/swapfile
  swapon /data/swapfile
  if ! grep -q '/data/swapfile' /etc/fstab; then
    echo '/data/swapfile none swap sw 0 0' >> /etc/fstab
  fi
fi

# --- Security hardening ---
echo "[8/8] Hardening SSH and firewall..."
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart sshd

systemctl enable fail2ban
systemctl start fail2ban

ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# --- Verify ---
echo ""
echo "=== Bootstrap Complete ==="
echo "Docker:  $(docker --version)"
echo "GPU:     $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'not detected yet — reboot may be needed')"
echo "Data:    $(df -h /data | tail -1 | awk '{print $2, "total,", $4, "free"}')"
echo "Swap:    $(free -h | grep Swap | awk '{print $2}')"
echo ""
echo "Next steps:"
echo "  1. Reboot if NVIDIA driver was just installed: sudo reboot"
echo "  2. After reboot, verify GPU: nvidia-smi"
echo "  3. Verify Docker GPU: docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi"
echo "  4. Clone repo: cd /data && git clone <repo-url> anveshak"
echo "  5. Configure: cd anveshak && cp .env.example .env && vim .env"
echo "  6. Deploy: see docs/prod_deployment.md"
