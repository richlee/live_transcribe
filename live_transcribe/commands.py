"""Explicit spoken commands only; recognized wording is otherwise unchanged."""
import re

COMMANDS = {'comma': ',', 'full stop': '.', 'new line': '\n', 'new paragraph': '\u2029'}
PATTERN = re.compile(r"(?<![\w'’])(full\s+stop|comma|new\s+paragraph|new\s+line)(?![\w'’])[.,!?;:]*", re.I)


def delivery_plan(text, enabled):
    rendered = text
    if enabled:
        rendered, end = '', 0
        for match in PATTERN.finditer(text):
            rendered += text[end:match.start()]
            value = COMMANDS[' '.join(match.group(1).lower().split())]
            rendered = rendered.rstrip()
            if value in ',.':
                # Explicit punctuation overrides adjacent model-generated punctuation.
                rendered = rendered.rstrip('.,!?;:')
            rendered += value
            end = match.end()
        rendered += text[end:]
    parts = []
    for token in re.findall(r'\n|\u2029|[^\S\n\u2029]*[^\s\u2029]+', rendered):
        if token in ('\n', '\u2029'):
            parts.append({'kind': 'line' if token == '\n' else 'paragraph', 'text': ''})
        else:
            if parts and parts[-1]['kind'] in ('line', 'paragraph'):
                token = token.lstrip()
            parts.append({'kind': 'text', 'text': token})
    return parts
