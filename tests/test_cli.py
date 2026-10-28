import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from spotify_playlist_sorter.cli import sort_playlist_by_artist, main, normalize_artist_name
import sys


PLAYLIST_METADATA = {"name": "My Playlist", "snapshot_id": "snap_1"}


@pytest.fixture(autouse=True)
def run_in_tmp_path(tmp_path, monkeypatch):
    """Run every test in a temp dir so backups never land in the repo."""
    monkeypatch.chdir(tmp_path)


class TestNormalizeArtistName:
    """Tests for the normalize_artist_name helper function."""

    def test_removes_leading_the(self):
        """Test that 'The' is removed from the beginning."""
        assert normalize_artist_name("The Beatles") == "beatles"
        assert normalize_artist_name("The Crystal Method") == "crystal method"
        assert normalize_artist_name("THE WHO") == "who"

    def test_does_not_remove_the_elsewhere(self):
        """Test that 'the' is only removed from the beginning."""
        assert normalize_artist_name("Them Crooked Vultures") == "them crooked vultures"
        assert normalize_artist_name("At The Drive-In") == "at the drive-in"

    def test_handles_no_the(self):
        """Test artists without 'the' are unchanged (but lowercased)."""
        assert normalize_artist_name("Daft Punk") == "daft punk"
        assert normalize_artist_name("Radiohead") == "radiohead"

    def test_handles_empty_string(self):
        """Test empty string handling."""
        assert normalize_artist_name("") == ""

    def test_case_insensitive(self):
        """Test that the function handles various cases."""
        assert normalize_artist_name("the beatles") == "beatles"
        assert normalize_artist_name("The Beatles") == "beatles"
        assert normalize_artist_name("THE BEATLES") == "beatles"


class TestSortPlaylistByArtist:
    """Tests for the sort_playlist_by_artist function."""

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_sort_playlist_basic(self, mock_spotify_class, capsys):
        """Test basic playlist sorting by artist."""
        # Setup mock
        mock_sp = Mock()
        mock_spotify_class.return_value = mock_sp
        mock_sp.playlist.return_value = PLAYLIST_METADATA

        # Mock playlist items response
        mock_sp.playlist_items.return_value = {
            "items": [
                {"track": {"artists": [{"name": "Zebra"}], "name": "Song Z", "uri": "spotify:track:z", "album": {"name": "Album Z"}}},
                {"track": {"artists": [{"name": "Alpha"}], "name": "Song A", "uri": "spotify:track:a", "album": {"name": "Album A"}}},
                {"track": {"artists": [{"name": "Beta"}], "name": "Song B", "uri": "spotify:track:b", "album": {"name": "Album B"}}},
            ],
            "next": None
        }

        # Call function
        sort_playlist_by_artist("client_id", "client_secret", "redirect_uri", "playlist_123")

        # Verify playlist was updated with sorted URIs
        mock_sp.playlist_replace_items.assert_called_once_with(
            "playlist_123",
            ["spotify:track:a", "spotify:track:b", "spotify:track:z"]
        )

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_sort_playlist_reverse(self, mock_spotify_class):
        """Test reverse sorting (Z to A)."""
        mock_sp = Mock()
        mock_spotify_class.return_value = mock_sp
        mock_sp.playlist.return_value = PLAYLIST_METADATA

        mock_sp.playlist_items.return_value = {
            "items": [
                {"track": {"artists": [{"name": "Alpha"}], "name": "Song A", "uri": "spotify:track:a", "album": {"name": "Album A"}}},
                {"track": {"artists": [{"name": "Zebra"}], "name": "Song Z", "uri": "spotify:track:z", "album": {"name": "Album Z"}}},
            ],
            "next": None
        }

        sort_playlist_by_artist("id", "secret", "uri", "playlist_123", reverse=True)

        # Should be sorted Z to A
        mock_sp.playlist_replace_items.assert_called_once_with(
            "playlist_123",
            ["spotify:track:z", "spotify:track:a"]
        )

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_empty_playlist(self, mock_spotify_class, capsys):
        """Test handling of empty playlist."""
        mock_sp = Mock()
        mock_spotify_class.return_value = mock_sp
        mock_sp.playlist.return_value = PLAYLIST_METADATA

        mock_sp.playlist_items.return_value = {"items": [], "next": None}

        sort_playlist_by_artist("id", "secret", "uri", "playlist_123")

        captured = capsys.readouterr()
        assert "No tracks found in playlist" in captured.out
        mock_sp.playlist_replace_items.assert_not_called()

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_pagination(self, mock_spotify_class):
        """Test handling of paginated results."""
        mock_sp = Mock()
        mock_spotify_class.return_value = mock_sp
        mock_sp.playlist.return_value = PLAYLIST_METADATA

        # First page
        first_page = {
            "items": [
                {"track": {"artists": [{"name": "Beta"}], "name": "Song 1", "uri": "spotify:track:1", "album": {"name": "Album B"}}},
            ],
            "next": "next_page_url"
        }

        # Second page
        second_page = {
            "items": [
                {"track": {"artists": [{"name": "Alpha"}], "name": "Song 2", "uri": "spotify:track:2", "album": {"name": "Album A"}}},
            ],
            "next": None
        }

        mock_sp.playlist_items.return_value = first_page
        mock_sp.next.return_value = second_page

        sort_playlist_by_artist("id", "secret", "uri", "playlist_123")

        # Verify both pages were fetched
        mock_sp.next.assert_called_once()

        # Verify sorted order (Alpha before Beta)
        mock_sp.playlist_replace_items.assert_called_once_with(
            "playlist_123",
            ["spotify:track:2", "spotify:track:1"]
        )

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_chunked_updates(self, mock_spotify_class):
        """Test that large playlists are updated in chunks of 100."""
        mock_sp = Mock()
        mock_spotify_class.return_value = mock_sp
        mock_sp.playlist.return_value = PLAYLIST_METADATA

        # Create 250 tracks
        tracks = []
        for i in range(250):
            tracks.append({
                "track": {
                    "artists": [{"name": f"Artist{i:03d}"}],
                    "name": f"Song {i}",
                    "uri": f"spotify:track:{i}",
                    "album": {"name": f"Album {i}"}
                }
            })

        mock_sp.playlist_items.return_value = {"items": tracks, "next": None}

        sort_playlist_by_artist("id", "secret", "uri", "playlist_123")

        # Should call replace_items once (first 100)
        assert mock_sp.playlist_replace_items.call_count == 1

        # Should call add_items twice (next 100, then remaining 50)
        assert mock_sp.playlist_add_items.call_count == 2

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_track_without_artists(self, mock_spotify_class):
        """Test handling of tracks with no artists."""
        mock_sp = Mock()
        mock_spotify_class.return_value = mock_sp
        mock_sp.playlist.return_value = PLAYLIST_METADATA

        mock_sp.playlist_items.return_value = {
            "items": [
                {"track": {"artists": [{"name": "Zebra"}], "name": "Song Z", "uri": "spotify:track:z", "album": {"name": "Album Z"}}},
                {"track": {"artists": [], "name": "No Artist", "uri": "spotify:track:na", "album": {"name": "No Album"}}},
                {"track": {"artists": [{"name": "Alpha"}], "name": "Song A", "uri": "spotify:track:a", "album": {"name": "Album A"}}},
            ],
            "next": None
        }

        sort_playlist_by_artist("id", "secret", "uri", "playlist_123")

        # Track with no artist should sort first (empty string)
        call_args = mock_sp.playlist_replace_items.call_args[0]
        assert call_args[1][0] == "spotify:track:na"

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_tertiary_sort_by_track_name(self, mock_spotify_class):
        """Test that tracks by same artist and album are sorted by track name."""
        mock_sp = Mock()
        mock_spotify_class.return_value = mock_sp
        mock_sp.playlist.return_value = PLAYLIST_METADATA

        mock_sp.playlist_items.return_value = {
            "items": [
                {"track": {"artists": [{"name": "Artist"}], "name": "Zoo", "uri": "spotify:track:z", "album": {"name": "Same Album"}}},
                {"track": {"artists": [{"name": "Artist"}], "name": "Apple", "uri": "spotify:track:a", "album": {"name": "Same Album"}}},
                {"track": {"artists": [{"name": "Artist"}], "name": "Middle", "uri": "spotify:track:m", "album": {"name": "Same Album"}}},
            ],
            "next": None
        }

        sort_playlist_by_artist("id", "secret", "uri", "playlist_123")

        # Should be sorted by track name (tertiary sort)
        mock_sp.playlist_replace_items.assert_called_once_with(
            "playlist_123",
            ["spotify:track:a", "spotify:track:m", "spotify:track:z"]
        )

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_sorts_by_album_as_secondary_key(self, mock_spotify_class):
        """Test that tracks by the same artist are grouped by album."""
        mock_sp = Mock()
        mock_spotify_class.return_value = mock_sp
        mock_sp.playlist.return_value = PLAYLIST_METADATA

        # Same artist, multiple albums - should be grouped by album
        mock_sp.playlist_items.return_value = {
            "items": [
                {"track": {"artists": [{"name": "Radiohead"}], "name": "Paranoid Android", "uri": "spotify:track:okc1", "album": {"name": "OK Computer"}}},
                {"track": {"artists": [{"name": "Radiohead"}], "name": "Pyramid Song", "uri": "spotify:track:amn1", "album": {"name": "Amnesiac"}}},
                {"track": {"artists": [{"name": "Radiohead"}], "name": "Karma Police", "uri": "spotify:track:okc2", "album": {"name": "OK Computer"}}},
                {"track": {"artists": [{"name": "Radiohead"}], "name": "I Might Be Wrong", "uri": "spotify:track:amn2", "album": {"name": "Amnesiac"}}},
                {"track": {"artists": [{"name": "Radiohead"}], "name": "Everything In Its Right Place", "uri": "spotify:track:kid1", "album": {"name": "Kid A"}}},
            ],
            "next": None
        }

        sort_playlist_by_artist("id", "secret", "uri", "playlist_123")

        # Expected order: All Radiohead, grouped by album (Amnesiac, Kid A, OK Computer)
        # Within each album, sorted by track name
        mock_sp.playlist_replace_items.assert_called_once_with(
            "playlist_123",
            [
                "spotify:track:amn2",  # Amnesiac - I Might Be Wrong
                "spotify:track:amn1",  # Amnesiac - Pyramid Song
                "spotify:track:kid1",  # Kid A - Everything In Its Right Place
                "spotify:track:okc2",  # OK Computer - Karma Police
                "spotify:track:okc1",  # OK Computer - Paranoid Android
            ]
        )

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_full_sort_hierarchy(self, mock_spotify_class):
        """Test the complete sort hierarchy: artist -> album -> track."""
        mock_sp = Mock()
        mock_spotify_class.return_value = mock_sp
        mock_sp.playlist.return_value = PLAYLIST_METADATA

        # Multiple artists, albums, and tracks to test the full sort
        mock_sp.playlist_items.return_value = {
            "items": [
                {"track": {"artists": [{"name": "Beatles"}], "name": "Come Together", "uri": "spotify:track:b2", "album": {"name": "Abbey Road"}}},
                {"track": {"artists": [{"name": "Arcade Fire"}], "name": "Wake Up", "uri": "spotify:track:a1", "album": {"name": "Funeral"}}},
                {"track": {"artists": [{"name": "Beatles"}], "name": "Yesterday", "uri": "spotify:track:b1", "album": {"name": "Help!"}}},
                {"track": {"artists": [{"name": "Arcade Fire"}], "name": "Rebellion", "uri": "spotify:track:a2", "album": {"name": "Funeral"}}},
            ],
            "next": None
        }

        sort_playlist_by_artist("id", "secret", "uri", "playlist_123")

        # Expected: Arcade Fire (Funeral: Rebellion, Wake Up), Beatles (Abbey Road: Come Together, Help!: Yesterday)
        mock_sp.playlist_replace_items.assert_called_once_with(
            "playlist_123",
            [
                "spotify:track:a2",  # Arcade Fire - Funeral - Rebellion
                "spotify:track:a1",  # Arcade Fire - Funeral - Wake Up
                "spotify:track:b2",  # Beatles - Abbey Road - Come Together
                "spotify:track:b1",  # Beatles - Help! - Yesterday
            ]
        )

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_ignores_leading_the(self, mock_spotify_class):
        """Test that 'The' is ignored when sorting artist names."""
        mock_sp = Mock()
        mock_spotify_class.return_value = mock_sp
        mock_sp.playlist.return_value = PLAYLIST_METADATA

        # The Crystal Method should sort under 'C' between Crosby and Daft Punk
        mock_sp.playlist_items.return_value = {
            "items": [
                {"track": {"artists": [{"name": "Daft Punk"}], "name": "Song 1", "uri": "spotify:track:daft", "album": {"name": "Discovery"}}},
                {"track": {"artists": [{"name": "The Crystal Method"}], "name": "Song 2", "uri": "spotify:track:crystal", "album": {"name": "Vegas"}}},
                {"track": {"artists": [{"name": "Crosby, Stills, Nash, & Young"}], "name": "Song 3", "uri": "spotify:track:csny", "album": {"name": "Deja Vu"}}},
                {"track": {"artists": [{"name": "The Beatles"}], "name": "Song 4", "uri": "spotify:track:beatles", "album": {"name": "Abbey Road"}}},
                {"track": {"artists": [{"name": "Arcade Fire"}], "name": "Song 5", "uri": "spotify:track:arcade", "album": {"name": "Funeral"}}},
            ],
            "next": None
        }

        sort_playlist_by_artist("id", "secret", "uri", "playlist_123")

        # Expected order: Arcade Fire, Beatles (ignoring "The"), Crosby, Crystal Method (ignoring "The"), Daft Punk
        mock_sp.playlist_replace_items.assert_called_once_with(
            "playlist_123",
            [
                "spotify:track:arcade",     # Arcade Fire
                "spotify:track:beatles",    # The Beatles (sorted as "Beatles")
                "spotify:track:csny",       # Crosby, Stills, Nash, & Young
                "spotify:track:crystal",    # The Crystal Method (sorted as "Crystal Method")
                "spotify:track:daft"        # Daft Punk
            ]
        )


def make_mock_sp(mock_spotify_class, items):
    mock_sp = Mock()
    mock_spotify_class.return_value = mock_sp
    mock_sp.playlist.return_value = PLAYLIST_METADATA
    mock_sp.playlist_items.return_value = {"items": items, "next": None}
    return mock_sp


UNSORTED_ITEMS = [
    {"added_at": "2025-01-02T00:00:00Z", "track": {"artists": [{"name": "Zebra"}], "name": "Song Z", "uri": "spotify:track:z", "album": {"name": "Album Z"}, "is_local": False, "type": "track"}},
    {"added_at": "2025-01-01T00:00:00Z", "track": None},
    {"added_at": "2025-01-03T00:00:00Z", "track": {"artists": [{"name": "Alpha"}], "name": "Song A", "uri": "spotify:track:a", "album": {"name": "Album A"}, "is_local": False, "type": "track"}},
]


class TestDryRun:
    """Tests for --dry-run behavior."""

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_dry_run_makes_no_changes(self, mock_spotify_class, tmp_path):
        mock_sp = make_mock_sp(mock_spotify_class, UNSORTED_ITEMS)

        assert sort_playlist_by_artist("id", "secret", "uri", "playlist_123", dry_run=True) is True

        mock_sp.playlist_replace_items.assert_not_called()
        mock_sp.playlist_add_items.assert_not_called()
        assert not (tmp_path / "backups").exists()

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_dry_run_prints_preview_in_sorted_order(self, mock_spotify_class, capsys):
        make_mock_sp(mock_spotify_class, UNSORTED_ITEMS)

        sort_playlist_by_artist("id", "secret", "uri", "playlist_123", dry_run=True)

        out = capsys.readouterr().out
        assert "1. Alpha — Album A — Song A" in out
        assert "2. Zebra — Album Z — Song Z" in out
        assert out.index("Alpha") < out.index("Zebra")
        assert "Note: 1 unavailable item(s) will be dropped." in out
        assert "Dry run: no changes made." in out

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_preview_numbering_is_padded(self, mock_spotify_class, capsys):
        items = [
            {"track": {"artists": [{"name": f"Artist{i:02d}"}], "name": f"Song {i}", "uri": f"spotify:track:{i}", "album": {"name": "A"}}}
            for i in range(10)
        ]
        make_mock_sp(mock_spotify_class, items)

        sort_playlist_by_artist("id", "secret", "uri", "playlist_123", dry_run=True)

        out = capsys.readouterr().out
        assert "01. Artist00" in out
        assert "10. Artist09" in out


class TestBackup:
    """Tests for JSON backup behavior."""

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_backup_written_before_replace(self, mock_spotify_class, tmp_path):
        mock_sp = make_mock_sp(mock_spotify_class, UNSORTED_ITEMS)

        def assert_backup_exists(*args, **kwargs):
            assert len(list((tmp_path / "backups").glob("playlist_123-*.json"))) == 1

        mock_sp.playlist_replace_items.side_effect = assert_backup_exists

        assert sort_playlist_by_artist("id", "secret", "uri", "playlist_123") is True
        mock_sp.playlist_replace_items.assert_called_once()

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_backup_contents(self, mock_spotify_class, tmp_path, capsys):
        make_mock_sp(mock_spotify_class, UNSORTED_ITEMS)

        sort_playlist_by_artist("id", "secret", "uri", "playlist_123")

        [backup_file] = (tmp_path / "backups").glob("playlist_123-*.json")
        assert f"Backup saved to {backup_file.relative_to(tmp_path)}" in capsys.readouterr().out
        data = json.loads(backup_file.read_text(encoding="utf-8"))
        assert data["playlist_id"] == "playlist_123"
        assert data["playlist_name"] == "My Playlist"
        assert data["snapshot_id"] == "snap_1"
        assert data["track_count"] == 3
        assert data["created_at"].endswith("+00:00")
        # Original order preserved, including the unavailable item
        assert [t["uri"] for t in data["tracks"]] == ["spotify:track:z", None, "spotify:track:a"]
        assert [t["position"] for t in data["tracks"]] == [0, 1, 2]
        assert data["tracks"][0] == {
            "position": 0,
            "uri": "spotify:track:z",
            "name": "Song Z",
            "artists": ["Zebra"],
            "album": "Album Z",
            "is_local": False,
            "type": "track",
            "added_at": "2025-01-02T00:00:00Z",
        }
        assert data["tracks"][1]["added_at"] == "2025-01-01T00:00:00Z"

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_backup_failure_aborts(self, mock_spotify_class, capsys):
        mock_sp = make_mock_sp(mock_spotify_class, UNSORTED_ITEMS)

        with patch("spotify_playlist_sorter.cli.open", create=True, side_effect=OSError("disk full")):
            result = sort_playlist_by_artist("id", "secret", "uri", "playlist_123")

        assert result is False
        mock_sp.playlist_replace_items.assert_not_called()
        mock_sp.playlist_add_items.assert_not_called()
        assert "ERROR: Could not write backup" in capsys.readouterr().out

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_no_backup(self, mock_spotify_class, tmp_path):
        mock_sp = make_mock_sp(mock_spotify_class, UNSORTED_ITEMS)

        sort_playlist_by_artist("id", "secret", "uri", "playlist_123", backup=False)

        assert not (tmp_path / "backups").exists()
        mock_sp.playlist_replace_items.assert_called_once()

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_custom_backup_dir(self, mock_spotify_class, tmp_path):
        make_mock_sp(mock_spotify_class, UNSORTED_ITEMS)

        sort_playlist_by_artist("id", "secret", "uri", "playlist_123", backup_dir="nested/dir")

        assert len(list((tmp_path / "nested" / "dir").glob("playlist_123-*.json"))) == 1
        assert not (tmp_path / "backups").exists()

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_no_backup_when_only_unavailable_items(self, mock_spotify_class, tmp_path, capsys):
        mock_sp = make_mock_sp(mock_spotify_class, [{"track": None}])

        assert sort_playlist_by_artist("id", "secret", "uri", "playlist_123") is True

        assert "No tracks found in playlist" in capsys.readouterr().out
        assert not (tmp_path / "backups").exists()
        mock_sp.playlist_replace_items.assert_not_called()


class TestLocalAndEpisodeItems:
    """Local files and episodes are kept in the sort, with a warning."""

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_local_track_is_kept_and_warned(self, mock_spotify_class, capsys):
        mock_sp = make_mock_sp(mock_spotify_class, [
            {"track": {"artists": [{"name": "Zebra"}], "name": "Song Z", "uri": "spotify:track:z", "album": {"name": "Album Z"}, "is_local": False, "type": "track"}},
            {"track": {"artists": [{"name": "Me"}], "name": "Demo", "uri": "spotify:local:Me:Demo:Demo:120", "album": {"name": "Demos"}, "is_local": True, "type": "track"}},
            {"track": {"artists": [{"name": "Pod"}], "name": "Ep 1", "uri": "spotify:episode:e1", "album": {"name": "Show"}, "is_local": False, "type": "episode"}},
        ])

        sort_playlist_by_artist("id", "secret", "uri", "playlist_123")

        mock_sp.playlist_replace_items.assert_called_once_with(
            "playlist_123",
            ["spotify:local:Me:Demo:Demo:120", "spotify:episode:e1", "spotify:track:z"],
        )
        assert "Warning: 1 local file(s) and 1 episode(s) found" in capsys.readouterr().out


class TestMain:
    """Tests for the main CLI entry point."""

    def test_missing_credentials(self, capsys):
        """Test error when credentials are missing."""
        test_args = ["prog", "--playlist-id", "123"]

        with patch.object(sys, "argv", test_args):
            with patch("os.getenv", return_value=None):
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "ERROR: You must provide Spotify client ID and secret" in captured.out

    @patch("spotify_playlist_sorter.cli.sort_playlist_by_artist")
    @patch("os.getenv")
    def test_credentials_from_env(self, mock_getenv, mock_sort):
        """Test loading credentials from environment variables."""
        mock_getenv.side_effect = lambda key: {
            "SPOTIPY_CLIENT_ID": "env_client_id",
            "SPOTIPY_CLIENT_SECRET": "env_client_secret",
            "SPOTIPY_REDIRECT_URI": "env_redirect_uri"
        }.get(key)

        test_args = ["prog", "--playlist-id", "test_playlist"]

        with patch.object(sys, "argv", test_args):
            main()

        mock_sort.assert_called_once_with(
            client_id="env_client_id",
            client_secret="env_client_secret",
            redirect_uri="env_redirect_uri",
            playlist_id="test_playlist",
            reverse=False,
            dry_run=False,
            backup=True,
            backup_dir="backups",
        )

    @patch("spotify_playlist_sorter.cli.sort_playlist_by_artist")
    def test_credentials_from_args(self, mock_sort):
        """Test loading credentials from command-line arguments."""
        test_args = [
            "prog",
            "--playlist-id", "test_playlist",
            "--client-id", "arg_client_id",
            "--client-secret", "arg_client_secret",
            "--redirect-uri", "arg_redirect_uri"
        ]

        with patch.object(sys, "argv", test_args):
            with patch("os.getenv", return_value=None):
                main()

        mock_sort.assert_called_once_with(
            client_id="arg_client_id",
            client_secret="arg_client_secret",
            redirect_uri="arg_redirect_uri",
            playlist_id="test_playlist",
            reverse=False,
            dry_run=False,
            backup=True,
            backup_dir="backups",
        )

    @patch("spotify_playlist_sorter.cli.sort_playlist_by_artist")
    @patch("os.getenv")
    def test_reverse_flag(self, mock_getenv, mock_sort):
        """Test that --reverse flag is passed correctly."""
        mock_getenv.side_effect = lambda key: {
            "SPOTIPY_CLIENT_ID": "id",
            "SPOTIPY_CLIENT_SECRET": "secret"
        }.get(key)

        test_args = ["prog", "--playlist-id", "test_playlist", "--reverse"]

        with patch.object(sys, "argv", test_args):
            main()

        assert mock_sort.call_args[1]["reverse"] is True

    @patch("spotify_playlist_sorter.cli.sort_playlist_by_artist")
    @patch("os.getenv")
    def test_dry_run_and_backup_flags(self, mock_getenv, mock_sort):
        """Test that --dry-run, --no-backup, and --backup-dir are passed correctly."""
        mock_getenv.side_effect = lambda key: {
            "SPOTIPY_CLIENT_ID": "id",
            "SPOTIPY_CLIENT_SECRET": "secret"
        }.get(key)

        test_args = ["prog", "--playlist-id", "p", "--dry-run", "--no-backup", "--backup-dir", "/tmp/bk"]

        with patch.object(sys, "argv", test_args):
            main()

        kwargs = mock_sort.call_args[1]
        assert kwargs["dry_run"] is True
        assert kwargs["backup"] is False
        assert kwargs["backup_dir"] == "/tmp/bk"

    @patch("spotify_playlist_sorter.cli.sort_playlist_by_artist", return_value=False)
    @patch("os.getenv")
    def test_exits_nonzero_on_failure(self, mock_getenv, mock_sort):
        """Test that main exits with code 1 when sorting fails (e.g. backup error)."""
        mock_getenv.side_effect = lambda key: {
            "SPOTIPY_CLIENT_ID": "id",
            "SPOTIPY_CLIENT_SECRET": "secret"
        }.get(key)

        with patch.object(sys, "argv", ["prog", "--playlist-id", "p"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1
