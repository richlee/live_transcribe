# Microphone-to-transcript prototype

This is stage 3: final phrase transcription in a desktop terminal. It does not
insert into Writer, use the clipboard, or install a shortcut, tray icon or daemon.
Recognition uses local Q5_0 tiny.en, the OpenBLAS build, two threads and English
greedy decoding. See `SETUP.md` for the engine/model build.

## Install and start

From the project directory:

```bash
.local/venv/bin/python -m pip install -r requirements-live.txt
.local/venv/bin/python -m live_transcribe
```

Run in the ordinary desktop terminal when ready to speak. Capture starts when
`LISTENING` appears, using the default PipeWire/Pulse microphone at mono 16 kHz
signed 16-bit PCM. No input-volume settings are changed. Session path is printed
first. Speak in short phrases and pause for about a second between them.

WebRTC VAD mode 2 detects speech. After approximately 750 ms classified as
non-speech, a phrase is saved and queued. Recognition proceeds while capture
continues. `PROCESSING` and `FINAL` refer to the recognizer; the microphone
continues listening until a `PAUSED`, `STOPPING`, `BACKLOG` or error message.
Only final text appears, after recognition completes. No provisional text is
written to the transcript. Words are not automatically rewritten by an LLM.

## Pause and stop

- Type `p`, then Enter, to pause capture. The current phrase is saved and queued;
  already queued recognition finishes. Type `p`, then Enter, again to resume.
- Type `q`, then Enter, or press Ctrl+C once to stop capture, save the current
  phrase and finish queued recognition. Wait for `STOPPED`.
- Press Ctrl+C again while stopping to cancel recognition promptly. Saved
  unfinished audio remains pending for recovery. The exit code is 1 if any
  phrases remain unfinished or capture/recognition failed.

The controls apply in the terminal running this command. There is no global
keyboard shortcut yet. EOF on terminal input also stops capture.

## Files and recovery

Each run creates a private directory under `.local/sessions/` (ignored by Git).
It contains phrase WAVs, numbered JSON records, per-attempt engine logs/text,
capture log, settings and a recoverable `transcript.txt`. Permissions are private
to the user when created by this command. These files contain dictated content;
do not commit or publish them. Delete them using the file manager when no
longer needed.

The numbered records are authoritative: complete records contain final text;
pending/processing/failed records identify retained audio. The transcript is
rebuilt atomically in phrase order, so retrying does not append completed text
again. Session locking prevents two processes from recovering the same session
concurrently. Recognition errors stop capture and preserve saved audio.

After correcting an engine error or interruption, replace `session-EXAMPLE`
with the path printed by the original run:

```bash
.local/venv/bin/python -m live_transcribe --recover .local/sessions/session-EXAMPLE
```

Recovery does not open the microphone. It retries unfinished records, skips
completed ones and rebuilds the transcript. An empty final result is completed
but flagged for review; its audio is retained and can be inspected/benchmarked
separately. Recovery cannot invent speech discarded by the VAD before phrase
onset, nor restore an in-memory unfinished phrase after power loss or SIGKILL.
Graceful stop and handled errors flush detected speech; hard interruption may
lose up to the current phrase length. A WAV saved immediately before a hard
crash but without its JSON record is not automatically recovered.

## Tuning and limits

```bash
.local/venv/bin/python -m live_transcribe --pause-ms 1000 --vad-mode 1
```

Mode 1 is more sensitive than mode 2; it may retain quiet speech more readily
but also classify more noise as speech. Mode 3 rejects noise more aggressively
and may miss words. These are experimental settings; review recognition on
this microphone rather than assuming a mode is accurate.

Default phrase limit is 15 seconds (configurable from 2 to 25 with
`--max-seconds`). Continuous speech is split at the limit without overlapping
audio; a split can cut a word, so natural pauses are preferable. Maximum phrase
length bounds memory use. Encoder context covers the whole phrase plus about
a second of margin, rounded up, with at least the tested six-second context
and at most 30 seconds. Audio is never silently shortened to fit context.

One worker serializes recognition, avoiding competing Whisper processes. If
eight phrases accumulate waiting for recognition, capture stops with a backlog
message and retains pending audio. Recovery can finish it later. Captured audio
already delivered to the pipe is drained during normal stop; device/server
buffering and abrupt capture failure can still lose a small undelivered tail.

VAD may miss quiet speech or react to machine noise. Whisper may produce wrong
words or hallucinate. Non-overlapping chunks prevent duplicate audio submission;
they do not guarantee the model never repeats a word. Gain and signal-to-noise
ratio remain important. This version does not normalize or denoise live audio.

## Replay, timing and verification

Replay never opens the microphone:

```bash
.local/venv/bin/python -m live_transcribe \
  --replay .local/whisper.cpp/samples/jfk.wav --realtime
.local/venv/bin/python -m unittest discover -s tests -v
```

Use `--no-text` to print statuses/timing without printing private recognized text.
Without `--realtime`, replay feeds frames as fast as possible and can create an
artificial backlog. Replay uses the same segmentation and recognition path;
the final partial PCM frame is zero-padded to 30 ms.

Records include recognition time, queue wait, and an estimated pause-to-final
time for naturally ended phrases. The estimate combines VAD-classified silence,
queue wait and recognition time; it excludes audio service buffering and the
VAD's own delay in classifying the real end of speech. It is not a measured
end-to-end microphone latency. Stop/forced-split phrases have no pause estimate.
Recovery queue timings refer to the new retry, not the original session delay.

Checked here: segmentation, silence, forced splits, short speech at stop,
synthetic capture pause/resume/stop, context coverage, engine failure/retry,
active cancellation, completed-output idempotence and session locking. Real
Whisper replay succeeds on public and existing user recordings. The first
user-started microphone session completed eight segments without engine errors;
two were empty results. The user reports pause/resume worked, final text is
accurate enough and delay is acceptable. Stopping saved the final detected
speech, and retrying this completed live session preserved its transcript
exactly without re-recognizing completed phrases. This verifies the current
stage 3 experiment; wider accuracy and long-session testing remain useful.

If capture fails, check `capture.log`, `pactl list short sources` and mute/input
settings. Specify a source with `--source SOURCE_NAME` if necessary. Avoid
playback-monitor sources. If no speech is detected, try mode 1 and check that
the microphone level is audible. If recognition fails, inspect the numbered
attempt log, check the local model/build, and recover the stopped session.
