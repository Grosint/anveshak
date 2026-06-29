# Ubuntu 24.04 Docker + NVIDIA Setup Differences

## Confidence: HIGH (verified in production 2026-06-29)

Ubuntu 24.04 Noble has several differences from 22.04 that break standard setup scripts.

### 1. Docker Package Name

`docker.io` not in Noble repos. Use official Docker repo:
```bash
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu noble stable" > /etc/apt/sources.list.d/docker.list
apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 2. NVIDIA Container Toolkit — Separate Repo

Not in Ubuntu repos. Needs NVIDIA's own apt repo:
```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://nvidia.github.io/libnvidia-container/stable/deb/amd64 /" > /etc/apt/sources.list.d/nvidia-container-toolkit.list
```

### 3. NVIDIA Driver — Use `-server` Variant

Headless VMs (no display): `nvidia-driver-550-server` not `nvidia-driver-550`.
GCP may pre-install drivers — check `nvidia-smi` before installing.

### 4. SSH Service Name

```bash
# Ubuntu 24.04
systemctl restart ssh     # ✓
systemctl restart sshd    # ✗ "Unit sshd.service not found"

# Portable:
systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null
```

### 5. echo with heredoc in SSH

Multi-line heredoc + tee breaks when pasted into SSH terminal. Use single-line:
```bash
# BAD — breaks on paste
sudo tee /etc/file <<'EOF'
content
EOF

# GOOD — single line
echo 'content' | sudo tee /etc/file
```

For JSON configs, put entire JSON on one line.
