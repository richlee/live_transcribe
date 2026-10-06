"""System-Python UNO sidecar. Writes only to one explicitly selected document."""
import json
import subprocess
import sys
import time

import uno


def active_window():
    return int(subprocess.check_output(['xdotool', 'getactivewindow'], text=True).strip())


def window_id(document):
    handle = document.CurrentController.Frame.ContainerWindow.getWindowHandle((), 6)
    return int(getattr(handle, 'WindowHandle', handle))


def bookmark(document, name, cursor):
    mark = document.createInstance('com.sun.star.text.Bookmark')
    mark.Name = name
    cursor.Text.insertTextContent(cursor, mark, False)


class Bridge:
    def __init__(self, port, window, token, recovering):
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)
        deadline = time.monotonic() + 3
        while True:
            try:
                context = resolver.resolve(f'uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext')
                break
            except uno.getClass('com.sun.star.connection.NoConnectException'):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)
        desktop = context.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', context)
        components = desktop.getComponents().createEnumeration()
        self.document = None
        while components.hasMoreElements():
            doc = components.nextElement()
            if doc.supportsService('com.sun.star.text.TextDocument') and window_id(doc) == window:
                self.document = doc
                break
        if self.document is None:
            raise RuntimeError('Selected window is not a Writer document on this UNO connection')
        self.window, self.token = window, token
        if recovering and not self.document.Bookmarks.hasByName(token):
            raise RuntimeError('This is not the original session document; recovery refused')
        if not recovering:
            bookmark(self.document, token, self.document.CurrentController.getViewCursor())

    def delivery_state(self, identity):
        if self.document.Bookmarks.hasByName(f'{self.token}_{identity}_done'):
            return 'inserted'
        if self.document.Bookmarks.hasByName(f'{self.token}_{identity}_begin'):
            return 'uncertain'
        return 'pending'

    def finish_words(self, identity, count, scheme='word'):
        if not all(self.delivery_state(f'{identity}_{scheme}_{index}') == 'inserted' for index in range(count)):
            return 'uncertain'
        return 'inserted'

    def insert(self, identity, text, literal_spacing=False, operation=None):
        doc = self.document
        begin, done = f'{self.token}_{identity}_begin', f'{self.token}_{identity}_done'
        if doc.Bookmarks.hasByName(done):
            return 'inserted'
        if doc.Bookmarks.hasByName(begin):
            return 'uncertain'
        if window_id(doc) != self.window or active_window() != self.window:
            return 'held'
        cursor = doc.CurrentController.getViewCursor()
        if doc.isReadonly() or not cursor.isCollapsed():
            return 'held'
        command = text.strip().lower().rstrip('.!?') if not literal_spacing else ''
        if operation is not None:
            command = {'line': 'new line', 'paragraph': 'new paragraph'}.get(operation, '')
        manager = doc.UndoManager
        manager.enterUndoContext('Dictation phrase')
        try:
            bookmark(doc, begin, cursor)
            if command in ('new line', 'new paragraph'):
                cursor.Text.insertControlCharacter(cursor, 1 if command == 'new line' else 0, False)
            else:
                # Separate phrases without altering recognized words or punctuation.
                previous = cursor.Text.createTextCursorByRange(cursor)
                previous.goLeft(1, True)
                prefix = ' ' if not literal_spacing and previous.String and not previous.String[-1].isspace() and text[0] not in ',.;:!?)]}' else ''
                cursor.Text.insertString(cursor, prefix + text, False)
            cursor.collapseToEnd()
            bookmark(doc, done, cursor)
        finally:
            manager.leaveUndoContext()
        return 'inserted'


def main():
    bridge = None
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if request['action'] == 'bind':
                bridge = Bridge(request['port'], request['window'], request['token'], request['recovering'])
                result = 'bound'
            elif request['action'] == 'check':
                result = bridge.delivery_state(request['id'])
            elif request['action'] == 'finish_words':
                result = bridge.finish_words(request['id'], request['count'], request.get('scheme', 'word'))
            else:
                result = bridge.insert(request['id'], request['text'], request.get('literal_spacing', False), request.get('operation'))
            response = {'result': result}
        except Exception as error:
            response = {'error': str(error)}
        print(json.dumps(response), flush=True)


if __name__ == '__main__':
    main()
