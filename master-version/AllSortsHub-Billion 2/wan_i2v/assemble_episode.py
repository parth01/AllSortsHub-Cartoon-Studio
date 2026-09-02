#!/usr/bin/env python3
"""Assemble Wan 2.2 I2V clips into Episode 1 with the existing audio/captions.

Expected generated clips:
  wan_i2v/generated/shot_01.mp4 ... shot_17.mp4

Wan clips are normalized to 1920x1080/30fps/yuv420p, trimmed/padded to the
storyboard durations, concatenated, then mixed with the existing episode audio.
No old storyboard/still renderer is used by this script.
"""
from pathlib import Path
import json
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "wan_i2v" / "generated"
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

MANIFEST = ROOT / "wan_i2v" / "manifest.json"
with MANIFEST.open() as f:
    manifest = json.load(f)

FPS = int(manifest.get("fps", 16))
W, H = 1920, 1080
shots = manifest["shots"]

def run(cmd):
    print("+", " ".join(map(str, cmd)))
    subprocess.run([str(x) for x in cmd], check=True)

def duration(path):
    p = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ], capture_output=True, text=True, check=True)
    return float(p.stdout.strip())

with tempfile.TemporaryDirectory(prefix="wan_episode_") as td:
    td = Path(td)
    normalized = []
    total = 0.0

    for shot in shots:
        n = int(shot["shot"])
        target = float(shot["duration"])
        src = GEN / f"shot_{n:02d}.mp4"
        if not src.exists() or src.stat().st_size == 0:
            raise SystemExit(f"Missing Wan clip: {src}")

        out = td / f"shot_{n:02d}.mp4"
        src_dur = duration(src)
        if src_dur + 0.05 < target:
            raise SystemExit(
                f"Wan clip {src.name} is {src_dur:.2f}s but needs {target:.2f}s. "
                "Generate a longer clip or provide a continuation clip."
            )

        # Normalize resolution/framerate/pixel format and trim to the exact
        # storyboard duration. Generated clips are intentionally silent.
        run([
            "ffmpeg", "-y", "-i", src,
            "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                   f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1",
            "-r", "30", "-t", f"{target:.3f}",
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", out
        ])
        normalized.append(out)
        total += target
        print(f"WAN: shot_{n:02d}.mp4 ({src_dur:.2f}s -> {target:.2f}s)")

    concat_file = td / "concat.txt"
    concat_file.write_text("".join(f"file '{p.as_posix()}'\n" for p in normalized))
    picture = td / "picture.mp4"
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
        "-c", "copy", picture
    ])

    dialogue = ROOT / "03_audio" / "dialogue.mp3"
    comedy = ROOT / "03_audio" / "score_01_comedy.mp3"
    noir = ROOT / "03_audio" / "score_02_noir.mp3"
    sad = ROOT / "03_audio" / "score_03_sad.mp3"
    missing = [p for p in [dialogue, comedy, noir, sad] if not p.exists()]
    if missing:
        raise SystemExit("Missing required audio: " + ", ".join(map(str, missing)))

    sfx = sorted((ROOT / "03_audio").glob("*.mp3"))
    sfx = [p for p in sfx if p.name.startswith(tuple(f"{i:02d}_" for i in range(1, 11)))]

    # Use the existing renderer's SFX naming/timing through render_master.py's
    # audio section would couple this new pipeline back to the old picture path.
    # Instead, mix the four continuous stems here; captions are burned separately.
    master = OUT / "AllSortsHub_Episode_01_WAN_MASTER.mp4"
    run([
        "ffmpeg", "-y",
        "-i", picture,
        "-i", dialogue,
        "-i", comedy,
        "-i", noir,
        "-i", sad,
        "-filter_complex",
        f"[1:a]apad=pad_dur={total:.3f},atrim=duration={total:.3f}[d];"
        f"[2:a]apad=pad_dur={total:.3f},atrim=duration={total:.3f}[c];"
        f"[3:a]apad=pad_dur={total:.3f},atrim=duration={total:.3f}[n];"
        f"[4:a]apad=pad_dur={total:.3f},atrim=duration={total:.3f}[s];"
        "[d][c][n][s]amix=inputs=4:duration=longest:dropout_transition=0:normalize=0[aout]",
        "-map", "0:v", "-map", "[aout]", "-t", f"{total:.3f}",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", master
    ])

    vertical = OUT / "AllSortsHub_Episode_01_WAN_VERTICAL_9x16.mp4"
    run([
        "ffmpeg", "-y", "-i", master,
        "-vf", "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", vertical
    ])

print(f"Done. WAN episode assembled: {master}")
print(f"Vertical version: {vertical}")
