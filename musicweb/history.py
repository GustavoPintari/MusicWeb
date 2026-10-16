"""Play history and most played tracks/artists."""
import time

from . import db
from .config import cfg
from .i18n import name
from .state import albums, item, lock, tracks, yt_items


def min_listen(dur):
    """Seconds a track must actually be listened to before it counts as a play."""
    if dur and dur < 2 * cfg.history_min_seconds:
        return max(1, dur / 2)                      # short tracks: half of it
    return cfg.history_min_seconds


def record_play(tid, output="remote"):
    if not cfg.history_enabled:
        return False
    with lock:
        it = item(tid)
        if it is None or it.get("radio"):          # radio is not part of the history / retrospective
            return False
        alb = albums.get(it["album"])
        title, artist = it["title"], it["artist"] or (alb["artist"] if alb else "")
        album = alb["name"] if alb else "YouTube"
    db.execute("INSERT INTO plays(track_id, played_at, title, artist, album, output, dur) VALUES(?, ?, ?, ?, ?, ?, ?)",
               (tid, int(time.time()), title, artist, album, output, it["dur"] or 0))
    return True


def _entry(tid, title, artist, album):
    """Adds what the page needs to show/play a history row (the track may no longer exist)."""
    with lock:
        t = tracks.get(tid)
        cover = t["album"] if t else (tid if tid in yt_items else None)
    return {"id": tid, "title": title, "artist": name(artist), "album": name(album), "cover": cover,
            "available": t is not None or tid in yt_items}


def stats(days=0):
    """Most played tracks and artists in the last `days` days (0 = all time) and the latest plays."""
    since = int(time.time() - days * 86400) if days > 0 else 0
    # SQLite returns the other columns from the row that has the MAX(), i.e. the latest title/artist
    top = db.query("SELECT track_id, COUNT(*) AS n, MAX(played_at), title, artist, album FROM plays "
                   "WHERE played_at >= ? GROUP BY track_id ORDER BY n DESC, MAX(played_at) DESC LIMIT 50", (since,))
    artists = db.query("SELECT artist, COUNT(*) AS n FROM plays WHERE played_at >= ? AND artist != '' "
                       "GROUP BY lower(artist) ORDER BY n DESC LIMIT 20", (since,))
    recent = db.query("SELECT track_id, played_at, title, artist, album FROM plays ORDER BY played_at DESC, id DESC LIMIT 50")
    total = db.query("SELECT COUNT(*) FROM plays WHERE played_at >= ?", (since,))[0][0]
    return {
        "enabled": cfg.history_enabled,
        "total": total,
        "top_tracks": [{**_entry(tid, ti, ar, al), "count": n} for tid, n, _, ti, ar, al in top],
        "top_artists": [{"artist": name(ar), "count": n} for ar, n in artists],
        "recent": [{**_entry(tid, ti, ar, al), "at": at} for tid, at, ti, ar, al in recent],
    }
