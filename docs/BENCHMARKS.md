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
this does not measure accuracy on the user's voice. User-speech accuracy
feedback is pending; its transcript remains private in ignored local storage.

The user described the recording as clear but quiet, with background machine
noise. Signal inspection found peak 0 dBFS, overall RMS about -11.9 dBFS, and
7,340 samples at absolute amplitude >= 32,767 (about 1.5% of all samples).
This suggests clipping; it does not identify whether speech, noise or another
input-processing effect caused the peaks. Do not simply increase gain based
on perceived quietness. Check the physical input port, capture gain and
microphone boost before another take if recognition quality is poor.

## Decision so far

Tiny.en is slower than real time in all three measured runs. On the two-thread
public sample, model loading was about 0.21 seconds and encoding about 17.79
seconds, so retaining the model in memory alone will not resolve that result.
Base.en comparison is deferred because even the smaller model lacks speed
headroom. A faster-than-real-time result is necessary but still would not
establish comfortable live dictation: pause detection, short-phrase processing,
queue growth, stopping and insertion must be tested separately.

Investigate `vosk-model-small-en-us-0.15` next. Its official model listing
describes it as a 40 MB lightweight English model:
https://alphacephei.com/vosk/models . Benchmark the same recording and get
user accuracy feedback before choosing an engine or implementing the tray UI.
