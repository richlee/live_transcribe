# Speech benchmark setup

For the current desktop application, start with [desktop setup](DESKTOP.md).
This page retains the individual engine setup and benchmark commands.
Upstream instructions: https://github.com/ggml-org/whisper.cpp#quick-start

## Install and build

Run from the project directory. The `.local/` directory is ignored by Git.

```bash
sudo apt-get install cmake ffmpeg
mkdir -p .local
git clone https://github.com/ggml-org/whisper.cpp.git .local/whisper.cpp
git -C .local/whisper.cpp checkout 4afec37b797ab531aaf363208d79d541fbc17ff4
cmake -S .local/whisper.cpp -B .local/whisper.cpp/build \
  -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON \
  -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_SERVER=OFF
cmake --build .local/whisper.cpp/build --target whisper-cli -j 1 --config Release
sh .local/whisper.cpp/models/download-ggml-model.sh tiny.en
```

The revision above was inspected on 2026-10-06 and identifies itself as
1.9.4-dev. CPU-native compilation selects instructions for this laptop;
rebuild on another CPU rather than copying this binary. One build job limits
memory pressure. GCC 14.2, CMake 3.31.6 and FFmpeg 7.1.5 are installed here.

Downloaded `tiny.en` SHA-256:
`921e4cf8686fdd993dcd081a5da5b6c365bfde1162e72b08d75ac75289920b1f`.
This records the downloaded artifact, not an independently verified upstream
checksum. A failed/interrupted download may leave a partial model file that
upstream's script skips on retry; move that file aside before retrying.

## Public sample check

```bash
python3 scripts/benchmark.py .local/whisper.cpp/samples/jfk.wav --threads 2
python3 scripts/benchmark.py .local/whisper.cpp/samples/jfk.wav --threads 4
```

This checks the build and gives a preliminary speed measurement; it does not
establish microphone quality or accuracy on the user's natural speech.

## Record and benchmark natural speech

Run from the normal XFCE desktop terminal, when ready to speak:

```bash
bash scripts/record-speech.sh
```

The script captures 30 seconds from the default PipeWire/Pulse source. It
prints the unique local filename and a `paplay` command to listen back.
Speak naturally and confirm your voice is audible without strong distortion
or background noise. Capture is resampled to mono, 16-bit PCM at 16 kHz.
It does not change input volume or mute settings. Check those in the desktop
audio controls if capture is quiet or silent. Use Ctrl+C to stop early;
an interrupted recording is reported as a capture failure and may be incomplete.

Benchmark the actual filename printed by the recorder:

```bash
python3 scripts/benchmark.py .local/recordings/speech-XXXXXX.wav --threads 2
```

Each invocation saves a transcript, engine log and aggregate metrics in a
new `.local/benchmarks/` directory. Read the transcript locally and assess
substitutions, omissions and unwanted additions against what you said. Do
not commit or paste private dictated content into shared benchmark notes.

The helper uses English greedy decoding (`beam-size=1`, `best-of=1`) to
establish a lightweight baseline. Wall time includes model loading and
transcript writing. Peak RSS is the child process's maximum resident memory
on Linux, not total system memory or swap use. A real-time factor below 1
means the process finished faster than the audio duration; comfortable live
dictation also depends on pause detection, phrase length, queueing and
insertion latency. Repeated file runs do not model a persistent live engine.

If practical, compare the same recording with `base.en`:

```bash
sh .local/whisper.cpp/models/download-ggml-model.sh base.en
python3 scripts/benchmark.py .local/recordings/speech-XXXXXX.wav --model base.en --threads 2
```

## Vosk fallback comparison

Whisper's initial unquantized, non-BLAS measurements lacked speed headroom.
Later optimization measurements are documented in `BENCHMARKS.md`.
Prepare an isolated Vosk environment and the official small English model:

```bash
sudo apt-get install python3-venv
python3 -m venv .local/venv
.local/venv/bin/python -m pip install -r requirements-vosk.txt
curl -fL --retry 3 -o .local/vosk-model-small-en-us-0.15.zip \
  https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
python3 -m zipfile -e .local/vosk-model-small-en-us-0.15.zip .local
.local/venv/bin/python scripts/benchmark-vosk.py .local/recordings/speech-XXXXXX.wav
```

Recorded archive SHA-256:
`30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498`.
The script uses the explicit local model path and performs no model downloads.
It processes audio in 250 ms blocks, saves only final recognition results,
and includes import/model loading in wall time. Peak RSS includes Python and
Vosk in the same process. It measures file processing, not real-time endpoint
latency. Review the local transcript for accuracy; the small model may omit
punctuation and casing.

## Experimental Whisper optimization

Keep the original CPU build for comparison. Build a separate OpenBLAS version:

```bash
sudo apt-get install libopenblas-dev pkg-config
cmake -S .local/whisper.cpp -B .local/whisper.cpp/build-blas \
  -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DGGML_BLAS=ON \
  -DGGML_BLAS_VENDOR=OpenBLAS -DWHISPER_BUILD_TESTS=OFF \
  -DWHISPER_BUILD_SERVER=OFF
cmake --build .local/whisper.cpp/build-blas --target whisper-cli -j 1 --config Release
python3 scripts/benchmark.py .local/whisper.cpp/samples/jfk.wav --build build-blas --threads 2
python3 scripts/benchmark.py .local/whisper.cpp/samples/jfk.wav --build build-blas --threads 4
```

Create Q5_0 weights locally from the existing English tiny model:

```bash
cmake --build .local/whisper.cpp/build --target whisper-quantize -j 1 --config Release
.local/whisper.cpp/build/bin/whisper-quantize \
  .local/whisper.cpp/models/ggml-tiny.en.bin \
  .local/whisper.cpp/models/ggml-tiny.en-q5_0.bin q5_0
python3 scripts/benchmark.py .local/whisper.cpp/samples/jfk.wav --model tiny.en-q5_0 --threads 2
```

Q5_0 artifact SHA-256:
`3d11806c1fec19226f210c5286f58ef8c0e883c8b1f6a8a9c695c3b1fee35ce8`.
This is a reproducibility record for the locally generated file.

Current candidate: Q5_0, OpenBLAS, two threads, reduced context covering the
whole phrase. For a ten-second clip (replace the placeholder with its path):

```bash
python3 scripts/benchmark.py .local/recordings/ten-second-clip.wav \
  --model tiny.en-q5_0 --build build-blas --threads 2 --audio-ctx 600
```

For short clips, experimentally reduce encoder context. Units correspond to
50 encoder positions per second: 300 covers six seconds, 600 covers twelve.
The benchmark helper rejects a context shorter than the entire input, avoiding
unmeasured audio loss. Context reduction changes inference and requires accuracy
review; matching a single public sample is insufficient.

```bash
ffmpeg -hide_banner -nostdin -n -i .local/whisper.cpp/samples/jfk.wav \
  -t 5 -ar 16000 -ac 1 -c:a pcm_s16le .local/jfk-5s.wav
python3 scripts/benchmark.py .local/jfk-5s.wav --threads 4
python3 scripts/benchmark.py .local/jfk-5s.wav --threads 4 --audio-ctx 300
python3 scripts/benchmark.py .local/jfk-5s.wav --threads 4 --audio-ctx 300 --model tiny.en-q5_0
```

The helper sets both `OPENBLAS_NUM_THREADS` and `OMP_NUM_THREADS` to the
requested thread count and records them in metrics. Flash attention remains
enabled by the pinned engine's default. Compare models/builds sequentially,
without compilation running alongside timed recognition. Review private
transcripts locally; models, excerpts and logs remain ignored.

## Stop, privacy and troubleshooting

The benchmark recorder installs no daemon. Its capture ends after 30 seconds;
recognition ends when the CLI exits. Ctrl+C stops a running command. The
download/build needs network access; recognition and recording run locally
after setup. Recordings, transcripts, models and build outputs stay in
ignored local storage. Delete recordings and transcripts through the file
manager when no longer needed.

Agent sandbox failures connecting to audio services do not imply desktop
audio is broken. Run capture in the ordinary desktop terminal. If recognition
fails, inspect the local `engine.log`; if it reports an illegal instruction,
check the CPU-native build rather than enabling AVX2/FMA on this CPU. Writer
setup and insertion are documented in [Writer instructions](WRITER.md).
