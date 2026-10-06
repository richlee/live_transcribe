import json
from pathlib import Path
import struct
import tempfile
import threading
import time
import unittest

from live_transcribe.core import FRAME_BYTES, FRAME_SAMPLES, Phrase, Segmenter, Session, audio_context
from live_transcribe.cli import Recognizer


def frame(identity):
    return struct.pack("<h", identity) * FRAME_SAMPLES


class SegmentationTests(unittest.TestCase):
    def test_silence_does_not_create_phrases(self):
        segmenter = Segmenter()
        for index in range(100):
            self.assertIsNone(segmenter.feed(frame(index), False))
        self.assertIsNone(segmenter.flush())

    def test_pause_and_stop_do_not_overlap_audio(self):
        segmenter = Segmenter(pause_ms=90)
        phrases = []
        for index in range(30):
            voiced = 3 <= index < 9 or 18 <= index < 24
            phrase = segmenter.feed(frame(index), voiced)
            if phrase:
                phrases.append(phrase)
        if phrase := segmenter.flush():
            phrases.append(phrase)
        self.assertEqual(len(phrases), 2)
        seen = []
        for phrase in phrases:
            seen.extend(struct.unpack("<h", phrase.pcm[i:i + 2])[0]
                        for i in range(0, len(phrase.pcm), FRAME_BYTES))
        self.assertEqual(len(seen), len(set(seen)))
        self.assertTrue(set(range(3, 9)) | set(range(18, 24)) <= set(seen))

    def test_forced_split_preserves_all_speech_once(self):
        segmenter = Segmenter(max_seconds=0.3)
        phrases = []
        for index in range(25):
            if phrase := segmenter.feed(frame(index), True):
                phrases.append(phrase)
        phrases.append(segmenter.flush())
        self.assertEqual(b"".join(p.pcm for p in phrases), b"".join(frame(i) for i in range(25)))
        self.assertTrue(all(p.seconds <= 0.3 for p in phrases))

    def test_stop_preserves_very_short_detected_speech(self):
        segmenter = Segmenter()
        self.assertIsNone(segmenter.feed(frame(1), True))
        self.assertEqual(segmenter.flush().pcm, frame(1))
        self.assertIsNone(segmenter.flush())

    def test_context_never_truncates_phrase(self):
        for seconds in (0.03, 5, 10, 15, 25, 30):
            self.assertGreaterEqual(audio_context(seconds) / 50, seconds)
        for seconds in (0, 30.01):
            with self.assertRaises(ValueError):
                audio_context(seconds)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.session = Session(Path(self.temporary.name) / "session")

    def tearDown(self):
        self.session.close()
        self.temporary.cleanup()

    def save(self):
        return self.session.save(Phrase(frame(1) * 10, 0, 10, 8, "pause"))

    def test_recovery_projection_is_ordered_and_idempotent(self):
        first, second = self.save(), self.save()
        record = self.session.read(second)
        record.update(status="complete", text="It's the second phrase.")
        self.session.update(record)
        self.session.rebuild_transcript()
        record = self.session.read(first)
        record.update(status="complete", text="First phrase.")
        self.session.update(record)
        self.session.rebuild_transcript()
        self.session.rebuild_transcript()
        self.assertEqual((self.session.path / "transcript.txt").read_text(),
                         "First phrase.\nIt's the second phrase.\n")

    def test_session_cannot_be_opened_twice(self):
        with self.assertRaises(RuntimeError):
            Session(self.session.path)

    def worker(self, executable, cancel=None):
        return Recognizer(self.session, executable, Path("unused-model"),
                          threading.Event(), cancel or threading.Event(), False)

    def test_engine_failure_retains_audio_for_retry(self):
        identity = self.save()
        executable = Path(self.temporary.name) / "engine"
        executable.write_text("#!/bin/sh\nexit 7\n")
        executable.chmod(0o700)
        worker = self.worker(executable)
        worker.worker.start()
        worker.submit(identity)
        worker.finish()
        self.assertTrue(worker.failed)
        self.assertTrue(worker.stop.is_set())
        self.assertEqual(self.session.read(identity)["status"], "failed")
        self.assertTrue((self.session.path / f"{identity:06}.wav").is_file())

    def test_cancel_keeps_pending_and_skips_completed(self):
        identity = self.save()
        cancel = threading.Event()
        cancel.set()
        worker = self.worker(Path("missing-engine"), cancel)
        worker.worker.start()
        worker.submit(identity)
        worker.finish()
        self.assertEqual(self.session.read(identity)["status"], "pending")

    def test_completed_phrase_is_not_recognized_again(self):
        identity = self.save()
        record = self.session.read(identity)
        record.update(status="complete", text="Already completed.")
        self.session.update(record)
        worker = self.worker(Path("missing-engine"))
        worker.worker.start()
        worker.submit(identity)
        worker.finish()
        self.assertFalse(worker.failed)
        self.assertEqual(self.session.read(identity)["text"], "Already completed.")

    def test_failure_then_retry_completes_without_duplicate_text(self):
        identity = self.save()
        executable = Path(self.temporary.name) / "engine"
        executable.write_text("#!/bin/sh\nexit 7\n")
        executable.chmod(0o700)
        worker = self.worker(executable)
        worker.worker.start()
        worker.submit(identity)
        worker.finish()
        executable.write_text("#!/bin/sh\nwhile [ \"$#\" -gt 0 ]; do\n"
                              "if [ \"$1\" = '-of' ]; then shift; printf 'Recovered phrase.\\n' > \"$1.txt\"; fi\n"
                              "shift\ndone\n")
        worker = self.worker(executable)
        worker.worker.start()
        worker.submit(identity)
        worker.submit(identity)
        worker.finish()
        self.assertFalse(worker.failed)
        self.assertEqual(self.session.read(identity)["status"], "complete")
        self.assertEqual((self.session.path / "transcript.txt").read_text(), "Recovered phrase.\n")

    def test_cancelling_running_engine_keeps_retryable_audio(self):
        identity = self.save()
        executable = Path(self.temporary.name) / "engine"
        executable.write_text("#!/bin/sh\nexec sleep 10\n")
        executable.chmod(0o700)
        cancel = threading.Event()
        worker = self.worker(executable, cancel)
        worker.worker.start()
        worker.submit(identity)
        deadline = time.monotonic() + 2
        while self.session.read(identity)["status"] != "processing" and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(self.session.read(identity)["status"], "processing")
        cancel.set()
        worker.finish()
        self.assertEqual(self.session.read(identity)["status"], "pending")
        self.assertTrue((self.session.path / f"{identity:06}.wav").is_file())


if __name__ == "__main__":
    unittest.main()
