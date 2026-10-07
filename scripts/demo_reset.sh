#!/bin/zsh
# put the viewer in the state the demo script expects:
#   star's spec back to the api-written version (so tag a line has something to fix on page 107),
#   no leftover corrections, no uploaded demo book, a fresh pdf copy to drop in
set -e
setopt null_glob
cd "$(dirname "$0")/.."
git show 892ecf3:specs/star-hardware-9839d1a1-division-8-specs-commons-lane.json > specs/star-hardware-9839d1a1-division-8-specs-commons-lane.json
rm -f out/star-hardware-9839d1a1-division-8-specs-commons-lane.json out/star.json
rm -f corrections/*.json
rm -f data/uploads/*.pdf specs/uploads-*.json out/uploads-*.json
mkdir -p out/demo
cp "data/valor-acres-building-e/087100-DOOR-HARDWARE_Rev_2.pdf" "out/demo/Valor Acres - Door Hardware.pdf"
echo "ready: drop out/demo/Valor Acres - Door Hardware.pdf on the library, star page 107 is missing set 102.1 again"
