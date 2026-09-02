#!/usr/bin/env python3
"""Production renderer for Episode 1.

GitHub Actions-safe: existing storyboard art + cinematic motion + captions + the
bundled dialogue/music/SFX. No paid generation service is required.
"""
from __future__ import annotations
import shutil, subprocess
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
TOTAL = sum(DURATIONS)


def run(*args: str) -> None:
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run([str(x) for x in args], check=True)


def ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise SystemExit("ffmpeg is required")
    return exe


def shot_path(i: int) -> Path:
    p = STORY / f"shot_{i:02d}.jpg"
    if p.exists():
        return p
    alternatives = [
        ROOT / "storyboard" / f"shot_{i:02d}.jpg",
        ROOT.parent / "storyboard_shots_01-06" / f"shot_{i:02d}.png",
        ROOT.parent / "storyboard_shots_07-12" / f"shot_{i:02d}.png",
    ]
    for p in alternatives:
        if p.exists():
            return p
    raise FileNotFoundError(f"Missing storyboard image for shot {i:02d}")


def make_shot_clips() -> list[Path]:
    WORK.mkdir(parents=True, exist_ok=True)
    clips=[]
    patterns=[
        (1.03,1.09,10,-5),(1.10,1.03,-8,4),(1.00,1.00,0,0),
        (1.04,1.11,7,0),(1.10,1.04,-7,0),(1.02,1.12,0,-5),
        (1.12,1.04,-8,3),(1.04,1.13,8,-4),(1.13,1.04,-6,0),
        (1.03,1.12,7,3),(1.12,1.04,-7,-3),(1.04,1.12,6,0),
        (1.13,1.03,-9,2),(1.03,1.13,9,-2),(1.10,1.03,-5,0),
        (1.03,1.16,3,-3),(1.16,1.00,-10,0)]
    for i,dur in enumerate(DURATIONS,1):
        src=shot_path(i); out=WORK/f"shot_{i:02d}.mp4"; clips.append(out)
        a,b,dx,dy=patterns[i-1]
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
        if i == 17:
            vf += ",eq=saturation=1.18:contrast=1.05"
        run(ffmpeg(),"-hide_banner","-loglevel","warning","-y","-loop","1","-i",src,"-t",str(dur),
            "-vf",vf,"-an","-c:v","libx264","-preset","veryfast","-crf","18","-movflags","+faststart",out)
    return clips


def concat(clips: list[Path]) -> Path:
    lst=WORK/"shots.txt"
    lst.write_text("\n".join(f"file '{p.as_posix()}'" for p in clips)+"\n")
    out=WORK/"picture.mp4"
    run(ffmpeg(),"-hide_banner","-loglevel","warning","-y","-f","concat","-safe","0","-i",lst,"-c","copy",out)
    return out


def add_audio(video: Path) -> Path:
    """Mix the real audio stems without accidentally truncating the 2:34 video.

    The previous renderer addressed the video stream as input 0's audio. Input 0
    is the picture-only MP4, so that filtergraph had no [0:a] stream and failed.
    This version explicitly uses dialogue=input 1, music=2..4, SFX=5..14 and
    pads dialogue with silence so the final mix lasts for the whole episode.
    """
    out=WORK/"master_audio.mp4"
    music=[AUDIO/"score_01_comedy.mp3",AUDIO/"score_02_noir.mp3",AUDIO/"score_03_sad.mp3"]
    sfx_events=[
        ("01_phone_deposit.mp3",0.8),("02_snap_zoom.mp3",20.5),("03_record_scratch.mp3",34.0),
        ("04_cha_ching.mp3",52.0),("05_car_rev.mp3",62.0),("06_error_alert.mp3",104.0),
        ("07_press_flashes.mp3",110.0),("08_stand_explode.mp3",139.0),("09_sad_slide_whistle.mp3",143.0),
        ("10_dramatic_hit.mp3",149.0)]
    inputs=["-i",str(AUDIO/"dialogue.mp3")]
    for p in music:
        inputs += ["-stream_loop","-1","-i",str(p)]
    for name,_ in sfx_events:
        inputs += ["-i",str(SFX/name)]

    fc=[]
    # input 0 = picture.mp4, input 1 = dialogue, input 2..4 = music, input 5..14 = SFX
    fc.append(f"[1:a]aresample=48000,volume=1.15,apad=pad_dur={TOTAL}[dialogue]")
    fc.append("[2:a]atrim=duration=76,asetpts=N/SR/TB,volume=0.20,afade=t=out:st=72:d=4[comedy]")
    fc.append("[3:a]atrim=duration=60,asetpts=N/SR/TB,volume=0.18,afade=t=in:st=0:d=2,afade=t=out:st=56:d=4[noir0]")
    fc.append("[noir0]adelay=76000|76000[noir]")
    fc.append("[4:a]atrim=duration=25,asetpts=N/SR/TB,volume=0.20,afade=t=in:st=0:d=2,afade=t=out:st=21:d=4[sad0]")
    fc.append("[sad0]adelay=136000|136000[sad]")

    labels=["[dialogue]","[comedy]","[noir]","[sad]"]
    for idx,(name,t) in enumerate(sfx_events,5):
        delay=int(t*1000)
        lab=f"[s{idx}]"
        fc.append(f"[{idx}:a]aresample=48000,volume=0.75,adelay={delay}|{delay}{lab}")
        labels.append(lab)

    fc.append("".join(labels)+f"amix=inputs={len(labels)}:duration=longest:dropout_transition=2,alimiter=limit=0.95[aout]")
    filt=";".join(fc)
    run(ffmpeg(),"-hide_banner","-loglevel","warning","-y","-i",video,*inputs,"-filter_complex",filt,
        "-map","0:v","-map","[aout]","-c:v","copy","-c:a","aac","-b:a","192k","-t",str(TOTAL),
        "-movflags","+faststart",out)
    return out


def captions(video: Path) -> Path:
    out=OUT/"AllSortsHub_Episode_01_MASTER.mp4"
    style=("FontName=DejaVu Sans,FontSize=20,PrimaryColour=&H00FFFFFF,"
           "OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,"
           "MarginV=55,Alignment=2")
    vf=f"subtitles='{CAPTIONS.as_posix()}':force_style='{style}'"
    run(ffmpeg(),"-hide_banner","-loglevel","warning","-y","-i",video,"-vf",vf,
        "-c:v","libx264","-preset","medium","-crf","18","-c:a","copy","-movflags","+faststart",out)
    return out


def make_vertical(master: Path) -> None:
    out=OUT/"AllSortsHub_Episode_01_VERTICAL_9x16.mp4"
    # Keep the center of the artwork and preserve the burned-in captions.
    vf="crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920:flags=lanczos,format=yuv420p"
    run(ffmpeg(),"-hide_banner","-loglevel","warning","-y","-i",master,"-vf",vf,
        "-c:v","libx264","-preset","medium","-crf","19","-c:a","aac","-b:a","192k","-movflags","+faststart",out)


def make_shorts(master: Path) -> None:
    shorts=[
        ("01_The_Notification",0,24),("02_Do_NOT_Spend_It",24,26),
        ("03_One_Of_Everything",50,30),("04_Change_The_World",80,24),
        ("05_What_Did_You_Learn",129,22)]
    for name,start,length in shorts:
        out=OUT/f"Short_{name}.mp4"
        vf="crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920:flags=lanczos,format=yuv420p"
        run(ffmpeg(),"-hide_banner","-loglevel","warning","-y","-ss",str(start),"-t",str(length),"-i",master,
            "-vf",vf,"-c:v","libx264","-preset","medium","-crf","19","-c:a","aac","-b:a","192k","-movflags","+faststart",out)


def main():
    print(f"Rendering {len(DURATIONS)} shots / {TOTAL}s episode", flush=True)
    if OUT.exists(): shutil.rmtree(OUT)
    if WORK.exists(): shutil.rmtree(WORK)
    OUT.mkdir(parents=True); WORK.mkdir(parents=True)
    clips=make_shot_clips()
    picture=concat(clips)
    mixed=add_audio(picture)
    master=captions(mixed)
    make_vertical(master)
    make_shorts(master)
    print("\nRENDER COMPLETE", flush=True)
    for p in sorted(OUT.glob("*.mp4")):
        print(f"{p.name}: {p.stat().st_size/1024/1024:.1f} MB", flush=True)


if __name__ == "__main__":
    main()
