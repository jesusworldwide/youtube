"""Production queue: render what's missing, upload what's ready, within YouTube's quota.

    .venv/bin/python queue_run.py [--render-only] [--max-uploads 5]

Runs daily via launchd (see studio/com.jesusworldwide.studio.plist). Safe to re-run:
specs that already have a youtube_id are skipped, and quota errors stop uploading
cleanly until the next day.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import traceback
from pathlib import Path

from googleapiclient.errors import HttpError

import make_long
import make_short
import yt_publish

RENDERERS = {"daily-bread": make_short.main, "music-video": make_long.main, "compilation": make_long.main}

ROOT = Path(__file__).resolve().parent.parent
PROD = ROOT / "production"
LOG = PROD / "queue.log"


def log(msg: str) -> None:
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M} {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def specs() -> list[Path]:
    items = []
    for p in sorted(PROD.glob("*/*/spec.json")):
        s = json.loads(p.read_text())
        items.append((s["youtube"].get("publish_at", ""), p))
    return [p for _, p in sorted(items)]


def main() -> None:
    import fcntl
    PROD.mkdir(parents=True, exist_ok=True)
    lock = open(PROD / ".queue.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("another queue run is in progress; exiting")
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("--render-only", action="store_true")
    ap.add_argument("--max-uploads", type=int, default=5)
    a = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    uploads = 0
    for p in specs():
        s = json.loads(p.read_text())
        video = p.parent / s.get("output", "video.mp4")
        if s.get("youtube_id"):
            continue
        if not video.exists():
            try:
                RENDERERS[s.get("kind", "daily-bread")](str(p))
                log(f"rendered {p.parent.name}")
            except BaseException as e:  # keep the queue going
                log(f"RENDER FAILED {p.parent.name}: {e!r}")
                continue
        if a.render_only or uploads >= a.max_uploads:
            continue
        pub = s["youtube"].get("publish_at")
        if pub and dt.datetime.fromisoformat(pub.replace("Z", "+00:00")) < now + dt.timedelta(minutes=30):
            log(f"SKIP {p.parent.name}: publish time {pub} has passed; needs a new date")
            continue
        try:
            yt_publish.main(str(p))
            uploads += 1
            log(f"uploaded {p.parent.name} -> {json.loads(p.read_text()).get('youtube_id')}")
        except HttpError as e:
            msg = str(e).lower()
            if "quota" in msg or "uploadlimitexceeded" in msg or "exceeded the number of videos" in msg:
                log("daily quota / channel upload limit reached; stopping uploads until tomorrow")
                a.render_only = True
                continue
            log(f"UPLOAD FAILED {p.parent.name}: {e}")
        except Exception:
            log(f"UPLOAD FAILED {p.parent.name}: {traceback.format_exc(limit=2)}")
    log(f"run finished: {uploads} uploaded")


if __name__ == "__main__":
    sys.exit(main())
