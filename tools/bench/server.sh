#!/bin/bash
# The dev server of a checkout on 127.0.0.1:7861, (re)started unless the one running already serves that checkout at
# that commit with the same Python files and the same extra env.
# usage: server.sh <bench dir> [repo dir = this checkout] [K=V ...]
#   <bench dir> holds venv/ (Python 3.11 with torch 2.4.1+cpu, transformers 4.44.2, numpy, fastapi, uvicorn,
#   python-multipart: tools/bench/README.md), hf/ (the models, fetched on the first start), dkcache/, server.log
B=${1:?the bench folder}; shift; R=${1:-$(cd "$(dirname "$0")/../.." && pwd)}; [ $# -gt 0 ] && shift
want="$R $(git -C "$R" rev-parse HEAD 2>/dev/null) $(git -C "$R" status --porcelain -- '*.py' | md5sum | cut -c1-8) $(cd "$R" && cat *.py | md5sum | cut -c1-8) $*"
if [ "$(cat "$B/server.id" 2>/dev/null)" = "$want" ] && curl -s -m 5 http://127.0.0.1:7861/health | grep -q '"version"'; then echo "server already up: $want"; exit 0; fi
for p in $(pgrep -f "uvicorn app:app"); do kill $p 2>/dev/null; done
for i in $(seq 1 20); do pgrep -f "uvicorn app:app" > /dev/null || break; sleep 1; done
# (the server keeps none of this script's own output open: a caller that pipes the script would wait for it for ever)
( cd "$R" && exec env HF_HOME="$B/hf" DK_CACHE="$B/dkcache" DK_KEY=testkey123 DK_NO_WARM=1 "$@" setsid "$B/venv/bin/python" -m uvicorn app:app --host 127.0.0.1 --port 7861 > "$B/server.log" 2>&1 < /dev/null & ) > /dev/null 2>&1
for i in $(seq 1 400); do
  sleep 3
  if curl -s -m 3 http://127.0.0.1:7861/health | grep -q '"version"'; then echo "$want" > "$B/server.id"; echo "server up: $want"; exit 0; fi
  pgrep -f "uvicorn app:app" > /dev/null || { echo "server died:"; tail -5 "$B/server.log"; exit 1; }
done
echo "server did not come up"; tail -5 "$B/server.log"; exit 1
