#!/bin/bash
# A public address for the dikduk server on this Mac, through a Cloudflare Tunnel: no router changes, no open ports,
# the Mac dials out to Cloudflare and Cloudflare forwards https://<hostname> to http://127.0.0.1:7860.
# The hostname must be in a domain that is in YOUR Cloudflare account (thepizmonim.com is); this adds ONE DNS record
# for that name and touches nothing else there.
#   bash tunnel.sh dikduk.thepizmonim.com
# Step 1 opens a browser window: log in to Cloudflare and pick the domain (that is the only sign-in; the script never
# sees a password). Steps 3–5 ask for your Mac password (sudo) to install the tunnel as a service that runs at boot.
set -euo pipefail
HOST="${1:-}"; NAME="dikduk"
[ -n "$HOST" ] || { echo "usage: bash tunnel.sh <hostname>   e.g. bash tunnel.sh dikduk.thepizmonim.com"; exit 1; }
command -v cloudflared >/dev/null 2>&1 || { echo "cloudflared is missing — run install.sh first"; exit 1; }
curl -fs -m 5 http://127.0.0.1:7860/health >/dev/null || { echo "the server is not answering on 127.0.0.1:7860 — run install.sh first"; exit 1; }
say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

say "1. Cloudflare login (a browser window opens; pick the domain of $HOST)"
if [ ! -f "$HOME/.cloudflared/cert.pem" ]; then cloudflared tunnel login; else echo "already logged in ($HOME/.cloudflared/cert.pem)"; fi

say "2. the tunnel '$NAME'"
if ! cloudflared tunnel list 2>/dev/null | awk '{print $2}' | grep -qx "$NAME"; then cloudflared tunnel create "$NAME"; else echo "tunnel '$NAME' exists"; fi
UUID="$(cloudflared tunnel list 2>/dev/null | awk -v n="$NAME" '$2==n {print $1}' | head -1)"
[ -n "$UUID" ] || { echo "could not read the tunnel id from 'cloudflared tunnel list'"; exit 1; }
CRED="$HOME/.cloudflared/$UUID.json"
[ -f "$CRED" ] || { echo "the tunnel's credentials file $CRED is missing (was the tunnel created on another machine? delete it with 'cloudflared tunnel delete $NAME' and run again)"; exit 1; }
echo "tunnel id $UUID"

say "3. the DNS record $HOST -> the tunnel (one CNAME in your zone)"
cloudflared tunnel route dns "$NAME" "$HOST" || echo "(the record may already exist — fine)"

say "4. the service (runs at boot; needs your password)"
sudo mkdir -p /etc/cloudflared
sudo cp "$CRED" /etc/cloudflared/
sudo tee /etc/cloudflared/config.yml >/dev/null <<EOF
tunnel: $UUID
credentials-file: /etc/cloudflared/$UUID.json
ingress:
  - hostname: $HOST
    service: http://127.0.0.1:7860
    originRequest:
      connectTimeout: 30s
      noTLSVerify: true
  - service: http_status:404
EOF
exec bash "$(dirname "$0")/fix_tunnel.sh" "$HOST"   # cloudflared's own "service install" starts it without "tunnel run" on macOS (error 1033)

say "5. checking https://$HOST/health"
for i in $(seq 1 30); do
  if curl -fs -m 8 "https://$HOST/health" >/dev/null 2>&1; then
    echo "up: https://$HOST  — the letter checker is at https://$HOST/letters, the booth at https://$HOST/record"
    echo "For the site: data-api=\"https://$HOST https://davidsitt-pizmonim-dikduk.hf.space\" (this Mac first, the Space when it is not answering)."
    exit 0
  fi
  sleep 4
done
echo "https://$HOST does not answer yet. DNS can take a few minutes; try: curl https://$HOST/health — and the service log: sudo tail -50 /Library/Logs/com.cloudflare.cloudflared.err.log"
