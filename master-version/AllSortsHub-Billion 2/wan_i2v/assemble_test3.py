#!/usr/bin/env python3
"""Assemble only shots 1-3 into a short review video.

This reuses the production assembler so the preview has the same normalization,
audio mixing, captions, and encoding pipeline as the final episode.
"""
from pathlib import Path
import shutil
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import assemble_episode as ae


def main():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise SystemExit("ffmpeg and ffprobe are required")

    ae.shots = ae.shots[:3]
    ae.TOTAL = sum(float(s["duration"]) for s in ae.shots)
    out = ae.OUT / "AllSortsHub_Episode_01_WAN_TEST3.mp4"

    with tempfile.TemporaryDirectory(prefix="wan_test3_") as td:
        td = Path(td)
        normalized = []
        for shot in ae.shots:
            n = int(shot["id"] if "id" in shot else shot["shot"])
            target = float(shot["duration"])
            target_file = td / f"shot_{n:02d}.mp4"
            parts = ae.source_parts(n)
            ae.normalize(parts, target, target_file)
            normalized.append(target_file)

        concat_file = td / "concat.txt"
        concat_file.write_text("".join(f"file '{p.as_posix()}'\n" for p in normalized))
        picture = td / "picture.mp4"
        ae.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", picture])

        mixed = td / "mixed.mp4"
        ae.add_audio(picture, mixed)
        ae.burn_captions(mixed, out)

    print(f"Created test video: {out}")


if __name__ == "__main__":
    main()
