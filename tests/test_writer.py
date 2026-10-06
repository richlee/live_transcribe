import tempfile
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from live_transcribe.core import Session
from live_transcribe.writer import Writer, select_document_window


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.session = Session(Path(self.directory.name))
        self.writer = Writer.__new__(Writer)
        self.writer.session = self.session
        self.writer.held = False
        self.writer.call = Mock(return_value='inserted')

    def tearDown(self):
        self.session.close()
        self.directory.cleanup()

    def record(self, identity, text='Test words.', **extra):
        self.session.update(dict(id=identity, status='complete', text=text, **extra))

    def test_focus_hold_blocks_later_phrases(self):
        self.record(1)
        self.record(2)
        self.writer.call.return_value = 'held'
        self.writer.deliver(1)
        self.writer.call.return_value = 'inserted'
        self.writer.deliver(2)
        self.assertEqual(self.writer.call.call_count, 1)
        self.assertEqual(self.session.read(2)['delivery'], 'held')

    def test_lost_acknowledgement_is_uncertain_and_blocks_queue(self):
        self.record(1)
        self.record(2)
        def lost(request):
            self.assertEqual(self.session.read(1)['delivery'], 'inserting')
            raise RuntimeError('Lost response')
        self.writer.call.side_effect = lost
        self.writer.deliver(1)
        self.writer.deliver(2)
        self.assertEqual(self.session.read(1)['delivery'], 'uncertain')
        self.assertEqual(self.session.read(2)['delivery'], 'held')
        self.assertEqual(self.writer.call.call_count, 1)

    def test_completed_delivery_and_empty_text_are_skipped(self):
        self.record(1, delivery='inserted')
        self.record(2, text='')
        self.writer.deliver(1)
        self.writer.deliver(2)
        self.writer.call.assert_not_called()

    def test_recovery_queries_bookmark_before_reinserting(self):
        self.record(1, delivery='inserting')
        self.writer.deliver(1)
        self.assertEqual(self.session.read(1)['delivery'], 'inserted')
        self.writer.deliver(1)
        self.assertEqual(self.writer.call.call_count, 1)

    def test_cancel_document_selection_does_not_leave_selector_running(self):
        original = subprocess.Popen
        children = []
        stop = threading.Event()
        def selector(command, **kwargs):
            self.assertEqual(command, ['xdotool', 'selectwindow'])
            child = original([sys.executable, '-c', 'import time; time.sleep(60)'], **kwargs)
            children.append(child)
            return child
        timer = threading.Timer(0.1, stop.set)
        timer.start()
        try:
            with patch('live_transcribe.writer.subprocess.Popen', selector):
                with self.assertRaisesRegex(RuntimeError, 'selection cancelled'):
                    Writer(self.session, 20027, stop=stop)
            self.assertEqual(len(children), 1)
            self.assertIsNotNone(children[0].poll())
            self.assertFalse((self.session.path / 'writer.json').exists())
        finally:
            timer.cancel()

    def test_selection_retries_temporary_mouse_grab(self):
        original = subprocess.Popen
        commands = []
        def selector(command, **kwargs):
            commands.append(command)
            code = ('import sys; print("Something already has the mouse grabbed", file=sys.stderr); sys.exit(1)'
                    if len(commands) == 1 else 'print("0x1234")')
            return original([sys.executable, '-c', code], **kwargs)
        with patch('live_transcribe.writer.subprocess.Popen', selector):
            self.assertEqual(select_document_window(), 0x1234)
        self.assertEqual(len(commands), 2)

    def test_selection_does_not_retry_unrelated_failure(self):
        original = subprocess.Popen
        with patch('live_transcribe.writer.subprocess.Popen',
                   side_effect=lambda command, **kwargs: original(
                       [sys.executable, '-c', 'import sys; sys.exit(2)'], **kwargs)) as selector:
            with self.assertRaisesRegex(RuntimeError, 'no microphone was opened'):
                select_document_window()
        self.assertEqual(selector.call_count, 1)


if __name__ == '__main__':
    unittest.main()
