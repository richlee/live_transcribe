## Purpose and hardware

This is a dedicated writing machine: an old Samsung NP900X Series 9, Intel Core i5, 4 GB RAM, running MX Linux with XFCE. LibreOffice Writer is the primary application.

The app should recognise microphone speech locally and insert completed phrases at the cursor in Writer. The finished app must work without Codex, Ollama, cloud APIs or an internet connection after installation and model downloads.

Assume English dictation initially.

## Start by proving feasibility

Inspect the actual CPU, available memory, Linux version, desktop session type, audio system and microphone devices. Report relevant findings without exposing credentials or unrelated personal files.

Set up `whisper.cpp` using its current official instructions. Start with `tiny.en`, then compare `base.en` if practical. Keep model files, build outputs, recordings and machine-specific configuration out of Git.

Arrange a short microphone recording test with the user. Measure transcription time against recording duration and assess accuracy using the user's natural speech. Explain that processing faster than the recording's duration is necessary but does not alone guarantee comfortable live dictation.

Do not promise a particular latency before measuring it. If Whisper cannot keep up comfortably, investigate a small English Vosk model as a fallback.

Save reproducible setup instructions and benchmark findings in the repository. Do not commit personal recordings or dictated content.

## Build the smallest useful prototype

Once recognition is viable, implement:

- A keyboard shortcut to toggle listening.
- A clear listening, processing and paused indicator.
- Recognition of short phrases ending at natural pauses.
- Insertion of final text at the cursor in LibreOffice Writer.
- Basic “new line” and “new paragraph” commands.
- Pausing or withholding insertion when Writer loses focus.
- A local recoverable transcript so failed insertion does not lose speech.

Keep provisional recognition out of the document. Avoid duplicate text when audio chunks overlap. Never send unfinished queued text into a different window.

Confirm whether the desktop uses X11 or Wayland before selecting the input mechanism. Test ordinary text, punctuation, apostrophes and paragraph breaks in a disposable Writer document. If clipboard insertion is used, handle clipboard preservation carefully and document limitations.

Use a lightweight implementation suited to 4 GB RAM. Prefer existing speech engines and desktop facilities. Avoid a browser-based interface or large application framework unless evidence justifies it.

Do not automatically rewrite prose with an LLM. Preserve the speaker's wording.

## Progress and verification

Proceed in small working stages:
1. Hardware and audio inspection.
2. Recorded-speech benchmark.
3. Microphone-to-transcript prototype.
4. Safe insertion into Writer.
5. Shortcut and tray interface.

Ask for user participation when speech recording or usability feedback is needed. Continue independent work while waiting where possible.

Verify the important behaviour on this laptop: microphone capture, processing speed, text insertion, focus changes, stopping dictation and recovery after errors. Add automated tests only where they meaningfully protect text handling or state transitions.

Provide clear install, start, stop and troubleshooting instructions. Keep a concise `HANDOFF.md` recording what works, benchmark results, outstanding issues and the next step so another Codex session can continue.

Use Git checkpoints for completed stages. Never overwrite unrelated changes, commit secrets or private transcripts, or force-push. Push completed work to the repository's configured GitHub remote when a stage is verified; use the existing branch or the repository's established workflow.

Start with inspection and the speech benchmark before building the full tray app.