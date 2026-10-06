#!/usr/bin/env python3
"""Measure one offline recognition run; keep speech and logs in ignored storage."""
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import tempfile
import time
import wave


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    parser.add_argument("--model", choices=("tiny.en", "base.en"), default="tiny.en")
    parser.add_argument("--threads", type=int, choices=(1, 2, 4), default=2)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    engine = root / ".local/whisper.cpp"
    binary = engine / "build/bin/whisper-cli"
    model = engine / f"models/ggml-{args.model}.bin"
    for path in (args.audio, binary, model):
        if not path.is_file():
            parser.error(f"Missing file: {path}")
    with wave.open(str(args.audio), "rb") as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
            parser.error("Expected mono 16-bit PCM WAV at 16000 Hz")
        duration = audio.getnframes() / audio.getframerate()
    if duration <= 0:
        parser.error("Recording is empty")
    os.umask(0o077)
    results = root / ".local/benchmarks"
    results.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix=f"{args.model}-t{args.threads}-", dir=results))
    command = [str(binary), "-m", str(model), "-f", str(args.audio.resolve()),
               "-l", "en", "-t", str(args.threads), "-bs", "1", "-bo", "1",
               "-otxt", "-of", str(run / "transcript")]
    started = time.perf_counter()
    with (run / "engine.log").open("w") as log:
        completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    elapsed = time.perf_counter() - started
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    metrics = {
        "model": args.model, "threads": args.threads, "beam_size": 1, "best_of": 1,
        "audio_seconds": round(duration, 3), "wall_seconds": round(elapsed, 3),
        "real_time_factor": round(elapsed / duration, 3),
        "peak_child_rss_mib": round(usage.ru_maxrss / 1024, 1),
        "exit_code": completed.returncode,
    }
    (run / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))
    print(f"Private transcript and engine log: {run}")
    if completed.returncode:
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
