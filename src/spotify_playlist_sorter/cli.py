import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

import spotipy
from spotipy.oauth2 import SpotifyOAuth, CacheFileHandler

load_dotenv()  # loads .env into environment variables


def normalize_artist_name(name: str) -> str:
    """
    Normalize artist name for sorting by removing leading 'the'.

    Examples:
        "The Beatles" -> "beatles"
        "The Crystal Method" -> "crystal method"
        "Them Crooked Vultures" -> "them crooked vultures" (only leading "the")
    """
    lower_name = name.lower()
    if lower_name.startswith("the "):
        return lower_name[4:]  # Remove "the " (4 characters)
    return lower_name


def fetch_playlist_items(sp: spotipy.Spotify, playlist_id: str) -> list[dict]:
    """Fetch all raw playlist items (including unavailable ones) via pagination."""
    items = []
    results = sp.playlist_items(playlist_id, additional_types=["track"])
    while True:
        items.extend(results.get("items", []))
        if results.get("next"):
            results = sp.next(results)
        else:
            break
    return items


def build_sorted_tracks(
    items: list[dict], reverse: bool = False
) -> tuple[list[dict], list[dict]]:
    """
    Sort playlist items by artist (alphabetical), then album (chronological),
    then position within the album (disc, track number).

    `reverse` flips only the artist order; albums stay oldest-first and
    tracks stay in album order.

    Returns (sorted_tracks, none_items) where none_items are items whose
    track is unavailable (None) and cannot be re-added.
    """
    tracks = []
    none_items = []
    for item in items:
        track = item.get("track")
        if not track:
            none_items.append(item)
            continue
        tracks.append(track)

    def artist_key(t: dict) -> str:
        artists = t.get("artists") or []
        return normalize_artist_name(artists[0]["name"]) if artists else ""

    def album_key(t: dict) -> tuple[str, str, str, int, int, str]:
        album = t.get("album") or {}
        # Dates are "YYYY", "YYYY-MM", or "YYYY-MM-DD"; these compare correctly
        # as strings. Albums with no date sort after dated ones.
        release_date = album.get("release_date") or "9999"
        album_name = (album.get("name") or "").lower()
        album_id = album.get("id") or ""
        disc_number = t.get("disc_number") or 0
        track_number = t.get("track_number") or 0
        track_name = (t.get("name") or "").lower()
        return (release_date, album_name, album_id, disc_number, track_number, track_name)

    # Two stable passes so `reverse` applies to artists only.
    tracks.sort(key=album_key)
    tracks.sort(key=artist_key, reverse=reverse)
    return tracks, none_items


def write_backup(
    sp: spotipy.Spotify, playlist_id: str, items: list[dict], backup_dir: str
) -> Path:
    """Write a JSON backup of the playlist's current order. Raises OSError on failure."""
    metadata = sp.playlist(playlist_id, fields="name,snapshot_id") or {}
    now = datetime.now(timezone.utc)

    backup_tracks = []
    for position, item in enumerate(items):
        track = item.get("track") or {}
        album = track.get("album") or {}
        backup_tracks.append({
            "position": position,
            "uri": track.get("uri"),
            "name": track.get("name"),
            "artists": [a.get("name") for a in (track.get("artists") or [])],
            "album": album.get("name"),
            "is_local": track.get("is_local"),
            "type": track.get("type"),
            "added_at": item.get("added_at"),
        })

    backup = {
        "playlist_id": playlist_id,
        "playlist_name": metadata.get("name"),
        "snapshot_id": metadata.get("snapshot_id"),
        "created_at": now.isoformat(),
        "track_count": len(items),
        "tracks": backup_tracks,
    }

    directory = Path(backup_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{playlist_id}-{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(backup, f, indent=2, ensure_ascii=False)
    return path


def print_preview(sorted_tracks: list[dict]) -> None:
    """Print the proposed playlist order."""
    width = len(str(len(sorted_tracks)))
    for position, t in enumerate(sorted_tracks, start=1):
        artists = t.get("artists") or []
        artist_name = artists[0]["name"] if artists else "(unknown artist)"
        album = t.get("album") or {}
        album_name = album.get("name") or "(unknown album)"
        year = (album.get("release_date") or "")[:4]
        if year:
            album_name = f"{album_name} ({year})"
        print(f"{position:0{width}d}. {artist_name} — {album_name} — {t.get('name', '')}")


def sort_playlist_by_artist(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    playlist_id: str,
    reverse: bool = False,
    dry_run: bool = False,
    backup: bool = True,
    backup_dir: str = "backups",
) -> bool:
    """Sort a playlist by artist. Returns False if the operation failed."""
    scope = "playlist-read-private playlist-modify-private playlist-modify-public"

    cache_handler = CacheFileHandler(cache_path=".cache-spotify-playlist-sorter")
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scope,
            open_browser=True,
            cache_handler=cache_handler,
        )
    )

    print(f"Fetching tracks for playlist {playlist_id}...")
    items = fetch_playlist_items(sp, playlist_id)
    if not items:
        print("No tracks found in playlist.")
        return True

    sorted_tracks, none_items = build_sorted_tracks(items, reverse=reverse)
    if not sorted_tracks:
        print("No tracks found in playlist.")
        return True

    print(f"Found {len(sorted_tracks)} tracks. Sorting by artist, then album release date...")

    if len(sorted_tracks) + len(none_items) != len(items):
        print("ERROR: Track count mismatch after sorting. Aborting.")
        return False

    local_count = sum(1 for t in sorted_tracks if t.get("is_local"))
    episode_count = sum(1 for t in sorted_tracks if t.get("type") == "episode")
    if local_count or episode_count:
        print(
            f"Warning: {local_count} local file(s) and {episode_count} episode(s) "
            "found; Spotify may reject re-adding them."
        )
    if none_items:
        print(f"Note: {len(none_items)} unavailable item(s) will be dropped.")

    if dry_run:
        print_preview(sorted_tracks)
        print("Dry run: no changes made.")
        return True

    if backup:
        try:
            backup_path = write_backup(sp, playlist_id, items, backup_dir)
        except OSError as e:
            print(f"ERROR: Could not write backup ({e}). Aborting; playlist unchanged.")
            return False
        print(f"Backup saved to {backup_path}")

    sorted_uris = [t["uri"] for t in sorted_tracks]

    print("Rewriting playlist order on Spotify...")
    chunk_size = 100

    first_chunk = sorted_uris[:chunk_size]
    sp.playlist_replace_items(playlist_id, first_chunk)

    offset = chunk_size
    while offset < len(sorted_uris):
        chunk = sorted_uris[offset : offset + chunk_size]
        sp.playlist_add_items(playlist_id, chunk)
        offset += chunk_size

    print("Done! Playlist is now sorted by artist, then album release date.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Sort a Spotify playlist by artist name."
    )

    parser.add_argument(
        "--playlist-id",
        required=True,
        help="Spotify playlist ID (the part after /playlist/ in the URL).",
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="Sort Z → A instead of A → Z.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the sorted order without modifying the playlist.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip writing a JSON backup before modifying the playlist.",
    )
    parser.add_argument(
        "--backup-dir",
        default="backups",
        help="Directory for JSON backups (default: backups).",
    )
    parser.add_argument(
        "--client-id",
        help="Spotify Client ID (defaults to SPOTIPY_CLIENT_ID env var).",
    )
    parser.add_argument(
        "--client-secret",
        help="Spotify Client Secret (defaults to SPOTIPY_CLIENT_SECRET env var).",
    )
    parser.add_argument(
        "--redirect-uri",
        default=None,
        help="Redirect URI (defaults to SPOTIPY_REDIRECT_URI env var, "
             "or http://127.0.0.1:8888/callback).",
    )

    args = parser.parse_args()

    client_id = args.client_id or os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = args.client_secret or os.getenv("SPOTIPY_CLIENT_SECRET")
    redirect_uri = (
        args.redirect_uri
        or os.getenv("SPOTIPY_REDIRECT_URI")
        or "http://127.0.0.1:8888/callback"
    )

    if not client_id or not client_secret:
        print(
            "ERROR: You must provide Spotify client ID and secret.\n"
            "Use --client-id / --client-secret or set SPOTIPY_CLIENT_ID / SPOTIPY_CLIENT_SECRET."
        )
        sys.exit(1)

    success = sort_playlist_by_artist(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        playlist_id=args.playlist_id,
        reverse=args.reverse,
        dry_run=args.dry_run,
        backup=not args.no_backup,
        backup_dir=args.backup_dir,
    )
    if success is False:
        sys.exit(1)


if __name__ == "__main__":
    main()
