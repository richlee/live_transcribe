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
    parser.add_argument("--model", choices=("tiny.en", "tiny.en-q5_0", "base.en"), default="tiny.en")
    parser.add_argument("--threads", type=int, choices=(1, 2, 4), default=2)
    parser.add_argument("--build", choices=("build", "build-blas"), default="build")
    parser.add_argument("--audio-ctx", type=int, default=0,
                        help="Experimental encoder context (0=default; 50 units per second)")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    engine = root / ".local/whisper.cpp"
    binary = engine / args.build / "bin/whisper-cli"
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
    if not 0 <= args.audio_ctx <= 1500:
        parser.error("Audio context must be between 0 and 1500")
    if args.audio_ctx and duration > args.audio_ctx / 50:
        parser.error("Experimental context must cover the entire clip; use a shorter input")
    os.umask(0o077)
    results = root / ".local/benchmarks"
    results.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix=f"{args.model}-t{args.threads}-", dir=results))
    command = [str(binary), "-m", str(model), "-f", str(args.audio.resolve()),
               "-l", "en", "-t", str(args.threads), "-bs", "1", "-bo", "1",
               "-ac", str(args.audio_ctx),
               "-otxt", "-of", str(run / "transcript")]
    env = os.environ.copy()
    env["OPENBLAS_NUM_THREADS"] = str(args.threads)
    env["OMP_NUM_THREADS"] = str(args.threads)
    started = time.perf_counter()
    with (run / "engine.log").open("w") as log:
        completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env)
    elapsed = time.perf_counter() - started
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    metrics = {
        "model": args.model, "threads": args.threads, "beam_size": 1, "best_of": 1,
        "build": args.build, "audio_ctx": args.audio_ctx,
        "openblas_num_threads": args.threads, "omp_num_threads": args.threads,
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
