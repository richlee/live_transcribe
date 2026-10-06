# Handoff

Updated: 2026-10-06.

## Current stage

Stage 1 inspection is documented in `docs/INSPECTION.md` and committed/pushed in checkpoint `46ee448`. Stage 2 is in progress: whisper.cpp builds and runs; the user successfully captured a 30-second microphone recording. Setup is in `docs/SETUP.md`, measured findings in `docs/BENCHMARKS.md`. No live application or Writer insertion is implemented.

## Findings and constraints

- Intel i5-2537M: two cores/four threads, AVX without reported AVX2/FMA.
- 3.5 GiB usable RAM; about 835 MiB available at inspection, with some swap already used.
- MX/Debian 13, XFCE on X11; PipeWire with WirePlumber installed.
- Kernel and user-terminal ALSA inventory confirm ALC269VC analog capture. Default input is Built-in Audio Analog Stereo, at 44% volume in the inspection. User capture works but was described as quiet with machine noise; signal analysis suggests clipping. Selected physical microphone port is unverified.
- CMake and FFmpeg are now installed. Writer was not found installed in the inspection.
- Whisper tiny.en takes 19.745 s (2 threads) / 18.217 s (4 threads) for the 11 s public sample, and 43.849 s (4 threads) for the 30.065 s user recording. Slower than real time; base.en comparison deferred. User reports some wrong words but no invented text.
- Whisper source, CPU-native Release build, models and private speech artifacts are under ignored `.local/`. Recorder and benchmark helpers are in `scripts/`.
- Vosk 0.3.45 installed in `.local/venv`; small English model extracted under `.local/`. The same 30.065 s recording takes 12.472 s (RTF 0.415), with peak process RSS 270.9 MiB. User reports too many errors, so it is not acceptable on this recording. Dependencies are pinned in `requirements-vosk.txt`, and `pip check` passes.
- GitHub authentication works outside the sandbox through the keyring. Git writes/network commands can request escalation; do not conclude the token is invalid from sandbox-only authentication checks.

## Next step

Neither engine has passed both speed and accuracy checks. Inspect the selected microphone port and gain from the user's desktop terminal, then arrange a clearer speech recording and repeat recognition before selecting an engine. If small Vosk remains inaccurate, investigate another recognition configuration. Do not build live integration yet. File benchmark speed alone does not establish comfortable phrase latency. Safe Writer insertion and tray controls come later. Commit/push aggregate findings, never private speech artifacts.
