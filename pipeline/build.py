#!/usr/bin/env python3
"""Сборка части «Ржавой воды» из озвучки, текста и картинок.
Использование: python3 build.py <папка_части>
В папке должны быть:
  voice.mp3        — озвучка ElevenLabs
  script.txt       — точный текст озвучки
  shots.json       — [["первое слово кадра", "img/файл.jpg", "in|in2|out|up|left|shake"], ...]
                     кадр начинается с первого появления этого слова ПОСЛЕ начала предыдущего кадра;
                     первый кадр всегда с 0 сек. Вместо картинки можно "vid/клип.mp4".
  meta.json        — {"keywords": [...], "endcard": "вопрос?|часть N — скоро",
                      "rain_from": "слово" (необязательно), "drips_at": ["слово", ...] (необязательно),
                      "out": "Ржавая вода — часть N.mp4"}
Результат: <out> в той же папке (H.264 1080x1920, ~20 МБ).
"""
import json, os, re, subprocess, sys

FPS = 30

def run(c): subprocess.run(c, check=True)
def dur(f): return float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f],capture_output=True,text=True).stdout)

def align(audio, text, sd):
    r = subprocess.run(['ffmpeg','-hide_banner','-i',audio,'-af',f'silencedetect=n=-38dB:d={sd}','-f','null','-'],capture_output=True,text=True).stderr
    st=[float(x) for x in re.findall(r'silence_start: ([\d.]+)',r)]; en=[float(x) for x in re.findall(r'silence_end: ([\d.]+)',r)]
    D=dur(audio); segs=[]; cur=0.0
    for s,e in zip(st,en):
        if s-cur>0.05: segs.append((cur,s))
        cur=e
    if D-cur>0.1: segs.append((cur,D))
    words=text.split()
    wl=lambda w: len(re.sub(r'[^\wёЁ]','',w))+1.5
    units=[]; cu=[]
    for w in words:
        cu.append(w)
        if re.search(r'[.,!?:;»—]$',w) or w=='—': units.append(cu); cu=[]
    if cu: units.append(cu)
    ul=[sum(wl(w) for w in u) for u in units]; rate=sum(e-s for s,e in segs)/sum(ul)
    N,M=len(units),len(segs); INF=1e18
    dp=[[INF]*(M+1) for _ in range(N+1)]; bk=[[0]*(M+1) for _ in range(N+1)]; dp[0][0]=0
    pre=[0]
    for x in ul: pre.append(pre[-1]+x)
    for j in range(1,M+1):
        d=segs[j-1][1]-segs[j-1][0]
        for i in range(1,N+1):
            for k in range(max(0,i-12),i):
                if dp[k][j-1]>=INF: continue
                c=dp[k][j-1]+(((pre[i]-pre[k])*rate-d)/max(d,0.3))**2
                if c<dp[i][j]: dp[i][j]=c; bk[i][j]=k
    if dp[N][M]>=INF: return None, INF
    res=[]; i=N
    for j in range(M,0,-1):
        k=bk[i][j]; res.append((k,i,segs[j-1])); i=k
    res.reverse(); timed=[]
    for k,i,(s,e) in res:
        ws=[w for u in units[k:i] for w in u]; L=sum(wl(w) for w in ws); t=s
        for w in ws:
            d=(e-s)*wl(w)/L; timed.append([w,round(t,3),round(t+d,3)]); t+=d
    return timed, dp[N][M]

def best_align(audio, text):
    best=(None,1e18)
    for sd in ('0.18','0.25','0.32'):
        t,c=align(audio,text,sd)
        if t and c<best[1]: best=(t,c)
    print(f'alignment cost {best[1]:.2f} (меньше 3 — хорошо)')
    return best[0]

norm=lambda w: w.strip('«»!?.,:;—"').lower().replace('ё','е')

def ts(t): return f"{int(t//3600)}:{int(t%3600//60):02d}:{t%60:05.2f}"

def font():
    out=subprocess.run(['fc-list',':lang=ru','family'],capture_output=True,text=True).stdout
    for f in ('Inter Display ExtraBold','Inter Display','DejaVu Sans'):
        if f in out: return f
    return 'DejaVu Sans'

def subs(W, keys, endcard, end, path):
    F=font(); keys={norm(k) for k in keys}
    hdr=f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: W,{F},92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,5,60,60,0,1
Style: E,{F},78,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,5,60,60,0,1
Style: S,{F},40,&H00BBBBBB,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    L=[]
    for i,(w,s,e) in enumerate(W):
        nxt=W[i+1][1] if i+1<len(W) else e+0.3
        e2=min(max(e,s+0.18),nxt) if nxt-e<0.6 else e+0.25
        disp=w.lower().replace('«','').replace('»','')
        col=r'\c&H00D7FF&' if norm(w) in keys else ''
        L.append(f"Dialogue: 0,{ts(s)},{ts(e2)},W,,0,0,0,,{{\\pos(540,1150){col}\\fscx80\\fscy80\\t(0,90,\\fscx100\\fscy100)}}{disp}")
    q,part=endcard.split('|')
    q=re.sub(r'\*(.+?)\*',r'{\\c&H00D7FF&}\1{\\c&HFFFFFF&}',q)
    L.append(f"Dialogue: 1,{ts(end)},{ts(end+3)},E,,0,0,0,,{{\\pos(540,930)\\fad(200,0)}}{q}")
    L.append(f"Dialogue: 1,{ts(end)},{ts(end+3)},S,,0,0,0,,{{\\pos(540,1030)\\fad(200,0)}}{part}")
    open(path,'w',encoding='utf-8').write(hdr+'\n'.join(L)+'\n')

def find_times(W, anchors):
    idx=0; out=[]
    for k,a in enumerate(anchors):
        a=norm(a)
        if k==0: out.append(0.0); continue
        j=idx
        while j<len(W) and norm(W[j][0])!=a: j+=1
        if j>=len(W): raise SystemExit(f'Слово-якорь «{a}» (кадр {k+1}) не найдено после предыдущего кадра')
        out.append(W[j][1]); idx=j+1
    return out

def render(P, S):
    os.makedirs(f'{P}/seg',exist_ok=True); files=[]
    for k,(kind,src,a,b,m) in enumerate(S):
        d=round(b-a,3); n=max(1,int(round(d*FPS))); out=f'{P}/seg/{k:02d}.mp4'; files.append(out)
        if kind=='v':
            f=max(d/dur(f'{P}/{src}'),1.0)
            run(['ffmpeg','-v','error','-y','-i',f'{P}/{src}','-vf',f"setpts={f:.4f}*PTS,fps={FPS},scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1",'-t',str(d),'-an','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p',out])
        elif kind=='b':
            run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'color=c=black:s=1080x1920:r={FPS}:d={d}','-c:v','libx264','-pix_fmt','yuv420p',out])
        else:
            z={'in':'1+0.08*on/{n}','in2':'1+0.16*on/{n}','out':'1.10-0.08*on/{n}','up':'1.12','left':'1.10','shake':'1.06+0.04*on/{n}'}.get(m,'1+0.08*on/{n}').format(n=n)
            x={'left':f'(iw-iw/zoom)*(1-on/{n})','shake':'iw/2-(iw/zoom/2)+6*sin(on*1.3)'}.get(m,'iw/2-(iw/zoom/2)')
            y={'up':f'(ih-ih/zoom)*(1-on/{n})','shake':'ih/2-(ih/zoom/2)+5*cos(on*1.7)'}.get(m,'ih/2-(ih/zoom/2)')
            vf=(f"scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
                f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s=1080x1920:fps={FPS},setsar=1")
            run(['ffmpeg','-v','error','-y','-loop','1','-i',f'{P}/{src}','-vf',vf,'-frames:v',str(n),'-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p',out])
        print(f'кадр {k+1}/{len(S)} {d:.1f}с',flush=True)
    open(f'{P}/seg/list.txt','w').write(''.join(f"file '{os.path.basename(f)}'\n" for f in files))
    run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',f'{P}/seg/list.txt','-c','copy',f'{P}/video_raw.mp4'])

def audio(P, end, total, drips, rain_from):
    run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f"aevalsrc='0.5*sin(2*PI*55*t)*(0.6+0.4*sin(2*PI*0.07*t))+0.35*sin(2*PI*82.4*t)*(0.6+0.4*sin(2*PI*0.05*t+1))+0.15*sin(2*PI*110.3*t)':s=44100:d={end}",
         '-f','lavfi','-i',f'anoisesrc=color=brown:amplitude=0.6:d={end}:r=44100','-filter_complex',
         f"[0]volume=0.5[a];[1]lowpass=f=300,volume=0.35[b];[a][b]amix=2:normalize=0,afade=t=in:d=2,afade=t=out:st={end-0.8}:d=0.8,volume=0.22,aformat=channel_layouts=stereo[out]",'-map','[out]',f'{P}/drone.wav'])
    run(['ffmpeg','-v','error','-y','-f','lavfi','-i',"aevalsrc='if(lt(t,0.09),sin(2*PI*(1500-11000*t)*t)*exp(-t*45),0)':s=44100:d=0.4",'-af','aecho=0.6:0.5:120:0.25,volume=0.9,aformat=channel_layouts=stereo',f'{P}/drip.wav'])
    run(['ffmpeg','-v','error','-y','-f','lavfi','-i',"aevalsrc='sin(2*PI*(60-30*t)*t)*exp(-t*3)':s=44100:d=2.5",'-af','volume=0.8,aformat=channel_layouts=stereo',f'{P}/boom.wav'])
    ins=['-i',f'{P}/voice.mp3','-i',f'{P}/drone.wav']; fx=['[1]']; flt=[]; n=2
    for t in drips:
        ins+=['-i',f'{P}/drip.wav']; ms=int(t*1000); flt.append(f'[{n}]adelay={ms}|{ms}[d{n}]'); fx.append(f'[d{n}]'); n+=1
    if rain_from is not None:
        rd=max(end-rain_from,1)
        run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'anoisesrc=color=pink:amplitude=0.5:d={rd}:r=44100','-af',f'highpass=f=400,lowpass=f=7000,tremolo=f=9:d=0.3,afade=t=in:d=2.5,afade=t=out:st={max(rd-0.7,0)}:d=0.6,volume=0.35,aformat=channel_layouts=stereo',f'{P}/rain.wav'])
        ins+=['-i',f'{P}/rain.wav']; ms=int(rain_from*1000); flt.append(f'[{n}]adelay={ms}|{ms}[r]'); fx.append('[r]'); n+=1
    ins+=['-i',f'{P}/boom.wav']; ms=int(end*1000); flt.append(f'[{n}]adelay={ms}|{ms}[bm]'); fx.append('[bm]')
    fc=';'.join([f'[0]apad=pad_dur=3.3,aformat=channel_layouts=stereo[v]']+flt+[f"{''.join(fx)}amix={len(fx)}:normalize=0[fx]",'[v][fx]amix=2:normalize=0,alimiter=limit=0.95,loudnorm=I=-14:TP=-1.5:LRA=11[out]'])
    run(['ffmpeg','-v','error','-y',*ins,'-filter_complex',fc,'-map','[out]','-t',str(total),'-ar','44100',f'{P}/mix.wav'])

def main(P):
    text=open(f'{P}/script.txt',encoding='utf-8').read().strip()
    shots=json.load(open(f'{P}/shots.json',encoding='utf-8'))
    meta=json.load(open(f'{P}/meta.json',encoding='utf-8'))
    W=best_align(f'{P}/voice.mp3',text)
    json.dump(W,open(f'{P}/words.json','w',encoding='utf-8'),ensure_ascii=False)
    end=round(W[-1][2]+0.3,2); total=round(end+3,2)
    starts=find_times(W,[s[0] for s in shots])
    S=[]
    for k,(a,src,m) in enumerate(shots):
        b=starts[k+1] if k+1<len(shots) else end
        if b-starts[k]<0.4: raise SystemExit(f'Кадр {k+1} слишком короткий ({b-starts[k]:.2f}с) — проверь якоря')
        S.append(('v' if src.startswith('vid/') else 'i',src,round(starts[k],2),round(b,2),m))
    S.append(('b',None,end,total,None))
    for s in S: print(s)
    subs(W,meta.get('keywords',[]),meta['endcard'],end,f'{P}/subs.ass')
    render(P,S)
    drips=find_times(W,['_']+meta.get('drips_at',[]))[1:] if meta.get('drips_at') else []
    rain=find_times(W,['_',meta['rain_from']])[1] if meta.get('rain_from') else None
    audio(P,end,total,drips,rain)
    out=f"{P}/{meta.get('out','final.mp4')}"
    run(['ffmpeg','-v','error','-y','-i',f'{P}/video_raw.mp4','-i',f'{P}/mix.wav','-vf',f"ass={P}/subs.ass",'-c:v','libx264','-preset','slow','-crf','22','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',out])
    sz=os.path.getsize(out)/1e6
    if sz>29:
        run(['ffmpeg','-v','error','-y','-i',f'{P}/video_raw.mp4','-i',f'{P}/mix.wav','-vf',f"ass={P}/subs.ass",'-c:v','libx264','-preset','slow','-crf','25','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-shortest','-movflags','+faststart',out])
        sz=os.path.getsize(out)/1e6
    print(f'ГОТОВО: {out} — {dur(out):.1f} с, {sz:.1f} МБ')

if __name__=='__main__': main(sys.argv[1].rstrip('/'))
