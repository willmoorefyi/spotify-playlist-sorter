import pytest
from unittest.mock import Mock, patch, MagicMock
from spotify_playlist_sorter.cli import sort_playlist_by_artist, main, normalize_artist_name
import sys


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
