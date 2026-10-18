"""Shared state: library, radio stations and the playback queue."""
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
    "fails": 0,            # tracks that failed in a row (with repeat on, stop instead of trying them forever)
    "shuffle": False,      # the queue is in random order; "order" keeps the original one, to go back to it
    "order": None,
    "repeat": "off",       # "off", "all" (the queue starts over at the end) or "one" (the same track again)
    "owner": None,         # device (browser id) playing on the Receiver: the others can't control it meanwhile
    "owner_name": "",      # that device, for the others to see ("Android · Chrome")
    "paused_at": None,     # time.time() of the last pause: a long pause frees the Receiver
}


radios = {}        # id ("radio_" + Radio Browser uuid) -> item (favorites, recent and the one playing)


def item(tid):
    """Library track or radio station."""
    return tracks.get(tid) or radios.get(tid)
