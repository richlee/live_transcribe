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
- Whisper tiny.en takes 19.745 s (2 threads) / 18.217 s (4 threads) for the 11 s public sample, and 43.849 s (4 threads) for the 30.065 s user recording. Slower than real time; base.en comparison deferred. User accuracy feedback is pending.
- Whisper source, CPU-native Release build, models and private speech artifacts are under ignored `.local/`. Recorder and benchmark helpers are in `scripts/`.
- Small English Vosk model downloaded and extracted under `.local/`. Vosk Python installation and benchmarking pending `python3-venv` installation by the user.
- GitHub authentication works outside the sandbox through the keyring. Git writes/network commands can request escalation; do not conclude the token is invalid from sandbox-only authentication checks.

## Next step

After the user installs `python3-venv`, create `.local/venv`, install Vosk there, and benchmark the same local recording using `scripts/benchmark-vosk.py`. Get user accuracy feedback on the local final transcripts. Check input port/gain if quality is poor. Choose an engine only after speed and accuracy support proceeding. Commit/push benchmark tools and aggregate findings, never private speech artifacts. Then build the microphone-to-transcript prototype before safe Writer insertion and tray controls.
