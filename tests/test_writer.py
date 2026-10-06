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
        self.writer.word_delay_ms = 0
        self.writer.spoken_commands = False
        self.writer.legacy_session = True
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

    def test_word_reveal_preserves_spacing_and_resumes_after_focus_loss(self):
        text = "It's smooth,  isn't it?"
        self.record(1, text=text)
        self.writer.word_delay_ms = 75
        written, completed = [], set()
        focused = False
        def bridge(request):
            nonlocal focused
            if request['action'] == 'check':
                return 'pending'
            if request['action'] == 'finish_words':
                return 'inserted'
            if request['id'] in completed:
                return 'inserted'
            if written and not focused:
                return 'held'
            written.append(request['text'])
            completed.add(request['id'])
            return 'inserted'
        self.writer.call.side_effect = bridge
        with patch('live_transcribe.writer.time.sleep'):
            self.writer.deliver(1)
        self.assertEqual(written, ["It's"])
        self.assertEqual(self.session.read(1)['delivery'], 'held')
        self.assertEqual(self.session.read(1)['delivery_style'], 'words-v1')
        # Explicit recovery with pacing disabled must still skip completed word markers.
        self.writer.held, self.writer.word_delay_ms, focused = False, 0, True
        self.writer.deliver(1)
        self.assertEqual(''.join(written), text)
        self.assertEqual(self.session.read(1)['delivery'], 'inserted')

    def test_paced_recovery_respects_previous_whole_phrase_marker(self):
        self.record(1, delivery='inserting')
        self.writer.word_delay_ms = 75
        self.writer.call.return_value = 'inserted'
        self.writer.deliver(1)
        self.writer.call.assert_called_once_with({'action': 'check', 'id': 1})
        self.assertEqual(self.session.read(1)['delivery'], 'inserted')

    def test_word_reveal_does_not_continue_after_uncertain_word(self):
        self.record(1, text='One two three.')
        self.writer.word_delay_ms = 75
        self.writer.call.side_effect = ['pending', 'inserted', 'uncertain']
        with patch('live_transcribe.writer.time.sleep'):
            self.writer.deliver(1)
        self.assertEqual(self.writer.call.call_count, 3)
        self.assertEqual(self.session.read(1)['delivery'], 'uncertain')
        self.assertTrue(self.writer.held)

    def test_long_phrase_reveal_delay_is_bounded(self):
        self.record(1, text=' '.join(['word'] * 100))
        self.writer.word_delay_ms = 200
        self.writer.call.side_effect = lambda request: 'pending' if request['action'] == 'check' else 'inserted'
        with patch('live_transcribe.writer.time.sleep') as sleep:
            self.writer.deliver(1)
        self.assertLessEqual(sum(call.args[0] for call in sleep.call_args_list), 1.200001)

    def test_paragraph_command_is_not_revealed_as_words(self):
        self.record(1, text='New paragraph.')
        self.writer.word_delay_ms = 75
        self.writer.deliver(1)
        self.writer.call.assert_called_once_with({'action': 'insert', 'id': 1, 'text': 'New paragraph.'})

    def test_inline_plan_is_frozen_before_hold_and_mode_changes(self):
        self.writer.legacy_session = False
        self.writer.spoken_commands = True
        self.writer.held = True
        source = 'Hello comma next full stop new paragraph Again.'
        self.record(1, text=source)
        self.writer.deliver(1)
        frozen = self.session.read(1)['delivery_plan']
        self.assertEqual(self.session.read(1)['text'], source)
        self.assertTrue(any(part['kind'] == 'paragraph' for part in frozen))
        self.writer.held = False
        self.writer.spoken_commands = False
        self.writer.call.side_effect = lambda request: 'pending' if request['action'] == 'check' else 'inserted'
        self.writer.deliver(1)
        self.assertEqual(self.session.read(1)['delivery_plan'], frozen)
        sent = [call.args[0] for call in self.writer.call.call_args_list if call.args[0]['action'] == 'insert']
        self.assertEqual([request['operation'] for request in sent], [part['kind'] for part in frozen])
        self.assertEqual(self.session.read(1)['delivery'], 'inserted')

    def test_off_mode_sends_command_names_as_literal_text(self):
        self.writer.legacy_session = False
        self.writer.spoken_commands = False
        self.record(1, text='new paragraph')
        self.writer.call.side_effect = lambda request: 'pending' if request['action'] == 'check' else 'inserted'
        self.writer.deliver(1)
        parts = self.session.read(1)['delivery_plan']
        self.assertEqual([part['kind'] for part in parts], ['text', 'text'])
        self.assertEqual(''.join(part['text'] for part in parts), 'new paragraph')

    def test_failed_action_blocks_rest_of_inline_sequence(self):
        self.writer.legacy_session = False
        self.writer.spoken_commands = True
        self.record(1, text='Hello full stop new paragraph Next.')
        self.writer.call.side_effect = ['pending', 'inserted', 'uncertain']
        self.writer.deliver(1)
        self.assertEqual(self.session.read(1)['delivery'], 'uncertain')
        self.assertEqual(self.writer.call.call_count, 3)
        self.assertTrue(self.writer.held)


if __name__ == '__main__':
    unittest.main()
