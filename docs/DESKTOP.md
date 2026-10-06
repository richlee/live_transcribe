# Desktop dictation on this laptop

Launch **Live Transcribe** from XFCE's applications menu. It starts a small tray controller with the microphone **off**. Nothing downloads during normal use. The source checkout, local engine, model and venv remain in this project directory; this is a local installation, not a portable binary package.

## Everyday controls

- **Ctrl+Alt+Space**: start a session, then toggle listening on/off.
- **Left click the tray icon**: the same toggle.
- **Right click**: pause/resume, stop and finish queued speech, open the latest session folder, instructions, or quit.

Open the Writer document you want to continue working in first. On the first toggle, the app enables the local UNO connection without creating another document. Click your existing Writer document when the crosshair appears. Capture stays off during selection; after successful binding the selected window is activated and listening starts. Later shortcut presses leave focus alone and affect only microphone capture. Each new session asks you to select a document again.

Pause flushes any speech already captured and lets recognition/insertion finish. Use the global shortcut while still in Writer to avoid withholding that final phrase. **Stop session — keep tray running** drains saved phrases and returns the tray to Ready. **Quit app — remove tray icon** drains saved phrases and closes the app, so its icon disappears. Relaunch Live Transcribe from the applications menu to bring it back. Starting again creates a new session; it does not deliver held text from an earlier session.

## Indicator

| Symbol/color | Meaning |
| --- | --- |
| Gray dot | Ready; microphone off |
| Gray crosshair | Select the intended Writer document; microphone off |
| Green microphone | Listening |
| Gray pause bars | Paused |
| Blue processing symbol | Recognizing final speech; hover to see whether capture is also on |
| Amber exclamation | Text is held; hover to check microphone state |
| Blue square | Finishing queued speech |
| Red cross | Error; inspect the session and `.local/desktop.log` |

Hover for the microphone state, processing state and shortcut. Held text takes priority over the listening/processing icon, but the tooltip and menu still explicitly report whether the microphone is on. Pausing does not cancel queued recognition. Amber does not itself mean capture stopped.

Writer focus and duplicate safeguards remain unchanged: held text stays withheld for that run. To recover it, stop first and follow [Writer recovery](WRITER.md). The tray menu opens the latest session folder, which contains `transcript.txt` and recoverable audio. Easier held-text delivery is a deferred improvement.

## Local install and reproducible setup

On this machine all required system libraries are already present. For a fresh MX/Debian XFCE/X11 machine, install:

```bash
sudo apt-get install git build-essential cmake ffmpeg pkg-config libopenblas-dev \
  python3-venv python3-gi python3-uno gir1.2-gtk-3.0 gir1.2-keybinder-3.0 \
  flatpak xdotool pulseaudio-utils desktop-file-utils
```

Install LibreOffice's Flatpak from Flathub if it is not present (`org.libreoffice.LibreOffice`). The current launcher targets this Flatpak installation and an X11 desktop with an XFCE tray host. Other desktops/package formats require adaptation.

From the project directory, prepare missing local dependencies:

```bash
bash scripts/setup-local.sh --prepare
```

This creates the isolated venv with WebRTC VAD 2.0.14, downloads the pinned Whisper source/model if missing, builds CPU-native OpenBLAS tools with one build job, and generates Q5_0 weights. It validates recorded model checksums and leaves an existing checkout at another revision untouched. Initial preparation needs internet; existing verified dependencies are reused. See [engine setup](SETUP.md) for the source revision, build flags and individual commands. A partial model download fails validation; move it aside before retrying. Model/license information remains with the downloaded upstream files. Rebuild the engine on a different CPU.

Verify setup without network access, then install the applications-menu entry:

```bash
bash scripts/setup-local.sh --offline
python3 scripts/install-desktop.py
```

The installer writes only `~/.local/share/applications/live-transcribe.desktop`, pointing to this checkout. It does not enable autostart, modify XFCE keyboard settings, or install a system daemon. Keep the project at this path; reinstall the desktop entry after moving it. Uninstall the launcher by removing that one desktop entry after quitting the tray; local sessions and model files remain until you remove them deliberately.

Launch from a terminal if needed:

```bash
bash scripts/launch-desktop.sh
```

Choose a different shortcut or matching local Writer port:

```bash
bash scripts/launch-desktop.sh --shortcut '<Control><Alt>d' --writer-port 20027
```

Only one tray instance per checkout runs at a time. Quit it before changing shortcut arguments. If the default shortcut is occupied, a dialog reports the conflict and tray controls still work; the app does not replace an existing desktop shortcut.

## Troubleshooting and verification

No icon: add XFCE's **Status Tray Plugin** to the panel. The implementation uses the existing GTK3/X11 tray protocol, suitable for this machine; it does not support Wayland. No Writer connection: save your work, close Writer windows and restart through the tray so the UNO accept option takes effect. Only one process can listen on a given port. Writer's endpoint binds to loopback and closes when that Writer process exits; quitting the tray leaves Writer and its documents open.

The launcher clears the inherited optional `GTK_MODULES` sound-module setting for the Flatpak Writer subprocess only. This addresses the reported canberra warning without changing desktop-wide settings. GTK settings can also request modules, so unrelated warnings may remain in `.local/desktop.log`.

Logs contain status and session paths, not recognized text (`--no-text` is always used). Private transcripts and audio remain in ignored `.local/sessions/`. The latest desktop log is replaced when a new session starts. The menu can still open the latest stopped session; restarting the tray resets that pointer.

Verified locally: 23 automated checks for existing capture/recovery, delivery safeguards, piped pause/resume and tray state priority; actual XFCE icon embedding; real global-key activation while preserving window focus; graceful stop and held-text indication. An end-to-end test substitutes public sample audio for microphone capture and exercises the real CLI, Whisper and UNO with a disposable Writer profile. User testing of the new shortcut and tray remains the final usability check. Earlier live Writer dictation was accepted at approximately 3–4 seconds per chunk.
