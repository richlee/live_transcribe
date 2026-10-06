# Live transcription experiment

Local English dictation for a Samsung Series 9 laptop running MX Linux/XFCE.
The current prototype transcribes completed microphone phrases in a terminal
using optimized whisper.cpp. Writer insertion and tray controls come later.

After following [setup instructions](docs/SETUP.md), start from this directory:

```bash
.local/venv/bin/python -m pip install -r requirements-live.txt
.local/venv/bin/python -m live_transcribe
```

Type `p` + Enter to pause/resume, or `q` + Enter to stop and finish queued
phrases. Final text and recoverable audio are saved privately under ignored
`.local/sessions/`. See [prototype instructions](docs/PROTOTYPE.md) for recovery,
limitations and verification; [benchmarks](docs/BENCHMARKS.md) for measurements;
and [handoff](HANDOFF.md) for current status.
