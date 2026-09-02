#!/usr/bin/env python3
import json, os, shutil, subprocess, math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parent; EP=ROOT/'episode_01.json'; BUILD=ROOT/'build'; OUT=ROOT/'output'
BUILD.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
W,H,FPS=1920,1080,30

def font(size,bold=False):
    paths=['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/System/Library/Fonts/Supplemental/Arial Bold.ttf' if bold else '/System/Library/Fonts/Supplemental/Arial.ttf']
    for p in paths:
        if os.path.exists(p): return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def bg(d,k,offset=0):
    if k=='bedroom':
        d.rectangle((0,0,W,H),fill=(225,235,250)); d.rectangle((0,720,W,H),fill=(170,130,95)); d.rectangle((1300+offset,120,1780+offset,500),fill=(170,205,235),outline=(70,90,110),width=8); d.line((1540+offset,120,1540+offset,500),fill=(70,90,110),width=6); d.rectangle((300,520,1050,760),fill=(210,70,80)); d.rectangle((380,460,680,570),fill=(245,245,245)); d.rectangle((720,460,1020,570),fill=(245,245,245))
    elif k=='city':
        d.rectangle((0,0,W,H),fill=(155,210,245)); d.rectangle((0,760,W,H),fill=(90,95,105))
        for i in range(9):
            x=80+i*220+offset; h=180+(i%4)*90; d.rectangle((x,760-h,x+150,760),fill=(90,105,130))
            for yy in range(760-h+30,740,55):
                for xx in range(x+20,x+140,45): d.rectangle((xx,yy,xx+20,yy+25),fill=(245,220,100))
    elif k=='bank':
        d.rectangle((0,0,W,H),fill=(235,240,245)); d.rectangle((0,780,W,H),fill=(190,190,185)); d.rectangle((250,260,1670,800),fill=(250,250,245),outline=(50,50,50),width=8)
        for x in [450,750,1050,1350]: d.rectangle((x,430,x+100,800),fill=(215,215,210),outline=(50,50,50),width=5)
        d.polygon([(180,260),(1740,260),(1600,120),(320,120)],fill=(55,75,95),outline=(40,40,40)); d.text((680,165),'BANK',font=font(70,True),fill='white')
    else:
        d.rectangle((0,0,W,H),fill=(150,215,250)); d.rectangle((0,700,W,H),fill=(75,75,80)); d.rectangle((0,660,W,700),fill=(120,180,100)); d.line((0,850,W,850),fill='white',width=8); d.line((0,970,W,970),fill='white',width=8)

def character(d,c,t):
    x=c.get('x',960)+math.sin(t*3)*8; y=c.get('y',450)+math.sin(t*5)*5; s=c.get('scale',1); name=c.get('name','Ravi'); mood=c.get('mood','normal'); skin=(238,183,132); shirt=(45,105,190) if name=='Ravi' else (62,150,92)
    d.ellipse((x-115*s,y+370*s,x+115*s,y+410*s),fill=(80,80,80))
    d.rounded_rectangle((x-95*s,y+70*s,x+95*s,y+290*s),radius=int(35*s),fill=shirt,outline=(35,35,35),width=max(2,int(5*s)))
    arm=math.sin(t*7)*18*s; d.line((x-80*s,y+120*s,x-155*s,y+235*s+arm),fill=skin,width=max(5,int(22*s))); d.line((x+80*s,y+120*s,x+155*s,y+235*s-arm),fill=skin,width=max(5,int(22*s)))
    d.ellipse((x-120*s,y-130*s,x+120*s,y+110*s),fill=skin,outline=(40,40,40),width=max(2,int(5*s))); d.arc((x-112*s,y-145*s,x+112*s,y+55*s),180,350,fill=(45,30,25),width=max(5,int(25*s)))
    if mood=='shocked':
        for dx in (-47,47): d.ellipse((x+(dx-18)*s,y-45*s,x+(dx+18)*s,y+15*s),fill='white',outline='black',width=max(2,int(3*s))); d.ellipse((x+(dx-6)*s,y-25*s,x+(dx+6)*s,y-8*s),fill='black')
        d.ellipse((x-25*s,y+25*s,x+25*s,y+75*s),outline='black',width=max(3,int(7*s)))
    else:
        for dx in (-48,48): d.ellipse((x+(dx-15)*s,y-28*s,x+(dx+15)*s,y+5*s),fill='white',outline='black',width=max(2,int(3*s))); d.ellipse((x+(dx-6)*s,y-18*s,x+(dx+6)*s,y-5*s),fill='black')
        d.arc((x-45*s,y+10*s,x+45*s,y+75*s),0 if mood=='happy' else 180,180 if mood=='happy' else 360,fill='black',width=max(3,int(8*s)))
    d.text((x-55*s,y+415*s),name,font=font(max(16,int(28*s)),True),fill='black')

def wrap(d,text,f,maxw):
    lines=[]; cur=''
    for w in text.split():
        q=(cur+' '+w).strip()
        if d.textbbox((0,0),q,font=f)[2]<=maxw: cur=q
        else: lines.append(cur); cur=w
    if cur: lines.append(cur)
    return lines

def frame(scene,t):
    img=Image.new('RGB',(W,H),'white'); d=ImageDraw.Draw(img); pan=int(18*math.sin(t*1.5)); bg(d,scene.get('background','bedroom'),pan)
    for c in scene.get('characters',[]): character(d,c,t)
    if scene.get('prop'):
        pulse=1+0.04*math.sin(t*8); f=font(int(52*pulse),True); txt=scene['prop']; bb=d.textbbox((0,0),txt,font=f); x=1530-(bb[2]-bb[0])/2; d.rounded_rectangle((1250,100,1810,230),25,fill='white',outline='black',width=5); d.text((x,135),txt,font=f,fill='black')
    if scene.get('title'):
        f=font(88,True); bb=d.textbbox((0,0),scene['title'],font=f); d.text(((W-(bb[2]-bb[0]))/2,100+int(8*math.sin(t*3))),scene['title'],font=f,fill='black')
    sub=scene.get('subtitle','')
    if sub:
        f=font(44,True); lines=wrap(d,sub,f,1500); boxh=len(lines)*60+35; y=H-80-boxh; d.rounded_rectangle((170,y,1750,H-45),30,fill='black',outline='white',width=3)
        for line in lines: bb=d.textbbox((0,0),line,font=f); d.text(((W-(bb[2]-bb[0]))/2,y+18),line,font=f,fill='white'); y+=60
    return img

def main():
    data=json.loads(EP.read_text()); scenes=data['scenes']; parts=[]; starts=[]; total=0
    for i,s in enumerate(scenes,1):
        dur=float(s.get('duration',5)); starts.append(total); total+=dur; scene_dir=BUILD/f's{i:02d}'; scene_dir.mkdir(exist_ok=True)
        for j in range(max(1,int(dur*FPS))): frame(s,j/FPS).save(scene_dir/f'f{j:05d}.jpg',quality=88)
        if not shutil.which('ffmpeg'): continue
        p=BUILD/f'part{i:02d}.mp4'; subprocess.run(['ffmpeg','-y','-framerate',str(FPS),'-i',str(scene_dir/'f%05d.jpg'),'-c:v','libx264','-pix_fmt','yuv420p','-preset','veryfast','-crf','20',str(p)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); parts.append(p)
    if not shutil.which('ffmpeg'): print('Frames created; FFmpeg required for MP4.'); return
    lst=BUILD/'parts.txt'; lst.write_text(''.join(f"file '{p.as_posix()}'\n" for p in parts))
    master=OUT/'AllSortsHub_Episode_01.mp4'; subprocess.run(['ffmpeg','-y','-f','concat','-safe','0','-i',str(lst),'-c','copy','-movflags','+faststart',str(master)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    highlights=[(starts[1],18),(starts[5],18),(starts[8],17),(max(0,total-15),15)]
    for k,(start,dur) in enumerate(highlights,1):
        out=OUT/f'AllSortsHub_Episode_01_Short_{k:02d}.mp4'; subprocess.run(['ffmpeg','-y','-ss',str(start),'-t',str(dur),'-i',str(master),'-vf',"scale=-2:1920,crop=1080:1920:(in_w-1080)/2:0,format=yuv420p",'-c:v','libx264','-preset','veryfast','-crf','22','-an','-movflags','+faststart',str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print('Created master episode and 4 animated Shorts in output/')
if __name__=='__main__': main()
