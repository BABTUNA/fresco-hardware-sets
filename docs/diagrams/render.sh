#!/bin/zsh
# render architecture.html to architecture.png at 2x with headless chrome
# usage: docs/diagrams/render.sh
set -e
cd "$(dirname "$0")"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=2 --window-size=1600,900 \
  --virtual-time-budget=4000 --screenshot="$PWD/architecture.png" "file://$PWD/architecture.html" 2>/dev/null
echo "wrote $PWD/architecture.png"
