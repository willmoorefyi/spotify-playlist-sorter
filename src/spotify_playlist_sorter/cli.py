import os
import sys
import argparse
from dotenv import load_dotenv

import spotipy
from spotipy.oauth2 import SpotifyOAuth, CacheFileHandler

load_dotenv()  # loads .env into environment variables

def sort_playlist_by_artist(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    playlist_id: str,
    reverse: bool = False,
):
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
    tracks = []
    results = sp.playlist_items(playlist_id, additional_types=["track"])
    while True:
        for item in results.get("items", []):
            track = item.get("track")
            if not track:
                continue
            tracks.append(track)
        if results.get("next"):
            results = sp.next(results)
        else:
            break

    if not tracks:
        print("No tracks found in playlist.")
        return

    print(f"Found {len(tracks)} tracks. Sorting by artist...")

    indexed_tracks = []
    for idx, t in enumerate(tracks):
        artists = t.get("artists") or []
        artist_name = artists[0]["name"].lower() if artists else ""
        track_name = t.get("name", "")
        uri = t["uri"]
        indexed_tracks.append((idx, artist_name, track_name, uri))

    indexed_tracks.sort(key=lambda x: (x[1], x[2].lower()), reverse=reverse)
    sorted_uris = [t[3] for t in indexed_tracks]

    if len(sorted_uris) != len(tracks):
        print("ERROR: Track count mismatch after sorting. Aborting.")
        return

    print("Rewriting playlist order on Spotify...")
    chunk_size = 100

    first_chunk = sorted_uris[:chunk_size]
    sp.playlist_replace_items(playlist_id, first_chunk)

    offset = chunk_size
    while offset < len(sorted_uris):
        chunk = sorted_uris[offset : offset + chunk_size]
        sp.playlist_add_items(playlist_id, chunk)
        offset += chunk_size

    print("Done! Playlist is now sorted by artist.")


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

    sort_playlist_by_artist(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        playlist_id=args.playlist_id,
        reverse=args.reverse,
    )


if __name__ == "__main__":
    main()
