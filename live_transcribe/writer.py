"""Durable final-text delivery, with a focus-loss latch and duplicate protection."""
import json
import re
import select
import subprocess
import time
import uuid

from .core import atomic_text
from .commands import delivery_plan


def select_document_window(stop=None):
    """Wait briefly for a popup/key grab to release before selecting a document."""
    deadline = time.monotonic() + 3
    while True:
        selection = subprocess.Popen(['xdotool', 'selectwindow'], stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True)
        try:
            while selection.poll() is None:
                if stop is not None and stop.is_set():
                    raise RuntimeError('Document selection cancelled; no microphone was opened')
                time.sleep(0.05)
            output, error = selection.communicate()
            if selection.returncode == 0:
                return int(output.strip(), 0)
            if 'mouse grabbed' not in error.lower() or time.monotonic() >= deadline:
                raise RuntimeError('Document selection failed. Close any popup or drag operation and try again; no microphone was opened')
        finally:
            if selection.poll() is None:
                selection.terminate()
                selection.wait(timeout=2)
            selection.stdout.close()
            selection.stderr.close()
        if stop is not None:
            if stop.wait(0.1):
                raise RuntimeError('Document selection cancelled; no microphone was opened')
        else:
            time.sleep(0.1)


class Writer:
    def __init__(self, session, port, window=None, recovering=False, stop=None, word_delay_ms=0, spoken_commands=True):
        self.session = session
        self.held = False
        self.process = None
        self.word_delay_ms = word_delay_ms
        self.spoken_commands = spoken_commands
        self.legacy_session = False
        if window is None:
            print('[WRITER] Click the intended Writer document to bind this session.', flush=True)
            window = select_document_window(stop)
        path = session.path / 'writer.json'
        if recovering:
            if not path.exists():
                raise RuntimeError('Session has no original Writer target; use transcript.txt manually')
            target = json.loads(path.read_text())
            self.legacy_session = 'spoken_commands' not in target
            self.spoken_commands = target.get('spoken_commands', False)
        else:
            target = {'token': '_live_transcribe_' + uuid.uuid4().hex, 'spoken_commands': spoken_commands}
        self.process = subprocess.Popen(['/usr/bin/python3', '-m', 'live_transcribe.writer_bridge'],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            self.call({'action': 'bind', 'port': port, 'window': window,
                       'token': target['token'], 'recovering': recovering})
            if not recovering:
                atomic_text(path, json.dumps(target) + '\n')
            # Explicit initial selection authorizes bringing this document to the front.
            subprocess.run(['xdotool', 'windowactivate', '--sync', str(window)], check=True)
        except Exception:
            self.close()
            raise

    def call(self, request):
        self.process.stdin.write(json.dumps(request) + '\n')
        self.process.stdin.flush()
        if not select.select([self.process.stdout], [], [], 5)[0]:
            raise RuntimeError('Writer bridge timed out; insertion may need manual review')
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError('Writer bridge stopped')
        response = json.loads(line)
        if 'error' in response:
            raise RuntimeError(response['error'])
        return response['result']

    def reveal_words(self, identity, text):
        state = self.call({'action': 'check', 'id': identity})
        if state != 'pending':
            return state
        # Leading whitespace belongs to the following word, preserving exact spacing.
        words = re.findall(r'\s*\S+', text)
        delay = min(self.word_delay_ms / 1000, 1.2 / max(1, len(words) - 1))
        for index, word in enumerate(words):
            result = self.call({'action': 'insert', 'id': f'{identity}_word_{index}',
                                'text': word, 'literal_spacing': index > 0})
            if result != 'inserted':
                return result
            if delay and index < len(words) - 1:
                time.sleep(delay)
        return self.call({'action': 'finish_words', 'id': identity, 'count': len(words)})

    def deliver(self, identity):
        record = self.session.read(identity)
        if record['status'] != 'complete' or not record.get('text') or record.get('delivery') == 'inserted':
            return
        # Freeze the exact sequence before the first attempt, including withheld phrases.
        # Existing partially delivered sessions retain their original tracking scheme.
        if not self.legacy_session and 'delivery_plan' not in record and 'delivery' not in record and 'delivery_style' not in record:
            record['delivery_plan'] = delivery_plan(record['text'], self.spoken_commands)
            record['delivery_style'] = 'commands-v1'
            self.session.update(record)
        if self.held:
            result = 'held'
        else:
            # Persist intent before crossing the process boundary. Bookmarks resolve lost acknowledgements.
            record['delivery'] = 'inserting'
            command = record['text'].strip().lower().rstrip('.!?')
            paced = 'delivery_plan' not in record and command not in ('new line', 'new paragraph') and (
                self.word_delay_ms > 0 or record.get('delivery_style') == 'words-v1')
            if paced:
                record['delivery_style'] = 'words-v1'
            self.session.update(record)
            try:
                if 'delivery_plan' in record:
                    result = self.deliver_plan(identity, record['delivery_plan'])
                elif paced:
                    result = self.reveal_words(identity, record['text'])
                else:
                    result = self.call({'action': 'insert', 'id': identity, 'text': record['text']})
            except Exception as error:
                result = 'uncertain'
                record['delivery_error'] = str(error)
        record['delivery'] = result
        self.session.update(record)
        if result != 'inserted':
            self.held = True
        print(f'[WRITER] Phrase {identity:06}: {result}; text remains in transcript.txt', flush=True)

    def deliver_plan(self, identity, parts):
        state = self.call({'action': 'check', 'id': identity})
        if state != 'pending':
            return state
        delay = min(self.word_delay_ms / 1000, 1.2 / max(1, len(parts) - 1))
        for index, part in enumerate(parts):
            result = self.call({'action': 'insert', 'id': f'{identity}_command_{index}',
                                'text': part['text'], 'operation': part['kind'],
                                'literal_spacing': index > 0})
            if result != 'inserted':
                return result
            if delay and index < len(parts) - 1:
                time.sleep(delay)
        return self.call({'action': 'finish_words', 'id': identity, 'count': len(parts), 'scheme': 'command'})

    def close(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process.stdin.close()
            self.process.stdout.close()
