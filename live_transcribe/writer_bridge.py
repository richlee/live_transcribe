"""System-Python UNO sidecar. Writes only to one explicitly selected document."""
import json
import subprocess
import sys

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
        context = resolver.resolve(f'uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext')
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

    def insert(self, identity, text):
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
        command = text.strip().lower().rstrip('.!?')
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
                prefix = ' ' if previous.String and not previous.String[-1].isspace() and text[0] not in ',.;:!?)]}' else ''
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
            else:
                result = bridge.insert(request['id'], request['text'])
            response = {'result': result}
        except Exception as error:
            response = {'error': str(error)}
        print(json.dumps(response), flush=True)


if __name__ == '__main__':
    main()
