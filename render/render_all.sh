#!/bin/sh
# Full render (R4): the 240 scroll frames, then the 120-frame rotation sheet.
# Resumable: frames already on disk are skipped, so it can simply be started again.
cd "$(dirname "$0")"
python3 build_scene.py scroll 0 239 240
python3 build_scene.py sheet
echo ALL_DONE
