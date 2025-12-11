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

#### `sort_playlist_by_artist()`
- **Location**: `cli.py:11-78`
- **Purpose**: Main sorting logic
- **Steps**:
  1. Authenticate with Spotify OAuth
  2. Fetch all tracks via pagination
  3. Extract artist/track names and URIs
  4. Sort alphabetically by artist (then track name)
  5. Update playlist in 100-track chunks

#### `main()`
- **Location**: `cli.py:81-138`
- **Purpose**: CLI entry point
- **Handles**: Argument parsing, credential validation, function invocation

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
3. **No Backup**: Doesn't create a backup before modifying playlists
4. **Browser Required**: OAuth flow requires browser access (no headless mode)
5. **No Dry Run**: Cannot preview changes before applying

## Future Enhancements

### High Priority
- [ ] Add dry-run mode to preview changes before applying
- [ ] Playlist backup/restore functionality
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
3. Modify sorting logic in the lambda function (line 59)
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
