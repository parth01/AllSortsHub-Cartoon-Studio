import json, math, os, shutil, subprocess, wave
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output_v2'; FR=ROOT/'v2'/'frames'; AUDIO=ROOT/'v2'/'audio'
W,H,FPS=1920,1080,24
for p in (OUT,FR,AUDIO): p.mkdir(parents=True,exist_ok=True)
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FONT_REG='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

def font(n,bold=True):
    try:return ImageFont.truetype(FONT if bold else FONT_REG,n)
    except:return ImageFont.load_default()

def lerp(a,b,t): return a+(b-a)*t

def rounded(draw,box,r,fill,outline=None,width=1): draw.rounded_rectangle(box,radius=r,fill=fill,outline=outline,width=width)

def char(draw,name,x,y,scale=1,expr='normal',pose='idle',phase=0):
    # Original procedural cartoon character: Ravi/Max
    s=scale; body=(80,150,230) if name=='Ravi' else (235,145,70); skin=(246,194,150)
    bob=math.sin(phase*2)*5*s if pose in ('walk','run') else math.sin(phase)*2*s
    y+=bob
    # legs
    stride=math.sin(phase*(2 if pose=='walk' else 3))*28*s if pose in ('walk','run') else 0
    draw.line((x-22*s,y+120*s,x-22*s+stride,y+175*s),fill=(35,35,45),width=max(8,int(12*s)))
    draw.line((x+22*s,y+120*s,x+22*s-stride,y+175*s),fill=(35,35,45),width=max(8,int(12*s)))
    draw.ellipse((x-45*s+stride,y+168*s,x-5*s+stride,y+185*s),fill=(25,25,30))
    draw.ellipse((x+5*s-stride,y+168*s,x+45*s-stride,y+185*s),fill=(25,25,30))
    # torso
    rounded(draw,(x-55*s,y+45*s,x+55*s,y+135*s),25*s,body)
    # arms
    arm=math.sin(phase*(2 if pose in ('walk','run') else 1.5))*25*s if pose in ('walk','run') else 0
    draw.line((x-48*s,y+60*s,x-90*s,y+105*s+arm),fill=skin,width=max(7,int(12*s)))
    draw.line((x+48*s,y+60*s,x+90*s,y+105*s-arm),fill=skin,width=max(7,int(12*s)))
    # head
    draw.ellipse((x-62*s,y-55*s,x+62*s,y+62*s),fill=skin,outline=(30,30,30),width=max(2,int(4*s)))
    # hair
    draw.arc((x-58*s,y-65*s,x+58*s,y+35*s),180,360,fill=(35,25,20),width=max(8,int(14*s)))
    # eyebrows/eyes
    ey=y-10*s
    if expr in ('angry','worried'):
        draw.line((x-35*s,ey-8*s,x-10*s,ey-14*s),fill=(20,20,20),width=max(3,int(5*s)))
        draw.line((x+10*s,ey-14*s,x+35*s,ey-8*s),fill=(20,20,20),width=max(3,int(5*s)))
    else:
        draw.line((x-35*s,ey-8*s,x-10*s,ey-8*s),fill=(20,20,20),width=max(3,int(5*s)))
        draw.line((x+10*s,ey-8*s,x+35*s,ey-8*s),fill=(20,20,20),width=max(3,int(5*s)))
    eye_y=ey+2*s
    if expr=='shocked':
        draw.ellipse((x-30*s,eye_y-10*s,x-8*s,eye_y+12*s),fill='white',outline='black',width=3)
        draw.ellipse((x+8*s,eye_y-10*s,x+30*s,eye_y+12*s),fill='white',outline='black',width=3)
    else:
        draw.ellipse((x-28*s,eye_y-5*s,x-12*s,eye_y+11*s),fill='white',outline='black',width=2)
        draw.ellipse((x+12*s,eye_y-5*s,x+28*s,eye_y+11*s),fill='white',outline='black',width=2)
    # mouth
    if expr in ('happy','laugh'):
        draw.arc((x-28*s,y+8*s,x+28*s,y+42*s),0,180,fill=(120,20,20),width=max(4,int(6*s)))
    elif expr=='shocked': draw.ellipse((x-12*s,y+15*s,x+12*s,y+42*s),fill=(100,30,30))
    elif expr=='angry': draw.line((x-22*s,y+32*s,x+22*s,y+24*s),fill=(100,20,20),width=max(4,int(6*s)))
    else: draw.arc((x-22*s,y+15*s,x+22*s,y+38*s),180,360,fill=(100,30,30),width=max(3,int(5*s)))
    # label
    draw.text((x,y+195*s),name,anchor='mm',font=font(max(18,int(22*s))),fill=(25,25,25))

def background(draw,kind,t):
    draw.rectangle((0,0,W,H),fill=(225,240,255))
    if kind=='bank':
        draw.rectangle((0,650,W,H),fill=(190,175,150)); draw.rectangle((180,180,1740,700),fill=(245,245,245),outline=(50,50,50),width=6)
        for x in (300,650,1000,1350): draw.rectangle((x,300,x+180,650),fill=(190,220,245),outline=(50,50,50),width=5)
        draw.text((960,235),'BANK',anchor='mm',font=font(80),fill=(35,70,110))
    elif kind=='mansion':
        draw.rectangle((0,650,W,H),fill=(105,180,100)); draw.polygon([(350,650),(350,400),(960,180),(1570,400),(1570,650)],fill=(235,225,205),outline=(50,50,50))
        draw.rectangle((760,470,1160,650),fill=(150,90,55)); draw.text((960,335),'$1B MANSION',anchor='mm',font=font(52),fill=(40,40,40))
    elif kind=='street':
        draw.rectangle((0,620,W,H),fill=(80,80,85)); draw.rectangle((0,680,W,H),fill=(55,55,60))
        for x in range(-100,2100,260): draw.rectangle((x,820,x+130,850),fill=(235,210,80))
        draw.rectangle((120,350,520,620),fill=(220,170,100)); draw.rectangle((1400,300,1800,620),fill=(160,190,215))
    elif kind=='home':
        draw.rectangle((0,650,W,H),fill=(150,105,70)); draw.rectangle((300,220,1620,700),fill=(240,225,200)); draw.text((960,300),'RAVI HQ',anchor='mm',font=font(70),fill=(50,50,50))
    else:
        draw.rectangle((0,700,W,H),fill=(110,180,100)); draw.ellipse((200,80,600,480),fill=(255,220,80));

def caption(draw,text,t,duration,speaker=''):
    if not text:return
    words=text.split(); count=max(1,min(len(words),math.ceil((t+0.05)/max(0.12,duration/max(1,len(words)))))); shown=' '.join(words[:count])
    box=(140,880,1780,1025); rounded(draw,box,30,(20,20,25))
    if speaker: draw.text((170,900),speaker.upper(),font=font(22),fill=(255,220,90))
    draw.text((170,930),shown,font=font(38),fill='white')

def scene_frame(sc,t,idx):
    img=Image.new('RGB',(W,H)); d=ImageDraw.Draw(img); background(d,sc.get('background','street'),t)
    camx=sc.get('camera_from',0)+(sc.get('camera_to',0)-sc.get('camera_from',0))*t/max(0.001,sc['duration'])
    zoom=1+sc.get('zoom',0)*t/max(0.001,sc['duration'])
    for c in sc.get('characters',[]):
        x=lerp(c.get('x',960),c.get('x2',c.get('x',960)),t/max(0.001,sc['duration']))-camx
        y=c.get('y',400); phase=t*(5 if c.get('pose')=='run' else 3)
        char(d,c['name'],x,y,c.get('scale',1),c.get('expression','normal'),c.get('pose','idle'),phase)
    for p in sc.get('props',[]):
        x=p.get('x',960)-camx; y=p.get('y',450); pulse=1+0.04*math.sin(t*8)
        d.ellipse((x-55*pulse,y-55*pulse,x+55*pulse,y+55*pulse),fill=p.get('color',(255,210,50)),outline=(50,50,50),width=4)
        d.text((x,y),p.get('text','!'),anchor='mm',font=font(40),fill=(40,40,40))
    caption(d,sc.get('subtitle',''),t,sc['duration'],sc.get('speaker',''))
    if sc.get('title'):
        a=min(1,t*4); d.text((W/2,H/2-40),sc['title'],anchor='mm',font=font(72),fill=(25,25,25))
    # camera zoom around center
    if zoom!=1:
        nw,nh=int(W/zoom),int(H/zoom); left=(W-nw)//2; top=(H-nh)//2
        img=img.crop((left,top,left+nw,top+nh)).resize((W,H),Image.Resampling.LANCZOS)
    return img

def tone(path,freq=440,dur=.15,amp=.25):
    rate=44100; n=int(rate*dur)
    with wave.open(str(path),'w') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate)
        import struct
        for i in range(n):
            env=min(1,i/(rate*.01),(n-i)/(rate*.03)); v=int(32767*amp*env*math.sin(2*math.pi*freq*i/rate)); w.writeframes(struct.pack('<h',v))

def silence(path,dur): tone(path,1,dur,0)

def make_tts(text,out,voice='en-us',speed=155,pitch=55):
    subprocess.run(['espeak-ng','-v',voice,'-s',str(speed),'-p',str(pitch),'-w',str(out),text],check=True)

def audio_scene(sc,idx):
    dur=sc['duration']; base=AUDIO/f'scene_{idx:02d}.wav'; parts=[]
    txt=sc.get('dialogue') or sc.get('subtitle')
    if txt:
        v=sc.get('speaker','Ravi'); speed,pitch=(160,52) if v=='Ravi' else (145,68) if v=='Max' else (125,35)
        p=AUDIO/f'voice_{idx:02d}.wav'; make_tts(txt,p,speed=speed,pitch=pitch); parts.append((p,0.0))
    sfx=sc.get('sfx');
    if sfx:
        p=AUDIO/f'sfx_{idx:02d}.wav'; tone(p,{'cash':880,'whoosh':300,'pop':650,'error':180,'gasp':500,'step':100}[sfx],.18,.18); parts.append((p,max(0,dur-.45)))
    # mix using ffmpeg; music is an original generated tone loop
    music=AUDIO/'music.wav'
    if not music.exists():
        rate=44100; seconds=90
        with wave.open(str(music),'w') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);import struct
            for i in range(rate*seconds):
                t=i/rate; beat=int(t*2)%4; f=110 if beat in (0,2) else 146.8; val=.045*math.sin(2*math.pi*f*t)+.018*math.sin(2*math.pi*f*2*t); w.writeframes(struct.pack('<h',int(32767*val)))
    inputs=['-i',str(music)]; filters=['[0:a]atrim=0:'+str(dur)+',volume=0.22[m]']; labels=['[m]']; n=1
    for p,delay in parts:
        inputs+=['-i',str(p)]; filters.append(f'[{n}:a]adelay={int(delay*1000)}:all=1,apad,atrim=0:{dur}[a{n}]');labels.append(f'[a{n}]');n+=1
    fc=';'.join(filters)+';'+''.join(labels)+f'amix=inputs={len(labels)}:duration=longest:normalize=0,atrim=0:{dur},volume=1.5[a]'
    subprocess.run(['ffmpeg','-y',*inputs,'-filter_complex',fc,'-map','[a]',str(base)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    return base

def main():
    data=json.load(open(ROOT/'episode_01.json'))
    scenes=data['scenes']; scene_vids=[]; aud=[]
    for i,sc in enumerate(scenes,1):
        d=FR/f's{i:02d}'; shutil.rmtree(d,ignore_errors=True); d.mkdir(parents=True)
        n=int(sc['duration']*FPS)
        for k in range(n): scene_frame(sc,k/FPS,k).save(d/f'{k:05d}.jpg',quality=88)
        v=OUT/f'_s{i:02d}.mp4'; subprocess.run(['ffmpeg','-y','-framerate',str(FPS),'-i',str(d/'%05d.jpg'),'-c:v','libx264','-pix_fmt','yuv420p','-crf','20','-preset','veryfast',str(v)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True); scene_vids.append(v)
        aud.append(audio_scene(sc,i))
    # concatenate video with short fade-to-black transitions handled by fades on each clip
    listf=ROOT/'v2'/'concat.txt'; listf.write_text(''.join(f"file '{p.resolve()}'\n" for p in scene_vids))
    master_noaudio=OUT/'episode_01_v2_noaudio.mp4'; subprocess.run(['ffmpeg','-y','-f','concat','-safe','0','-i',str(listf),'-c','copy',str(master_noaudio)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    alist=ROOT/'v2'/'audio_concat.txt'; alist.write_text(''.join(f"file '{p.resolve()}'\n" for p in aud))
    fullwav=AUDIO/'full.wav'; subprocess.run(['ffmpeg','-y','-f','concat','-safe','0','-i',str(alist),'-c:a','pcm_s16le',str(fullwav)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    master=OUT/'AllSortsHub_Episode_01_V2_16x9.mp4'; subprocess.run(['ffmpeg','-y','-i',str(master_noaudio),'-i',str(fullwav),'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','160k','-shortest',str(master)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    # automatic 9:16 highlights, centered correctly by scaling to height first
    for j,(start,dur) in enumerate([(0,14),(13,15),(28,15),(43,15)],1):
        out=OUT/f'AllSortsHub_Episode_01_V2_Short_{j}.mp4'
        vf='scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920'
        subprocess.run(['ffmpeg','-y','-ss',str(start),'-t',str(dur),'-i',str(master),'-vf',vf,'-c:v','libx264','-crf','20','-preset','veryfast','-c:a','aac','-b:a','128k',str(out)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    master_noaudio.unlink(missing_ok=True)
    print('V2 render complete:',master)

if __name__=='__main__': main()
