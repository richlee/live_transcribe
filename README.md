# Live transcription experiment

Local English dictation for a Samsung Series 9 laptop running MX Linux/XFCE.
The current prototype transcribes completed microphone phrases in a terminal
using optimized whisper.cpp, with optional insertion into one bound Writer document.
A small XFCE tray controller provides a global listening shortcut.

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

For direct dictation into LibreOffice, follow [Writer setup and recovery](docs/WRITER.md)
and start with `--writer --no-text`.

For applications-menu launch, **Ctrl+Alt+Space** and tray controls, follow
[desktop setup and usage](docs/DESKTOP.md).

Spoken punctuation, examples and the literal-mode toggle are in the
[command reference](docs/COMMANDS.md).
