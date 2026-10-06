import unittest

from live_transcribe.commands import delivery_plan


def rendered(parts):
    return ''.join({'line': '\n', 'paragraph': '\u2029'}.get(part['kind'], part['text']) for part in parts)


class CommandTests(unittest.TestCase):
    def test_inline_punctuation_and_structure(self):
        source = 'Hello comma how are you full stop New paragraph Next line new line Last line.'
        self.assertEqual(rendered(delivery_plan(source, True)), 'Hello, how are you.\u2029Next line\nLast line.')

    def test_case_and_model_punctuation_on_commands(self):
        self.assertEqual(rendered(delivery_plan('Hello, COMMA. how are you FULL STOP? New paragraph.', True)),
                         'Hello, how are you.\u2029')

    def test_disabled_commands_preserve_literal_words_and_spacing(self):
        source = "Say comma and full stop.  It's a new paragraph."
        self.assertEqual(rendered(delivery_plan(source, False)), source)

    def test_non_commands_preserve_wording_and_spacing(self):
        source = "It's smooth,  isn't it? The commander mentions commas and comma's meaning."
        self.assertEqual(rendered(delivery_plan(source, True)), source)

    def test_commands_at_phrase_boundaries(self):
        self.assertEqual(rendered(delivery_plan('comma.', True)), ',')
        self.assertEqual(rendered(delivery_plan('full stop.', True)), '.')
        self.assertEqual(rendered(delivery_plan('new paragraph', True)), '\u2029')

    def test_command_words_split_between_phrases_are_not_guessed(self):
        self.assertEqual(rendered(delivery_plan('This is full', True)), 'This is full')
        self.assertEqual(rendered(delivery_plan('stop here.', True)), 'stop here.')


if __name__ == '__main__':
    unittest.main()
