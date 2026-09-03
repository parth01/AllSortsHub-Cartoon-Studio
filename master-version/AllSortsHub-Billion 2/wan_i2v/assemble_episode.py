#!/usr/bin/env python3
"""Assemble Wan 2.2 I2V clips into Episode 1.

Each shot may be supplied as either generated/shot_XX.mp4 or, for shots longer
than the 5-second generation target, generated/shot_XXa.mp4 + shot_XXb.mp4.
If an old short shot_XX.mp4 exists alongside a/b segments, the segmented clips
are preferred when they provide enough duration for the manifest target.
"""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "wan_i2v" / "generated"
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
MANIFEST = ROOT / "wan_i2v" / "manifest.json"

with MANIFEST.open() as f:
    manifest = json.load(f)

W, H = 1920, 1080
shots = manifest["shots"]
TOTAL = sum(float(s["duration"]) for s in shots)


def run(cmd):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(x) for x in cmd], check=True)


def ffprobe_duration(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], capture_output=True, text=True, check=True)
    return float(p.stdout.strip())


def source_parts(n, target):
    single = GEN / f"shot_{n:02d}.mp4"
    a = GEN / f"shot_{n:02d}a.mp4"
    b = GEN / f"shot_{n:02d}b.mp4"

    # Prefer segmented generation when present. This prevents an old 2-second
    # shot_XX.mp4 from masking the newer 5s + continuation clips.
    parts = [p for p in (a, b) if p.exists() and p.stat().st_size]
    if parts:
        # If both segments exist, use both. If only a exists and it is long
        # enough for the target, it is also a valid source.
        if len(parts) == 2:
            return parts
        if ffprobe_duration(parts[0]) + 0.05 >= target:
            return parts

    if single.exists() and single.stat().st_size:
        return [single]

    raise SystemExit(f"Missing Wan clip for shot {n:02d}. Expected {single.name} or {a.name} + {b.name}.")


def prepare_source(parts, out):
    if len(parts) == 1:
        return parts[0], ffprobe_duration(parts[0])
    joined = out.with_name(out.stem + "_joined.mp4")
    lst = out.with_name(out.stem + "_parts.txt")
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    return joined, ffprobe_duration(joined)


def normalize(n, target, out):
    parts = source_parts(n, target)
    src, src_dur = prepare_source(parts, out)
    if src_dur + 0.05 < target:
        raise SystemExit(f"Wan source for {out.stem} is only {src_dur:.2f}s but needs {target:.2f}s. Found: {', '.join(p.name for p in parts)}")
    run(["ffmpeg", "-y", "-i", src, "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1", "-r", "30", "-t", f"{target:.3f}", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", out])
    return src_dur


def add_audio(picture, out):
    audio = ROOT / "03_audio"
    sfx_dir = audio / "sfx"
    dialogue = audio / "dialogue.mp3"
    music = [audio / "score_01_comedy.mp3", audio / "score_02_noir.mp3", audio / "score_03_sad.mp3"]
    sfx_events = [("01_phone_deposit.mp3",0.8),("02_snap_zoom.mp3",20.5),("03_record_scratch.mp3",34.0),("04_cha_ching.mp3",52.0),("05_car_rev.mp3",62.0),("06_error_alert.mp3",104.0),("07_press_flashes.mp3",110.0),("08_stand_explode.mp3",139.0),("09_sad_slide_whistle.mp3",143.0),("10_dramatic_hit.mp3",149.0)]
    required = [dialogue, *music] + [sfx_dir / n for n,_ in sfx_events if _ < TOTAL]
    missing = [p for p in required if not p.exists()]
    if missing:
        raise SystemExit("Missing required audio: " + ", ".join(map(str, missing)))

    inputs = ["-i", str(dialogue)]
    for p in music: inputs += ["-stream_loop", "-1", "-i", str(p)]
    active = [(n,t) for n,t in sfx_events if t < TOTAL]
    for n,_ in active: inputs += ["-i", str(sfx_dir/n)]

    fc = [f"[1:a]aresample=48000,volume=1.15,apad=pad_dur={TOTAL:.3f}[dialogue]"]
    comedy_end=min(76,TOTAL); fc.append(f"[2:a]atrim=duration={comedy_end},asetpts=N/SR/TB,volume=0.20[comedy]")
    labels=["[dialogue]","[comedy]"]
    if TOTAL > 76:
        noir_d=min(60,TOTAL-76); fc += [f"[3:a]atrim=duration={noir_d},asetpts=N/SR/TB,volume=0.18[noir0]", "[noir0]adelay=76000|76000[noir]"]; labels.append("[noir]")
    if TOTAL > 136:
        sad_d=min(25,TOTAL-136); fc += [f"[4:a]atrim=duration={sad_d},asetpts=N/SR/TB,volume=0.20[sad0]", "[sad0]adelay=136000|136000[sad]"]; labels.append("[sad]")
    for idx,(name,t) in enumerate(active,5):
        delay=int(t*1000); lab=f"[s{idx}]"; fc.append(f"[{idx}:a]aresample=48000,volume=0.75,adelay={delay}|{delay}{lab}"); labels.append(lab)
    fc.append("".join(labels)+f"amix=inputs={len(labels)}:duration=longest:dropout_transition=2,alimiter=limit=0.95[aout]")
    run(["ffmpeg","-y","-i",picture,*inputs,"-filter_complex",";".join(fc),"-map","0:v","-map","[aout]","-c:v","copy","-c:a","aac","-b:a","192k","-t",f"{TOTAL:.3f}","-movflags","+faststart",out])


def burn_captions(video, out):
    captions=ROOT/"captions.srt"
    style="FontName=DejaVu Sans,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,MarginV=55,Alignment=2"
    run(["ffmpeg","-y","-i",video,"-vf",f"subtitles='{captions.as_posix()}':force_style='{style}'","-c:v","libx264","-preset","medium","-crf","18","-c:a","copy","-movflags","+faststart",out])


def make_vertical(master,out):
    run(["ffmpeg","-y","-i",master,"-vf","crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920:flags=lanczos,format=yuv420p","-c:v","libx264","-preset","medium","-crf","19","-c:a","aac","-b:a","192k","-movflags","+faststart",out])


def main():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"): raise SystemExit("ffmpeg and ffprobe are required")
    with tempfile.TemporaryDirectory(prefix="wan_episode_") as td:
        td=Path(td); normalized=[]
        for shot in shots:
            n=int(shot["id"]); target=float(shot["duration"]); out=td/f"shot_{n:02d}.mp4"; src_dur=normalize(n,target,out); normalized.append(out); print(f"WAN: shot_{n:02d} {src_dur:.2f}s source -> {target:.2f}s final")
        concat_file=td/"concat.txt"; concat_file.write_text("".join(f"file '{p.as_posix()}'\n" for p in normalized)); picture=td/"picture.mp4"; run(["ffmpeg","-y","-f","concat","-safe","0","-i",concat_file,"-c","copy",picture]); mixed=td/"mixed.mp4"; add_audio(picture,mixed); master=OUT/"AllSortsHub_Episode_01_WAN_MASTER.mp4"; burn_captions(mixed,master); vertical=OUT/"AllSortsHub_Episode_01_WAN_VERTICAL_9x16.mp4"; make_vertical(master,vertical); print(f"Done. WAN master: {master}")

if __name__=="__main__": main()
