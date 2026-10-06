import unittest

from live_transcribe.desktop_state import DesktopState


class DesktopStateTests(unittest.TestCase):
    def test_paused_processing_does_not_claim_microphone_is_on(self):
        state = DesktopState()
        state.consume('[LISTENING] Speak naturally.')
        state.consume('[PROCESSING] Phrase 000001')
        self.assertEqual(state.label, 'Processing')
        self.assertTrue(state.listening)
        state.consume('[PAUSED] Capture stopped')
        self.assertEqual(state.label, 'Processing')
        self.assertFalse(state.listening)
        state.consume('[IDLE] Recognition worker ready')
        self.assertEqual(state.label, 'Paused')

    def test_held_text_survives_resuming_capture_and_finishing(self):
        state = DesktopState()
        state.consume('[WRITER] Phrase 000001: held; text remains in transcript.txt')
        state.consume('[LISTENING] Speak naturally.')
        state.consume('[PROCESSING] Phrase 000002')
        self.assertEqual(state.label, 'Held text')
        self.assertTrue(state.listening)
        state.consume('[STOPPED] 2 complete')
        self.assertEqual(state.label, 'Held text')
        self.assertFalse(state.listening)
        self.assertIn('withheld', state.detail)

    def test_uncertain_and_bridge_error_are_visible(self):
        for message in ('Phrase 000001: uncertain; text remains', 'Insertion stopped; final transcript retained'):
            state = DesktopState()
            state.consume('[WRITER] ' + message)
            self.assertEqual(state.label, 'Held text')

    def test_status_parser_ignores_plain_dictated_text(self):
        state = DesktopState()
        state.consume('This is dictated text.')
        self.assertEqual(state.label, 'Ready')
        state.consume('[SESSION] /tmp/session-test')
        self.assertEqual(state.session, '/tmp/session-test')
        state.consume('[ERROR] Capture failed')
        self.assertEqual(state.label, 'Error')
        self.assertEqual(state.error, 'Capture failed')


if __name__ == '__main__':
    unittest.main()
