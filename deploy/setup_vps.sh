#!/usr/bin/env bash
# One-time VPS provisioning. Run on the VPS itself (or via ssh from deploy.sh).
# Installs only what's missing: Docker, Python venv tooling. The app runs under systemd
# (already present on any systemd-based distro) and Nginx/certbot are assumed already installed
# — this script targets shared servers that already host other apps, not a bare fresh box.
set -euo pipefail

echo "== Checking/installing prerequisites =="

if ! command -v docker >/dev/null 2>&1; then
  echo "-- Installing Docker"
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
else
  echo "-- Docker already installed"
fi

if ! dpkg -s python3-venv >/dev/null 2>&1; then
  echo "-- Installing python3-venv"
  sudo apt-get update -y
  sudo apt-get install -y python3-venv python3-pip
else
  echo "-- python3-venv already installed"
fi

if ! command -v nginx >/dev/null 2>&1; then
  echo "-- WARNING: nginx not found — this script assumes it's already set up on shared servers." \
       "Install it manually (apt-get install nginx) if this is actually a fresh box."
else
  echo "-- nginx already installed"
fi

mkdir -p /opt/resumechecker
echo "== Done. App directory: /opt/resumechecker =="
