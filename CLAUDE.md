# CLAUDE.md - Development Notes & Project Tracking

This file tracks development progress, architectural decisions, and future improvements for the Spotify Playlist Sorter project.

## Project Overview

A Python CLI tool that sorts Spotify playlists alphabetically by artist name using the Spotify Web API.

## Technology Stack

- **Language**: Python 3.12+
- **Package Manager**: Poetry
- **Key Libraries**:
  - spotipy (Spotify API wrapper)
  - python-dotenv (environment configuration)
- **Authentication**: OAuth 2.0 with browser-based flow

## Current State (2025-12-11)

### Completed
- ✅ Core functionality: Sort playlists by artist name
- ✅ Reverse sorting option (Z→A)
- ✅ OAuth authentication with token caching
- ✅ Pagination support for large playlists
- ✅ Chunked playlist updates (respects 100-track API limit)
- ✅ Comprehensive README.md documentation
- ✅ Proper .gitignore for Python projects
- ✅ Test suite with unit tests

### Current Features
- Sort by first artist name (primary) and track name (secondary)
- Command-line interface with argparse
- Environment variable configuration via .env
- Error handling for missing credentials and empty playlists

## Architecture Notes

### File Structure
```
src/spotify_playlist_sorter/
  ├── cli.py           # Main CLI logic and sorting function
  └── __init__.py      # Package marker

tests/
  ├── test_cli.py      # Unit tests
  └── __init__.py      # Package marker
```

### Key Functions

#### Helpers
- `fetch_playlist_items()`: paginated fetch of raw playlist items (including unavailable ones)
- `build_sorted_tracks()`: returns `(sorted_tracks, none_items)`; the sort key lives in its inner `sort_key()`
- `write_backup()`: writes the JSON backup of the original order; raises `OSError` on failure
- `print_preview()`: numbered dry-run output

#### `sort_playlist_by_artist()`
- **Purpose**: Orchestrates the sort; returns `False` on failure
- **Steps**:
  1. Authenticate with Spotify OAuth
  2. Fetch all items, sort by artist → album → track name
  3. Warn about local files / episodes; note unavailable items that will be dropped
  4. `--dry-run`: print preview and stop
  5. Write JSON backup (abort if it fails) unless `--no-backup`
  6. Update playlist in 100-track chunks

#### `main()`
- **Purpose**: CLI entry point
- **Handles**: Argument parsing, credential validation, function invocation, exit code 1 on failure

### API Considerations
- **Spotify Playlist API Limits**:
  - 100 tracks per request (fetch)
  - 100 tracks per request (update)
- **Required OAuth Scopes**:
  - `playlist-read-private`
  - `playlist-modify-private`
  - `playlist-modify-public`

## Known Limitations

1. **Single Artist Sorting**: Only uses the first artist for multi-artist tracks
2. **Artist-Only Sorting**: Cannot sort by album, release date, or other metadata
3. **No Restore**: Backups are written as JSON but there's no restore command yet
4. **Browser Required**: OAuth flow requires browser access (no headless mode)
5. **Non-atomic Rewrite**: A local-file URI in a later chunk can fail after the replace call has truncated the playlist; restore from backup
6. **Date Added Reset**: Rewriting the playlist resets each track's "date added"

## Future Enhancements

### High Priority
- [x] Add dry-run mode to preview changes before applying
- [x] Playlist backup (JSON)
- [ ] Playlist restore from backup
- [ ] Support for additional sort options:
  - [ ] By album name
  - [ ] By release date
  - [ ] By track name
  - [ ] By date added to playlist
  - [ ] Custom sort orders (multi-field)

### Medium Priority
- [ ] Better error handling and user feedback
- [ ] Progress bars for long operations
- [ ] Logging system (optional verbose mode)
- [ ] Configuration file support (.config.toml)
- [ ] Undo last sort operation
- [ ] Sort multiple playlists in batch

### Low Priority
- [ ] Interactive mode with playlist selection
- [ ] Integration tests with mock Spotify API
- [ ] Support for sorting by multiple artists (not just first)
- [ ] Custom sort rules (e.g., ignore "The" in artist names)
- [ ] Web UI alternative to CLI
- [ ] Support for saved albums and liked songs

## Testing Strategy

### Current Coverage
- Argument parsing validation
- Credential handling
- Track sorting logic
- Empty playlist handling
- Track count validation

### Test Approach
- Mock Spotify API calls to avoid live API dependency
- Test data transformation and sorting logic
- Validate error handling paths
- Ensure correct chunking behavior

## Development Guidelines

### Code Style
- Follow PEP 8 conventions
- Use type hints for function parameters
- Keep functions focused and single-purpose
- Add docstrings for public functions

### Testing
- Write tests before adding new features (TDD approach)
- Maintain test coverage above 80%
- Use mocking for external API calls
- Test both success and failure scenarios

### Security
- Never commit `.env` or `.cache-*` files
- Validate all user inputs
- Handle API credentials securely
- Sanitize error messages (don't leak credentials)

## Common Development Tasks

### Adding a New Sort Option

1. Add argument to parser in `main()`
2. Pass argument to `sort_playlist_by_artist()`
3. Modify `sort_key()` inside `build_sorted_tracks()`
4. Update README.md with new option
5. Add tests for new sort behavior

### Debugging OAuth Issues

1. Delete `.cache-spotify-playlist-sorter`
2. Verify Redirect URI matches Spotify app settings
3. Check Client ID/Secret are correct
4. Ensure required scopes are present

### Running Local Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src/spotify_playlist_sorter

# Run specific test
poetry run pytest tests/test_cli.py::test_function_name

# Run with verbose output
poetry run pytest -v
```

## Changelog

### 2026-10-28
- Added `--dry-run` preview mode
- Added automatic JSON backup before modifying playlists (`--no-backup`, `--backup-dir`)
- Refactored `cli.py` into helpers; `main()` exits 1 on failure
- Warn about local files/episodes and unavailable items

### 2025-12-11
- Created comprehensive README.md
- Created CLAUDE.md for project tracking
- Fixed .gitignore typo and added Python-specific ignores
- Added initial test suite with unit tests
- Documented current architecture and limitations

## Resources

- [Spotify Web API Documentation](https://developer.spotify.com/documentation/web-api)
- [Spotipy Documentation](https://spotipy.readthedocs.io/)
- [Poetry Documentation](https://python-poetry.org/docs/)

## Notes

- The app modifies playlists in-place; there's no undo feature currently
- OAuth token is cached locally to avoid repeated authentication
- First artist is used for sorting on multi-artist tracks (matches most music library behaviors)
- Project uses Poetry for dependency management instead of pip/requirements.txt
