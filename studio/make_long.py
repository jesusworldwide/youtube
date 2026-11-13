"""Render long-form 1920x1080 music videos: official-audio singles and worship compilations.

    .venv/bin/python make_long.py ../production/music/<slug>/spec.json

Spec kinds:
  "music-video": one song -> branded artwork + live waveform + title card
  "compilation": several songs crossfaded, per-song artwork, chapter list written
                 back into the YouTube description
Also renders thumbnail.png (1280x720), which yt_publish.py uploads automatically.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

from make_short import FFMPEG, LOGO, THEMES, chrome_shot, run, wav_seconds

W, H, FPS = 1920, 1080, 30
XF = 4.0  # crossfade between songs in compilations (seconds)
THEME = {t["name"]: t for t in THEMES}


def art_html(title: str, kicker: str, verse: str, ref: str, th: dict, w: int, h: int, big: bool = False) -> str:
    e = html.escape
    s = w / 1920
    rings = "".join(
        f'<div class="ring" style="left:{x*s}px;top:{y*s}px;width:{r*s}px;height:{r*s}px;opacity:{o}"></div>'
        for x, y, r, o in [(-260, -220, 760, .35), (1460, -160, 640, .28), (-200, 700, 560, .22), (1500, 640, 600, .3)])
    tsize = (150 if big else 118) * s
    return f"""<section class="a" style="width:{w}px;height:{h}px;background:{th['bg']};color:{th['ink']}">{rings}
      <div class="logo" style="width:{170*s}px;height:{170*s}px;top:{70*s}px">{LOGO}</div>
      <div class="kicker" style="font-size:{34*s}px;top:{270*s}px;color:{th['accent']}">{e(kicker)}</div>
      <div class="title" style="font-size:{tsize}px;top:{330*s}px">{e(title)}</div>
      <div class="verse" style="font-size:{38*s}px;top:{(560 if big else 520)*s}px">“{e(verse)}”<span style="color:{th['accent']}"> {e(ref)}</span></div>
      <div class="word" style="font-size:{60*s}px;bottom:{50*s}px">Jesus Worldwide</div></section>"""


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Dancing+Script:wght@700&family=Inter:wght@600;800;900&display=block');
*{box-sizing:border-box;margin:0} body{background:#000}
.a{position:relative;overflow:hidden;font-family:Inter,sans-serif}
.ring{position:absolute;border-radius:50%;border:34px solid rgba(255,255,255,.5)}
.logo{position:absolute;left:0;right:0;margin:auto} .logo svg{width:100%;height:100%}
.kicker{position:absolute;left:0;right:0;text-align:center;font-weight:800;letter-spacing:.24em;text-transform:uppercase}
.title{position:absolute;left:6%;right:6%;text-align:center;font-weight:900;letter-spacing:-.02em;line-height:1.02}
.verse{position:absolute;left:14%;right:14%;text-align:center;font-weight:600;line-height:1.35;opacity:.92}
.word{position:absolute;left:0;right:0;text-align:center;font-family:'Dancing Script',cursive}
"""


def render_pngs(sections: list[tuple[str, int, int]], out: Path, name: str) -> list[Path]:
    """sections: (html, w, h). All must share the same width; stacked vertically and cropped."""
    w = sections[0][1]
    total_h = sum(h for _, _, h in sections)
    page = out / f"_{name}.html"
    page.write_text(f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"
                    + "".join(s for s, _, _ in sections) + "</body></html>")
    sheet = out / f"_{name}.png"
    chrome_shot(["--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={out / '.chrome'}",
                 "--force-device-scale-factor=1", f"--window-size={w},{total_h}", "--virtual-time-budget=7000",
                 page.as_uri()], sheet)
    paths, y = [], 0
    for i, (_, sw, sh) in enumerate(sections):
        p = out / f"{name}{i}.png"
        run([FFMPEG, "-y", "-loglevel", "error", "-i", str(sheet), "-vf", f"crop={sw}:{sh}:0:{y}", str(p)])
        paths.append(p)
        y += sh
    return paths


def mmss(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def main(spec_path: str) -> None:
    spec_file = Path(spec_path).resolve()
    spec, out = json.loads(spec_file.read_text()), spec_file.parent
    th = THEME[spec.get("theme", "night")]
    tracks = spec["tracks"]
    durs = [wav_seconds(Path(t["file"])) for t in tracks]

    # artwork: one 1920x1080 per track, plus a 1280x720 thumbnail
    kicker = spec.get("kicker", "Official Audio")
    arts = [(art_html(t["title"], kicker if len(tracks) == 1 else f"{spec['title']} · {i + 1}/{len(tracks)}",
                      t["verse"], t["ref"], THEME[t.get("theme", spec.get("theme", "night"))], W, H), W, H)
            for i, t in enumerate(tracks)]
    pngs = render_pngs(arts, out, "art")
    thumb = render_pngs([(art_html(spec.get("thumb_title", tracks[0]["title"]), spec.get("thumb_kicker", kicker),
                                   tracks[0]["verse"], tracks[0]["ref"], th, 1280, 720, big=True), 1280, 720)], out, "thumb")[0]
    thumb.replace(out / "thumbnail.png")

    # timeline (crossfades shorten the total)
    starts, t = [], 0.0
    for i, d in enumerate(durs):
        starts.append(t)
        t += d - (XF if i < len(durs) - 1 else 0)
    total = t

    inputs, filt = [], []
    for p in pngs:
        inputs += ["-loop", "1", "-framerate", str(FPS), "-i", p.name]
    for tr in tracks:
        inputs += ["-i", tr["file"]]
    n = len(tracks)
    # video: each artwork shown for its song, crossfaded
    for i in range(n):
        d = durs[i] + (0 if i == n - 1 else 0)
        filt.append(f"[{i}:v]trim=duration={d:.3f},setpts=PTS-STARTPTS,format=yuv420p[v{i}]")
    last = "v0"
    for i in range(1, n):
        filt.append(f"[{last}][v{i}]xfade=transition=fade:duration={XF}:offset={starts[i]:.3f}[vx{i}]")
        last = f"vx{i}"
    # audio: crossfade chain, then loudness
    alast = f"{n}:a"
    for i in range(1, n):
        filt.append(f"[{alast}][{n + i}:a]acrossfade=d={XF}:c1=tri:c2=tri[ax{i}]")
        alast = f"ax{i}"
    filt.append(f"[{alast}]aresample=48000,loudnorm=I=-14:TP=-1.0:LRA=11,aresample=48000,asplit=2[aout][aw]")
    # live waveform along the bottom, in brand colours
    filt.append(f"[aw]showwaves=s=1500x150:mode=cline:rate={FPS}:colors=0xFFD60A|0xF7871F:scale=sqrt,"
                f"format=rgba,colorchannelmixer=aa=0.85[wave]")
    filt.append(f"[{last}][wave]overlay=(W-w)/2:H-250:shortest=1,trim=duration={total:.3f}[vout]")

    video = out / spec.get("output", "video.mp4")
    run([FFMPEG, "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt),
         "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
         "-tune", "stillimage", "-pix_fmt", "yuv420p", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart",
         "-t", f"{total:.3f}", video.name], cwd=out)

    if n > 1:  # chapters in the description
        chapters = "\n".join(f"{mmss(s)} {tr['title']}" for s, tr in zip(starts, tracks))
        desc = spec["youtube"]["description"]
        if "{CHAPTERS}" in desc:
            spec["youtube"]["description"] = desc.replace("{CHAPTERS}", chapters)
            spec_file.write_text(json.dumps(spec, indent=2, ensure_ascii=False))
    print(f"{out.name}  {mmss(total)}  tracks={n}  -> {video.name} + thumbnail.png")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
