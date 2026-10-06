# Handoff

Updated: 2026-10-06.

## Current stage

Stage 1 inspection and stage 2 recorded-speech experiments are documented. Optimized tiny.en now has speed headroom on tested excerpts; the user reports some errors but considers it worth pursuing. A live microphone-to-transcript prototype is the next feasibility test. Setup is in `docs/SETUP.md`, measured findings in `docs/BENCHMARKS.md`. No live application or Writer insertion is implemented.

## Findings and constraints

- Intel i5-2537M: two cores/four threads, AVX without reported AVX2/FMA.
- 3.5 GiB usable RAM; about 835 MiB available at inspection, with some swap already used.
- MX/Debian 13, XFCE on X11; PipeWire with WirePlumber installed.
- Kernel and user-terminal ALSA inventory confirm ALC269VC analog capture. Internal microphone port is active. First recording clipped. User made a second take after a suggested Capture adjustment; it is very quiet but has no clipped samples (peak -15 dBFS). User restored Capture to +30 dB before the later inspection, which showed PipeWire 32% (-30 dB). The earlier inference that the adjustment did not persist was incorrect.
- CMake and FFmpeg are now installed. Writer was not found installed in the inspection.
- Whisper tiny.en takes 19.745 s (2 threads) / 18.217 s (4 threads) for the 11 s public sample, and 43.849 s (4 threads) for the 30.065 s user recording. Slower than real time; base.en comparison deferred. User reports some wrong words but no invented text.
- Whisper source, CPU-native Release build, models and private speech artifacts are under ignored `.local/`. Recorder and benchmark helpers are in `scripts/`.
- Vosk 0.3.45 installed in `.local/venv`; small English model extracted under `.local/`. The same 30.065 s recording takes 12.472 s (RTF 0.415), with peak process RSS 270.9 MiB. User reports too many errors, so it is not acceptable on this recording. Dependencies are pinned in `requirements-vosk.txt`, and `pip check` passes.
- Second 30.011 s take takes 8.535 s with Vosk; a derived +10 dB copy takes 8.498 s. Derived copy is unclipped (peak -5 dBFS), original retained. User reports recognition is still too inaccurate. Amplification boosts noise equally and does not establish better recording quality.
- Further Whisper testing changes the speed conclusion: Q5_0 quantization plus reduced encoder context processes a 5 s public excerpt in 1.203 s (4 threads, context 300), and a 10 s user excerpt in 1.946 s (2 threads, context 600). User reports some errors in the four-thread excerpt but considers it worth pursuing. Full 30.011 s amplified take with Q5_0/default context takes 9.891 s. Original default unquantized timings must not be generalized to these configurations.
- OpenBLAS 0.3.29 separate `build-blas` is built and verified through linkage and backend logs. Ordinary tiny.en processes the public 11 s sample in 5.116 s (2 threads) / 7.346 s (4 threads). Q5_0 with two threads and reduced context takes 1.165 s for a 5 s public excerpt and 1.810 s for a 10 s user excerpt. Original build preserved. Helper accepts build, weights and context, sets thread environment explicitly and rejects context shorter than input; guard and syntax checks pass.
- GitHub authentication works outside the sandbox through the keyring. Git writes/network commands can request escalation; do not conclude the token is invalid from sandbox-only authentication checks.

## Next step

Build stage 3 microphone-to-final-transcript as an experimental validation of the candidate: Q5_0 tiny.en, OpenBLAS, two threads, English greedy decoding and encoder context covering each complete phrase with a margin. Tested contexts: 300 for 5 s, 600 for 10 s. User assessment is qualified (some errors, worth pursuing), not a general accuracy pass. Measure actual pause-to-text delay, queueing, stopping and recoverable private output; never silently truncate audio to fit context. Preserve wording, and save only final recognition. File benchmarks do not establish comfortable phrase latency. Writer insertion and tray controls come later. The user restored original gain before inspection; do not infer mixer failure. Commit/push aggregate findings, never private speech artifacts.
