"""Exercise terminal controls with synthetic capture, never a real microphone."""
import os
import pty
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from live_transcribe.cli import microphone_frames
from live_transcribe.core import Segmenter, Session


class CaptureControlTests(unittest.TestCase):
    def test_pause_resume_and_stop_preserve_frames(self):
        original_popen = subprocess.Popen
        code = "import os,time\nfor i in range(1000):\n os.write(1,b'\\1\\0'*480); time.sleep(.03)\n"

        def synthetic_capture(_command, **kwargs):
            return original_popen([sys.executable, "-c", code], **kwargs)

        master, slave = pty.openpty()
        terminal = os.fdopen(slave, "r")
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory)
            segmenter = Segmenter()
            stop = threading.Event()
            paused = threading.Event()
            frame_count = []
            phrases = []
            errors = []

            def save(phrase):
                if phrase:
                    phrases.append(phrase)
                    if phrase.reason == "pause-command":
                        paused.set()

            def capture():
                try:
                    for frame in microphone_frames("unused", session, segmenter, save, stop):
                        frame_count.append(frame)
                        save(segmenter.feed(frame, True))
                    save(segmenter.flush())
                except Exception as error:
                    errors.append(error)

            with patch("live_transcribe.cli.subprocess.Popen", synthetic_capture), patch("sys.stdin", terminal):
                thread = threading.Thread(target=capture)
                thread.start()
                try:
                    deadline = time.monotonic() + 2
                    while len(frame_count) < 5 and time.monotonic() < deadline:
                        time.sleep(.02)
                    self.assertGreaterEqual(len(frame_count), 5)
                    os.write(master, b"p\n")
                    self.assertTrue(paused.wait(2))
                    count = len(frame_count)
                    time.sleep(.15)
                    self.assertEqual(count, len(frame_count))
                    os.write(master, b"p\n")
                    deadline = time.monotonic() + 2
                    while len(frame_count) <= count + 3 and time.monotonic() < deadline:
                        time.sleep(.02)
                    self.assertGreater(len(frame_count), count)
                    os.write(master, b"q\n")
                    thread.join(3)
                    self.assertFalse(thread.is_alive())
                finally:
                    stop.set()
                    thread.join(3)
            self.assertFalse(errors)
            self.assertEqual(sum(len(p.pcm) for p in phrases), sum(len(f) for f in frame_count))
            self.assertGreaterEqual(len(phrases), 2)
            self.assertEqual(phrases[0].reason, "pause-command")
            self.assertGreaterEqual(phrases[1].start_frame, phrases[0].end_frame)
            session.close()
        terminal.close()
        os.close(master)


if __name__ == "__main__":
    unittest.main()
