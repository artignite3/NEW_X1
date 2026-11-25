#!/usr/bin/env bash
# One-time VM preparation for Ubuntu 22.04/24.04 (x86_64 or ARM64).
# Usage on the VM:  sudo bash deploy/oracle/setup.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo bash deploy/oracle/setup.sh" >&2
  exit 1
fi

echo "==> Installing Docker Engine and the Compose plugin"
if ! command -v docker >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
if [[ -n "${SUDO_USER:-}" ]]; then usermod -aG docker "$SUDO_USER"; fi

echo "==> Opening ports 80 and 443 in the VM firewall"
# Oracle's Ubuntu images ship iptables rules that reject everything except SSH.
for port in 80 443; do
  if ! iptables -C INPUT -p tcp --dport "$port" -m state --state NEW -j ACCEPT 2>/dev/null; then
    iptables -I INPUT 6 -p tcp --dport "$port" -m state --state NEW -j ACCEPT
  fi
done
if command -v netfilter-persistent >/dev/null 2>&1; then
  netfilter-persistent save
else
  DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent
  netfilter-persistent save
fi

echo "==> Adding 4 GB of swap for the first image build"
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

cat <<'EOF'

Done. Next:
  1. cd deploy/oracle && cp server.env.example server.env && nano server.env
  2. (optional) cp worker.env.example worker.env && nano worker.env
  3. Log out and back in once so Docker works without sudo
  4. docker compose up -d --build
  5. curl https://<API_DOMAIN>/health
EOF
