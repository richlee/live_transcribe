"""Durable final-text delivery, with a focus-loss latch and duplicate protection."""
import json
import select
import subprocess
import time
import uuid

from .core import atomic_text


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
    def __init__(self, session, port, window=None, recovering=False, stop=None):
        self.session = session
        self.held = False
        self.process = None
        if window is None:
            print('[WRITER] Click the intended Writer document to bind this session.', flush=True)
            window = select_document_window(stop)
        path = session.path / 'writer.json'
        if recovering:
            if not path.exists():
                raise RuntimeError('Session has no original Writer target; use transcript.txt manually')
            target = json.loads(path.read_text())
        else:
            target = {'token': '_live_transcribe_' + uuid.uuid4().hex}
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

    def deliver(self, identity):
        record = self.session.read(identity)
        if record['status'] != 'complete' or not record.get('text') or record.get('delivery') == 'inserted':
            return
        if self.held:
            result = 'held'
        else:
            # Persist intent before crossing the process boundary. Bookmarks resolve lost acknowledgements.
            record['delivery'] = 'inserting'
            self.session.update(record)
            try:
                result = self.call({'action': 'insert', 'id': identity, 'text': record['text']})
            except Exception as error:
                result = 'uncertain'
                record['delivery_error'] = str(error)
        record['delivery'] = result
        self.session.update(record)
        if result != 'inserted':
            self.held = True
        print(f'[WRITER] Phrase {identity:06}: {result}; text remains in transcript.txt', flush=True)

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
