import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from live_transcribe.core import Session
from live_transcribe.writer import Writer


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


if __name__ == '__main__':
    unittest.main()
