"""Shared state: library, YouTube history and the playback queue."""
import threading


tracks = {}      # id -> track
albums = {}      # id -> album
lock = threading.Lock()
state = {
    "queue": [], "pos": -1,
    "active": False,       # mpv is playing (or paused on) state["queue"][state["pos"]]
    "restored": None,      # seconds: queue restored after a restart, waiting for "play" to resume from here
    "gen": 0,              # bumped on every play_pos(), so replaying the same track counts as a new play
    "appended": None,      # gapless: queue index already appended to mpv's playlist after the current one
    "error": "", "lib": 0, "seek": None,
}


yt_items = {}      # id ("yt_" + video id) -> item, oldest first
yt_playlists = {}  # id ("ytpl_" + list id) -> playlist: title, entries (yt_items ids), oldest first
radios = {}        # id ("radio_" + Radio Browser uuid) -> item (favorites, recent and the one playing)


def item(tid):
    """Library track, YouTube video or radio station."""
    return tracks.get(tid) or yt_items.get(tid) or radios.get(tid)
