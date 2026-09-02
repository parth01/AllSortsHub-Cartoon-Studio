#!/usr/bin/env python3
"""Generate Wan 2.2 I2V clips through a public Hugging Face ZeroGPU Space.

This version intentionally uses a public Space instead of Replicate, so the
GitHub Actions workflow does not need a paid API token. The Space currently
used is a public Wan 2.2 14B Lightning Space with 4-8 step inference.

The free Hugging Face ZeroGPU quota is limited, so test3 should be used first.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

SPACE = "https://huggingface.co/spaces/Saravutw/WAN2.2_I2V_LIGHTNING_4-8step_custom"
API_NAME = "/generate_video"
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


def find_video(value):
    """Find a generated video path/URL in a Gradio result."""
    if isinstance(value, (str, Path)):
        text = str(value)
        if text.startswith("http://") or text.startswith("https://"):
            return text
        if Path(text).exists():
            return text
    if isinstance(value, (list, tuple)):
        for item in value:
            found = find_video(item)
            if found:
                return found
    if isinstance(value, dict):
        for key in ("video", "path", "url", "value"):
            if key in value:
                found = find_video(value[key])
                if found:
                    return found
    return None


def copy_result(result, out: Path, client):
    video = find_video(result)
    if not video:
        fail(f"Hugging Face Space returned no video file: {result!r}")
    if str(video).startswith("http"):
        with urlopen(video, timeout=180) as r:
            out.write_bytes(r.read())
    else:
        shutil.copyfile(video, out)
    if out.stat().st_size < 10000:
        fail(f"Generated video is unexpectedly small: {out}")


def generate(client, image: Path, prompt: str, duration: float, out: Path, seed: int, last_image=None):
    if out.exists() and out.stat().st_size > 10000:
        print(f"  exists: {out.name}; skipping", flush=True)
        return

    # The public Lightning Space accepts 4-8 inference steps. Four steps are
    # deliberately used here to minimize ZeroGPU time and make free testing
    # practical. The Space runs at 16 FPS and supports up to 10 seconds.
    duration = max(0.5, min(float(duration), 10.0))
    print(f"  starting Hugging Face ZeroGPU generation -> {out.name} ({duration:.2f}s)", flush=True)

    from gradio_client import handle_file

    result = client.predict(
        handle_file(str(image)),
        handle_file(str(last_image)) if last_image else None,
        prompt,
        4,
        NEGATIVE,
        duration,
        1.0,
        1.0,
        seed,
        False,
        5,
        "UniPCMultistep",
        3.0,
        16,
        False,
        True,
        api_name=API_NAME,
    )
    copy_result(result, out, client)
    print(f"  downloaded {out.name} ({out.stat().st_size} bytes)", flush=True)


def extract_last_frame(video: Path, image: Path) -> None:
    subprocess.run([
        "ffmpeg", "-y", "-sseof", "-0.08", "-i", str(video),
        "-frames:v", "1", "-q:v", "2", str(image)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    with MANIFEST.open() as f:
        manifest = json.load(f)
    prompts_text = PROMPTS.read_text()
    shots = manifest["shots"]
    if mode == "test3":
        shots = shots[:3]
    elif mode != "full":
        fail("Usage: huggingface_generate.py [test3|full]")

    try:
        from gradio_client import Client
    except ImportError:
        fail("gradio_client is not installed")

    GEN.mkdir(parents=True, exist_ok=True)
    print(f"Connecting to public Hugging Face Space: {SPACE}", flush=True)
    print(f"Generating {len(shots)} shot(s) in {mode} mode", flush=True)
    client = Client(SPACE, verbose=True)

    for shot in shots:
        n = int(shot["id"])
        duration = float(shot["duration"])
        image = ROOT / shot["image"]
        if not image.exists():
            fail(f"Missing storyboard image: {image}")
        prompt = prompt_for(n, prompts_text)
        seed = 910000 + n

        first_duration = min(duration, 5.0)
        first = GEN / f"shot_{n:02d}a.mp4" if duration > 5 else GEN / f"shot_{n:02d}.mp4"
        generate(client, image, prompt, first_duration, first, seed)

        if duration > 5:
            frame = GEN / f"shot_{n:02d}_continuation.jpg"
            extract_last_frame(first, frame)
            second = GEN / f"shot_{n:02d}b.mp4"
            continuation_prompt = (
                f"{STYLE} Continue the exact scene from the supplied final frame. "
                f"Continue naturally from the previous motion without resetting the "
                f"characters, camera, lighting, props, clothing, hair, or background. "
                f"{prompt} {NEGATIVE}"
            )
            generate(client, frame, continuation_prompt, min(duration - 5, 5.0), second, seed + 100000)
            frame.unlink(missing_ok=True)

    print("Generation complete.", flush=True)


if __name__ == "__main__":
    main()
