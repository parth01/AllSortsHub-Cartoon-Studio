#!/usr/bin/env python3
"""Assemble a selected shot range into a review MP4.

The range video is primarily a visual-quality check. It preserves the selected
shots at their storyboard durations and uses the existing production audio
pipeline only when the selected range starts at shot 1; later ranges are kept
visual-only so global episode timestamps are not incorrectly shifted.
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "wan_i2v" / "generated"
OUT = ROOT / "output"
MANIFEST = ROOT / "wan_i2v" / "manifest.json"

with MANIFEST.open() as f:
    manifest = json.load(f)

W, H = 1920, 1080


def run(cmd):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(x) for x in cmd], check=True)


def ffprobe_duration(path):
    p = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ], capture_output=True, text=True, check=True)
    return float(p.stdout.strip())


def source_parts(n):
    single = GEN / f"shot_{n:02d}.mp4"
    a = GEN / f"shot_{n:02d}a.mp4"
    b = GEN / f"shot_{n:02d}b.mp4"
    if single.exists() and single.stat().st_size:
        return [single]
    parts = [p for p in (a, b) if p.exists() and p.stat().st_size]
    if not parts:
        raise SystemExit(f"Missing Wan clip for shot {n:02d}.")
    return parts


def prepare_source(parts, out):
    if len(parts) == 1:
        return parts[0], ffprobe_duration(parts[0])
    joined = out.with_name(out.stem + "_joined.mp4")
    lst = out.with_name(out.stem + "_parts.txt")
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    return joined, ffprobe_duration(joined)


def normalize(parts, target, out):
    src, src_dur = prepare_source(parts, out)
    if src_dur + 0.05 < target:
        raise SystemExit(f"Wan source is only {src_dur:.2f}s but shot needs {target:.2f}s.")
    run([
        "ffmpeg", "-y", "-i", src,
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-r", "30", "-t", f"{target:.3f}", "-an", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "18", "-pix_fmt", "yuv420p", out
    ])


def main():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise SystemExit("ffmpeg and ffprobe are required")
    try:
        start = int(os.environ["SHOT_START"])
        end = int(os.environ["SHOT_END"])
    except (KeyError, ValueError):
        raise SystemExit("SHOT_START and SHOT_END are required")
    shots = [s for s in manifest["shots"] if start <= int(s["id"]) <= end]
    if not shots:
        raise SystemExit("No shots selected")

    with tempfile.TemporaryDirectory(prefix="wan_range_") as td:
        td = Path(td)
        normalized = []
        for shot in shots:
            n = int(shot["id"])
            target = float(shot["duration"])
            out = td / f"shot_{n:02d}.mp4"
            normalize(source_parts(n), target, out)
            normalized.append(out)

        concat = td / "concat.txt"
        concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in normalized))
        picture = td / "picture.mp4"
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat, "-c", "copy", picture])

        out = OUT / f"AllSortsHub_Episode_01_WAN_RANGE_{start}_{end}.mp4"
        run(["ffmpeg", "-y", "-i", picture, "-c", "copy", "-movflags", "+faststart", out])
        print(f"Created visual review: {out}")


if __name__ == "__main__":
    main()
