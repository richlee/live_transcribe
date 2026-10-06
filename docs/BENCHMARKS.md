# Recognition benchmarks

Date: 2026-10-06. Hardware and desktop details: `INSPECTION.md`.
These are single-run feasibility measurements on this laptop, not latency promises.

## Whisper tiny.en

Build: whisper.cpp revision `4afec37b797ab531aaf363208d79d541fbc17ff4`,
CPU-native Release. English greedy decoding, beam size 1, best-of 1.
Wall time includes loading the model, recognition and transcript output.
Peak RSS measures the recognition child process on Linux.

| Audio | Threads | Audio duration | Wall time | Real-time factor | Peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bundled public JFK sample | 2 | 11.000 s | 19.745 s | 1.795 | 148.9 MiB |
| Bundled public JFK sample | 4 | 11.000 s | 18.217 s | 1.656 | 150.7 MiB |
| User natural-speech recording | 4 | 30.065 s | 43.849 s | 1.458 | 170.1 MiB |

The public sample produced the expected spoken words on manual inspection;
this does not measure accuracy on the user's voice. The user reports some
wrong words but no invented text in the natural-speech transcript. No numeric
word-error rate was measured; its transcript remains private in ignored storage.

The user described the recording as clear but quiet, with background machine
noise. Signal inspection found peak 0 dBFS, overall RMS about -11.9 dBFS, and
7,340 samples at absolute amplitude >= 32,767 (about 1.5% of all samples).
This suggests clipping; it does not identify whether speech, noise or another
input-processing effect caused the peaks. Do not simply increase gain based
on perceived quietness. Check the physical input port, capture gain and
microphone boost before another take if recognition quality is poor.

Follow-up inspection confirms the internal microphone port is active; the
external microphone port is unavailable. Hardware Capture is at +30 dB on
both channels, Internal Mic Boost is 0 dB, and the unmuted PipeWire source is
at 44% (-21.43 dB). High hardware gain followed by downstream attenuation is
a plausible explanation for quiet perceived output with clipping, but the
cause is not yet established. Next test: lower hardware capture gain and
measure clipping and recognition on a new recording. No gain changes were
made during this inspection.

## Decision so far

Tiny.en is slower than real time in all three measured runs. On the two-thread
public sample, model loading was about 0.21 seconds and encoding about 17.79
seconds, so retaining the model in memory alone will not resolve that result.
Base.en comparison is deferred because even the smaller model lacks speed
headroom. A faster-than-real-time result is necessary but still would not
establish comfortable live dictation: pause detection, short-phrase processing,
queue growth, stopping and insertion must be tested separately.

## Vosk fallback

Installed Vosk 0.3.45 in a local Python 3.13 virtual environment. Dependencies
are pinned in `requirements-vosk.txt`; `pip check` reports no broken requirements.
The official model listing describes `vosk-model-small-en-us-0.15` as a 40 MB
lightweight English model: https://alphacephei.com/vosk/models .

| Audio | Audio duration | Wall time | Real-time factor | Peak RSS |
| --- | ---: | ---: | ---: | ---: |
| Same user natural-speech recording | 30.065 s | 12.472 s | 0.415 | 270.9 MiB |

Wall time includes Vosk import, model loading, recognition in 250 ms audio
blocks and writing final text. Peak RSS includes the Python interpreter and
Vosk in the same process. No partial recognition is saved as final text.
The run succeeded inside the network-restricted sandbox using the explicit
local model path. The private transcript remains in ignored local storage.

Vosk processed this recording about 3.5 times faster than Whisper's four-thread
run and faster than real time. This supports testing a live microphone-to-final-
transcript prototype if user accuracy feedback is acceptable. It does not
measure pause-to-text delay, capture queue behaviour or stopping latency.
The user reports too many errors in Vosk's transcript. The small model is not
acceptable on this recording despite its speed. Neither tested engine has
passed both speed and user accuracy checks; do not proceed to live integration
yet. Next, verify the selected input port and gain, obtain a clearer recording,
and repeat the comparison. If small Vosk remains inaccurate on improved input,
investigate another recognition configuration before choosing an engine.

## Quieter microphone retest

The user supplied a second recording after the suggested gain adjustment and
reported very quiet playback. Its duration is 30.011 s, peak -15.0 dBFS,
overall RMS -39.9 dBFS, and there are no samples at the digital limit. This
removes the first take's clipping indicator but does not establish good
signal-to-noise ratio or accurate recognition.

Later mixer inspection shows hardware Capture at +30 dB again, with PipeWire
source volume 32% (-30 dB). These are readings after capture, not proof of the
settings used during it. Direct ALSA adjustment did not leave the requested
hardware setting in place; the cause is unverified. Avoid drawing conclusions
about hardware gain from the command alone.

A derived copy was amplified uniformly by 10 dB using FFmpeg `volume=10dB`.
It has peak -5.0 dBFS, RMS -29.9 dBFS and no clipped samples. The original is
preserved. This boosts speech and noise equally, without improving the original
signal-to-noise ratio or restoring information. Both files remain private.

| Audio | Wall time | Real-time factor | Peak RSS |
| --- | ---: | ---: | ---: |
| Second take, unamplified | 8.535 s | 0.284 | 243.6 MiB |
| Same take, +10 dB copy | 8.498 s | 0.283 | 243.4 MiB |

Both runs use the same small English Vosk model and benchmark helper as above.
User accuracy assessment of the retest is pending. No engine has yet passed
both speed and user accuracy checks.
