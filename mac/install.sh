#!/bin/bash
# The dikduk server on an Apple-Silicon Mac (David's M4 Mac mini): installs what it needs, fetches the code and the two
# models, and runs it at boot as a LaunchDaemon on http://127.0.0.1:7860 (the public name comes from tunnel.sh).
# Safe to run again: every step checks what is already there. It asks for your password once or twice (sudo), for the
# LaunchDaemon and the sleep settings — never type it anywhere else.
#   bash install.sh
set -euo pipefail
DIR="$HOME/dikduk"; APP="$DIR/app"; VENV="$DIR/venv"; LOGS="$DIR/logs"; ENVF="$DIR/env"
REPO="https://github.com/davidsitt810-ops/dikduk-space.git"
LABEL="com.pizmonim.dikduk"; PLIST="/Library/LaunchDaemons/$LABEL.plist"
say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

say "checks"
[ "$(uname -s)" = Darwin ] || { echo "this is for macOS"; exit 1; }
[ "$(uname -m)" = arm64 ] || { echo "this is for an Apple-Silicon Mac (arm64), not $(uname -m)"; exit 1; }
if ! xcode-select -p >/dev/null 2>&1; then
  echo "macOS needs its command-line tools first (git). A dialog will open — install them, then run this script again."
  xcode-select --install || true; exit 1
fi
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is not installed. Install it from https://brew.sh (one command there), open a new Terminal window, then run this script again."
  exit 1
fi

say "ffmpeg, cloudflared, python 3.12 (Homebrew)"
brew list --versions ffmpeg >/dev/null 2>&1 || brew install ffmpeg
brew list --versions cloudflared >/dev/null 2>&1 || brew install cloudflared
brew list --versions python@3.12 >/dev/null 2>&1 || brew install python@3.12
PY="$(brew --prefix python@3.12)/bin/python3.12"
"$PY" --version

say "the code: $APP"
mkdir -p "$DIR" "$LOGS"
if [ -d "$APP/.git" ]; then git -C "$APP" pull --ff-only; else git clone --depth 1 "$REPO" "$APP"; fi

say "python packages (the same versions as the Space)"
[ -x "$VENV/bin/python" ] || "$PY" -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet "torch==2.4.1" "transformers==4.44.2" "huggingface_hub>=0.24,<1.0" fastapi uvicorn numpy requests
"$VENV/bin/python" -c "import torch, transformers; print('torch', torch.__version__, '· transformers', transformers.__version__, '· mps available:', torch.backends.mps.is_available())"

say "settings: $ENVF"
if [ ! -f "$ENVF" ]; then
  KEY="$(openssl rand -hex 16)"
  cat > "$ENVF" <<EOF
# the dikduk server's settings (read by run.sh). Lines are KEY=value.
HF_HOME=$DIR/hf
HF_HUB_DISABLE_TELEMETRY=1
DK_CACHE=$DIR/cache
# the lab page, the booth, the letters page and embed.js come from the newest copy on GitHub (as on the Space);
# the server code itself updates with update.sh
DK_PAGE_BASE=https://raw.githubusercontent.com/davidsitt810-ops/dikduk-space/main/static/
# this machine answers the public internet through the tunnel: the booth's recordings need the key below
DK_PUBLIC=1
DK_KEY=$KEY
# cpu is the measured setting; mps (the Mac's GPU) is the experiment — bench.sh compares them
DK_DEVICE=cpu
# DK_THREADS=4
PORT=7860
EOF
  chmod 600 "$ENVF"
  echo "wrote $ENVF (the booth key is in it — keep the file to yourself)"
else
  echo "keeping the existing $ENVF"
fi

say "the two models (about 2.6 GB, once)"
set -a; . "$ENVF"; set +a
mkdir -p "$HF_HOME" "$DK_CACHE"
"$VENV/bin/python" - <<'EOF'
from transformers import Wav2Vec2ForCTC, Wav2Vec2FeatureExtractor, Wav2Vec2Processor
from huggingface_hub import hf_hub_download
m = 'facebook/wav2vec2-xlsr-53-espeak-cv-ft'; Wav2Vec2FeatureExtractor.from_pretrained(m); Wav2Vec2ForCTC.from_pretrained(m); hf_hub_download(m, 'vocab.json')
a = 'jonatasgrosman/wav2vec2-large-xlsr-53-arabic'; Wav2Vec2Processor.from_pretrained(a); Wav2Vec2ForCTC.from_pretrained(a)
print('models ready')
EOF

say "run.sh"
cat > "$DIR/run.sh" <<EOF
#!/bin/bash
# starts the dikduk server (launchd runs this at boot; you can also run it by hand to watch it)
set -a; . "$ENVF"; set +a
cd "$APP"
exec "$VENV/bin/uvicorn" app:app --host 127.0.0.1 --port "\${PORT:-7860}" --workers 1
EOF
chmod +x "$DIR/run.sh"

say "the LaunchDaemon (runs at boot, restarts if it dies; needs your password)"
TMP="$(mktemp)"
cat > "$TMP" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$DIR/run.sh</string></array>
  <key>UserName</key><string>$USER</string>
  <key>WorkingDirectory</key><string>$APP</string>
  <key>EnvironmentVariables</key><dict>
    <key>HOME</key><string>$HOME</string>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$LOGS/server.log</string>
  <key>StandardErrorPath</key><string>$LOGS/server.log</string>
</dict></plist>
EOF
sudo cp "$TMP" "$PLIST"; sudo chown root:wheel "$PLIST"; sudo chmod 644 "$PLIST"; rm -f "$TMP"
sudo launchctl bootout system/"$LABEL" 2>/dev/null || true
sudo launchctl bootstrap system "$PLIST"
echo "the Mac must not sleep for this to answer at night:"
sudo pmset -a sleep 0 disksleep 0 autorestart 1 || true

say "waiting for the server (loading the models takes a minute)"
for i in $(seq 1 60); do
  if curl -fs -m 3 http://127.0.0.1:7860/health >/dev/null 2>&1; then
    curl -s http://127.0.0.1:7860/health | "$VENV/bin/python" -c "import json,sys; j=json.load(sys.stdin); print('up: version', j['version'], '· device', j['device'], '· threads', j['threads'], '· perakim', len(j['ears']['tehillim_perakim']))"
    echo; echo "Done. The server runs at http://127.0.0.1:7860 (try http://127.0.0.1:7860/letters on this Mac)."
    echo "Next: bash $(dirname "$0")/tunnel.sh dikduk.thepizmonim.com   (or another name you own) to give it a public address."
    exit 0
  fi
  sleep 3
done
echo "the server did not answer in 3 minutes — look at $LOGS/server.log"; tail -30 "$LOGS/server.log"; exit 1
