"""Tray state derived from the worker's public status lines, never dictated text."""
from dataclasses import dataclass


@dataclass
class DesktopState:
    phase: str = 'ready'
    listening: bool = False
    processing: bool = False
    held: bool = False
    session: str | None = None
    error: str | None = None

    def consume(self, line):
        if not line.startswith('[') or '] ' not in line:
            return
        status, message = line[1:].split('] ', 1)
        if status == 'SESSION':
            self.session = message
        elif status == 'LISTENING':
            self.phase, self.listening = 'running', True
        elif status == 'PAUSED':
            self.phase, self.listening = 'running', False
        elif status == 'PROCESSING':
            self.processing = True
        elif status == 'IDLE':
            self.processing = False
        elif status == 'WRITER' and (': held;' in message or ': uncertain;' in message or 'Insertion stopped' in message):
            self.held = True
        elif status == 'ERROR':
            self.error = message
        elif status in ('STOPPING', 'BACKLOG'):
            self.phase, self.listening = 'stopping', False
        elif status == 'STOPPED':
            self.phase, self.listening, self.processing = 'ready', False, False

    @property
    def label(self):
        if self.error:
            return 'Error'
        if self.held:
            return 'Held text'
        if self.phase == 'starting':
            return 'Select Writer'
        if self.phase == 'stopping':
            return 'Finishing'
        if self.processing:
            return 'Processing'
        if self.listening:
            return 'Listening'
        return 'Paused' if self.phase == 'running' else 'Ready'

    @property
    def detail(self):
        if self.phase == 'starting':
            return 'Click the intended Writer document; capture stays off until it is bound.'
        return ('Microphone: on' if self.listening else 'Microphone: off') + ('; processing final speech' if self.processing else '') + ('; text withheld — stop and recover explicitly' if self.held else '')
