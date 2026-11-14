"""Upload and schedule videos on @JesusIsWorldwide using the youtube-mcp sign-in.

    .venv/bin/python yt_publish.py production/daily-bread/2026-12-01/spec.json

The spec's "youtube" block holds title, description, tags, category_id,
publish_at (ISO 8601 UTC, e.g. 2026-12-01T06:00:00Z) and an optional playlist_id.
Videos are uploaded as private and YouTube makes them public at publish_at.

Quota: an upload costs 1,600 of the 10,000 daily units (about 6 uploads a day).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "youtube-mcp"))

import yt_auth  # noqa: E402  (shared OAuth token from youtube-mcp)
from googleapiclient.errors import HttpError  # noqa: E402
from googleapiclient.http import MediaFileUpload  # noqa: E402


def upload(video_path: Path, meta: dict, thumbnail: Path | None = None) -> str:
    yt = yt_auth.youtube()
    status = {
        "privacyStatus": "private" if meta.get("publish_at") else meta.get("privacy", "public"),
        "selfDeclaredMadeForKids": False,
        "embeddable": True,
        "license": "youtube",
        # Sent for completeness; YouTube does not reliably save it via the API,
        # so Altered content must still be confirmed in Studio.
        "containsSyntheticMedia": True,
    }
    if meta.get("publish_at"):
        status["publishAt"] = meta["publish_at"]
    body = {
        "snippet": {
            "title": meta["title"][:100],
            "description": meta["description"][:5000],
            "tags": meta.get("tags", []),
            "categoryId": str(meta.get("category_id", "10")),
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": status,
    }
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp, retries = None, 0
    while resp is None:
        try:
            prog, resp = req.next_chunk()
            if prog:
                print(f"  uploading… {int(prog.progress() * 100)}%", flush=True)
        except HttpError as e:
            if e.status_code in (500, 502, 503, 504) and retries < 5:
                retries += 1
                time.sleep(2 ** retries)
                continue
            raise
        except (OSError, TimeoutError) as e:
            # Wi-Fi drop mid-upload (14 Nov 2026): wait, then resume from the last chunk.
            if retries < 5:
                retries += 1
                print(f"  network error ({e.__class__.__name__}); resuming in {15 * retries}s", flush=True)
                time.sleep(15 * retries)
                continue
            raise
    vid = resp["id"]
    print(f"  uploaded https://youtu.be/{vid}  ({status['privacyStatus']}, publishAt={status.get('publishAt')})")

    if thumbnail and thumbnail.exists():
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumbnail))).execute()
        print("  thumbnail set")
    if meta.get("playlist_id"):
        yt.playlistItems().insert(part="snippet", body={"snippet": {
            "playlistId": meta["playlist_id"],
            "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
        print(f"  added to playlist {meta['playlist_id']}")
    return vid


def main(spec_path: str) -> None:
    spec_file = Path(spec_path).resolve()
    spec = json.loads(spec_file.read_text())
    out_dir = spec_file.parent
    if spec.get("youtube_id"):
        print(f"Already uploaded: https://youtu.be/{spec['youtube_id']}")
        return
    video = out_dir / spec.get("output", "video.mp4")
    thumb = out_dir / "thumbnail.png" if (out_dir / "thumbnail.png").exists() else None
    vid = upload(video, spec["youtube"], thumb)
    spec["youtube_id"] = vid
    spec_file.write_text(json.dumps(spec, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
