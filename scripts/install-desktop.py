#!/usr/bin/env python3
"""Install only this project's desktop entry; source/model files stay in place."""
import argparse
from pathlib import Path


def exec_quote(value):
    # Desktop Entry Exec uses its own quoting, followed by string-value unescaping.
    value = str(value).replace('%', '%%')
    value = value.replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$')
    return '"' + value.replace('\\', '\\\\') + '"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--applications-dir', type=Path, default=Path.home() / '.local/share/applications')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.applications_dir.mkdir(parents=True, exist_ok=True)
    entry = args.applications_dir / 'live-transcribe.desktop'
    entry.write_text('[Desktop Entry]\nType=Application\nName=Live Transcribe\n'
                     'Comment=Offline English dictation into LibreOffice Writer\n'
                     f'Exec=/bin/bash {exec_quote(root / "scripts/launch-desktop.sh")}\n'
                     f'Icon={root / "assets/listening.svg"}\n'
                     'Terminal=false\nCategories=Office;\nStartupNotify=false\n')
    entry.chmod(0o644)
    print(f'Installed {entry}. Launch Live Transcribe from the applications menu.')


if __name__ == '__main__':
    main()
