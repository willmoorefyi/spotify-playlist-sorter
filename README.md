# Spotify Playlist Sorter

A Python CLI tool to sort your Spotify playlists alphabetically by artist name.

## Features

- Sort playlists by artist name (A-Z or Z-A)
- Handles playlists of any size via pagination
- OAuth 2.0 authentication with token caching
- Simple command-line interface

## Prerequisites

- Python 3.12 or higher
- A Spotify account
- Spotify Developer credentials (Client ID and Client Secret)

## Getting Started

### 1. Create a Spotify App

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account
3. Click "Create app"
4. Fill in the required fields:
   - App name: "Spotify Playlist Sorter" (or any name you prefer)
   - App description: "CLI tool to sort playlists"
   - Redirect URI: `http://127.0.0.1:8888/callback`
5. Check the agreements and click "Save"
6. Copy your Client ID and Client Secret

### 2. Install the Application

```bash
# Clone the repository
git clone <repository-url>
cd spotify_playlist_sorter

# Install dependencies using Poetry
poetry install

# Or install in development mode
poetry install --with dev
```

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```bash
SPOTIPY_CLIENT_ID="your_client_id_here"
SPOTIPY_CLIENT_SECRET="your_client_secret_here"
SPOTIPY_REDIRECT_URI="http://127.0.0.1:8888/callback"
```

**Important**: Never commit your `.env` file to version control!

## Usage

### Basic Usage

```bash
# Activate the poetry environment
poetry shell

# Sort a playlist by artist (A-Z)
sort-playlist --playlist-id <PLAYLIST_ID>

# Sort in reverse order (Z-A)
sort-playlist --playlist-id <PLAYLIST_ID> --reverse

# Preview the sorted order without changing anything
sort-playlist --playlist-id <PLAYLIST_ID> --dry-run
```

### Finding Your Playlist ID

The playlist ID is the string after `/playlist/` in your Spotify playlist URL:

```
https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M
                                  ^^^^^^^^^^^^^^^^^^^^^^^^
                                  This is your playlist ID
```

### Command-Line Options

```
--playlist-id   (required)  Spotify playlist ID
--reverse                   Sort Z-A instead of A-Z
--dry-run                   Preview the sorted order; make no changes
--no-backup                 Skip the JSON backup before modifying
--backup-dir PATH           Where to write backups (default: backups)
--client-id                 Override SPOTIPY_CLIENT_ID env var
--client-secret             Override SPOTIPY_CLIENT_SECRET env var
--redirect-uri              Override SPOTIPY_REDIRECT_URI env var
```

### Examples

```bash
# Sort a playlist alphabetically
sort-playlist --playlist-id 37i9dQZF1DXcBWIGoYBM5M

# Sort in reverse alphabetical order
sort-playlist --playlist-id 37i9dQZF1DXcBWIGoYBM5M --reverse

# Back up to a custom directory
sort-playlist --playlist-id 37i9dQZF1DXcBWIGoYBM5M --backup-dir ~/spotify-backups

# Provide credentials via command line
sort-playlist --playlist-id 37i9dQZF1DXcBWIGoYBM5M \
  --client-id YOUR_ID \
  --client-secret YOUR_SECRET
```

## How It Works

1. **Authentication**: On first run, the app opens your browser for Spotify OAuth authentication. Your access token is cached locally.
2. **Fetch Tracks**: The app retrieves all tracks from your playlist using pagination.
3. **Sort**: Tracks are sorted alphabetically by artist name, then chronologically by album release date, then in album track order.
4. **Backup**: Before changing anything, the current order is saved to `backups/<playlist_id>-<UTC timestamp>.json` (playlist name, snapshot ID, and every item with URI, artists, album, and date added). If the backup can't be written, the playlist is left untouched and the command exits with code 1.
5. **Update**: The playlist is updated on Spotify in chunks of 100 tracks (API limit).

With `--dry-run`, steps 4–5 are skipped and a numbered preview (`Artist — Album — Track`) is printed instead.

**Note**: Unavailable tracks are dropped when the playlist is rewritten, and re-adding resets each track's "date added". Local files and podcast episodes are kept but Spotify may reject re-adding them; the tool warns when it finds any. Keep the backup until you've checked the result.

## Sorting Logic

- Primary sort: First artist's name (case-insensitive, ignoring leading "the")
- Secondary sort: Album release date, oldest first (undated albums go last; same-date albums are ordered by name)
- Tertiary sort: Position on the album (disc number, then track number)
- `--reverse` flips the artist order only; albums stay chronological and tracks stay in album order
- For tracks with multiple artists, only the first artist is used for sorting
- Artist names starting with "The" are sorted by the word following "The" (e.g., "The Beatles" sorts under "B")

## Development

### Running Tests

```bash
# Run tests with pytest
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=src/spotify_playlist_sorter
```

### Project Structure

```
spotify_playlist_sorter/
|-- src/
|   |-- spotify_playlist_sorter/
|       |-- __init__.py
|       |-- cli.py              # Main application code
|-- tests/
|   |-- __init__.py
|   |-- test_cli.py             # Test suite
|-- pyproject.toml              # Poetry configuration
|-- poetry.lock                 # Locked dependencies
|-- .env                        # Environment variables (not in git)
|-- .gitignore                  # Git ignore rules
|-- README.md                   # This file
```

## Dependencies

- **spotipy**: Spotify Web API wrapper for Python
- **python-dotenv**: Environment variable management

## Troubleshooting

### "No tracks found in playlist"

- Ensure the playlist ID is correct
- Check that the playlist is not empty
- Verify your account has access to the playlist

### Authentication Issues

- Delete `.cache-spotify-playlist-sorter` and try again
- Verify your Client ID and Client Secret are correct
- Ensure the Redirect URI in your Spotify app matches the one in `.env`

### "ERROR: You must provide Spotify client ID and secret"

- Check that your `.env` file exists and contains the correct variables
- Ensure you're running the command from the project root directory
- Try providing credentials via command-line flags instead

## License

This project is licensed under the BSD Zero Clause License (0BSD) - see the [LICENSE.md](LICENSE.md) file for details.

The 0BSD license allows you to use, modify, and distribute this software freely without any attribution requirements or warranties.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Acknowledgments

Built with [Spotipy](https://github.com/spotipy-dev/spotipy), the Spotify Web API wrapper for Python.
