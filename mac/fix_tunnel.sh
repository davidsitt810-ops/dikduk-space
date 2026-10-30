#!/bin/bash
# Starts the dikduk tunnel as a boot service the right way (cloudflared's own "service install" on macOS starts it
# without "tunnel run", so it never connects -> error 1033). Uses /etc/cloudflared/config.yml written by tunnel.sh.
#   bash fix_tunnel.sh dikduk.thepizmonim.com
set -euo pipefail
HOST="${1:-dikduk.thepizmonim.com}"
CF="$(command -v cloudflared)"; LABEL="com.pizmonim.tunnel"; PLIST="/Library/LaunchDaemons/$LABEL.plist"; LOG="/Library/Logs/dikduk-tunnel.log"
[ -f /etc/cloudflared/config.yml ] || { echo "/etc/cloudflared/config.yml is missing — run tunnel.sh first"; exit 1; }
echo "== removing cloudflared's own service (it starts without 'tunnel run')"
sudo launchctl bootout system/com.cloudflare.cloudflared 2>/dev/null || true
sudo cloudflared service uninstall >/dev/null 2>&1 || true
echo "== the tunnel service"
TMP="$(mktemp)"
cat > "$TMP" <<P
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array>
    <string>$CF</string><string>tunnel</string><string>--config</string><string>/etc/cloudflared/config.yml</string>
    <string>--protocol</string><string>http2</string><string>--no-autoupdate</string><string>run</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict></plist>
P
sudo cp "$TMP" "$PLIST"; sudo chown root:wheel "$PLIST"; sudo chmod 644 "$PLIST"; rm -f "$TMP"
sudo launchctl bootout system/"$LABEL" 2>/dev/null || true
sudo launchctl bootstrap system "$PLIST"
echo "== checking https://$HOST/health (up to 2 minutes)"
for i in $(seq 1 30); do
  if R="$(curl -fsS -m 8 "https://$HOST/health" 2>/dev/null)"; then echo "up: https://$HOST"; echo "$R" | head -c 200; echo; exit 0; fi
  sleep 4
done
echo "not answering yet — the tunnel's log:"; sudo tail -25 "$LOG"; exit 1
