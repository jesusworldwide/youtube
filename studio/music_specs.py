"""Create release specs for long-form music videos (production/music/<slug>/spec.json).

    .venv/bin/python music_specs.py

Edit RELEASES to plan new ones. Existing specs keep their youtube_id.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SONGS = ROOT / "songs " / "Unreleased"
OUT = ROOT / "production" / "music"

FOOTER = (
    "\n\n🙏 Subscribe for new Afro gospel music every week:\nhttps://www.youtube.com/@JesusIsWorldwide?sub_confirmation=1"
    "\n📖 Daily Bread every morning: https://www.youtube.com/playlist?list=PLbjnEjWYKSSw"
    "\n🌍 https://jesusisworldwide.vercel.app\n✉️ Bookings & ministry invitations: jesusworldwide.hvn@gmail.com"
    "\n\nScripture: King James Version. Music produced with AI tools by Jesus Worldwide."
)
TAGS = ["Jesus Worldwide", "afro gospel", "gospel music", "worship songs", "praise and worship",
        "Christian music", "African gospel", "Ghana gospel music", "gospel music 2026"]

TRACK = {
    "perfect-peace": {"title": "Perfect Peace", "file": SONGS / "Perfect Peace.wav", "theme": "field",
                      "verse": "Thou wilt keep him in perfect peace, whose mind is stayed on thee: because he trusteth in thee.",
                      "ref": "Isaiah 26:3"},
    "rest-in-you": {"title": "Rest in You", "file": SONGS / "Rest in You.wav", "theme": "night",
                    "verse": "Come unto me, all ye that labour and are heavy laden, and I will give you rest.",
                    "ref": "Matthew 11:28"},
    "he-will-do-it": {"title": "He Will Do It", "file": SONGS / "He Will Do It.wav", "theme": "sunrise",
                      "verse": "Faithful is he that calleth you, who also will do it.", "ref": "1 Thessalonians 5:24"},
    "new-heart-gentle-spirit": {"title": "New Heart, Gentle Spirit", "file": SONGS / "New Heart, Gentle Spirit.wav",
                                "theme": "praise",
                                "verse": "A new heart also will I give you, and a new spirit will I put within you.",
                                "ref": "Ezekiel 36:26"},
    "mysteries-of-praise": {"title": "Mysteries of Praise", "file": SONGS / "Mysteries of Praise.wav", "theme": "deep",
                            "verse": "I will sing with the spirit, and I will sing with the understanding also.",
                            "ref": "1 Corinthians 14:15"},
}


def single(slug: str, publish_at: str, extra_tags: list[str]) -> dict:
    t = TRACK[slug]
    return {
        "kind": "music-video", "title": t["title"], "theme": t["theme"], "kicker": "Official Audio",
        "tracks": [{**t, "file": str(t["file"])}], "output": "video.mp4",
        "youtube": {
            "title": f"{t['title']} (Official Audio) | Afro Gospel Worship | Jesus Worldwide",
            "description": (f"\"{t['verse']}\" ({t['ref']}, KJV)\n\n"
                            f"\"{t['title']}\" is a new worship song from Jesus Worldwide, an Afro gospel music ministry "
                            "from Ghana proclaiming the Good News of Jesus Christ to every nation. Let it be the soundtrack "
                            "to your prayer and quiet time today. 🙏\n\n"
                            "💬 Where are you listening from? Share what this song means to you in the comments."
                            + FOOTER + f"\n\n#JesusWorldwide #AfroGospel #WorshipSongs #{t['title'].replace(' ', '').replace(',', '')} #GospelMusic"),
            "tags": [t["title"], f"{t['title']} Jesus Worldwide"] + extra_tags + TAGS,
            "category_id": "10", "publish_at": publish_at,
            "playlist_id": "PLLiIhgd0UoXM" if t["theme"] in ("night", "deep", "field") else "PLe97inruzCn8",
        },
    }


def compilation(publish_at: str) -> dict:
    order = ["perfect-peace", "rest-in-you", "new-heart-gentle-spirit", "he-will-do-it", "mysteries-of-praise"]
    return {
        "kind": "compilation", "title": "Soaking Worship", "theme": "deep", "kicker": "Soaking Worship",
        "thumb_title": "Soaking Worship", "thumb_kicker": "Prayer · Rest · Presence",
        "tracks": [{**TRACK[s], "file": str(TRACK[s]["file"])} for s in order], "output": "video.mp4",
        "youtube": {
            "title": "Soaking Worship: Afro Gospel for Prayer & Quiet Time | Jesus Worldwide",
            "description": ("Spend time in God's presence with five Spirit-filled worship songs from Jesus Worldwide, flowing "
                            "one into the next without breaks. Perfect for prayer, Bible study, work, or rest. 🕊️\n\n"
                            "\"Thou wilt keep him in perfect peace, whose mind is stayed on thee.\" (Isaiah 26:3, KJV)\n\n"
                            "🎵 Songs\n{CHAPTERS}\n\n"
                            "💬 Drop your prayer request in the comments; we pray over every one." + FOOTER
                            + "\n\n#SoakingWorship #AfroGospel #JesusWorldwide #PrayerMusic #WorshipSongs"),
            "tags": ["soaking worship", "prayer music", "worship compilation", "deep worship",
                     "quiet time music"] + TAGS,
            "category_id": "10", "publish_at": publish_at, "playlist_id": "PLLiIhgd0UoXM",
        },
    }


RELEASES = {
    "perfect-peace": single("perfect-peace", "2026-11-20T19:00:00Z", ["peace", "Isaiah 26:3"]),
    "rest-in-you": single("rest-in-you", "2026-11-24T19:00:00Z", ["rest", "Matthew 11:28"]),
    "he-will-do-it": single("he-will-do-it", "2026-11-27T19:00:00Z", ["faith song", "God is faithful"]),
    "new-heart-gentle-spirit": single("new-heart-gentle-spirit", "2026-12-01T19:00:00Z", ["Ezekiel 36:26", "surrender"]),
    "soaking-worship-vol-1": compilation("2026-12-06T19:00:00Z"),
}

if __name__ == "__main__":
    for slug, spec in RELEASES.items():
        d = OUT / slug
        d.mkdir(parents=True, exist_ok=True)
        f = d / "spec.json"
        if f.exists():
            old = json.loads(f.read_text())
            if old.get("youtube_id"):
                spec["youtube_id"] = old["youtube_id"]
        missing = [t["file"] for t in spec["tracks"] if not Path(t["file"]).exists()]
        f.write_text(json.dumps(spec, indent=2, ensure_ascii=False))
        print(f"{slug:26s} {spec['youtube']['publish_at']}  {'MISSING ' + str(missing) if missing else 'ok'}  {len(spec['youtube']['title'])} chars")
