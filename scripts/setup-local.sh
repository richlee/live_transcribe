#!/usr/bin/env bash
# --prepare downloads/builds missing dependencies; --offline only validates.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_dir"
mode="${1:---offline}"
if [[ "$mode" != --offline && "$mode" != --prepare ]]; then
    echo 'Usage: bash scripts/setup-local.sh [--offline|--prepare]' >&2
    exit 2
fi
for command_name in git cmake ffmpeg pkg-config flatpak xdotool parec /usr/bin/python3; do
    if ! command -v "$command_name" >/dev/null; then
        echo "Missing $command_name. See docs/DESKTOP.md for system packages." >&2
        exit 1
    fi
done
pkg-config --exists openblas
/usr/bin/python3 - <<'PY'
import gi, uno, venv
gi.require_version('Gtk', '3.0')
gi.require_version('Keybinder', '3.0')
from gi.repository import Gtk, Keybinder
print('System Python, GTK, Keybinder and UNO are available.')
PY
flatpak info org.libreoffice.LibreOffice >/dev/null
mkdir -p .local
source_dir=.local/whisper.cpp
revision=4afec37b797ab531aaf363208d79d541fbc17ff4
if [[ "$mode" == --prepare ]]; then
    if [[ ! -d .local/venv ]]; then
        /usr/bin/python3 -m venv .local/venv
    fi
    if ! .local/venv/bin/python -c 'import webrtcvad; import importlib.metadata as m; assert m.version("webrtcvad-wheels") == "2.0.14"' 2>/dev/null; then
        .local/venv/bin/python -m pip install -r requirements-live.txt
    fi
    if [[ ! -d "$source_dir" ]]; then
        git clone https://github.com/ggml-org/whisper.cpp.git "$source_dir"
        git -C "$source_dir" checkout "$revision"
    fi
    if [[ "$(git -C "$source_dir" rev-parse HEAD)" != "$revision" ]]; then
        echo 'Existing Whisper checkout differs from pinned revision; leaving it untouched.' >&2
        exit 1
    fi
    if [[ ! -x "$source_dir/build-blas/bin/whisper-cli" || ( ! -f "$source_dir/models/ggml-tiny.en-q5_0.bin" && ! -x "$source_dir/build-blas/bin/whisper-quantize" ) ]]; then
        cmake -S "$source_dir" -B "$source_dir/build-blas" -DCMAKE_BUILD_TYPE=Release \
            -DGGML_NATIVE=ON -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS \
            -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_SERVER=OFF
        cmake --build "$source_dir/build-blas" --target whisper-cli whisper-quantize -j 1
    fi
    if [[ ! -f "$source_dir/models/ggml-tiny.en-q5_0.bin" ]]; then
        if [[ ! -f "$source_dir/models/ggml-tiny.en.bin" ]]; then
            bash "$source_dir/models/download-ggml-model.sh" tiny.en
        fi
        echo '921e4cf8686fdd993dcd081a5da5b6c365bfde1162e72b08d75ac75289920b1f  .local/whisper.cpp/models/ggml-tiny.en.bin' | sha256sum --check
        "$source_dir/build-blas/bin/whisper-quantize" "$source_dir/models/ggml-tiny.en.bin" "$source_dir/models/ggml-tiny.en-q5_0.bin" q5_0
    fi
fi
.local/venv/bin/python -c 'import webrtcvad; import importlib.metadata as m; assert m.version("webrtcvad-wheels") == "2.0.14"'
[[ -x "$source_dir/build-blas/bin/whisper-cli" ]]
[[ "$(git -C "$source_dir" rev-parse HEAD)" == "$revision" ]]
echo '3d11806c1fec19226f210c5286f58ef8c0e883c8b1f6a8a9c695c3b1fee35ce8  .local/whisper.cpp/models/ggml-tiny.en-q5_0.bin' | sha256sum --check
echo 'Local setup verified. Install the launcher: python3 scripts/install-desktop.py'
