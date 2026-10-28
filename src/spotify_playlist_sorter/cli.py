import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

import spotipy
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth, CacheFileHandler

load_dotenv()  # loads .env into environment variables

VARIOUS_ARTISTS_ID = "0LyfQWJT6nXafLPZqxe9Of"  # Spotify's shared "Various Artists" artist


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


def entry_media(entry: dict) -> dict | None:
    """Return the track/episode of a playlist entry, preferring `item` over the deprecated `track`."""
    return entry.get("item") or entry.get("track")


def spotify_error_detail(e: SpotifyException) -> str:
    """Spotify's error text without the request URL spotipy prefixes to `msg`."""
    return (e.msg or "").split("\n", 1)[-1].strip()


def is_definite_rejection(e: SpotifyException) -> bool:
    """
    True for 4xx errors other than 429, where Spotify refused the request
    outright. spotipy retries 429/5xx, so after those the write may have been
    applied anyway.
    """
    return 400 <= e.http_status < 500 and e.http_status != 429


def is_various_artists_album(t: dict) -> bool:
    """
    True if the track's first album artist is "Various Artists". Only album
    artists are checked; the name match covers entries without an id.
    """
    album_artists = (t.get("album") or {}).get("artists") or []
    if not album_artists:
        return False
    first = album_artists[0]
    return (
        first.get("id") == VARIOUS_ARTISTS_ID
        or (first.get("name") or "").strip().lower() == "various artists"
    )


def primary_sort_key(t: dict) -> str:
    """
    Primary sort key: the album name for "Various Artists" albums, otherwise
    the first album artist, falling back to the first track artist.
    """
    album = t.get("album") or {}
    if is_various_artists_album(t):
        return normalize_artist_name(album.get("name") or "")
    album_artists = album.get("artists") or []
    if album_artists:
        return normalize_artist_name(album_artists[0].get("name") or "")
    artists = t.get("artists") or []
    return normalize_artist_name(artists[0]["name"]) if artists else ""


def build_sorted_tracks(
    items: list[dict], reverse: bool = False
) -> tuple[list[dict], list[dict]]:
    """
    Sort playlist items by album artist (alphabetical; album name for
    "Various Artists" albums), then album (chronological), then position
    within the album (disc, track number).

    `reverse` flips only the primary (album artist / album name) order;
    albums stay oldest-first and tracks stay in album order.

    Returns (sorted_tracks, none_items) where none_items are items whose
    track is unavailable (None) and cannot be re-added.
    """
    tracks = []
    none_items = []
    for entry in items:
        track = entry_media(entry)
        if not track:
            none_items.append(entry)
            continue
        tracks.append(track)

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
    tracks.sort(key=primary_sort_key, reverse=reverse)
    return tracks, none_items


def write_backup(
    sp: spotipy.Spotify, playlist_id: str, items: list[dict], backup_dir: str
) -> Path:
    """Write a JSON backup of the playlist's current order. Raises OSError on failure."""
    metadata = sp.playlist(playlist_id, fields="name,snapshot_id") or {}
    now = datetime.now(timezone.utc)

    backup_tracks = []
    for position, entry in enumerate(items):
        track = entry_media(entry) or {}
        album = track.get("album") or {}
        backup_tracks.append({
            "position": position,
            "uri": track.get("uri"),
            "name": track.get("name"),
            "artists": [a.get("name") for a in (track.get("artists") or [])],
            "album": album.get("name"),
            "is_local": track.get("is_local"),
            "type": track.get("type"),
            "added_at": entry.get("added_at"),
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


def format_artist(t: dict) -> str:
    artists = t.get("artists") or []
    return artists[0]["name"] if artists else "(unknown artist)"


def format_album(t: dict) -> str:
    album = t.get("album") or {}
    album_name = album.get("name") or "(unknown album)"
    year = (album.get("release_date") or "")[:4]
    return f"{album_name} ({year})" if year else album_name


def print_preview(sorted_tracks: list[dict]) -> None:
    """Print the proposed playlist order."""
    width = len(str(len(sorted_tracks)))
    for position, t in enumerate(sorted_tracks, start=1):
        # Show why a Various Artists track sits under its album name.
        prefix = ""
        if is_various_artists_album(t):
            prefix = f"{(t.get('album') or {}).get('name') or '(unknown album)'} [Various Artists] — "
        print(f"{position:0{width}d}. {prefix}{format_artist(t)} — {format_album(t)} — {t.get('name', '')}")


def find_possible_duplicates(sorted_tracks: list[dict]) -> list[list[tuple[int, dict]]]:
    """
    Group tracks with the same first artist and title (case-insensitive).

    Returns groups of (1-based position, track) with more than one entry,
    in order of first appearance.
    """
    groups: dict[tuple[str, str], list[tuple[int, dict]]] = {}
    for position, t in enumerate(sorted_tracks, start=1):
        artists = t.get("artists") or []
        artist_name = normalize_artist_name(artists[0]["name"]).strip() if artists else ""
        title = " ".join((t.get("name") or "").lower().split())
        if not title:
            continue
        groups.setdefault((artist_name, title), []).append((position, t))
    return [group for group in groups.values() if len(group) > 1]


def print_duplicate_warning(sorted_tracks: list[dict]) -> None:
    """Warn about possible duplicate songs (same artist and title)."""
    duplicates = find_possible_duplicates(sorted_tracks)
    if not duplicates:
        return
    width = len(str(len(sorted_tracks)))
    print(
        f"\nWarning: {len(duplicates)} possible duplicate song(s) found "
        "(same artist and title; may be album vs. compilation versions):"
    )
    for group in duplicates:
        _, first = group[0]
        print(f"  {format_artist(first)} — {first.get('name', '')}")
        for position, t in group:
            print(f"    {position:0{width}d}. {format_album(t)}")


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
    try:
        items = fetch_playlist_items(sp, playlist_id)
    except SpotifyException as e:
        print(f"ERROR: Could not read playlist (HTTP {e.http_status}: {spotify_error_detail(e)}).")
        return False
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
        print_duplicate_warning(sorted_tracks)
        print("Dry run: no changes made.")
        return True

    backup_path = None
    if backup:
        try:
            backup_path = write_backup(sp, playlist_id, items, backup_dir)
        except OSError as e:
            print(f"ERROR: Could not write backup ({e}). Aborting; playlist unchanged.")
            return False
        except SpotifyException as e:
            print(
                f"ERROR: Could not write backup (HTTP {e.http_status}: "
                f"{spotify_error_detail(e)}). Aborting; playlist unchanged."
            )
            return False
        print(f"Backup saved to {backup_path}")

    sorted_uris = [t["uri"] for t in sorted_tracks]

    print("Rewriting playlist order on Spotify...")
    chunk_size = 100

    restore_hint = (
        f"Restore from backup: {backup_path}" if backup_path
        else "No backup was written (--no-backup)."
    )

    first_chunk = sorted_uris[:chunk_size]
    try:
        sp.playlist_replace_items(playlist_id, first_chunk)
    except SpotifyException as e:
        print(f"ERROR: Spotify rejected the update (HTTP {e.http_status}: {spotify_error_detail(e)}).")
        if is_definite_rejection(e):
            print("Playlist unchanged.")
            if e.http_status in (403, 404):
                print("Your account may not have permission to edit this playlist.")
            if backup_path:
                print(f"Backup: {backup_path}")
        else:
            print("The playlist may have been modified; check it on Spotify.")
            print(restore_hint)
        return False

    offset = chunk_size
    while offset < len(sorted_uris):
        chunk = sorted_uris[offset : offset + chunk_size]
        try:
            sp.playlist_add_items(playlist_id, chunk)
        except SpotifyException as e:
            print(
                f"ERROR: Spotify rejected the update at track {offset + 1} of {len(sorted_uris)} "
                f"(HTTP {e.http_status}: {spotify_error_detail(e)})."
            )
            print(
                f"The playlist is only partially rewritten (at least {offset} of "
                f"{len(sorted_uris)} tracks)."
            )
            print(restore_hint)
            return False
        offset += chunk_size

    print("Done! Playlist is now sorted by artist, then album release date.")
    print_duplicate_warning(sorted_tracks)
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
