#!/usr/bin/env python3
"""Generate Wan 2.2 I2V clips through Magic Hour's hosted API.

This backend is intended as a fallback when Hugging Face ZeroGPU quota is
exhausted. It generates each storyboard shot as one continuous clip, so a
9-second shot does not require the 5s + 4s two-call continuation pattern.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "wan_i2v" / "generated"
MANIFEST = ROOT / "wan_i2v" / "manifest.json"
PROMPTS = ROOT / "wan_i2v" / "prompts.txt"

NEGATIVE = (
    "No photorealism, no 3D CGI, no live action, no extra fingers, no duplicate "
    "limbs, no warped faces, no character morphing, no costume changes, no "
    "hairstyle changes, no background replacement, no random objects, no random "
    "text, no logos, no watermark, no scene cuts inside the generated clip, "
    "no sudden camera spins, no extreme deformation."
)
STYLE = (
    "Modern 2D cel-shaded cartoon animation, bold clean black linework, "
    "semi-flat shading, vibrant colors, expressive anime-influenced facial "
    "acting, preserve the exact character designs and environment in the input "
    "image. Natural hand-drawn animation feel. Keep faces, hair, clothing, "
    "proportions, props and background layout consistent with the source frame. "
    "Motion should be smooth, readable and physically plausible. No new "
    "characters, no redesign, no text changes."
)


def fail(msg: str) -> None:
    raise SystemExit(msg)


def prompt_for(shot_id: int, prompts_text: str) -> str:
    marker = f"SHOT {shot_id:02d} —"
    start = prompts_text.find(marker)
    if start < 0:
        fail(f"No prompt found for {marker}")
    end = prompts_text.find("\n\nSHOT ", start + 2)
    if end < 0:
        end = prompts_text.find("\n\nNEGATIVE", start + 2)
    section = prompts_text[start:end if end >= 0 else None]
    section = section.split("\n", 1)[1].strip()
    return f"{STYLE} {section} {NEGATIVE}"


def select_shots(shots, mode: str):
    if mode == "test3":
        return shots[:3]
    if mode == "full":
        return shots
    if mode == "range":
        try:
            start = int(os.environ["SHOT_START"])
            end = int(os.environ["SHOT_END"])
        except (KeyError, ValueError):
            fail("range mode requires SHOT_START and SHOT_END")
        if start < 1 or end < start or end > len(shots):
            fail(f"Invalid shot range {start}-{end}; valid range is 1-{len(shots)}")
        return [s for s in shots if start <= int(s["id"]) <= end]
    fail("Usage: magichour_generate.py [test3|full|range]")


def newest_video(before: set[Path]) -> Path | None:
    candidates = []
    for p in GEN.rglob("*.mp4"):
        if p.is_file() and p not in before and p.stat().st_size > 10000:
            candidates.append(p)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def generate(client, image: Path, prompt: str, duration: float, out: Path, shot_id: int):
    if out.exists() and out.stat().st_size > 10000:
        print(f"  exists: {out.name}; skipping", flush=True)
        return

    duration = max(3.0, min(float(duration), 15.0))
    print(
        f"  starting Magic Hour Wan 2.2 generation -> {out.name} "
        f"({duration:.2f}s, 480p)",
        flush=True,
    )

    before = {p for p in GEN.rglob("*.mp4") if p.is_file()}
    result = client.v1.image_to_video.generate(
        assets={"image_file_path": str(image)},
        end_seconds=duration,
        model="wan-2.2",
        name=f"AllSortsHub Episode 1 Shot {shot_id:02d}",
        resolution="480p",
        style={"prompt": prompt},
        wait_for_completion=True,
        download_outputs=True,
        download_directory=str(GEN),
    )
    print(f"  Magic Hour result: {result!r}", flush=True)

    video = newest_video(before)
    if video is None:
        # Some SDK versions may return the downloaded path directly.
        candidates = []
        if isinstance(result, str):
            candidates.append(Path(result))
        elif isinstance(result, dict):
            for key in ("video", "video_url", "url", "path", "output"):
                value = result.get(key)
                if isinstance(value, str):
                    candidates.append(Path(value))
        for candidate in candidates:
            if candidate.exists() and candidate.stat().st_size > 10000:
                video = candidate
                break

    if video is None or not video.exists():
        fail("Magic Hour completed but no downloadable MP4 was found in the output directory.")

    if video.resolve() != out.resolve():
        shutil.copyfile(video, out)
    if out.stat().st_size < 10000:
        fail(f"Generated video is unexpectedly small: {out}")
    print(f"  downloaded {out.name} ({out.stat().st_size} bytes)", flush=True)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    token = os.environ.get("MAGIC_HOUR_API_KEY", "").strip()
    if not token:
        fail("MAGIC_HOUR_API_KEY is missing. Add it as a GitHub Actions secret.")

    try:
        from magic_hour import Client
    except ImportError:
        fail("magic_hour is not installed")

    with MANIFEST.open() as f:
        manifest = json.load(f)
    prompts_text = PROMPTS.read_text()
    shots = select_shots(manifest["shots"], mode)

    GEN.mkdir(parents=True, exist_ok=True)
    print("Connecting to Magic Hour API", flush=True)
    print(f"Generating {len(shots)} shot(s) in {mode} mode", flush=True)
    client = Client(token=token)

    for shot in shots:
        n = int(shot["id"])
        duration = float(shot["duration"])
        image = ROOT / shot["image"]
        if not image.exists():
            fail(f"Missing storyboard image: {image}")
        prompt = prompt_for(n, prompts_text)
        # Magic Hour can generate the complete storyboard duration in one call.
        generate(client, image, prompt, duration, GEN / f"shot_{n:02d}.mp4", n)

    print("Magic Hour generation complete.", flush=True)


if __name__ == "__main__":
    main()
