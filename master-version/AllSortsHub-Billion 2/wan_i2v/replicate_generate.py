#!/usr/bin/env python3
"""Generate Wan 2.2 I2V clips from GitHub using Replicate's hosted API.

The GitHub Actions workflow supplies REPLICATE_API_TOKEN. Storyboard images are
read directly from the checked-out repository and sent as data URIs, so no
local machine or image hosting is required.

For shots longer than 5 seconds, a second generation is made from the final
frame of the first generation. Outputs are written to wan_i2v/generated/.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

API = "https://api.replicate.com/v1/models/wan-video/wan-2.2-i2v-a14b/predictions"
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


def post_json(payload: dict) -> dict:
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        fail("REPLICATE_API_TOKEN GitHub secret is required.")
    body = json.dumps(payload).encode()
    req = Request(API, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "wait=60",
    })
    with urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())


def get_json(url: str) -> dict:
    token = os.environ["REPLICATE_API_TOKEN"]
    req = Request(url, headers={"Authorization": f"Bearer {token}"})
    with urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def wait_prediction(pred: dict) -> str:
    status = pred.get("status")
    if status == "succeeded":
        return output_url(pred)
    if status in {"failed", "canceled"}:
        fail(f"Replicate prediction {status}: {pred.get('error')}")
    poll = pred.get("urls", {}).get("get")
    if not poll:
        fail("Replicate response has no polling URL.")
    for _ in range(120):
        time.sleep(5)
        cur = get_json(poll)
        status = cur.get("status")
        print(f"  prediction {cur.get('id')} -> {status}", flush=True)
        if status == "succeeded":
            return output_url(cur)
        if status in {"failed", "canceled"}:
            fail(f"Replicate prediction {status}: {cur.get('error')}")
    fail("Timed out waiting for Replicate prediction.")


def output_url(pred: dict) -> str:
    out = pred.get("output")
    if isinstance(out, str):
        return out
    if isinstance(out, list) and out and isinstance(out[0], str):
        return out[0]
    if isinstance(out, dict):
        for value in out.values():
            if isinstance(value, str) and value.startswith("http"):
                return value
    fail(f"Unsupported Replicate output: {out!r}")


def image_data_uri(path: Path) -> str:
    raw = base64.b64encode(path.read_bytes()).decode()
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64,{raw}"


def download(url: str, path: Path) -> None:
    req = Request(url)
    with urlopen(req, timeout=120) as r:
        path.write_bytes(r.read())


def extract_last_frame(video: Path, image: Path) -> None:
    subprocess.run([
        "ffmpeg", "-y", "-sseof", "-0.08", "-i", str(video),
        "-frames:v", "1", "-q:v", "2", str(image)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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


def generate(image: Path, prompt: str, out: Path, seed: int) -> None:
    if out.exists() and out.stat().st_size > 10000:
        print(f"  exists: {out.name}; skipping")
        return
    payload = {"input": {
        "image": image_data_uri(image),
        "prompt": prompt,
        "seed": seed,
        "go_fast": False,
        "num_frames": 81,
        "resolution": "480p",
        "sample_shift": 5,
        "sample_steps": 30,
        "frames_per_second": 16,
    }}
    print(f"  starting Replicate generation -> {out.name}", flush=True)
    pred = post_json(payload)
    url = wait_prediction(pred)
    download(url, out)
    print(f"  downloaded {out.name} ({out.stat().st_size} bytes)", flush=True)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    with MANIFEST.open() as f:
        manifest = json.load(f)
    prompts_text = PROMPTS.read_text()
    shots = manifest["shots"]
    if mode == "test3":
        shots = shots[:3]
    elif mode != "full":
        fail("Usage: replicate_generate.py [test3|full]")

    GEN.mkdir(parents=True, exist_ok=True)
    print(f"Generating {len(shots)} shot(s) in {mode} mode", flush=True)

    for shot in shots:
        n = int(shot["id"])
        duration = float(shot["duration"])
        image = ROOT / shot["image"]
        if not image.exists():
            fail(f"Missing storyboard image: {image}")
        prompt = prompt_for(n, prompts_text)
        # Deterministic seeds keep reruns stable while still giving each shot a
        # distinct motion result.
        seed = 910000 + n
        first = GEN / f"shot_{n:02d}a.mp4" if duration > 5 else GEN / f"shot_{n:02d}.mp4"
        generate(image, prompt, first, seed)

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
            generate(frame, continuation_prompt, second, seed + 100000)
            frame.unlink(missing_ok=True)

    print("Generation complete.", flush=True)


if __name__ == "__main__":
    main()
