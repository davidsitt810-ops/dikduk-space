#!/bin/bash
# Pulls the newest server code from GitHub and restarts the service (the pages update by themselves; this is for app.py,
# letters.py, the heads). Needs your password for the restart.
#   bash update.sh
set -euo pipefail
DIR="$HOME/dikduk"; APP="$DIR/app"
git -C "$APP" pull --ff-only
# settings added since the first install (the booth's recordings are kept on this Mac's disk)
grep -q '^DK_DURABLE=' "$DIR/env" 2>/dev/null || printf '# recordings stay on this Mac'"'"'s disk (DK_CACHE)\nDK_DURABLE=1\n' >> "$DIR/env"
sudo launchctl kickstart -k system/com.pizmonim.dikduk
echo "restarting (the models take a minute to load) …"
for i in $(seq 1 60); do
  if curl -fs -m 3 http://127.0.0.1:7860/health >/dev/null 2>&1; then curl -s http://127.0.0.1:7860/health | head -c 60; echo; exit 0; fi
  sleep 3
done
echo "not up after 3 minutes — see $DIR/logs/server.log"; exit 1
