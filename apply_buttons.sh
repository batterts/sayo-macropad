#!/usr/bin/env bash
# Regenerate + compile the button script, flash it to the device, restart the daemon.
# Run after editing gen_modes.py or pulling config changes:  ./apply_buttons.sh
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$DIR"
PLIST="$HOME/Library/LaunchAgents/com.shauny.sayodaemon.plist"
PY="$DIR/venv/bin/python3"

echo "==> Regenerating + compiling modes.bin"
"$PY" gen_modes.py
"$PY" -c "import sys;sys.path.insert(0,'.');from sayo_toolkit.assembler import assemble;open('modes.bin','wb').write(assemble(open('modes.v3').read()))"

echo "==> Freeing the device (stop daemon)"
launchctl unload "$PLIST" 2>/dev/null || true
pkill -9 -f sayo_daemon.py 2>/dev/null || true
sleep 2

echo "==> Flashing button script to device"
"$PY" -c "import sys,time;sys.path.insert(0,'.')
from sayo_toolkit.upload import upload_script
for a in range(3):
    try: upload_script(open('modes.bin','rb').read(), do_write=True, name='modes', slot=0, verbose=False); print('flashed'); break
    except Exception as e: print('retry',a,e); time.sleep(1.5)
else: raise SystemExit('flash failed - is a browser holding the device via WebHID?')"

echo "==> Restarting daemon"
launchctl load "$PLIST"
sleep 2
pgrep -f sayo_daemon.py >/dev/null && echo "✅ buttons updated; daemon running" || echo "⚠️ daemon not running (check /tmp/sayodaemon.err)"
