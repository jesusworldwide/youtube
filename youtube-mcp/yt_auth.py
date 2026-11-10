"""Shared Google OAuth helpers for the Jesus Worldwide YouTube tools."""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

HERE = Path(__file__).resolve().parent
CLIENT_SECRET = HERE / "client_secret.json"
TOKEN = HERE / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube",  # read + edit videos, playlists, channel
    "https://www.googleapis.com/auth/yt-analytics.readonly",  # read analytics
]


def run_login() -> Credentials:
    """Open a browser so the channel owner can approve access. Saves token.json."""
    if not CLIENT_SECRET.exists():
        raise SystemExit(
            f"Missing {CLIENT_SECRET.name}. Download your OAuth client (Desktop app) "
            f"from Google Cloud Console and save it as:\n  {CLIENT_SECRET}"
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    TOKEN.write_text(creds.to_json())
    TOKEN.chmod(0o600)
    return creds


def load_credentials() -> Credentials:
    """Load saved credentials, refreshing them if needed. Never opens a browser."""
    if not TOKEN.exists():
        raise RuntimeError(
            "Not signed in yet. In a terminal, run:\n"
            f'  cd "{HERE}" && .venv/bin/python auth.py'
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN.write_text(creds.to_json())
        else:
            raise RuntimeError("Saved sign-in is no longer valid. Run auth.py again.")
    return creds


def youtube():
    return build("youtube", "v3", credentials=load_credentials(), cache_discovery=False)


def analytics():
    return build("youtubeAnalytics", "v2", credentials=load_credentials(), cache_discovery=False)
