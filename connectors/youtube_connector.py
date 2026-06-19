"""
YouTube connector — authenticates via OAuth2 and pulls liked videos,
watch history signals, and channel subscriptions.

Usage:
    python connectors/youtube_connector.py --auth        # First-time auth
    python connectors/youtube_connector.py --fetch       # Pull latest signals
"""

import os
import json
import datetime
import click
from pathlib import Path
from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

CLIENT_SECRET_FILE = os.getenv("YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")
TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_FILE", "storage/youtube_token.json")
HISTORY_LOG = "storage/history_log.jsonl"


def get_authenticated_service():
    """Authenticate and return a YouTube API service object."""
    creds = None

    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not Path(CLIENT_SECRET_FILE).exists():
                raise FileNotFoundError(
                    f"client_secret.json not found.\n"
                    f"Download it from https://console.cloud.google.com → "
                    f"APIs & Services → Credentials → OAuth 2.0 Client IDs"
                )
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        Path(TOKEN_FILE).parent.mkdir(exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print(f"Token saved to {TOKEN_FILE}")

    return build("youtube", "v3", credentials=creds)


def fetch_liked_videos(service, max_results=50):
    """Pull liked videos — strong positive taste signal."""
    signals = []
    request = service.videos().list(
        part="snippet,contentDetails,statistics",
        myRating="like",
        maxResults=min(max_results, 50),
    )
    while request and len(signals) < max_results:
        response = request.execute()
        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            signals.append({
                "source": "youtube",
                "event": "liked",
                "video_id": item["id"],
                "title": snippet.get("title", ""),
                "channel": snippet.get("channelTitle", ""),
                "category_id": snippet.get("categoryId", ""),
                "tags": snippet.get("tags", [])[:10],
                "duration": item.get("contentDetails", {}).get("duration", ""),
                "view_count": item.get("statistics", {}).get("viewCount", 0),
                "published_at": snippet.get("publishedAt", ""),
                "captured_at": datetime.datetime.utcnow().isoformat(),
                "signal_weight": 1.0,
            })
        request = service.videos().list_next(request, response)

    return signals


def fetch_subscriptions(service, max_results=50):
    """Pull subscriptions — reveals topic affinity."""
    signals = []
    request = service.subscriptions().list(
        part="snippet",
        mine=True,
        maxResults=50,
        order="relevance",
    )
    while request and len(signals) < max_results:
        response = request.execute()
        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            signals.append({
                "source": "youtube",
                "event": "subscribed",
                "channel_id": snippet.get("resourceId", {}).get("channelId", ""),
                "channel_title": snippet.get("title", ""),
                "description": snippet.get("description", "")[:200],
                "captured_at": datetime.datetime.utcnow().isoformat(),
                "signal_weight": 0.6,
            })
        request = service.subscriptions().list_next(request, response)

    return signals


def fetch_playlist_videos(service, playlist_id, label="playlist", max_results=50):
    """Pull videos from any playlist — use for Watch Later etc."""
    signals = []
    request = service.playlistItems().list(
        part="snippet,contentDetails",
        playlistId=playlist_id,
        maxResults=50,
    )
    while request and len(signals) < max_results:
        response = request.execute()
        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            signals.append({
                "source": "youtube",
                "event": label,
                "video_id": item.get("contentDetails", {}).get("videoId", ""),
                "title": snippet.get("title", ""),
                "channel": snippet.get("videoOwnerChannelTitle", ""),
                "captured_at": datetime.datetime.utcnow().isoformat(),
                "signal_weight": 0.5,
            })
        request = service.playlistItems().list_next(request, response)

    return signals


def append_signals_to_log(signals):
    """Append new signals to the JSONL history log (deduplicates by video_id+event)."""
    existing_keys = set()
    log_path = Path(HISTORY_LOG)
    log_path.parent.mkdir(exist_ok=True)

    if log_path.exists():
        with open(log_path, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    key = f"{entry.get('event')}:{entry.get('video_id', entry.get('channel_id', ''))}"
                    existing_keys.add(key)
                except json.JSONDecodeError:
                    pass

    new_signals = []
    for s in signals:
        key = f"{s.get('event')}:{s.get('video_id', s.get('channel_id', ''))}"
        if key not in existing_keys:
            new_signals.append(s)
            existing_keys.add(key)

    if new_signals:
        with open(log_path, "a") as f:
            for s in new_signals:
                f.write(json.dumps(s) + "\n")

    return len(new_signals)


@click.command()
@click.option("--auth", is_flag=True, help="Authenticate with YouTube (run first time)")
@click.option("--fetch", is_flag=True, help="Fetch signals from your YouTube account")
@click.option("--max", "max_results", default=100, help="Max signals to fetch per type")
def main(auth, fetch, max_results):
    """CuratorTaste AI — YouTube connector."""
    if auth or fetch:
        print("Authenticating with YouTube...")
        service = get_authenticated_service()
        print("Authenticated.")

    if fetch:
        print("Fetching liked videos...")
        liked = fetch_liked_videos(service, max_results)
        print(f"  Found {len(liked)} liked videos")

        print("Fetching subscriptions...")
        subs = fetch_subscriptions(service, max_results)
        print(f"  Found {len(subs)} subscriptions")

        all_signals = liked + subs
        added = append_signals_to_log(all_signals)
        print(f"\nDone. {added} new signals added to {HISTORY_LOG}")
        print(f"Total signals captured: {len(all_signals)}")
    elif not auth:
        print("Use --auth to authenticate or --fetch to pull signals.")
        print("Run: python connectors/youtube_connector.py --help")


if __name__ == "__main__":
    main()
