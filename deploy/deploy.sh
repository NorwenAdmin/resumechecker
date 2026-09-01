#!/usr/bin/env bash
# Deploys resumechecker to the shared VPS (checker.norwen.nl). Run from the local machine.
# Required env vars: VPS_HOST, VPS_USER
# Optional: SSH_KEY (path to private key), APP_DIR (default /opt/resumechecker), ANTHROPIC_API_KEY,
# SESSION_SECRET
#
# This targets a box that already runs another app (Norwen) under nginx with an existing
# *.norwen.nl wildcard cert — no certbot run, no PM2, systemd instead (see deploy/*.service).
# Postgres runs in Docker on host port 5434 (5432/5433 are already taken on this box).
set -euo pipefail

: "${VPS_HOST:?Set VPS_HOST (IP or hostname)}"
: "${VPS_USER:?Set VPS_USER}"
APP_DIR="${APP_DIR:-/opt/resumechecker}"
DB_HOST_PORT="${DB_HOST_PORT:-5434}"
DOMAIN="checker.norwen.nl"
SSH_OPTS=()
if [[ -n "${SSH_KEY:-}" ]]; then
  SSH_OPTS+=(-i "$SSH_KEY")
fi

REMOTE="$VPS_USER@$VPS_HOST"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== Syncing code to $REMOTE:$APP_DIR =="
ssh "${SSH_OPTS[@]}" "$REMOTE" "mkdir -p $APP_DIR"
rsync -az --delete \
  -e "ssh ${SSH_OPTS[*]}" \
  --exclude '.venv' --exclude '__pycache__' --exclude '.git' --exclude 'node_modules' --exclude '.env' \
  "$ROOT_DIR/backend" "$ROOT_DIR/frontend" "$ROOT_DIR/docker-compose.yml" \
  "$REMOTE:$APP_DIR/"

echo "== Starting Postgres+pgvector via docker compose (host port $DB_HOST_PORT) =="
ssh "${SSH_OPTS[@]}" "$REMOTE" "cd $APP_DIR && DB_HOST_PORT=$DB_HOST_PORT docker compose up -d"

REMOTE_ENV_EXISTS=$(ssh "${SSH_OPTS[@]}" "$REMOTE" "[ -f $APP_DIR/backend/.env ] && echo yes || echo no")
if [[ "$REMOTE_ENV_EXISTS" == "yes" && -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "== .env already exists on the box and ANTHROPIC_API_KEY not set locally — leaving it untouched =="
else
  echo "== Writing .env (fill in ANTHROPIC_API_KEY on the box afterward if not already set) =="
  ANTHROPIC_KEY_TO_WRITE="${ANTHROPIC_API_KEY:-sk-ant-REPLACE-ME}"
  SESSION_SECRET_TO_WRITE="${SESSION_SECRET:-$(python3 -c 'import secrets; print(secrets.token_hex(32))')}"
  ssh "${SSH_OPTS[@]}" "$REMOTE" "cat > $APP_DIR/backend/.env" <<EOF
DATABASE_URL=postgresql+asyncpg://resumechecker:resumechecker@localhost:$DB_HOST_PORT/resumechecker
ANTHROPIC_API_KEY=$ANTHROPIC_KEY_TO_WRITE
CLAUDE_MODEL=claude-sonnet-5
SESSION_SECRET=$SESSION_SECRET_TO_WRITE
EOF
fi

echo "== Installing Python deps =="
ssh "${SSH_OPTS[@]}" "$REMOTE" "cd $APP_DIR/backend && python3 -m venv .venv && ./.venv/bin/pip install --upgrade pip -q && ./.venv/bin/pip install -q -r requirements.txt"

echo "== Deploying systemd service =="
scp "${SSH_OPTS[@]}" "$ROOT_DIR/deploy/resumechecker.service" "$REMOTE:/tmp/resumechecker.service"
ssh "${SSH_OPTS[@]}" "$REMOTE" "sudo mv /tmp/resumechecker.service /etc/systemd/system/resumechecker.service && sudo systemctl daemon-reload && sudo systemctl enable --now resumechecker && sudo systemctl restart resumechecker"

echo "== Health check (systemd 'active' doesn't catch DB auth/connection failures — an actual request does) =="
HEALTH_CODE=""
for attempt in 1 2 3 4 5; do
  sleep 2
  # '|| true' so a transient connection-refused during startup doesn't kill the script via
  # set -e before this loop gets to decide whether to retry.
  HEALTH_CODE=$(ssh "${SSH_OPTS[@]}" "$REMOTE" "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/onboarding/questions" || true)
  if [[ "$HEALTH_CODE" == "200" ]]; then
    break
  fi
  echo "-- Attempt $attempt: HTTP ${HEALTH_CODE:-<no response>}, retrying..."
done
if [[ "$HEALTH_CODE" != "200" ]]; then
  echo "!! Health check failed after 5 attempts (last: HTTP ${HEALTH_CODE:-<no response>}) — the service is running but not answering requests correctly."
  echo "!! Check: ssh $REMOTE 'journalctl -u resumechecker -n 50 --no-pager'"
  exit 1
fi
echo "-- Health check passed (HTTP 200)"

echo "== Configuring Nginx for $DOMAIN (reusing existing *.norwen.nl cert) =="
ssh "${SSH_OPTS[@]}" "$REMOTE" "cat <<'NGINXCONF' | sudo tee /etc/nginx/sites-available/resumechecker >/dev/null
$(cat "$ROOT_DIR/deploy/nginx.conf.template")
NGINXCONF
sudo ln -sf /etc/nginx/sites-available/resumechecker /etc/nginx/sites-enabled/resumechecker
sudo nginx -t && sudo systemctl reload nginx"

echo "== Done. Check https://$DOMAIN =="
echo "== Regression check: confirm https://norwen.nl and https://demo.norwen.nl still respond =="
