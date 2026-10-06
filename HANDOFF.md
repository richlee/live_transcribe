# Handoff

Updated: 2026-10-06.

## Current stage

Stages 1–3 are verified for the current experiment. The terminal microphone-to-transcript prototype is in `live_transcribe/`. Thirteen automated tests pass, including synthetic capture controls, error/retry and cancellation. Actual Whisper replay and live microphone capture succeed. The user reports pause/resume worked, final text is accurate enough and delay is acceptable. Stopping saved the last phrase, and recovery of the completed live session leaves the transcript unchanged. Start/stop/recovery are in `docs/PROTOTYPE.md`. No Writer insertion, global shortcut or tray is implemented.

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
- Prototype uses `parec` capture, WebRTC VAD 2.0.14, 750 ms pause, 15 s maximum non-overlapping phrases, one recognition worker and private durable per-phrase records. Context covers phrase plus margin, minimum 300, maximum 1500. Pause/resume and graceful stop flush detected speech; a second Ctrl+C cancels recognition while preserving saved pending audio. Recovery skips completed output and atomically rebuilds the transcript.
- Real-time-paced quiet user-recording replay yielded five segments, one empty final result and one forced 15 s split. Most recognition times 0.47–2.27 s, longest 4.39 s; negligible queue waits. This was before raising minimum context to 300. Afterwards a 5 s public replay completed in 1.06 s. These are replay measurements, not actual microphone latency or accuracy validation. Private session artifacts stay ignored.
- First user-started live microphone session: eight completed segments (six natural pauses, one manual pause, one stop), no engine errors, empty capture log. Recognition 0.758–1.160 s, queue waits 0.007–0.028 s. Two empty text results retained for review; user considers the final transcript accurate enough. Estimated pause-to-final times 1.516–1.918 s exclude capture buffering and VAD end-detection delay. User reports acceptable delay and working pause/resume. Completed-session recovery preserves transcript bytes exactly; private content was not printed in verification.

## Next step

Proceed to stage 4 safe Writer insertion when requested. Confirm/install Writer (not found during initial inspection), use the confirmed X11 session, and test ordinary text, punctuation, apostrophes and paragraph breaks in a disposable document. Withhold insertion when Writer loses focus, retain pending final text for recovery, and never send queued text to another window. Add new line/new paragraph commands without rewriting prose. Keep clipboard preservation explicit if clipboard insertion is chosen. Global shortcut/tray are stage 5. Preserve the verified terminal path and its local recovery. Never commit private session content.
