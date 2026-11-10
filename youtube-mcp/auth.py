"""Run once to connect your YouTube channel:  .venv/bin/python auth.py"""

from yt_auth import TOKEN, run_login, youtube

if __name__ == "__main__":
    run_login()
    resp = youtube().channels().list(part="snippet,statistics", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        print("Signed in, but this Google account has no YouTube channel.")
        print("Run again and pick the account or Brand Account that owns @JesusIsWorldwide.")
    else:
        ch = items[0]
        print(f"✅ Connected to: {ch['snippet']['title']} ({ch['snippet'].get('customUrl', '')})")
        print(f"   Subscribers: {ch['statistics'].get('subscriberCount')}  Videos: {ch['statistics'].get('videoCount')}")
        print(f"   Token saved to {TOKEN}. Keep this file private.")
