#!/bin/bash
# restarts the local v4 server on port 7861 (kills only the python process whose command line is the uvicorn one)
S=/tmp/claude-0/-home-claude/13b8b04f-7b29-591b-ba7b-28708cdbf43a/scratchpad
for p in $(pgrep -f "uvicorn app:app"); do
  if tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q "^python3 -m uvicorn"; then kill $p; fi
done
sleep 2
cd $S/space && HF_HOME=$S/hf DK_CACHE=$S/dkcache DK_NO_WARM=1 nohup python3 -m uvicorn app:app --host 127.0.0.1 --port 7861 > $S/space_test/server_$(date +%H%M%S).log 2>&1 &
for i in $(seq 1 40); do sleep 3; curl -s -m 3 http://127.0.0.1:7861/health | head -c 50 && echo && exit 0; done
echo "server did not come up"; exit 1
