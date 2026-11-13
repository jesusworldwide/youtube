"""Turn a month of Daily Bread scripts (content/daily-bread/*.md) into render specs.

    .venv/bin/python daily_bread.py ../content/daily-bread/2026-12-december.md [--only 2026-12-01]

Writes production/daily-bread/<date>/spec.json for each day.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "production" / "daily-bread"

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
VOICE = "en-US-AndrewNeural"  # chosen by the user on 2026-11-13, for all videos
FOOTER = (
    "\n\n🎵 Our songs: https://www.youtube.com/@JesusIsWorldwide/videos"
    "\n🙏 Subscribe for Daily Bread every morning: https://www.youtube.com/@JesusIsWorldwide?sub_confirmation=1"
    "\n🌍 https://jesusisworldwide.vercel.app"
    "\n\nScripture: King James Version (public domain). Voice and visuals produced with AI tools by Jesus Worldwide."
)


def field(block: str, name: str) -> str:
    m = re.search(rf"- \*\*{re.escape(name)}[^*]*:\*\*\s*(.+)", block)
    return m.group(1).strip() if m else ""


def parse(md: str, year: int) -> list[dict]:
    days = []
    for block in re.split(r"\n(?=### )", md):
        head = re.match(r"### (\w{3}) (\d{1,2}) (\w{3}) · (.+?) · (.+)", block)
        if not head:
            continue
        _, d, mon, fmt, theme = head.groups()
        date = f"{year}-{MONTHS[mon]:02d}-{int(d):02d}"
        verse_line = field(block, "Verse")
        vm = re.match(r'"(.+)"\s*\((.+?),\s*(KJV|WEB)\)', verse_line)
        beats_m = re.search(r"- \*\*On-screen text beats:\*\*\s*\n((?:\s+- .+\n?)+)", block)
        beats = [b.strip()[2:].strip() for b in beats_m.group(1).strip().splitlines()] if beats_m else []
        desc_m = re.search(r"- \*\*Description:\*\*\s*(.+?)(?=\n### |\n---|\Z)", block, re.S)
        desc = desc_m.group(1).strip() if desc_m else ""
        tags = sorted(set(re.findall(r"#(\w+)", desc)))
        title = field(block, "Title")
        days.append({
            "kind": "daily-bread",
            "date": date,
            "format": fmt.strip(),
            "theme": theme.strip(),
            "voice": VOICE,
            "rate": "-6%",
            "hook": field(block, "On-screen hook"),
            "verse": {"text": vm.group(1), "ref": f"{vm.group(2)} ({vm.group(3)})"} if vm else None,
            "script": field(block, "Script"),
            "beats": beats,
            "output": "video.mp4",
            "youtube": {
                "title": title,
                "description": desc + FOOTER,
                "tags": ["Daily Bread", "Jesus Worldwide", "Bible verse", "daily devotional", "Christian shorts"]
                        + [t for t in tags if t.lower() not in ("shorts",)],
                "category_id": "27",  # Education: spoken devotional content
                "publish_at": f"{date}T06:00:00Z",
                "playlist_id": "PLbjnEjWYKSSw",
            },
        })
    return days


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("markdown")
    ap.add_argument("--only")
    a = ap.parse_args()
    md_path = Path(a.markdown).resolve()
    year = int(re.search(r"(20\d\d)", md_path.name).group(1))
    for d in parse(md_path.read_text(), year):
        if a.only and d["date"] != a.only:
            continue
        out = OUT / d["date"]
        out.mkdir(parents=True, exist_ok=True)
        spec = out / "spec.json"
        if spec.exists():
            old = json.loads(spec.read_text())
            if old.get("youtube_id"):
                d["youtube_id"] = old["youtube_id"]  # never lose an upload record
        spec.write_text(json.dumps(d, indent=2, ensure_ascii=False))
        ok = "ok" if d["verse"] and d["script"] and d["hook"] and d["beats"] else "INCOMPLETE"
        print(f"{d['date']}  {ok}  {d['youtube']['title']}")


if __name__ == "__main__":
    main()
