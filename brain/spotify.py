"""
brain/spotify.py
-----------------
Spotify music control for JOSEPH.

Controls Spotify playback via the Spotify Web API.
Requires a free Spotify account and one-time app setup.

Setup (one-time, 5 minutes):
  1. Go to https://developer.spotify.com/dashboard
  2. Create an app (any name)
  3. Set Redirect URI to: http://localhost:8888/callback
  4. Copy Client ID and Client Secret
  5. Add to .env:
       SPOTIFY_CLIENT_ID=your_client_id
       SPOTIFY_CLIENT_SECRET=your_client_secret
  6. Run: python -m brain.spotify
  7. Authorize in browser

After setup Joseph can:
  - Play any song, artist, or playlist
  - Pause/resume
  - Skip tracks
  - Control volume
  - Search music
  - Play your saved playlists
"""

import logging
import os
import webbrowser
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

TOKEN_FILE = settings.BASE_DIR / "configs" / "spotify_token.json"
REDIRECT_URI = "http://localhost:8888/callback"
SCOPES = [
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "playlist-read-private",
    "user-library-read",
    "streaming",
]


class SpotifyController:
    """
    Controls Spotify via Web API.

    Usage:
        spotify = SpotifyController()
        if spotify.is_available:
            spotify.play("lofi hip hop")
            spotify.pause()
            spotify.next_track()
    """

    def __init__(self):
        self._sp = None
        self._available = False
        self._client_id = os.getenv("SPOTIFY_CLIENT_ID", "")
        self._client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")
        self._initialize()

    def _initialize(self) -> None:
        """Initialize Spotify client."""
        if not self._client_id or not self._client_secret:
            logger.info(
                "Spotify not configured. Add SPOTIFY_CLIENT_ID and "
                "SPOTIFY_CLIENT_SECRET to .env to enable music control."
            )
            return

        try:
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth

            auth_manager = SpotifyOAuth(
                client_id=self._client_id,
                client_secret=self._client_secret,
                redirect_uri=REDIRECT_URI,
                scope=" ".join(SCOPES),
                cache_path=str(TOKEN_FILE),
                open_browser=False,
            )

            self._sp = spotipy.Spotify(auth_manager=auth_manager)

            # Test connection
            self._sp.current_user()
            self._available = True
            logger.info("Spotify connected")

        except Exception as e:
            logger.debug(f"Spotify init failed: {e}")
            self._available = False

    # ------------------------------------------------------------------ #
    # Playback Control
    # ------------------------------------------------------------------ #

    def play(self, query: str = "") -> str:
        """
        Play music. If query provided, searches and plays it.
        If no query, resumes current playback.

        Args:
            query: Song, artist, album, or playlist name.

        Returns:
            Status message.
        """
        if not self._available:
            return self._not_configured()

        try:
            if not query:
                self._sp.start_playback()
                return "Resuming playback."

            # Search for the query
            results = self._sp.search(q=query, limit=1, type="track,playlist,artist")

            # Try track first
            tracks = results.get("tracks", {}).get("items", [])
            if tracks:
                track = tracks[0]
                self._sp.start_playback(uris=[track["uri"]])
                artist = track["artists"][0]["name"]
                return f"Playing '{track['name']}' by {artist}."

            # Try playlist
            playlists = results.get("playlists", {}).get("items", [])
            if playlists:
                playlist = playlists[0]
                self._sp.start_playback(context_uri=playlist["uri"])
                return f"Playing playlist '{playlist['name']}'."

            return f"Couldn't find '{query}' on Spotify."

        except Exception as e:
            logger.error(f"Spotify play error: {e}")
            return f"Spotify error: {e}"

    def pause(self) -> str:
        """Pause playback."""
        if not self._available:
            return self._not_configured()
        try:
            self._sp.pause_playback()
            return "Paused."
        except Exception as e:
            return f"Couldn't pause: {e}"

    def resume(self) -> str:
        """Resume playback."""
        if not self._available:
            return self._not_configured()
        try:
            self._sp.start_playback()
            return "Resumed."
        except Exception as e:
            return f"Couldn't resume: {e}"

    def next_track(self) -> str:
        """Skip to next track."""
        if not self._available:
            return self._not_configured()
        try:
            self._sp.next_track()
            import time
            time.sleep(0.5)
            return f"Skipped. {self.now_playing()}"
        except Exception as e:
            return f"Couldn't skip: {e}"

    def previous_track(self) -> str:
        """Go to previous track."""
        if not self._available:
            return self._not_configured()
        try:
            self._sp.previous_track()
            return "Going back."
        except Exception as e:
            return f"Couldn't go back: {e}"

    def set_volume(self, volume: int) -> str:
        """
        Set volume (0-100).

        Args:
            volume: Volume level 0-100.
        """
        if not self._available:
            return self._not_configured()
        try:
            volume = max(0, min(100, volume))
            self._sp.volume(volume)
            return f"Volume set to {volume}%."
        except Exception as e:
            return f"Couldn't set volume: {e}"

    def now_playing(self) -> str:
        """Get currently playing track info."""
        if not self._available:
            return self._not_configured()
        try:
            current = self._sp.current_playback()
            if not current or not current.get("item"):
                return "Nothing playing."

            track = current["item"]
            artist = track["artists"][0]["name"]
            name = track["name"]
            is_playing = current.get("is_playing", False)
            status = "Playing" if is_playing else "Paused"
            return f"{status}: '{name}' by {artist}."

        except Exception as e:
            return f"Couldn't get playback info: {e}"

    def get_playlists(self, limit: int = 10) -> list[dict]:
        """Get user's playlists."""
        if not self._available:
            return []
        try:
            results = self._sp.current_user_playlists(limit=limit)
            return [
                {"name": p["name"], "id": p["id"], "tracks": p["tracks"]["total"]}
                for p in results.get("items", [])
            ]
        except Exception as e:
            logger.error(f"Get playlists error: {e}")
            return []

    def play_playlist(self, name: str) -> str:
        """Play a playlist by name."""
        if not self._available:
            return self._not_configured()
        try:
            playlists = self.get_playlists(limit=50)
            name_lower = name.lower()
            for pl in playlists:
                if name_lower in pl["name"].lower():
                    self._sp.start_playback(
                        context_uri=f"spotify:playlist:{pl['id']}"
                    )
                    return f"Playing playlist '{pl['name']}'."
            return f"Playlist '{name}' not found."
        except Exception as e:
            return f"Playlist error: {e}"

    def _not_configured(self) -> str:
        return (
            "Spotify not configured. "
            "Add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET to .env, "
            "then run: python -m brain.spotify"
        )

    def setup(self) -> bool:
        """Run the OAuth setup flow."""
        if not self._client_id or not self._client_secret:
            print(
                "\nSpotify Setup:\n"
                "1. Go to https://developer.spotify.com/dashboard\n"
                "2. Create an app\n"
                "3. Set Redirect URI to: http://localhost:8888/callback\n"
                "4. Add to .env:\n"
                "   SPOTIFY_CLIENT_ID=your_client_id\n"
                "   SPOTIFY_CLIENT_SECRET=your_client_secret\n"
                "5. Run this script again\n"
            )
            return False

        try:
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth

            auth_manager = SpotifyOAuth(
                client_id=self._client_id,
                client_secret=self._client_secret,
                redirect_uri=REDIRECT_URI,
                scope=" ".join(SCOPES),
                cache_path=str(TOKEN_FILE),
            )

            auth_url = auth_manager.get_authorize_url()
            print(f"\nOpening browser for Spotify authorization...")
            webbrowser.open(auth_url)

            code = input("Paste the redirect URL here: ").strip()
            if "code=" in code:
                code = code.split("code=")[1].split("&")[0]

            auth_manager.get_access_token(code)
            self._initialize()

            if self._available:
                print("✓ Spotify connected!")
                return True
            return False

        except Exception as e:
            print(f"Setup failed: {e}")
            return False

    @property
    def is_available(self) -> bool:
        return self._available

    def __repr__(self) -> str:
        return f"SpotifyController(available={self._available})"


# Module-level singleton
spotify = SpotifyController()


if __name__ == "__main__":
    s = SpotifyController()
    if not s.is_available:
        s.setup()
    else:
        print(f"Spotify connected: {s.now_playing()}")
