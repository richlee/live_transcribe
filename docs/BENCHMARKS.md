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

## Initial decision before optimization

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

Later mixer inspection shows hardware Capture at +30 dB, with PipeWire source
volume 32% (-30 dB). The user confirms they had already restored Capture to
+30 dB before that inspection. These readings do not establish the settings
during capture, and do not indicate a failed or overridden gain adjustment.
The earlier inference that ALSA adjustment did not persist was incorrect.

A derived copy was amplified uniformly by 10 dB using FFmpeg `volume=10dB`.
It has peak -5.0 dBFS, RMS -29.9 dBFS and no clipped samples. The original is
preserved. This boosts speech and noise equally, without improving the original
signal-to-noise ratio or restoring information. Both files remain private.

| Audio | Wall time | Real-time factor | Peak RSS |
| --- | ---: | ---: | ---: |
| Second take, unamplified | 8.535 s | 0.284 | 243.6 MiB |
| Same take, +10 dB copy | 8.498 s | 0.283 | 243.4 MiB |

Both runs use the same small English Vosk model and benchmark helper as above.
The user reports that recognition is still too inaccurate on the amplified,
unclipped take. Small Vosk therefore remains unsuitable on the tested input;
removing the clipping indicator and raising playback level did not make its
recognition acceptable. This does not prove microphone quality is otherwise
ideal. At this stage no engine had passed both speed and user accuracy checks. Further
recognition configurations should be evaluated before live integration.

## Whisper context and quantization experiments

The original rejection applied to the default unquantized configuration. It
does not establish that every tiny.en configuration is too slow. Engine logs
for the first 30.065 s recording show two encoder passes at about 18 s each,
accounting for 36.06 s of the 43.85 s run; model loading was only 0.11 s.
Short-phrase performance must be measured independently.

The following runs use the original CPU-native build, English greedy decoding
and default-enabled flash attention. The updated helper sets OpenMP and
OpenBLAS thread environment variables explicitly to the requested count.
Context 0 uses the model's default; 300, 500 and 600 correspond to six, ten
and twelve seconds of encoder context respectively. No context is shorter
than its input. Quantized Q5_0 weights were generated locally from tiny.en.

| Audio | Weights | Threads | Context | Wall time | Peak RSS |
| --- | --- | ---: | ---: | ---: | ---: |
| Public sample, first 5 s | Original | 4 | Default | 16.888 s | 146.8 MiB |
| Same 5 s | Original | 4 | 500 | 5.907 s | 124.9 MiB |
| Same 5 s | Original | 4 | 300 | 3.790 s | 122.5 MiB |
| Same 5 s | Q5_0 | 4 | 300 | 1.203 s | 87.0 MiB |
| Full 11 s public sample | Q5_0 | 2 | Default | 4.441 s | 99.7 MiB |
| Full 11 s public sample | Q5_0 | 4 | Default | 6.147 s | 99.8 MiB |
| Clearer amplified take, first 10 s | Q5_0 | 4 | 600 | 2.149 s | 90.2 MiB |
| Same 10 s | Q5_0 | 2 | 600 | 1.946 s | 90.1 MiB |
| Full clearer amplified take, 30.011 s | Q5_0 | 4 | Default | 9.891 s | 122.7 MiB |

All five-second public runs produced the same spoken words, with a terminal
punctuation difference in the quantized result. Both quantized full public
sample runs reproduced the words in the original transcript. This is a small
sample, not an accuracy guarantee. The user reports some errors in the
ten-second quantized private excerpt but considers it worth pursuing.
An excerpt may cut off speech mid-phrase; assess only
audible words. Quantization and reduced context can change recognition.

The five-second latency fell substantially with Q5_0 plus reduced context.
Two threads outperformed four on the full quantized public sample and slightly
on the ten-second user excerpt, consistent with testing the two physical cores
rather than assuming four hardware threads are faster. These are single runs,
not a controlled distribution; differences in background load may contribute.
All timings include fresh model loading, and none measure live capture,
pause-to-output delay, queueing or insertion. Accuracy remains the gate for
proceeding.

## OpenBLAS comparison and candidate configuration

The separate CPU-native Release build uses OpenBLAS 0.3.29 with the OpenBLAS
vendor selected explicitly. CMake found the library, `ldd` confirms linkage,
and engine logs confirm the BLAS backend is selected. Compilation finished
before timed runs. Original build and weights remain available for comparison.

| Audio | Weights | Threads | Context | OpenBLAS wall time | Peak RSS |
| --- | --- | ---: | ---: | ---: | ---: |
| Full 11 s public sample | Original | 2 | Default | 5.116 s | 158.1 MiB |
| Full 11 s public sample | Original | 4 | Default | 7.346 s | 158.7 MiB |
| User excerpt, 10 s | Original | 2 | 600 | 2.609 s | 145.8 MiB |
| Same 10 s | Q5_0 | 2 | 600 | 1.810 s | 99.2 MiB |
| Public excerpt, 5 s | Q5_0 | 2 | 300 | 1.165 s | 94.0 MiB |

OpenBLAS improves the ordinary model substantially on the public sample,
especially with two threads. The smaller Q5_0 ten-second difference with
OpenBLAS (1.810 vs 1.946 s) is too small to establish a robust improvement from
single runs. On that private excerpt, Q5_0 with/without OpenBLAS and ordinary
weights with OpenBLAS produced identical text; Q5_0 two/four-thread outputs
were identical too. The user reports some errors but considers this recognition
worth pursuing. This is qualified encouragement, not a general accuracy pass.

Candidate for stage 3: tiny.en Q5_0, OpenBLAS build, two threads, English
greedy decoding, default-enabled flash attention, encoder context covering
the entire phrase with a margin (tested at 300 for 5 s and 600 for 10 s).
Do not silently discard audio to fit context. Ordinary weights with OpenBLAS
are an available accuracy comparison, although this excerpt showed no text
difference. Before selecting a final configuration, measure real microphone
pause-to-final-text delay, output accuracy, queue behaviour, stopping and error
recovery. No Writer insertion or tray application has been implemented yet.

## Stage 3 microphone-to-transcript verification

The terminal prototype uses WebRTC VAD mode 2, a 750 ms natural pause, 15 s
phrase cap, Q5_0/OpenBLAS/two-thread recognition and a minimum encoder context
of 300. Thirteen tests pass, including synthetic capture pause/resume/stop,
non-overlap, short speech on stop, cancellation, failure/retry, duplicate-free
recovery and locking. Public replay plus existing user-recording replay run
through the actual engine, with capture and recognition progressing concurrently.

The first user-started live microphone session produced eight completed segments:
six ended at natural pauses, one at manual pause and one at stop. No engine
errors were recorded and the capture log was empty. Recognition times were
0.758–1.160 s and queue waits 0.007–0.028 s. Two segments produced empty text;
their audio remains private for review. The user reports pause/resume worked,
final text is accurate enough and delay is acceptable. Stopping saved the last
detected speech, and recovery of this completed session left the transcript
byte-for-byte unchanged, skipping recognition of completed records.

Estimated pause-to-final times for naturally ended segments were 1.516–1.918 s.
These combine VAD-classified silence, queue wait and recognition; they exclude
audio-service buffering and VAD's delay in detecting the real speech endpoint.
They are not measured end-to-end user-perceived latency. Session contents and
recordings are not committed. Instructions and limitations: `PROTOTYPE.md`.
