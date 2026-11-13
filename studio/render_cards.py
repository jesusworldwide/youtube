"""Render square (1080x1080) community-post images from a posts JSON file.

    .venv/bin/python render_cards.py ../content/community/2026-11-12-posts.json

Writes production/community/<date>.png (image posts) and <date>-opt<N>.png (image polls).
"""

from __future__ import annotations

import html
import json
import subprocess
import sys
from pathlib import Path

from make_short import FFMPEG, LOGO, THEMES, chrome_shot, run

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "production" / "community"
S = 1080
THEME = {t["name"]: t for t in THEMES}


def card(img: dict) -> str:
    th = THEME[img.get("theme", "praise")]
    e = html.escape
    rings = "".join(f'<div class="ring" style="left:{x}px;top:{y}px;width:{r}px;height:{r}px;opacity:{o}"></div>'
                    for x, y, r, o in [(-200, -180, 520, .35), (760, -120, 460, .25), (-160, 820, 420, .22), (800, 780, 440, .3)])
    if img.get("verse"):
        v = img["verse"]
        size = 66 if len(v) < 70 else 56 if len(v) < 130 else 46
        body = (f'<div class="label">{e(img.get("label") or img.get("title", ""))}</div>'
                f'<div class="quote" style="font-size:{size}px">“{e(v)}”</div><div class="ref">{e(img["ref"])}</div>')
    else:
        body = f'<div class="title">{e(img["title"])}</div><div class="sub">Daily Bread look</div>'
    return (f'<section class="c" style="background:{th["bg"]};color:{th["ink"]}">{rings}'
            f'<div class="inner">{body}</div>'
            f'<div class="brand"><div class="logo">{LOGO}</div><span>Jesus Worldwide</span></div></section>'
            ).replace("RINGCOLOR", th["swirl"]).replace("ACCENT", th["accent"])


def main(path: str) -> None:
    data = json.loads(Path(path).read_text())
    jobs = []
    for p in data["posts"]:
        if p["type"] == "image":
            jobs.append((f'{p["date"]}.png', p["image"]))
        elif p["type"] == "image_poll":
            for i, o in enumerate(p["options"], 1):
                jobs.append((f'{p["date"]}-opt{i}.png', o["image"]))
    OUT.mkdir(parents=True, exist_ok=True)
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Dancing+Script:wght@700&family=Inter:wght@600;800;900&display=block');
    *{box-sizing:border-box;margin:0} body{width:1080px}
    .c{width:1080px;height:1080px;position:relative;overflow:hidden;font-family:Inter,sans-serif}
    .ring{position:absolute;border-radius:50%;border:30px solid rgba(255,255,255,.55)}
    .inner{position:absolute;left:90px;right:90px;top:90px;bottom:200px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;gap:28px}
    .label{font-size:30px;font-weight:800;letter-spacing:.2em;text-transform:uppercase;opacity:.85}
    .quote{font-weight:800;line-height:1.25}
    .ref{font-family:'Dancing Script',cursive;font-size:60px}
    .title{font-size:120px;font-weight:900;letter-spacing:-.02em;line-height:1}
    .sub{font-size:36px;font-weight:800;letter-spacing:.18em;text-transform:uppercase;opacity:.8}
    .brand{position:absolute;left:0;right:0;bottom:56px;display:flex;justify-content:center;align-items:center;gap:14px}
    .brand .logo{width:70px;height:70px} .brand svg{width:100%;height:100%}
    .brand span{font-family:'Dancing Script',cursive;font-size:52px}
    """
    page = f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>" + \
           "".join(card(img) for _, img in jobs) + "</body></html>"
    sheet_html = OUT / "_cards.html"
    sheet_html.write_text(page)
    sheet = OUT / "_cards.png"
    chrome_shot(["--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={OUT / '.chrome'}",
                 "--force-device-scale-factor=1", f"--window-size={S},{S * len(jobs)}", "--virtual-time-budget=7000",
                 sheet_html.as_uri()], sheet)
    for i, (name, _) in enumerate(jobs):
        run([FFMPEG, "-y", "-loglevel", "error", "-i", str(sheet), "-vf", f"crop={S}:{S}:0:{i * S}", str(OUT / name)])
        print(name)


if __name__ == "__main__":
    main(sys.argv[1])
