"""Retrospective ("Retrospectiva"): a month or a year of listening, from the play history.

Times are in the phone's local time zone. Radio is not part of the history, so it is not here either.
"""
import datetime as dt
from collections import Counter

from . import db
from .i18n import name
from .state import lock, tracks


def periods():
    """Months and years that have plays, newest first: [{"id": "2026-10", "plays": n}, {"id": "2026", ...}]."""
    rows = db.query("SELECT strftime('%Y-%m', played_at, 'unixepoch', 'localtime') AS m, COUNT(*) "
                    "FROM plays GROUP BY m ORDER BY m DESC")
    years = Counter()
    for m, n in rows:
        years[m[:4]] += n
    return {"months": [{"id": m, "plays": n} for m, n in rows],
            "years": [{"id": y, "plays": n} for y, n in sorted(years.items(), reverse=True)]}


def _bounds(period):
    """(start, end, previous start) in unix time for "YYYY" or "YYYY-MM" (local time)."""
    if len(period) == 4:
        y = int(period)
        start, end, prev = dt.datetime(y, 1, 1), dt.datetime(y + 1, 1, 1), dt.datetime(y - 1, 1, 1)
    else:
        y, m = map(int, period.split("-"))
        start = dt.datetime(y, m, 1)
        end = dt.datetime(y + (m == 12), m % 12 + 1, 1)
        prev = dt.datetime(y - (m == 1), (m - 2) % 12 + 1, 1)
    return start.timestamp(), end.timestamp(), prev.timestamp()


def _cover(tid):
    with lock:
        t = tracks.get(tid)
        return t["album"] if t else None


def _dur(tid, dur):
    """Stored length, or the current one for plays recorded before lengths were stored."""
    if dur:
        return dur
    with lock:
        it = tracks.get(tid)
    return it["dur"] if it else 0


def retro(period):
    try:
        start, end, prev = _bounds(period)
    except (ValueError, IndexError):
        return {"ok": False}
    rows = db.query("SELECT track_id, played_at, title, artist, album, dur FROM plays "
                    "WHERE played_at >= ? AND played_at < ? ORDER BY played_at", (start, end))
    before = db.query("SELECT track_id, dur FROM plays WHERE played_at >= ? AND played_at < ?", (prev, start))
    known_artists = {a for (a,) in db.query("SELECT DISTINCT lower(artist) FROM plays WHERE played_at < ? AND artist != ''",
                                            (start,))}
    seconds = 0
    by_track, by_artist, by_album = Counter(), Counter(), Counter()
    artist_secs, info, album_cover = Counter(), {}, {}
    hours, weekdays, days = [0] * 24, [0] * 7, set()
    for tid, at, title, artist, album, dur in rows:
        d = _dur(tid, dur)
        seconds += d
        when = dt.datetime.fromtimestamp(at)
        hours[when.hour] += 1
        weekdays[when.weekday()] += 1               # 0 = Monday
        days.add(when.date())
        by_track[tid] += 1
        info[tid] = (title, artist, album)          # latest names win
        if artist:
            key = artist.lower()
            by_artist[key] += 1
            artist_secs[key] += d
            info.setdefault(("artist", key), artist)
        if album and album != "YouTube":            # plays of YouTube videos (removed feature) have no album
            by_album[(album, artist)] += 1
            album_cover.setdefault((album, artist), _cover(tid))
    # longest run of consecutive days with music
    streak = best = 0
    for day in sorted(days):
        streak = streak + 1 if day - dt.timedelta(days=1) in days else 1
        best = max(best, streak)
    prev_secs = sum(_dur(tid, dur) for tid, dur in before)
    top_tracks = []
    for tid, n in by_track.most_common(5):
        title, artist, album = info[tid]
        with lock:
            available = tid in tracks
        top_tracks.append({"id": tid, "title": title, "artist": name(artist), "album": name(album), "count": n,
                           "cover": _cover(tid), "available": available})
    return {
        "ok": True, "period": period,
        "plays": len(rows), "seconds": seconds, "tracks": len(by_track), "artists": len(by_artist),
        "albums": len(by_album), "days": len(days), "streak": best,
        "new_artists": len(set(by_artist) - known_artists),
        "previous": {"plays": len(before), "seconds": prev_secs},
        "top_tracks": top_tracks,
        "top_artists": [{"artist": name(info[("artist", k)]), "count": n, "seconds": artist_secs[k]}
                        for k, n in by_artist.most_common(5)],
        "top_albums": [{"album": name(al), "artist": name(ar), "count": n, "cover": album_cover[(al, ar)]}
                       for (al, ar), n in by_album.most_common(5)],
        "hours": hours, "weekdays": weekdays,
    }
