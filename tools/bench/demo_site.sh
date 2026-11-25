#!/bin/bash
# The demo site the embed's page tests open (http://127.0.0.1:8099): a site page of its own with this checkout's
# embed.js on it, talking to the dev server on 7861. Built fresh in <dir> on every call (so the embed is the current
# one), then served unless something already answers on 8099.
# usage: demo_site.sh <dir>      pages: demo_th23.html (Tehillim 23, line 1), demo_th23_2.html (line 2), demo_follow.html
D=${1:?a folder for the demo site}; R=$(cd "$(dirname "$0")/../.." && pwd); mkdir -p "$D"
cp "$R/static/embed.js" "$D/embed.js"; cp "$R/tools/demo_th23_2.html" "$R/tools/demo_follow.html" "$D/"
sed 's/data-th="23" data-line="2"/data-th="23" data-line="1"/' "$R/tools/demo_th23_2.html" > "$D/demo_th23.html"
grep -q 'data-line="1"' "$D/demo_th23.html" || { echo "demo_th23.html: the line was not set"; exit 1; }
if curl -s -m 3 -o /dev/null http://127.0.0.1:8099/embed.js; then echo "demo site refreshed in $D (already served on 8099)"; exit 0; fi
( cd "$D" && exec setsid python3 -m http.server 8099 --bind 127.0.0.1 > "$D/http.log" 2>&1 < /dev/null & ) > /dev/null 2>&1
for i in $(seq 1 20); do sleep 0.5; curl -s -m 3 -o /dev/null http://127.0.0.1:8099/embed.js && { echo "demo site up on 8099 from $D"; exit 0; }; done
echo "the demo site did not come up"; exit 1
