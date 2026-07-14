#!/usr/bin/env bash
# Plug-and-play installer for the app-aware SayoDevice macropad daemon.
# The DEVICE already holds its own config (icons, button bindings, calibration);
# this only installs the host daemon that drives the LCD/LEDs per foreground app.
#
# Bootstrap (what the device's button types):
#   git clone https://github.com/batterts/sayo-macropad.git ~/sayo && cd ~/sayo && ./setup.sh
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
echo "==> Installing app-aware SayoDevice daemon in $DIR"

# 1) venv + deps
if [ ! -d venv ]; then
  echo "==> Creating venv"
  python3 -m venv venv
fi
echo "==> Installing Python deps (hidapi, Pillow, ...)"
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -r requirements.txt
PY="$DIR/venv/bin/python3"

# 2) generate a LaunchAgent with THIS machine's paths
PLIST="$HOME/Library/LaunchAgents/com.shauny.sayodaemon.plist"
mkdir -p "$HOME/Library/LaunchAgents"
echo "==> Writing LaunchAgent -> $PLIST"
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.shauny.sayodaemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PY</string>
        <string>$DIR/sayo_daemon.py</string>
    </array>
    <key>WorkingDirectory</key><string>$DIR</string>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>/tmp/sayodaemon.out</string>
    <key>StandardErrorPath</key><string>/tmp/sayodaemon.err</string>
</dict>
</plist>
PLISTEOF

# 3) (re)load it
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
sleep 2

echo ""
if pgrep -f sayo_daemon.py >/dev/null; then
  echo "✅ Daemon running. Switch apps and the LCD icon + LED colors will follow."
else
  echo "⚠️  Daemon not detected — check /tmp/sayodaemon.err. Is the device plugged in?"
fi
echo "   Test mapping:   $PY $DIR/sayo_daemon.py --once"
echo "   Preview icons:  $PY $DIR/sayo_show.py tour"
echo "   Remap apps:     edit $DIR/sayo_config.json"
