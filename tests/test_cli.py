import pytest
from unittest.mock import Mock, patch, MagicMock
from spotify_playlist_sorter.cli import sort_playlist_by_artist, main
import sys


class TestSortPlaylistByArtist:
    """Tests for the sort_playlist_by_artist function."""

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_sort_playlist_basic(self, mock_spotify_class, capsys):
        """Test basic playlist sorting by artist."""
        # Setup mock
        mock_sp = Mock()
        mock_spotify_class.return_value = mock_sp

        # Mock playlist items response
        mock_sp.playlist_items.return_value = {
            "items": [
                {"track": {"artists": [{"name": "Zebra"}], "name": "Song Z", "uri": "spotify:track:z"}},
                {"track": {"artists": [{"name": "Alpha"}], "name": "Song A", "uri": "spotify:track:a"}},
                {"track": {"artists": [{"name": "Beta"}], "name": "Song B", "uri": "spotify:track:b"}},
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

        mock_sp.playlist_items.return_value = {
            "items": [
                {"track": {"artists": [{"name": "Alpha"}], "name": "Song A", "uri": "spotify:track:a"}},
                {"track": {"artists": [{"name": "Zebra"}], "name": "Song Z", "uri": "spotify:track:z"}},
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

        # First page
        first_page = {
            "items": [
                {"track": {"artists": [{"name": "Beta"}], "name": "Song 1", "uri": "spotify:track:1"}},
            ],
            "next": "next_page_url"
        }

        # Second page
        second_page = {
            "items": [
                {"track": {"artists": [{"name": "Alpha"}], "name": "Song 2", "uri": "spotify:track:2"}},
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

        # Create 250 tracks
        tracks = []
        for i in range(250):
            tracks.append({
                "track": {
                    "artists": [{"name": f"Artist{i:03d}"}],
                    "name": f"Song {i}",
                    "uri": f"spotify:track:{i}"
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

        mock_sp.playlist_items.return_value = {
            "items": [
                {"track": {"artists": [{"name": "Zebra"}], "name": "Song Z", "uri": "spotify:track:z"}},
                {"track": {"artists": [], "name": "No Artist", "uri": "spotify:track:na"}},
                {"track": {"artists": [{"name": "Alpha"}], "name": "Song A", "uri": "spotify:track:a"}},
            ],
            "next": None
        }

        sort_playlist_by_artist("id", "secret", "uri", "playlist_123")

        # Track with no artist should sort first (empty string)
        call_args = mock_sp.playlist_replace_items.call_args[0]
        assert call_args[1][0] == "spotify:track:na"

    @patch("spotify_playlist_sorter.cli.spotipy.Spotify")
    def test_secondary_sort_by_track_name(self, mock_spotify_class):
        """Test that tracks by same artist are sorted by track name."""
        mock_sp = Mock()
        mock_spotify_class.return_value = mock_sp

        mock_sp.playlist_items.return_value = {
            "items": [
                {"track": {"artists": [{"name": "Artist"}], "name": "Zoo", "uri": "spotify:track:z"}},
                {"track": {"artists": [{"name": "Artist"}], "name": "Apple", "uri": "spotify:track:a"}},
                {"track": {"artists": [{"name": "Artist"}], "name": "Middle", "uri": "spotify:track:m"}},
            ],
            "next": None
        }

        sort_playlist_by_artist("id", "secret", "uri", "playlist_123")

        # Should be sorted by track name
        mock_sp.playlist_replace_items.assert_called_once_with(
            "playlist_123",
            ["spotify:track:a", "spotify:track:m", "spotify:track:z"]
        )


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
            reverse=False
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
            reverse=False
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
