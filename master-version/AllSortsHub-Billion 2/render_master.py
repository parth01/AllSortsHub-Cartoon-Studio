#!/usr/bin/env python3
"""Render the Master Version cartoon episode using only GitHub Actions-safe tools.

Uses the existing illustrated storyboard frames as high-quality keyframes, then adds
cinematic camera motion, cuts, color treatment, captions, music, dialogue and SFX.
No paid AI/video API is required.
"""
from __future__ import annotations
import subprocess, shutil, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STORY = ROOT / "01_storyboard"
AUDIO = ROOT / "03_audio"
SFX = AUDIO / "sfx"
CAPTIONS = ROOT / "captions.srt"
OUT = ROOT / "output"
WORK = ROOT / "build"
W, H, FPS = 1920, 1080, 30
DURATIONS = [9,10,5,9,9,8,9,10,10,8,10,10,10,10,10,9,8]


def run(*args: str) -> None:
    print("+", " ".join(map(str, args)))
    subprocess.run([str(x) for x in args], check=True)


def ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise SystemExit("ffmpeg is required")
    return exe


def shot_path(i: int) -> Path:
    p = STORY / f"shot_{i:02d}.jpg"
    if p.exists(): return p
    # fallback for the PNG storyboard exports kept elsewhere in master-version
    alt = ROOT.parent / f"storyboard_shots_{'01-06' if i <= 6 else '07-12'}" / f"shot_{i:02d}.png"
    if alt.exists(): return alt
    raise FileNotFoundError(p)


def make_shot_clips() -> list[Path]:
    WORK.mkdir(parents=True, exist_ok=True)
    clips=[]
    # Different motion patterns stop the episode from feeling like a slideshow.
    patterns=[
        ("1.03","1.09","+10","-5"),("1.10","1.03","-8","+4"),("1.00","1.00","0","0"),
        ("1.04","1.11","+7","0"),("1.10","1.04","-7","0"),("1.02","1.12","0","-5"),
        ("1.12","1.04","-8","+3"),("1.04","1.13","+8","-4"),("1.13","1.04","-6","0"),
        ("1.03","1.12","+7","+3"),("1.12","1.04","-7","-3"),("1.04","1.12","+6","0"),
        ("1.13","1.03","-9","+2"),("1.03","1.13","+9","-2"),("1.10","1.03","-5","0"),
        ("1.03","1.16","+3","-3"),("1.16","1.00","-10","0")]
    for i,dur in enumerate(DURATIONS,1):
        src=shot_path(i); out=WORK/f"shot_{i:02d}.mp4"; clips.append(out)
        a,b,dx,dy=patterns[i-1]
        # overscale + crop gives clean 1080p motion without exposing image borders.
        frames=dur*FPS
        z=f"{a}+({b}-{a})*on/{max(frames-1,1)}"
        x=f"iw/2-(iw/zoom/2)+({dx})*sin(on/{FPS}*1.7)"
        y=f"ih/2-(ih/zoom/2)+({dy})*sin(on/{FPS}*1.3)"
        vf=(f"scale=2400:-2:force_original_aspect_ratio=increase,"
            f"crop=2400:1350,zoompan=z='{z}':x='{x}':y='{y}':d=1:s={W}x{H}:fps={FPS},"
            "format=yuv420p")
        if i in (6,16):
            vf += ",eq=contrast=1.06:saturation=1.12"
        if i in (11,12,13):
            vf += ",eq=contrast=1.12:saturation=0.82:brightness=-0.02,vignette=PI/5"
        if i==17:
            vf += ",eq=saturation=1.18:contrast=1.05"
        run(ffmpeg(),"-y","-loop","1","-i",src,"-t",str(dur),"-vf",vf,
            "-an","-c:v","libx264","-preset","veryfast","-crf","18","-movflags","+faststart",out)
    return clips


def concat(clips: list[Path]) -> Path:
    lst=WORK/"shots.txt"
    lst.write_text("\n".join(f"file '{p.as_posix()}'" for p in clips)+"\n")
    out=WORK/"picture.mp4"
    run(ffmpeg(),"-y","-f","concat","-safe","0","-i",lst,"-c","copy",out)
    return out


def add_audio(video: Path) -> Path:
    out=WORK/"master_audio.mp4"
    # Dialogue is the spine. Music beds are selected by story section and looped/trimmed.
    # SFX are short accents, delayed to the story beats described in SHOT_LIST.
    inputs=["-i",str(AUDIO/"dialogue.mp3")]
    music=[AUDIO/"score_01_comedy.mp3",AUDIO/"score_02_noir.mp3",AUDIO/"score_03_sad.mp3"]
    for p in music: inputs += ["-stream_loop","-1","-i",str(p)]
    sfx_events=[
        ("01_phone_deposit.mp3",0.8),("02_snap_zoom.mp3",20.5),("03_record_scratch.mp3",34.0),
        ("04_cha_ching.mp3",52.0),("05_car_rev.mp3",62.0),("06_error_alert.mp3",104.0),
        ("07_press_flashes.mp3",110.0),("08_stand_explode.mp3",139.0),("09_sad_slide_whistle.mp3",143.0),
        ("10_dramatic_hit.mp3",149.0)]
    for name,t in sfx_events: inputs += ["-i",str(SFX/name)]
    fc=[]
    fc.append("[0:a]aresample=48000,volume=1.15[dialogue]")
    # comedy 0-76, noir 76-136, sad 136-157
    fc += [
        "[1:a]atrim=duration=76,asetpts=N/SR/TB,volume=0.20[comedy]",
        "[2:a]atrim=duration=60,asetpts=N/SR/TB,volume=0.18[noir]",
        "[3:a]atrim=duration=25,asetpts=N/SR/TB,volume=0.20[sad]",
        "[noir]adelay=76000|76000[noird]",
        "[sad]adelay=136000|136000[sadd]",
        "[comedy]anull[comed]",
    ]
    labels=["[dialogue]","[comed]","[noird]","[sadd]"]
    for idx,(name,t) in enumerate(sfx_events,4):
        lab=f"[s{idx}]"; delay=int(t*1000)
        fc.append(f"[{idx}:a]aresample=48000,volume=0.75,adelay={delay}|{delay}{lab}")
        labels.append(lab)
    fc.append("".join(labels)+f"amix=inputs={len(labels)}:duration=first:dropout_transition=2,alimiter=limit=0.95[aout]")
    filt=";".join(fc)
    run(ffmpeg(),"-y","-i",video,*inputs,"-filter_complex",filt,"-map","0:v","-map","[aout]",
        "-c:v","copy","-c:a","aac","-b:a","192k","-shortest","-movflags","+faststart",out)
    return out


def captions(video: Path) -> Path:
    out=OUT/"AllSortsHub_Episode_01_MASTER.mp4"
    # Burn captions into the master so playback never depends on a subtitle track.
    # force_style keeps them readable on phones and TVs.
    style="FontName=DejaVu Sans,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,MarginV=55,Alignment=2"
    vf=f"subtitles='{CAPTIONS.as_posix().replace(chr(39),chr(92)+chr(39))}':force_style='{style}'"
    run(ffmpeg(),"-y","-i",video,"-vf",vf,"-c:v","libx264","-preset","medium","-crf","18",
        "-c:a","copy","-movflags","+faststart",out)
    return out


def make_vertical(master: Path) -> None:
    # 9:16 crop centered on the action; captions are already burned in.
    out=OUT/"AllSortsHub_Episode_01_VERTICAL_9x16.mp4"
    vf="crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920:flags=lanczos,format=yuv420p"
    run(ffmpeg(),"-y","-i",master,"-vf",vf,"-c:v","libx264","-preset","medium","-crf","19","-c:a","aac","-b:a","192k","-movflags","+faststart",out)


def make_shorts(master: Path) -> None:
    # High-retention clips matching the launch package's strongest beats.
    shorts=[
        ("01_The_Notification",0,24),
        ("02_Do_NOT_Spend_It",24,50),
        ("03_One_Of_Everything",50,80),
        ("04_Change_The_World",80,104),
        ("05_What_Did_You_Learn",129,151),
    ]
    for name,start,length in shorts:
        out=OUT/f"Short_{name}.mp4"
        vf="crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920:flags=lanczos,format=yuv420p"
        run(ffmpeg(),"-y","-ss",str(start),"-t",str(length),"-i",master,"-vf",vf,"-c:v","libx264","-preset","medium","-crf","19","-c:a","aac","-b:a","192k","-movflags","+faststart",out)


def main():
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    if WORK.exists(): shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    clips=make_shot_clips()
    picture=concat(clips)
    mixed=add_audio(picture)
    master=captions(mixed)
    make_vertical(master)
    make_shorts(master)
    # Keep the repository clean: Actions uploads output/ only.
    print("\nRENDER COMPLETE")
    for p in sorted(OUT.glob("*.mp4")):
        print(p.name, p.stat().st_size)

if __name__ == "__main__":
    main()
