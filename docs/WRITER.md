# Writer dictation (stage 4)

Writer on this machine is installed through Flatpak. Install the host Python bridge:

```bash
sudo apt-get install python3-uno
```

This also installs supporting native LibreOffice libraries. The transcription venv remains separate: a small `/usr/bin/python3` sidecar uses UNO.

## Start and stop

Open Writer with a local UNO connection (no internet required):

```bash
flatpak run org.libreoffice.LibreOffice --writer --accept='socket,host=127.0.0.1,port=20027;urp;StarOffice.ServiceManager'
```

From another terminal in the project directory:

```bash
.local/venv/bin/python -m live_transcribe --writer --no-text
```

Click the intended Writer document when the crosshair appears. The app brings that explicitly selected window to the front and starts capture. Dictate short phrases with pauses. Final text is inserted at the current cursor. Say **new line** or **new paragraph** as a standalone phrase; those exact commands are case insensitive and allow trailing sentence punctuation. Commands embedded in a sentence remain ordinary text. The local transcript preserves recognized command words.

To pause or stop, switch to the terminal and use `p` + Enter or `q` + Enter (Ctrl+C also stops). Returning to the terminal can withhold a phrase still being processed. Pause stops capture but lets recognition finish; stop flushes the final speech and drains recognition. Watch the printed `[WRITER]` statuses. Global controls are stage 5.

## Focus and recovery

A session binds to one Writer document. Delivery checks its X11 window and focus before each insertion. Writes use the bound document's UNO API, never simulated typing into an arbitrary window. A focus change during the check/write interval can still allow a phrase into the original document; it cannot redirect that write into the newly focused application. The clipboard is never used or changed by insertion.

If insertion is withheld (focus elsewhere, selection not collapsed, document read-only, bridge failure), all subsequent text stays withheld for this run. Returning to Writer does not release that queue. The transcript and per-phrase audio remain under the printed private session directory. To explicitly deliver held text after stopping:

```bash
.local/venv/bin/python -m live_transcribe --recover .local/sessions/session-YOUR-ID --writer --no-text
```

Click the **original document** again. Recovery opens no microphone, retries unfinished recognition, and delivers completed phrases in order at the current cursor. It rejects a different document using a session bookmark. Keep the document open, or save it as ODT to preserve bookmarks. Plain-text export does not preserve them. Sessions originally run without `--writer` have no bound target; copy their transcript manually.

Invisible per-phrase bookmarks protect against duplicate insertion after a lost acknowledgement. A beginning marker without an end marker means `uncertain`: review that phrase manually in the document and local transcript. Automatic recovery will continue to withhold it and later phrases. Manual editing, undoing dictation, deleting bookmarks or copying documents can invalidate tracking; review rather than blindly recovering after those actions. If an inserted phrase was subsequently undone, recovery does not automatically restore it.

## Troubleshooting and checks

Connection refused: start Writer with the command above. If an existing Writer process does not accept the connection, save work and close its windows, then restart with that command. `--writer-port PORT` supports a different matching local port. The UNO endpoint allows local process access to this Writer instance; it listens only on loopback. Close that Writer process to close the endpoint.

If selection is highlighted, collapse it to a cursor before dictation. No selection is overwritten. If a connection error occurs, recognized text remains recoverable. `python3-uno` is an apt package, not a pip dependency. The terminal-only path still works without it.

Verified on this laptop with Flatpak LibreOffice 26.8.1.1 and Debian's Python UNO: ordinary text, apostrophes, punctuation, distinct line/paragraph breaks, clipboard preservation, another Writer document gaining focus, held queue recovery into the original document, wrong-document rejection, duplicate acknowledgement recovery, and ambiguous insertion withholding. Tests used disposable documents and public sample text. Actual microphone-to-Writer usability still needs user feedback.
