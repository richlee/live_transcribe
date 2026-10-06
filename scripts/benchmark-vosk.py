#!/usr/bin/env python3
"""Benchmark local Vosk recognition, retaining only final text in local storage."""
import argparse
import json
import os
from pathlib import Path
import resource
import tempfile
import time
import wave


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    model_path = root / ".local/vosk-model-small-en-us-0.15"
    if not model_path.is_dir():
        parser.error("Small English Vosk model is not installed")
    with wave.open(str(args.audio), "rb") as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getcomptype()) != (1, 2, 16000, "NONE"):
            parser.error("Expected mono 16-bit PCM WAV at 16000 Hz")
        duration = audio.getnframes() / audio.getframerate()
        if duration <= 0:
            parser.error("Recording is empty")
        os.umask(0o077)
        results = root / ".local/benchmarks"
        results.mkdir(parents=True, exist_ok=True)
        run = Path(tempfile.mkdtemp(prefix="vosk-", dir=results))
        started = time.perf_counter()
        from vosk import Model, KaldiRecognizer, SetLogLevel
        SetLogLevel(-1)
        model = Model(str(model_path))
        recognizer = KaldiRecognizer(model, 16000)
        phrases = []
        while data := audio.readframes(4000):
            if recognizer.AcceptWaveform(data):
                phrases.append(json.loads(recognizer.Result()).get("text", ""))
        phrases.append(json.loads(recognizer.FinalResult()).get("text", ""))
        (run / "transcript.txt").write_text("\n".join(p for p in phrases if p) + "\n")
        elapsed = time.perf_counter() - started
    metrics = {
        "model": model_path.name, "audio_seconds": round(duration, 3),
        "wall_seconds": round(elapsed, 3), "real_time_factor": round(elapsed / duration, 3),
        "peak_process_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
        "exit_code": 0,
    }
    (run / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))
    print(f"Private final transcript: {run / 'transcript.txt'}")


if __name__ == "__main__":
    main()
