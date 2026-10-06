#!/usr/bin/env bash
# Run explicitly from the desktop terminal when ready to speak.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
umask 077
mkdir -p .local/recordings
recording=$(mktemp .local/recordings/speech-XXXXXX.wav)
printf 'Recording the default microphone for 30 seconds. Speak naturally now.\n'
if ! ffmpeg -hide_banner -nostdin -loglevel warning -y \
    -f pulse -i default -t 30 -ar 16000 -ac 1 -c:a pcm_s16le "$recording"; then
    printf 'Capture failed; the file may be incomplete: %s\n' "$recording" >&2
    exit 1
fi
printf 'Saved locally: %s\nListen back with: paplay %q\n' "$recording" "$recording"
