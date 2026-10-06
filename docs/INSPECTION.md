# Hardware and audio inspection

Inspected on 2026-10-06. No audio was recorded.

## Findings

- CPU: Intel Core i5-2537M, 1.40 GHz nominal / 2.30 GHz maximum, two physical cores and four hardware threads. Supports AVX, but the reported flags do not include AVX2 or FMA. Build the recognition engine for this CPU rather than assuming modern instruction support.
- Memory: 3.5 GiB usable; approximately 835 MiB available at inspection. Swap: 2.0 GiB total, 513 MiB used. These are a snapshot, not a stable resource budget.
- Storage: approximately 96 GiB free on the project filesystem.
- OS: MX 25.3 Infinity on Debian 13 (trixie); kernel `6.12.111+deb13-amd64`.
- Desktop: XFCE, X11 (`XDG_SESSION_TYPE=x11`). `xdotool` and `xclip` are available for later insertion experiments. Their operation and Writer focus handling have not been tested.
- Audio: PipeWire 1.4.5, `pipewire-pulse`, `pipewire-alsa`, and WirePlumber 0.5.10 are installed. Desktop PipeWire and Pulse-compatible socket files exist.
- Kernel audio inventory: HDA Intel PCH with ALC269VC Analog, one capture device and one analog playback device; HDMI playback is also present. This does not establish which physical microphone is selected or whether it works.
- Available tools: GCC, G++, Python 3, Git, Make, `arecord`, `parec`, `pactl`, and `wpctl`.
- CMake, FFmpeg, and LibreOffice Writer were not found as installed packages or executable commands in this inspection. Confirm Writer availability before the insertion stage.

## Audio access limitation

User-supplied `pactl info` from the ordinary desktop terminal confirms that the local Pulse-compatible server is running on PipeWire 1.4.5 and the default source is analog input rather than a playback monitor. The server's default sample specification is float32, stereo, 48 kHz; this does not establish the microphone's native format or the format required for transcription. Physical microphone selection, mute state, input volume, and successful capture remain unverified. User and host identifiers, cookie, and machine-specific source paths are intentionally omitted here.

User-supplied `pactl list short sources` lists one analog input and one analog-output monitor, both reporting signed 32-bit little-endian stereo at 48 kHz and `SUSPENDED` at inspection. This is consistent with idle sources; it is not evidence of successful capture or an audio fault. No additional input sources appear in that snapshot.

User-supplied `wpctl status` confirms WirePlumber is connected and Built-in Audio Analog Stereo is the default input, with reported volume 0.44 (44%) and no mute marker shown. No active microphone capture stream appears in the snapshot. The analog source label does not distinguish an internal microphone from a microphone jack; the selected port and actual capture still need verification. Unrelated client and video-device details are omitted.

User-supplied desktop `arecord -l` confirms ALSA exposes one capture device: HDA Intel PCH / ALC269VC Analog, with one available subdevice out of one. This resolves the misleading "no soundcards" result from the restricted agent session. Successful speech capture remains untested.

The restricted agent session has no `/dev/snd` directory and cannot connect to desktop audio/session-bus sockets. Consequently `arecord -l` reports no soundcards in this session, while `/proc/asound/cards` and `/proc/asound/pcm` show the kernel device above. `pactl` and `wpctl` connection failures do not establish that the desktop audio service is broken.

Run these read-only commands in an ordinary terminal on the laptop to identify the active input:

```bash
pactl info
pactl list short sources
wpctl status
arecord -l
```

Share the audio device/source portions of the output; server usernames and hostnames can be omitted. In `wpctl status`, check the audio Sources section and the default source marker. Pulse sources ending in `.monitor` capture playback rather than a microphone.

## Reproducing the inspection

```bash
lscpu
free -h
cat /etc/os-release /etc/mx-version
uname -r
df -h .
printf 'Session: %s; desktop: %s\n' "$XDG_SESSION_TYPE" "$XDG_CURRENT_DESKTOP"
cat /proc/asound/cards /proc/asound/pcm
```

## Next stage

Confirm the microphone inventory from the desktop terminal, then follow current official `whisper.cpp` setup instructions and benchmark `tiny.en` with user-approved short speech capture. Compare `base.en` only if resources and measured speed justify it. No recognition speed, accuracy, or live-dictation latency has yet been measured.
