#!/usr/bin/env bash
# download the challenge specbooks into data/<project>/
# the drive folder ids are not in the repo, put one "folder_id:project-name" per line in scripts/drive_ids.txt
# rerunning is safe, gdown skips files it already has
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IDS="$ROOT/scripts/drive_ids.txt"
DATA_DIR="$ROOT/data"
[ -f "$IDS" ] || { echo "missing $IDS"; exit 1; }
mkdir -p "$DATA_DIR"

failed=()
while IFS=: read -r id name; do
  [ -z "$id" ] && continue
  dest="$DATA_DIR/$name"
  mkdir -p "$dest"
  echo "==> $name"
  if ! uvx gdown --folder "https://drive.google.com/drive/folders/$id" -O "$dest" --continue; then
    echo "retry $name"
    sleep 5
    uvx gdown --folder "https://drive.google.com/drive/folders/$id" -O "$dest" --continue || failed+=("$name")
  fi
done < "$IDS"

if [ "${#failed[@]}" -gt 0 ]; then
  echo "failed folders: ${failed[*]}"
  echo "drive rate limits gdown, single files can be fetched from https://drive.usercontent.google.com/download?id=<file id>&export=download&confirm=t"
  exit 1
fi
echo "all folders downloaded"
