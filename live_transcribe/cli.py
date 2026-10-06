"""Local microphone-to-final-text dictation, with optional safe Writer insertion."""
import argparse
import json
import os
from pathlib import Path
import queue
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import wave

from .core import FRAME_BYTES, FRAME_MS, FRAME_SAMPLES, RATE, Segmenter, Session, atomic_text, audio_context

PRINT_LOCK = threading.Lock()


def say(status, message):
    with PRINT_LOCK:
        print(f"[{status}] {message}", flush=True)


class Recognizer:
    def __init__(self, session, binary, model, stop, cancel, show_text=True, writer=None):
        self.session, self.binary, self.model = session, binary, model
        self.stop, self.cancel = stop, cancel
        self.show_text = show_text
        self.writer = writer
        self.jobs = queue.Queue(maxsize=8)
        self.failed = False
        self.worker = threading.Thread(target=self.run, name="recognizer")

    def submit(self, identity):
        self.jobs.put_nowait((identity, time.monotonic()))

    def finish(self):
        self.jobs.put(None)
        self.worker.join()

    def deliver(self, identity):
        if self.writer:
            try:
                self.writer.deliver(identity)
            except Exception as error:
                self.writer.held = True
                say("WRITER", f"Insertion stopped; final transcript retained: {error}")

    def run(self):
        while (job := self.jobs.get()) is not None:
            identity, queued = job
            if self.cancel.is_set():
                continue  # Durable audio remains pending for recovery.
            try:
                self.recognize(identity, queued)
            except Exception as error:
                self.failed = True
                self.stop.set()
                try:
                    record = self.session.read(identity)
                    record.update(status="failed", error=str(error))
                    self.session.update(record)
                except Exception:
                    # Disk errors must not kill the worker and leave shutdown blocked.
                    self.cancel.set()
                say("ERROR", f"Phrase {identity:06} retained for recovery: {error}")
            finally:
                say("IDLE", "Recognition worker ready.")

    def recognize(self, identity, queued):
        record = self.session.read(identity)
        if record["status"] == "complete":
            self.deliver(identity)
            return
        context = audio_context(record["audio_seconds"])
        record.update(status="processing", audio_ctx=context)
        self.session.update(record)
        attempt = self.session.path / f"{identity:06}-{uuid.uuid4().hex[:8]}"
        command = [str(self.binary), "-m", str(self.model), "-f",
                   str(self.session.path / f"{identity:06}.wav"), "-l", "en", "-t", "2",
                   "-bs", "1", "-bo", "1", "-ac", str(context), "-otxt", "-of", str(attempt)]
        env = dict(os.environ, OPENBLAS_NUM_THREADS="2", OMP_NUM_THREADS="2")
        started = time.monotonic()
        say("PROCESSING", f"Phrase {identity:06}: {record['audio_seconds']:.2f}s, queue {self.jobs.qsize()}")
        with attempt.with_suffix(".log").open("w") as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                       env=env, start_new_session=True)
            interrupted = False
            timed_out = False
            try:
                while process.poll() is None:
                    interrupted = self.cancel.is_set()
                    timed_out = time.monotonic() - started > 60
                    if interrupted or timed_out:
                        process.terminate()
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                        break
                    time.sleep(0.05)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        if interrupted:
            record.update(status="pending", error="Recognition cancelled; retry with --recover")
            self.session.update(record)
            return
        if timed_out or process.returncode:
            raise RuntimeError(f"Engine {'timed out' if timed_out else 'exited ' + str(process.returncode)}; see {attempt.name}.log")
        text = attempt.with_suffix(".txt").read_text().strip()
        elapsed = time.monotonic() - started
        wait = started - queued
        record.update(status="complete", text=text, recognition_seconds=round(elapsed, 3),
                      queue_wait_seconds=round(wait, 3),
                      pause_to_final_estimate_seconds=round(record["pause_seconds"] + wait + elapsed, 3)
                      if record["reason"] == "pause" else None)
        record.pop("error", None)
        self.session.update(record)
        self.session.rebuild_transcript()
        say("FINAL", f"Phrase {identity:06}: {elapsed:.2f}s recognition, {wait:.2f}s queue")
        if text and self.show_text:
            with PRINT_LOCK:
                print(text, flush=True)
        elif not text:
            say("REVIEW", f"Phrase {identity:06} produced no text; its audio is retained")
        self.deliver(identity)


def replay_frames(path, realtime, stop):
    with wave.open(str(path), "rb") as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getcomptype()) != (1, 2, RATE, "NONE"):
            raise ValueError("Replay requires mono 16-bit PCM WAV at 16000 Hz")
        deadline = time.monotonic()
        while not stop.is_set() and (frame := audio.readframes(FRAME_SAMPLES)):
            if realtime:
                deadline += FRAME_MS / 1000
                stop.wait(max(0, deadline - time.monotonic()))
                if stop.is_set():
                    break
            yield frame.ljust(FRAME_BYTES, b"\0")


def microphone_frames(source, session, segmenter, submit, stop, control_stdin=False, start_paused=False):
    """Capture with small buffers; p pauses/resumes, q stops from the terminal."""
    paused = start_paused
    process = None
    selector = selectors.DefaultSelector()
    if sys.stdin.isatty() or control_stdin:
        selector.register(sys.stdin, selectors.EVENT_READ, "control")
    pending = bytearray()
    log = (session.path / "capture.log").open("a")

    def close_capture():
        nonlocal process
        if process is not None:
            selector.unregister(process.stdout)
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            # Preserve audio already delivered to the pipe, including partial frames.
            pending.extend(process.stdout.read())
            process.stdout.close()
            process = None

    try:
        if paused:
            say("PAUSED", "Capture is off; toggle listening to begin.")
        while not stop.is_set():
            if not paused and process is None:
                command = ["parec", "--raw", "--format=s16le", "--rate=16000", "--channels=1",
                           "--latency-msec=60", f"--device={source}", "--client-name=live-transcribe"]
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=log,
                                           start_new_session=True)
                selector.register(process.stdout, selectors.EVENT_READ, "audio")
                say("LISTENING", "Speak naturally. p + Enter pauses/resumes; q + Enter or Ctrl+C stops.")
            for key, _ in selector.select(timeout=0.1):
                if key.data == "control":
                    if control_stdin:
                        # Avoid TextIO read-ahead hiding a second command from select().
                        raw = bytearray()
                        while (character := os.read(sys.stdin.fileno(), 1)):
                            raw.extend(character)
                            if character == b"\n":
                                break
                        line = raw.decode(errors="replace")
                    else:
                        line = sys.stdin.readline()
                    if not line:
                        stop.set()
                        break
                    action = line.strip().lower()
                    if action == "q":
                        stop.set()
                        break
                    if action == "p":
                        paused = not paused
                        if paused:
                            close_capture()
                            while len(pending) >= FRAME_BYTES:
                                yield bytes(pending[:FRAME_BYTES])
                                del pending[:FRAME_BYTES]
                            if pending:
                                yield bytes(pending).ljust(FRAME_BYTES, b"\0")
                                pending.clear()
                            submit(segmenter.flush("pause-command"))
                            say("PAUSED", "Capture stopped; queued phrases still finish. p + Enter resumes.")
                        break
                else:
                    data = os.read(key.fd, FRAME_BYTES * 4)
                    if not data:
                        raise RuntimeError("Microphone capture ended unexpectedly; see capture.log")
                    pending.extend(data)
                    while len(pending) >= FRAME_BYTES and not stop.is_set():
                        yield bytes(pending[:FRAME_BYTES])
                        del pending[:FRAME_BYTES]
    finally:
        close_capture()
        log.close()
        selector.close()
    # On an ordinary stop preserve buffered capture before flushing the phrase.
    while len(pending) >= FRAME_BYTES:
        yield bytes(pending[:FRAME_BYTES])
        del pending[:FRAME_BYTES]
    if pending:
        yield bytes(pending).ljust(FRAME_BYTES, b"\0")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", type=Path, help="Test on an existing WAV, without opening the microphone")
    parser.add_argument("--realtime", action="store_true", help="Pace replay like microphone audio")
    parser.add_argument("--recover", type=Path, help="Retry unfinished phrases in a stopped session")
    parser.add_argument("--source", default="@DEFAULT_SOURCE@")
    parser.add_argument("--pause-ms", type=int, default=750)
    parser.add_argument("--max-seconds", type=float, default=15)
    parser.add_argument("--vad-mode", type=int, choices=range(4), default=2)
    parser.add_argument("--no-text", action="store_true", help="Print statuses without private recognized text")
    parser.add_argument("--writer", action="store_true", help="Select and bind one Writer document")
    parser.add_argument("--writer-port", type=int, default=20027, help="Local UNO port (default 20027)")
    parser.add_argument("--writer-window", type=lambda value: int(value, 0), help="Explicit X11 Writer window ID")
    parser.add_argument("--control-stdin", action="store_true", help="Accept p/q controls through a pipe")
    parser.add_argument("--start-paused", action="store_true", help="Bind Writer without opening the microphone")
    parser.add_argument("--word-delay-ms", type=int, default=0, help="Reveal final words gradually (0–200 ms; 0 inserts a chunk)")
    parser.add_argument("--spoken-commands", action=argparse.BooleanOptionalAction, default=True,
                        help="Interpret comma, full stop, new line and new paragraph inline")
    args = parser.parse_args()
    if not 0 <= args.word_delay_ms <= 200:
        parser.error("Word delay must be 0–200 ms")
    if not 300 <= args.pause_ms <= 2000 or not 2 <= args.max_seconds <= 25:
        parser.error("Pause must be 300–2000 ms and maximum phrase length 2–25 s")
    if args.recover and args.replay:
        parser.error("Choose recovery or replay, not both")
    root = Path(__file__).resolve().parents[1]
    binary = root / ".local/whisper.cpp/build-blas/bin/whisper-cli"
    model = root / ".local/whisper.cpp/models/ggml-tiny.en-q5_0.bin"
    if not binary.is_file() or not model.is_file():
        parser.error("Optimized Whisper build/model missing; see docs/SETUP.md")
    if not args.recover:
        try:
            import webrtcvad
        except ImportError:
            parser.error("Install requirements-live.txt in .local/venv")
        if not args.replay and not shutil.which("parec"):
            parser.error("parec is required for microphone capture")
    os.umask(0o077)
    parent = root / ".local/sessions"
    parent.mkdir(parents=True, exist_ok=True)
    if args.recover and not args.recover.is_dir():
        parser.error("Recovery session directory does not exist")
    path = args.recover or Path(tempfile.mkdtemp(prefix="session-", dir=parent))
    try:
        session = Session(path)
    except (RuntimeError, OSError) as error:
        parser.error(str(error))
    stop, cancel = threading.Event(), threading.Event()

    def interrupt(_signal, _frame):
        if stop.is_set():
            cancel.set()
        stop.set()

    old_int = signal.signal(signal.SIGINT, interrupt)
    old_term = signal.signal(signal.SIGTERM, interrupt)
    writer = None
    if args.writer:
        from .writer import Writer
        try:
            writer = Writer(session, args.writer_port, args.writer_window, bool(args.recover), stop,
                            args.word_delay_ms, args.spoken_commands)
        except Exception as error:
            session.close()
            parser.error(f"Writer connection failed: {error}; see docs/WRITER.md")
    worker = Recognizer(session, binary, model, stop, cancel, not args.no_text, writer)
    worker.worker.start()
    failed = False
    say("SESSION", str(session.path))

    def submit(phrase):
        if phrase is None:
            return
        identity = session.save(phrase)
        try:
            worker.submit(identity)
        except queue.Full:
            stop.set()
            say("BACKLOG", f"Capture stopping; phrase {identity:06} is saved pending recovery.")
        if phrase.reason == "max-length":
            say("SPLIT", "Long phrase split without overlap; pause regularly for better recognition.")

    try:
        session.rebuild_transcript()
        if args.recover:
            say("RECOVERING", "No microphone will be opened; completed phrases are skipped.")
            for record in session.records():
                if (record["status"] != "complete" or writer) and not cancel.is_set():
                    # Recovery can wait for capacity; no microphone audio is arriving.
                    worker.jobs.put((record["id"], time.monotonic()))
        else:
            atomic_text(session.path / "settings.json", json.dumps({
                "source": args.source, "vad_mode": args.vad_mode, "pause_ms": args.pause_ms,
                "max_seconds": args.max_seconds, "replay": bool(args.replay),
                "realtime": bool(args.realtime), "model": model.name, "threads": 2}, indent=2) + "\n")
            detector = webrtcvad.Vad(args.vad_mode)
            segmenter = Segmenter(args.pause_ms, args.max_seconds)
            frames = replay_frames(args.replay, args.realtime, stop) if args.replay else microphone_frames(
                args.source, session, segmenter, submit, stop, args.control_stdin, args.start_paused)
            say("REPLAY" if args.replay else "READY", "Only completed phrases are transcribed locally.")
            try:
                for frame in frames:
                    submit(segmenter.feed(frame, detector.is_speech(frame, RATE)))
            finally:
                frames.close()
                submit(segmenter.flush("stop"))
    except Exception as error:
        failed = True
        say("ERROR", str(error))
    finally:
        stop.set()
        say("STOPPING", "Finishing saved phrases. Ctrl+C again cancels recognition and keeps pending audio.")
        worker.finish()
        if writer:
            writer.close()
        session.rebuild_transcript()
        records = session.records()
        unfinished = sum(r["status"] != "complete" for r in records)
        say("STOPPED", f"{len(records) - unfinished} complete, {unfinished} unfinished; transcript: {session.path / 'transcript.txt'}")
        if not records and not args.recover:
            say("REVIEW", "No speech detected. Check microphone input or try --vad-mode 1.")
        session.close()
        signal.signal(signal.SIGINT, old_int)
        signal.signal(signal.SIGTERM, old_term)
    if failed or worker.failed or unfinished:
        raise SystemExit(1)
