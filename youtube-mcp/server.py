"""MCP server that lets Claude read and manage the Jesus Worldwide YouTube channel."""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

import yt_auth

server = MCPServer(
    name="youtube",
    instructions=(
        "Tools for the channel owner's own YouTube channel (YouTube Data API v3 and "
        "YouTube Analytics API). Read tools are safe. Write tools change the live "
        "channel, so state what will change before calling them."
    ),
)

READ = ToolAnnotations(read_only_hint=True, open_world_hint=True)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=True)


def api_errors(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except HttpError as e:
            raise ToolError(f"YouTube API error {e.status_code}: {e.reason}") from None
        except (RuntimeError, ValueError) as e:
            raise ToolError(str(e)) from None
    return wrapper


def _my_channel(parts: str) -> dict[str, Any]:
    items = yt_auth.youtube().channels().list(part=parts, mine=True).execute().get("items", [])
    if not items:
        raise RuntimeError("The signed-in Google account has no YouTube channel.")
    return items[0]


def _video_summary(v: dict[str, Any]) -> dict[str, Any]:
    sn, st = v.get("snippet", {}), v.get("statistics", {})
    return {
        "id": v["id"],
        "url": f"https://youtu.be/{v['id']}",
        "title": sn.get("title"),
        "published": sn.get("publishedAt"),
        "category_id": sn.get("categoryId"),
        "duration": v.get("contentDetails", {}).get("duration"),
        "privacy": v.get("status", {}).get("privacyStatus"),
        "views": st.get("viewCount"),
        "likes": st.get("likeCount"),
        "comments": st.get("commentCount"),
        "tags": sn.get("tags", []),
        "description": sn.get("description"),
    }


# ---------------------------------------------------------------- read tools

@server.tool(annotations=READ)
@api_errors
def channel_info() -> dict[str, Any]:
    """Channel title, handle, stats, description, keywords, trailer and country."""
    ch = _my_channel("snippet,statistics,brandingSettings,contentDetails")
    b = ch.get("brandingSettings", {}).get("channel", {})
    return {
        "id": ch["id"],
        "title": ch["snippet"]["title"],
        "handle": ch["snippet"].get("customUrl"),
        "statistics": ch["statistics"],
        "description": b.get("description", ch["snippet"].get("description")),
        "keywords": b.get("keywords"),
        "country": b.get("country"),
        "trailer_video_id": b.get("unsubscribedTrailer"),
        "uploads_playlist_id": ch["contentDetails"]["relatedPlaylists"]["uploads"],
    }


@server.tool(annotations=READ)
@api_errors
def list_videos(max_results: int = 50) -> list[dict[str, Any]]:
    """All uploads (videos and Shorts), newest first, with stats, tags and descriptions."""
    yt = yt_auth.youtube()
    uploads = _my_channel("contentDetails")["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while len(ids) < max_results:
        resp = yt.playlistItems().list(
            part="contentDetails", playlistId=uploads, maxResults=50, pageToken=token
        ).execute()
        ids += [i["contentDetails"]["videoId"] for i in resp.get("items", [])]
        token = resp.get("nextPageToken")
        if not token:
            break
    ids = ids[:max_results]
    out = []
    for i in range(0, len(ids), 50):
        resp = yt.videos().list(
            part="snippet,statistics,contentDetails,status", id=",".join(ids[i:i + 50])
        ).execute()
        out += [_video_summary(v) for v in resp.get("items", [])]
    return out


@server.tool(annotations=READ)
@api_errors
def get_video(video_id: str) -> dict[str, Any]:
    """Full details for one video."""
    items = yt_auth.youtube().videos().list(
        part="snippet,statistics,contentDetails,status", id=video_id
    ).execute().get("items", [])
    if not items:
        raise RuntimeError(f"No video {video_id} on this channel.")
    return _video_summary(items[0])


@server.tool(annotations=READ)
@api_errors
def list_categories(region_code: str = "GH") -> list[dict[str, str]]:
    """Video category IDs (e.g. Music = 10)."""
    resp = yt_auth.youtube().videoCategories().list(part="snippet", regionCode=region_code).execute()
    return [{"id": c["id"], "title": c["snippet"]["title"]} for c in resp.get("items", [])
            if c["snippet"].get("assignable")]


@server.tool(annotations=READ)
@api_errors
def list_playlists() -> list[dict[str, Any]]:
    """The channel's playlists."""
    resp = yt_auth.youtube().playlists().list(
        part="snippet,contentDetails,status", mine=True, maxResults=50
    ).execute()
    return [{
        "id": p["id"],
        "title": p["snippet"]["title"],
        "description": p["snippet"].get("description"),
        "items": p["contentDetails"]["itemCount"],
        "privacy": p["status"]["privacyStatus"],
    } for p in resp.get("items", [])]


@server.tool(annotations=READ)
@api_errors
def analytics_report(
    start_date: str,
    end_date: str,
    metrics: str = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,subscribersLost,likes,shares",
    dimensions: str | None = None,
    filters: str | None = None,
    sort: str | None = None,
    max_results: int | None = None,
) -> dict[str, Any]:
    """YouTube Analytics report for the channel. Dates are YYYY-MM-DD.

    Useful dimensions: day, month, video, country, insightTrafficSourceType,
    deviceType, ageGroup, gender (ageGroup/gender need metric viewerPercentage).
    Example: top videos -> dimensions="video", sort="-views", max_results=10.
    """
    params: dict[str, Any] = {
        "ids": "channel==MINE", "startDate": start_date, "endDate": end_date, "metrics": metrics,
    }
    if dimensions:
        params["dimensions"] = dimensions
    if filters:
        params["filters"] = filters
    if sort:
        params["sort"] = sort
    if max_results:
        params["maxResults"] = max_results
    resp = yt_auth.analytics().reports().query(**params).execute()
    cols = [h["name"] for h in resp.get("columnHeaders", [])]
    return {"columns": cols, "rows": [dict(zip(cols, r)) for r in resp.get("rows", [])]}


# --------------------------------------------------------------- write tools

@server.tool(annotations=WRITE)
@api_errors
def update_video(
    video_id: str,
    title: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    category_id: str | None = None,
) -> dict[str, Any]:
    """Change a video's title, description, tags and/or category (Music = "10").
    Fields left out stay as they are.

    The altered/synthetic (AI) content disclosure is NOT settable here: the API
    accepts status.containsSyntheticMedia and echoes it back, but YouTube does not
    save it (confirmed in Studio, Nov 2026). Set it in YouTube Studio instead."""
    yt = yt_auth.youtube()
    items = yt.videos().list(part="snippet,status", id=video_id).execute().get("items", [])
    if not items:
        raise RuntimeError(f"No video {video_id} on this channel.")
    v = items[0]
    sn = v["snippet"]
    before = {"title": sn.get("title"), "category_id": sn.get("categoryId"), "tags": sn.get("tags", [])}

    if title is not None:
        if len(title) > 100:
            raise ValueError(f"Title is {len(title)} characters; YouTube allows 100.")
        sn["title"] = title
    if description is not None:
        if len(description) > 5000:
            raise ValueError(f"Description is {len(description)} characters; YouTube allows 5000.")
        sn["description"] = description
    if tags is not None:
        if sum(len(t) + 1 for t in tags) > 500:
            raise ValueError("Tags exceed YouTube's ~500 character limit.")
        sn["tags"] = tags
    if category_id is not None:
        sn["categoryId"] = category_id

    body = {"id": video_id, "snippet": {k: sn[k] for k in
            ("title", "description", "tags", "categoryId", "defaultLanguage") if k in sn}}
    res = yt.videos().update(part="snippet", body=body).execute()
    rs = res["snippet"]
    return {
        "video_id": video_id,
        "before": before,
        "after": {"title": rs.get("title"), "category_id": rs.get("categoryId"), "tags": rs.get("tags", [])},
    }


@server.tool(annotations=WRITE)
@api_errors
def set_thumbnail(video_id: str, image_path: str) -> dict[str, Any]:
    """Upload a custom thumbnail (JPG/PNG, under 2 MB, ideally 1280x720).
    The channel must be phone-verified to use custom thumbnails."""
    p = Path(image_path).expanduser().resolve()
    if not p.is_file():
        raise ValueError(f"File not found: {p}")
    if p.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Thumbnail must be under 2 MB.")
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    res = yt_auth.youtube().thumbnails().set(
        videoId=video_id, media_body=MediaFileUpload(str(p), mimetype=mime)
    ).execute()
    return {"video_id": video_id, "thumbnails": res.get("items", [])}


@server.tool(annotations=WRITE)
@api_errors
def update_channel(
    description: str | None = None,
    keywords: str | None = None,
    trailer_video_id: str | None = None,
) -> dict[str, Any]:
    """Change the channel description (max 1000 characters), keywords (space-separated,
    multi-word terms in double quotes) and/or the trailer shown to non-subscribers.

    IMPORTANT: always pass ALL THREE fields together. YouTube serves stale channel
    settings for several minutes after a write, and this tool writes back every field,
    so updating one field alone can silently revert a recent change to another."""
    if description is not None and len(description) > 1000:
        raise ValueError(f"Channel description is {len(description)} characters; YouTube allows 1000.")
    yt = yt_auth.youtube()
    ch = _my_channel("brandingSettings")
    b = ch.get("brandingSettings", {}).get("channel", {})
    before = {k: b.get(k) for k in ("description", "keywords", "unsubscribedTrailer")}
    if description is not None:
        b["description"] = description
    if keywords is not None:
        b["keywords"] = keywords
    if trailer_video_id is not None:
        b["unsubscribedTrailer"] = trailer_video_id
    res = yt.channels().update(
        part="brandingSettings", body={"id": ch["id"], "brandingSettings": {"channel": b}}
    ).execute()
    a = res["brandingSettings"]["channel"]
    return {"before": before, "after": {k: a.get(k) for k in before}}


@server.tool(annotations=WRITE)
@api_errors
def create_playlist(title: str, description: str = "", privacy: str = "public") -> dict[str, Any]:
    """Create a playlist. privacy: public, unlisted or private."""
    res = yt_auth.youtube().playlists().insert(
        part="snippet,status",
        body={"snippet": {"title": title, "description": description},
              "status": {"privacyStatus": privacy}},
    ).execute()
    return {"id": res["id"], "title": res["snippet"]["title"],
            "url": f"https://www.youtube.com/playlist?list={res['id']}"}


@server.tool(annotations=WRITE)
@api_errors
def add_to_playlist(playlist_id: str, video_id: str) -> dict[str, Any]:
    """Add a video to the end of a playlist."""
    res = yt_auth.youtube().playlistItems().insert(
        part="snippet",
        body={"snippet": {"playlistId": playlist_id,
                          "resourceId": {"kind": "youtube#video", "videoId": video_id}}},
    ).execute()
    return {"playlist_item_id": res["id"], "playlist_id": playlist_id, "video_id": video_id}


if __name__ == "__main__":
    server.run("stdio")
