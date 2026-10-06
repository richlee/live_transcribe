"""Small XFCE/X11 tray controller. GTK stays outside the recognition venv."""
import argparse
import fcntl
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Keybinder', '3.0')
from gi.repository import GLib, Gtk, Keybinder

from .desktop_state import DesktopState

ROOT = Path(__file__).resolve().parents[1]


def ensure_writer_connection(port, log):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.2):
            return None  # Reuse the running Writer instance without invoking it again.
    except OSError:
        return subprocess.Popen(['flatpak', 'run', '--env=GTK_MODULES=',
            'org.libreoffice.LibreOffice', '--nologo',
            f'--accept=socket,host=127.0.0.1,port={port};urp;StarOffice.ServiceManager'],
            stdout=log, stderr=log)


class Tray:
    def __init__(self, shortcut='<Control><Alt>space', port=20027):
        self.shortcut, self.port = shortcut, port
        self.state = DesktopState()
        self.child = None
        self.writer_process = None
        self.buffer = b''
        self.want_listening = False
        self.quitting = False
        self.stopping_at = None
        self.log = None
        self.menu = Gtk.Menu()
        self.status = Gtk.MenuItem(label='Ready')
        self.status.set_sensitive(False)
        self.menu.append(self.status)
        self.toggle_item = self.item('Start dictation / select Writer', self.toggle)
        self.stop_item = self.item('Stop session — keep tray running', self.stop)
        self.item('Open latest session folder', self.open_session)
        self.item('Instructions', lambda *_: subprocess.Popen(['xdg-open', str(ROOT / 'docs/DESKTOP.md')]))
        self.item('Quit app — remove tray icon', self.quit)
        self.menu.show_all()
        self.icon = Gtk.StatusIcon()
        self.icon.set_title('Live Transcribe')
        self.icon.connect('activate', self.toggle)
        self.icon.connect('popup-menu', self.popup)
        Keybinder.init()
        self.bound = Keybinder.bind(shortcut, self.toggle)
        if not self.bound:
            self.dialog(f'Could not bind {shortcut}. It may already be in use. Tray menu controls remain available. Relaunch with --shortcut to choose another combination.')
        GLib.timeout_add(50, self.poll)
        GLib.timeout_add_seconds(3, self.check_tray)
        self.refresh()

    def item(self, label, callback):
        item = Gtk.MenuItem(label=label)
        item.connect('activate', callback)
        self.menu.append(item)
        return item

    def dialog(self, message):
        dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK, text='Live Transcribe')
        dialog.format_secondary_text(message)
        dialog.connect('response', lambda window, _response: window.destroy())
        dialog.show_all()

    def check_tray(self):
        if not self.icon.is_embedded():
            self.dialog('No tray host is visible. Add the XFCE Status Tray Plugin to your panel. The global shortcut still works.')
        return False

    def popup(self, icon, button, timestamp):
        self.menu.popup(None, None, Gtk.StatusIcon.position_menu, icon, button, timestamp)

    def refresh(self):
        label = self.state.label
        # Local vector icons: colors plus distinct symbols for each state.
        filename = ROOT / 'assets' / f"{label.lower().replace(' ', '-')}.svg"
        self.icon.set_from_file(str(filename))
        self.icon.set_tooltip_text(f'Live Transcribe — {label}\n{self.state.detail}\nToggle: {self.shortcut}')
        self.status.set_label(f'{label} — {self.state.detail}')
        self.toggle_item.set_label('Pause listening' if self.want_listening else ('Resume listening' if self.child else 'Start dictation / select Writer'))
        self.toggle_item.set_sensitive(self.state.phase not in ('starting', 'stopping'))
        self.stop_item.set_sensitive(self.child is not None and self.state.phase != 'stopping')

    def start(self):
        self.state = DesktopState(phase='starting')
        self.want_listening = True
        self.stopping_at = None
        self.buffer = b''
        local = ROOT / '.local'
        local.mkdir(exist_ok=True, mode=0o700)
        self.log = (local / 'desktop.log').open('w')
        # Suppress the inherited optional sound module only for Flatpak Writer.
        self.writer_process = ensure_writer_connection(self.port, self.log)
        command = [str(ROOT / '.local/venv/bin/python'), '-m', 'live_transcribe',
                   '--writer', '--writer-port', str(self.port), '--no-text', '--control-stdin', '--start-paused']
        self.child = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT)
        os.set_blocking(self.child.stdout.fileno(), False)
        self.refresh()

    def send(self, action):
        try:
            self.child.stdin.write((action + '\n').encode())
            self.child.stdin.flush()
        except (BrokenPipeError, OSError):
            self.state.error = 'Worker stopped; check the latest session and desktop.log.'

    def toggle(self, *_):
        if self.quitting or self.stopping_at or self.state.phase in ('starting', 'stopping'):
            return
        if not self.child:
            try:
                self.start()
            except Exception as error:
                self.state.phase = 'ready'
                self.state.error = str(error)
                self.dialog(str(error))
                self.refresh()
            return
        self.want_listening = not self.want_listening
        self.send('p')
        self.refresh()

    def stop(self, *_):
        if self.child and self.state.phase != 'stopping':
            if self.state.phase == 'starting':
                # SIGTERM also interrupts document selection; no audio has started.
                self.child.terminate()
            else:
                self.send('q')
            self.want_listening = False
            self.state.phase = 'stopping'
            self.stopping_at = time.monotonic()
            self.refresh()

    def quit(self, *_):
        self.quitting = True
        if self.child:
            self.stop()
        else:
            Gtk.main_quit()

    def open_session(self, *_):
        path = Path(self.state.session) if self.state.session else ROOT / '.local/sessions'
        if path.is_dir():
            subprocess.Popen(['xdg-open', str(path)])

    def consume(self, line):
        self.state.consume(line)
        if self.stopping_at and not line.startswith('[STOPPED]'):
            self.state.phase = 'stopping'
            self.state.listening = False
        if line.startswith('[PAUSED]') and self.state.phase != 'stopping' and self.want_listening:
            # Only the initial paused acknowledgement starts capture. Later pauses reflect commands.
            if 'Capture is off;' in line:
                self.send('p')
        if line.startswith('[ERROR]') and not self.quitting:
            self.dialog(line.partition('] ')[2])
        self.refresh()

    def poll(self):
        if self.child:
            while True:
                try:
                    data = os.read(self.child.stdout.fileno(), 8192)
                except BlockingIOError:
                    break
                if not data:
                    break
                self.buffer += data
                while b'\n' in self.buffer:
                    raw, self.buffer = self.buffer.split(b'\n', 1)
                    line = raw.decode(errors='replace')
                    if self.log:
                        self.log.write(line + '\n')
                        self.log.flush()
                    self.consume(line)
            result = self.child.poll()
            if result is not None:
                if self.buffer:
                    self.consume(self.buffer.decode(errors='replace'))
                    self.buffer = b''
                self.child.stdin.close()
                self.child.stdout.close()
                self.child = None
                self.want_listening = False
                self.state.phase, self.state.listening, self.state.processing = 'ready', False, False
                if result and not self.state.error and not self.stopping_at:
                    self.state.error = 'Worker failed; inspect .local/desktop.log and the session transcript.'
                    self.dialog(self.state.error)
                if self.log:
                    self.log.close()
                    self.log = None
                self.refresh()
                self.stopping_at = None
                if self.quitting:
                    Gtk.main_quit()
            elif self.stopping_at and time.monotonic() - self.stopping_at > 120:
                # A stuck worker must not hold the tray forever. Durable audio remains recoverable.
                self.child.send_signal(signal.SIGINT)
                self.stopping_at = time.monotonic()
        return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shortcut', default='<Control><Alt>space')
    parser.add_argument('--writer-port', type=int, default=20027)
    args = parser.parse_args()
    if os.environ.get('XDG_SESSION_TYPE', 'x11') != 'x11' or not os.environ.get('DISPLAY'):
        parser.error('The current desktop prototype requires XFCE/X11')
    os.umask(0o077)
    local = ROOT / '.local'
    local.mkdir(exist_ok=True, mode=0o700)
    lock = (local / 'tray.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('Live Transcribe is already running in the tray.', file=sys.stderr)
        return
    tray = Tray(args.shortcut, args.writer_port)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, tray.quit)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, tray.quit)
    try:
        Gtk.main()
    finally:
        if tray.bound:
            Keybinder.unbind(args.shortcut)
        lock.close()


if __name__ == '__main__':
    main()
