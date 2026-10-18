#!/usr/bin/env bash
# Convert the latest Playwright recording to mp4 and enforce the 3:00–4:00 limit.
set -euo pipefail
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "ffmpeg is not installed (macOS: brew install ffmpeg)"; exit 2; }
IN=$(ls -t out/*.webm | head -1)
ffmpeg -y -loglevel error -i "$IN" -c:v libx264 -pix_fmt yuv420p -crf 20 kasflow-demo.mp4
DUR=$(ffprobe -v error -show_entries format=duration -of default=nk=1:nw=1 kasflow-demo.mp4)
echo "duration: ${DUR}s"
python3 - "$DUR" <<'EOF' || { echo "Duration must be 180–240 s. Re-record with PACE=<factor> (e.g. PACE=1.2 makes pauses longer)."; exit 1; }
import sys
d = float(sys.argv[1])
sys.exit(0 if 180 <= d <= 240 else 1)
EOF
echo "OK: video/kasflow-demo.mp4"
