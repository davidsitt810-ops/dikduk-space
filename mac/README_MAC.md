# The dikduk server on the Mac mini

Three scripts, run in Terminal on the Mac, in this order. Each one can be run again safely.

1. **Install** — `bash ~/Downloads/dikduk-v4/mac/install.sh`
   Installs ffmpeg, cloudflared and Python 3.12 with Homebrew, clones the GitHub repo to `~/dikduk/app`, makes a
   Python environment with the same package versions as the Space, downloads the two models (2.6 GB, once), and
   installs the server as a system service (`com.pizmonim.dikduk`) that starts at boot and restarts if it dies. It
   asks for your Mac password for the service and to stop the Mac from sleeping. At the end it prints `up: version 4.7`.
   If Homebrew or the command-line tools are missing it stops and says what to install first.
2. **Public address** — `bash ~/Downloads/dikduk-v4/mac/tunnel.sh dikduk.thepizmonim.com`
   A Cloudflare Tunnel: the Mac dials out, nothing is opened on the router. Step 1 opens the browser for the
   Cloudflare login (your account; pick the domain). It adds one DNS record for that name and nothing else, and
   installs the tunnel as a service. Use another name if you prefer (`checker.thepizmonim.com`); it must be in a
   domain that is in your Cloudflare account.
3. **Speed** — `~/dikduk/venv/bin/python ~/dikduk/app/mac/bench.py --mps`
   Times a pasuk check and six letter takes on the CPU, then the same on the Mac's GPU (MPS), and says whether the
   numbers came out the same. If MPS is faster and the same, set `DK_DEVICE=mps` in `~/dikduk/env` and
   `sudo launchctl kickstart -k system/com.pizmonim.dikduk`.

Afterwards:
- `bash ~/Downloads/dikduk-v4/mac/update.sh` — pulls the newest server code and restarts (the pages, the booth and
  embed.js update by themselves from GitHub, like the Space).
- Log: `tail -f ~/dikduk/logs/server.log`. Tunnel log: `sudo tail -50 /Library/Logs/com.cloudflare.cloudflared.err.log`.
- Stop / start: `sudo launchctl bootout system/com.pizmonim.dikduk` / `sudo launchctl bootstrap system /Library/LaunchDaemons/com.pizmonim.dikduk.plist`.
- Settings: `~/dikduk/env` (the booth key `DK_KEY` is in it: the Mac answers the public internet, so the booth's
  recordings need it; `/takes?key=…`). `DK_THREADS=4` limits torch to the four performance cores if the Mac feels
  sluggish while checking.
- The site: load `embed.js` from a place that is up even when a server is not —
  `<script src="https://cdn.jsdelivr.net/gh/davidsitt810-ops/dikduk-space@main/static/embed.js"></script>` — and give
  it both servers, the Mac first: `data-api="https://dikduk.thepizmonim.com https://davidsitt-pizmonim-dikduk.hf.space"`.
  The embed uses whichever answers `/health` first (a dead tunnel fails in a second; the sleeping Space answers late)
  and asks the other one if a check cannot reach the chosen one. jsDelivr keeps a copy for up to 12 hours; after a
  push, `https://purge.jsdelivr.net/gh/davidsitt810-ops/dikduk-space@main/static/embed.js` refreshes it.

What can go wrong: a macOS update that reboots the Mac — the service comes back by itself after the reboot, but the
Mac must reach the login screen (FileVault asks for a password before anything starts; if the Mac has FileVault on and
is rebooted remotely, nothing runs until someone types it). Power or internet at home: the site falls back to the Space.
