#!/bin/sh
# Full render (R4): the scroll frames (positions in build/plist.json), then the rotation sheet.
# Resumable: frames already on disk are skipped, so it can simply be started again.
cd "$(dirname "$0")"
python3 build_scene.py plist
python3 build_scene.py sheet
echo ALL_DONE
