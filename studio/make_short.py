"""Render a vertical Short (1080x1920) from a spec.json made by daily_bread.py.

    .venv/bin/python make_short.py ../production/daily-bread/2026-12-01/spec.json

Pipeline: AI narration with word timings -> branded slides (headless Chrome)
-> Ken Burns + crossfades -> word-timed captions -> soft music bed -> loudness
normalised MP4 (H.264/AAC, 30 fps).
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
import subprocess
import sys
from pathlib import Path

import edge_tts
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent.parent
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
LOGO = (ROOT / "website" / "assets" / "logo.svg").read_text()
W, H, FPS = 1080, 1920, 30
LEAD_IN = 0.45      # seconds of hook before the voice starts
TAIL = 2.0          # seconds after the voice ends (music rings out under the CTA)
XFADE = 0.35

# Rotating looks so consecutive days don't look templated.
THEMES = [
    {"name": "sunrise", "bg": "linear-gradient(165deg,#FFF4E0 0%,#FFD9A8 45%,#F7871F 100%)", "ink": "#2a1606", "accent": "#E5322D", "swirl": "#ffffff"},
    {"name": "night", "bg": "linear-gradient(165deg,#0f1b4d 0%,#1A4FC4 60%,#0E8F86 100%)", "ink": "#ffffff", "accent": "#FFD60A", "swirl": "#9fd8ff"},
    {"name": "praise", "bg": "linear-gradient(165deg,#fffdfb 0%,#ffeef3 50%,#FCE7C4 100%)", "ink": "#1d1b22", "accent": "#E5322D", "swirl": "#F06292"},
    {"name": "deep", "bg": "linear-gradient(165deg,#1a1033 0%,#3b1f6e 55%,#7E57C2 100%)", "ink": "#ffffff", "accent": "#FFC400", "swirl": "#d1c4e9"},
    {"name": "field", "bg": "linear-gradient(165deg,#f3fbe9 0%,#c9efc0 50%,#22A84B 100%)", "ink": "#0e2a14", "accent": "#1A4FC4", "swirl": "#ffffff"},
]
SONGS_DIR = ROOT / "songs "  # note: the folder name ends with a space
BED_LUFS = -31      # music bed loudness before ducking; the voice sits at -16 (about 15 dB above)


def song_pool() -> list[Path]:
    return sorted(p for p in SONGS_DIR.rglob("*") if p.suffix.lower() in (".wav", ".mp3", ".m4a"))


def wav_seconds(p: Path) -> float:
    import wave
    try:
        with wave.open(str(p)) as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        return 180.0


CHORDS = [  # fallback soft pad (Hz) if no songs are available: A, C, D, F, G major
    (220.0, 277.18, 329.63), (261.63, 329.63, 392.0), (293.66, 369.99, 440.0),
    (174.61, 220.0, 261.63), (196.0, 246.94, 293.66)]


def run(cmd: list[str], cwd: Path | None = None) -> None:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        sys.stderr.write(p.stderr[-3000:])
        raise SystemExit(f"command failed: {cmd[0]}")


def chrome_shot(args: list[str], shot: Path) -> None:
    """Headless Chrome screenshot. Chrome sometimes crashes during teardown on a busy
    machine after writing the file, so success = a fresh, non-empty screenshot."""
    shot.unlink(missing_ok=True)
    for attempt in range(3):
        try:
            p = subprocess.run([CHROME, *args, f"--screenshot={shot}"], capture_output=True, text=True, timeout=180)
            err = p.stderr
        except subprocess.TimeoutExpired:
            err = "Chrome timed out"
        if shot.exists() and shot.stat().st_size > 10_000:
            return
        sys.stderr.write(err[-1500:])
    raise SystemExit("Chrome screenshot failed")


# ---------------------------------------------------------------- narration

async def _tts(text: str, voice: str, rate: str, mp3: Path) -> list[dict]:
    words: list[dict] = []
    com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    with mp3.open("wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({"t": chunk["offset"] / 1e7, "d": chunk["duration"] / 1e7, "w": chunk["text"]})
    return words


def narrate(spec: dict, out: Path) -> tuple[Path, list[dict], float]:
    mp3, wj = out / "voice.mp3", out / "words.json"
    key = hashlib.sha1(f"{spec['voice']}|{spec['rate']}|{spec['script']}".encode()).hexdigest()
    if mp3.exists() and wj.exists() and json.loads(wj.read_text()).get("key") == key:
        words = json.loads(wj.read_text())["words"]
    else:
        import time
        # The voice service sometimes returns no audio for a given text+rate combination
        # (seen 13 Nov 2026); nudging the rate by 1% (inaudible) gets past it.
        base = int(spec["rate"].rstrip("%"))
        rates = [base, base + 1, base - 1, base]
        for attempt in range(4):
            try:
                rate = f"{rates[attempt]:+d}%"
                # a stalled connection to the voice service once froze a whole queue run
                words = asyncio.run(asyncio.wait_for(_tts(spec["script"], spec["voice"], rate, mp3), 120))
                if words and mp3.stat().st_size > 10_000:
                    break
            except Exception as e:  # NoAudioReceived, network hiccups
                if attempt == 3:
                    raise
                print(f"  voice attempt {attempt + 1} failed ({e.__class__.__name__}); retrying")
            time.sleep(5 * (attempt + 1))
        wj.write_text(json.dumps({"key": key, "words": words}))
    dur = words[-1]["t"] + words[-1]["d"] if words else 0
    return mp3, words, dur


# ---------------------------------------------------------------- timeline

def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def find_span(words: list[dict], phrase: str) -> tuple[float, float] | None:
    target = [norm(w) for w in phrase.split() if norm(w)]
    seq = [norm(w["w"]) for w in words]
    n = len(target)
    for i in range(len(seq)):
        if seq[i:i + 3] == target[:3]:
            j = min(i + n - 1, len(words) - 1)
            return words[i]["t"], words[j]["t"] + words[j]["d"]
    return None


def timeline(spec: dict, words: list[dict], voice_dur: float) -> list[dict]:
    total = LEAD_IN + voice_dur + TAIL
    slides = [{"kind": "hook", "start": 0.0}]
    span = find_span(words, spec["verse"]["text"]) if spec.get("verse") else None
    beats = spec.get("beats", [])
    if span:
        vs, ve = span[0] + LEAD_IN, span[1] + LEAD_IN
        pre = max(1.6, min(vs, 3.2))
        # beats before the verse (if the verse is late) and after it
        slides.append({"kind": "verse", "start": pre})
        after_start, after_end = ve, total - 2.6
    else:
        after_start, after_end = 2.6, total - 2.6
    usable = [b for b in beats]
    if usable and after_end - after_start > 1.5:
        step = (after_end - after_start) / len(usable)
        for k, b in enumerate(usable):
            slides.append({"kind": "beat", "text": b, "start": after_start + k * step})
    slides.append({"kind": "cta", "start": total - 2.6})
    slides.sort(key=lambda s: s["start"])
    # drop slides shorter than 1.2 s
    clean = []
    for s in slides:
        if clean and s["start"] - clean[-1]["start"] < 1.2:
            if s["kind"] in ("cta", "verse"):
                clean[-1] = s
            continue
        clean.append(s)
    for i, s in enumerate(clean):
        s["end"] = clean[i + 1]["start"] if i + 1 < len(clean) else total
    return clean


# ---------------------------------------------------------------- slides

def slide_html(spec: dict, s: dict, th: dict) -> str:
    e = html.escape
    ring = lambda x, y, r, o: (f'<div class="ring" style="left:{x}px;top:{y}px;width:{r}px;height:{r}px;'
                               f'opacity:{o}"></div>')
    deco = ring(-220, -160, 620, .35) + ring(760, 120, 520, .25) + ring(-180, 1480, 560, .22) + ring(820, 1500, 480, .3)
    label = f'<div class="label">Daily Bread · {e(spec["date"][8:].lstrip("0"))} {e(month_name(spec["date"]))}</div>'
    if s["kind"] == "hook":
        body = f'<div class="logo big">{LOGO}</div><div class="hook">{e(spec["hook"])}</div>{label}'
    elif s["kind"] == "verse":
        v = spec["verse"]
        size = 64 if len(v["text"]) < 160 else 54 if len(v["text"]) < 240 else 46
        body = (f'{label}<div class="quote" style="font-size:{size}px">“{e(v["text"])}”</div>'
                f'<div class="ref">{e(v["ref"])}</div>')
    elif s["kind"] == "beat":
        t = s["text"]
        size = 110 if len(t) < 22 else 92 if len(t) < 40 else 76
        body = f'{label}<div class="beat" style="font-size:{size}px">{e(t)}</div>'
    else:
        body = (f'<div class="logo">{LOGO}</div><div class="word">Jesus Worldwide</div>'
                f'<div class="cta">Follow for Daily Bread<br>every morning 🙏</div><div class="handle">@JesusIsWorldwide</div>')
    return f'<section class="s {s["kind"]}">{deco}<div class="inner">{body}</div></section>'


def month_name(date: str) -> str:
    return ["January", "February", "March", "April", "May", "June", "July", "August",
            "September", "October", "November", "December"][int(date[5:7]) - 1]


def render_slides(spec: dict, slides: list[dict], th: dict, out: Path) -> list[Path]:
    css = f"""
    @import url('https://fonts.googleapis.com/css2?family=Dancing+Script:wght@700&family=Inter:wght@500;700;800;900&display=block');
    *{{box-sizing:border-box;margin:0}} body{{width:{W}px;background:#000}}
    .s{{width:{W}px;height:{H}px;position:relative;overflow:hidden;background:{th['bg']};color:{th['ink']};font-family:Inter,sans-serif}}
    .ring{{position:absolute;border-radius:50%;border:34px solid {th['swirl']};box-shadow:0 0 0 70px transparent}}
    .inner{{position:absolute;left:90px;right:90px;top:250px;height:1080px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;gap:34px}}
    .label{{font-size:34px;font-weight:800;letter-spacing:.18em;text-transform:uppercase;color:{th['accent']}}}
    .logo{{width:260px;height:260px}} .logo.big{{width:330px;height:330px}} .logo svg{{width:100%;height:100%}}
    .hook{{font-size:104px;font-weight:900;line-height:1.02;letter-spacing:-.02em}}
    .quote{{font-weight:700;line-height:1.28}}
    .ref{{font-family:'Dancing Script',cursive;font-size:68px;color:{th['accent']}}}
    .beat{{font-weight:900;line-height:1.04;letter-spacing:-.02em}}
    .word{{font-family:'Dancing Script',cursive;font-size:110px;line-height:1}}
    .cta{{font-size:62px;font-weight:800;line-height:1.2}}
    .handle{{font-size:40px;font-weight:700;color:{th['accent']}}}
    """
    page = f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>" + \
           "".join(slide_html(spec, s, th) for s in slides) + "</body></html>"
    html_path = out / "slides.html"
    html_path.write_text(page)
    sheet = out / "slides.png"
    chrome_shot(["--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={out / '.chrome'}",
                 "--force-device-scale-factor=1", f"--window-size={W},{H * len(slides)}",
                 "--virtual-time-budget=7000", html_path.as_uri()], sheet)
    paths = []
    for i in range(len(slides)):
        p = out / f"slide{i}.png"
        run([FFMPEG, "-y", "-loglevel", "error", "-i", str(sheet), "-vf", f"crop={W}:{H}:0:{i * H}", str(p)])
        paths.append(p)
    return paths


# ---------------------------------------------------------------- captions

def ass_time(t: float) -> str:
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def captions(words: list[dict], out: Path, hide: tuple[float, float] | None = None) -> Path:
    """Word-timed captions; `hide` is a (start, end) window (output time) with no captions,
    used while the verse card already shows the same words."""
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 3 or re.search(r"[.,;:!?]$", w["w"]):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    lines = []
    for c in chunks:
        a = c[0]["t"] + LEAD_IN
        b = c[-1]["t"] + c[-1]["d"] + LEAD_IN + 0.05
        if hide and a >= hide[0] - 0.05 and b <= hide[1] + 0.3:
            continue
        text =" ".join(x["w"] for x in c).upper().replace("{", "(").replace("}", ")")
        lines.append(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Cap,,0,0,0,,{text}")
    ass = out / "captions.ass"
    ass.write_text(f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Arial Black,92,&H00FFFFFF,&H00FFFFFF,&H00151515,&H80000000,1,0,0,0,100,100,1,0,1,7,3,2,90,90,430,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(lines) + "\n")
    return ass


# ---------------------------------------------------------------- assemble

def assemble(spec: dict, slides: list[dict], pngs: list[Path], voice: Path, ass: Path,
             chord: tuple, out: Path, total: float) -> Path:
    inputs, filt = [], []
    for i, (s, p) in enumerate(zip(slides, pngs)):
        d = (s["end"] - s["start"]) + (XFADE if i < len(slides) - 1 else 0)
        frames = max(2, int(round(d * FPS)))
        inputs += ["-i", p.name]
        zin = "in" if i % 2 == 0 else "out"
        z = "min(1.0+0.0006*on,1.06)" if zin == "in" else "max(1.06-0.0006*on,1.0)"
        filt.append(f"[{i}:v]scale={int(W*1.25)}:{int(H*1.25)},zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                    f":d={frames}:s={W}x{H}:fps={FPS},setsar=1,format=yuv420p[v{i}]")
    last = "v0"
    for i in range(1, len(slides)):
        off = slides[i]["start"]
        filt.append(f"[{last}][v{i}]xfade=transition=fade:duration={XFADE}:offset={off:.3f}[x{i}]")
        last = f"x{i}"
    filt.append(f"[{last}]subtitles={ass.name},trim=duration={total:.3f}[vout]")

    vi = len(pngs)
    inputs += ["-i", voice.name]
    filt.append(f"[{vi}:a]adelay={int(LEAD_IN*1000)}|{int(LEAD_IN*1000)},aresample=48000,"
                f"loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,apad=whole_dur={total:.3f},asplit=2[voice][key]")
    song = spec.get("_song")
    if song:
        # One of our songs as a soft bed: centre (lead vocal) removed, highs rolled off,
        # ~18 dB under the narration and ducked further whenever the voice speaks.
        inputs += ["-ss", f"{spec['_song_start']:.2f}", "-t", f"{total + 1:.2f}", "-i", song]
        filt.append(f"[{vi+1}:a]aresample=48000,aformat=channel_layouts=stereo,"
                    f"pan=stereo|c0=0.5*c0-0.5*c1|c1=0.5*c0-0.5*c1,"
                    f"highpass=f=110,lowpass=f=3200,aecho=0.8:0.6:40:0.2,"
                    f"loudnorm=I={BED_LUFS}:TP=-9:LRA=7,aresample=48000,"
                    f"afade=t=in:d=1.5,afade=t=out:st={total-1.1:.2f}:d=1.1[bed0]")
        filt.append("[bed0][key]sidechaincompress=threshold=0.03:ratio=5:attack=40:release=600:makeup=1[bed]")
    else:
        f1, f2, f3 = chord
        pad = (f"aevalsrc='0.05*sin(2*PI*{f1}*t)+0.035*sin(2*PI*{f2}*t)+0.035*sin(2*PI*{f3}*t)"
               f"+0.02*sin(2*PI*{f1*2}*t)':s=48000:d={total:.2f}")
        inputs += ["-f", "lavfi", "-i", pad]
        filt.append("[key]anullsink")
        filt.append(f"[{vi+1}:a]tremolo=f=0.25:d=0.35,lowpass=f=1800,aecho=0.8:0.7:60|120:0.25|0.18,"
                    f"volume=0.55,afade=t=in:d=1.2,afade=t=out:st={total-1.6:.2f}:d=1.6[bed]")
    filt.append("[voice][bed]amix=inputs=2:duration=first:normalize=0,"
                f"apad=whole_dur={total:.3f},atrim=duration={total:.3f},loudnorm=I=-14:TP=-1.0[aout]")
    video = out / spec.get("output", "video.mp4")
    run([FFMPEG, "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt),
         "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart",
         "-t", f"{total:.3f}", video.name], cwd=out)
    return video


def main(spec_path: str) -> None:
    spec_file = Path(spec_path).resolve()
    spec, out = json.loads(spec_file.read_text()), spec_file.parent
    day = int(spec["date"][8:10])
    th, chord = THEMES[day % len(THEMES)], CHORDS[day % len(CHORDS)]
    voice, words, vdur = narrate(spec, out)
    total = round(LEAD_IN + vdur + TAIL, 2)
    pool = song_pool()
    if pool:
        song = pool[(day + int(spec["date"][5:7])) % len(pool)]
        length = wav_seconds(song)
        # start somewhere in the middle third, varied by day, so each Short sounds different
        start = max(8.0, min(length - total - 5, length * (0.25 + 0.08 * (day % 5))))
        spec["_song"], spec["_song_start"] = str(song), start
    if total > 59:
        print(f"  warning: {total:.1f}s is long for a Short")
    slides = timeline(spec, words, vdur)
    pngs = render_slides(spec, slides, th, out)
    span = find_span(words, spec["verse"]["text"]) if spec.get("verse") else None
    ass = captions(words, out, (span[0] + LEAD_IN, span[1] + LEAD_IN) if span else None)
    video = assemble(spec, slides, pngs, voice, ass, chord, out, total)
    song_name = Path(spec.get("_song", "pad")).stem
    print(f"{spec['date']}  {total:.1f}s  theme={th['name']}  music={song_name}  -> {video.name}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
