#!/usr/bin/env bash
# Full device restore after a factory reset: recompile + flash the button script,
# re-assert the button bindings, and re-upload the 7 app icons — in one command.
#
# Prereq (after a factory reset): via sayodevice.com, (1) Backup & Restore -> Restore
# sayobk-blank.sayobak (clears the factory screen layers), then (2) Calibrate the keys.
# See RECOVERY.md. Calibration + screen layout need the web app; the rest is below.
#
#   ./restore.sh
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$DIR"
PLIST="$HOME/Library/LaunchAgents/com.shauny.sayodaemon.plist"
PY="$DIR/venv/bin/python3"

echo "==> Recompiling modes.bin"
"$PY" gen_modes.py
"$PY" -c "import sys;sys.path.insert(0,'.');from sayo_toolkit.assembler import assemble;open('modes.bin','wb').write(assemble(open('modes.v3').read()))"

echo "==> Freeing the device (stop daemon)"
launchctl unload "$PLIST" 2>/dev/null || true
pkill -9 -f sayo_daemon.py 2>/dev/null || true
sleep 2

echo "==> Restoring device"
"$PY" restore_device.py

echo "==> Restarting daemon"
launchctl load "$PLIST"
sleep 2
if pgrep -f sayo_daemon.py >/dev/null; then
  echo "✅ Restore done. Switch apps to confirm the LCD + buttons follow."
else
  echo "⚠️ Daemon not running (check /tmp/sayodaemon.err)"
fi
