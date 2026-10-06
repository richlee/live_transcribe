"""Phrase segmentation and durable local session storage."""
from collections import deque
from dataclasses import dataclass
import fcntl
import json
import math
import os
from pathlib import Path
import tempfile
import wave

RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = RATE * FRAME_MS // 1000
FRAME_BYTES = FRAME_SAMPLES * 2


@dataclass
class Phrase:
    pcm: bytes
    start_frame: int
    end_frame: int
    last_voice_frame: int
    reason: str

    @property
    def seconds(self):
        return len(self.pcm) / (RATE * 2)


class Segmenter:
    """Non-overlapping frames, short pre-roll, pause ending, bounded phrases."""

    def __init__(self, pause_ms=750, max_seconds=15):
        self.pause_frames = math.ceil(pause_ms / FRAME_MS)
        self.max_frames = math.floor(max_seconds * 1000 / FRAME_MS)
        self.history = deque(maxlen=10)
        self.active = []
        self.index = 0
        self.silent = 0

    def feed(self, pcm, voiced):
        if len(pcm) != FRAME_BYTES:
            raise ValueError("Expected one 30 ms PCM frame")
        frame = (self.index, pcm, voiced)
        self.index += 1
        if not self.active:
            self.history.append(frame)
            if sum(f[2] for f in list(self.history)[-5:]) < 3:
                return None
            self.active = list(self.history)
            self.history.clear()
        else:
            self.active.append(frame)
        self.silent = 0 if voiced else self.silent + 1
        if self.silent >= self.pause_frames:
            return self.flush("pause")
        if len(self.active) >= self.max_frames:
            return self.flush("max-length")
        return None

    def flush(self, reason="stop"):
        # Include brief detected speech on stop, even if onset was not confirmed.
        frames = self.active or list(self.history)
        self.active = []
        self.history.clear()
        self.silent = 0
        voiced = [f[0] for f in frames if f[2]]
        if not voiced:
            return None
        return Phrase(b"".join(f[1] for f in frames), frames[0][0],
                      frames[-1][0] + 1, voiced[-1], reason)


def atomic_text(path, text):
    """Replace one durable file; never append provisional or duplicate text."""
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Session:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = (self.path / ".lock").open("a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            raise RuntimeError("This session is already open in another process") from None
        self.next_id = max((int(p.stem) for p in self.path.glob("[0-9]*.json")), default=0) + 1

    def close(self):
        self.lock.close()

    def read(self, identity):
        return json.loads((self.path / f"{identity:06}.json").read_text())

    def update(self, record):
        atomic_text(self.path / f"{record['id']:06}.json",
                    json.dumps(record, indent=2) + "\n")

    def records(self):
        return [json.loads(p.read_text()) for p in sorted(self.path.glob("[0-9]*.json"))]

    def save(self, phrase):
        identity = self.next_id
        self.next_id += 1
        path = self.path / f"{identity:06}.wav"
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(RATE)
            audio.writeframes(phrase.pcm)
        with path.open("rb") as stream:
            os.fsync(stream.fileno())
        self.update({"id": identity, "status": "pending", "audio_seconds": phrase.seconds,
                     "start_frame": phrase.start_frame, "end_frame": phrase.end_frame,
                     "pause_seconds": (phrase.end_frame - phrase.last_voice_frame - 1) * FRAME_MS / 1000,
                     "reason": phrase.reason})
        return identity

    def rebuild_transcript(self):
        # Completed record files are authoritative. Recovery regenerates this view.
        final = [r["text"] for r in self.records() if r["status"] == "complete" and r.get("text")]
        atomic_text(self.path / "transcript.txt", "\n".join(final) + ("\n" if final else ""))


def audio_context(seconds):
    """Cover the entire phrase plus margin, capped at the model's 30 seconds."""
    if not 0 < seconds <= 30:
        raise ValueError("Phrase must be between zero and thirty seconds")
    return max(300, min(1500, math.ceil(seconds + 1) * 50))
