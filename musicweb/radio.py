"""Internet radio from Radio Browser (radio-browser.info): search, favorites, recent stations.

Radio Browser is a free, community-run catalog (no account or API key). Following its
guidelines, the server is picked from the list behind all.api.radio-browser.info, requests
send a descriptive User-Agent, and a "click" is reported when a station is played.
"""
import os, random, re, socket, threading, time, urllib.parse, urllib.request

from . import db
from .config import cfg
from .state import lock, radios
from .util import UA, http_get

FALLBACK_HOSTS = ["de1.api.radio-browser.info", "nl1.api.radio-browser.info", "at1.api.radio-browser.info"]
MAX_RECENT = 12

_host = [None]          # server that answered last
_seen = {}              # uuid -> station item, from the latest searches (so the page only sends the uuid)
_cache = {}             # "countries" / "tags" -> (time, data)


def _hosts():
    if _host[0]:
        yield _host[0]
    names = []
    try:
        for info in socket.getaddrinfo("all.api.radio-browser.info", 443, proto=socket.IPPROTO_TCP):
            try:
                names.append(socket.gethostbyaddr(info[4][0])[0])
            except OSError:
                pass
    except OSError:
        pass
    names = list(dict.fromkeys(names)) or list(FALLBACK_HOSTS)
    random.shuffle(names)                        # spread the load, as the project asks
    yield from (n for n in names if n != _host[0])


def rb_get(path, params=None, timeout=10):
    """GET on the Radio Browser API, trying the next server when one fails."""
    qs = "?" + urllib.parse.urlencode(params) if params else ""
    err = None
    for host in _hosts():
        try:
            data = http_get(f"https://{host}/json/{path}{qs}", True, timeout=timeout)
            _host[0] = host
            return data
        except Exception as e:
            err = e
    raise err or OSError("Radio Browser unreachable")


def _cached(key, fetch, ttl=24 * 3600):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    data = fetch()
    _cache[key] = (time.time(), data)
    return data


def station_item(st):
    uuid = st["stationuuid"]
    bitrate = st.get("bitrate") or 0
    return {"id": "radio_" + uuid, "uuid": uuid, "radio": True,
            "title": (st.get("name") or "").strip() or uuid, "artist": "", "album": "radio_" + uuid,
            "dur": 0, "n": 0, "disc": 1, "fmt": (st.get("codec") or "").upper(), "q": f"{bitrate}k" if bitrate else "",
            "path": st.get("url_resolved") or st.get("url"), "src": st.get("url") or "", "favicon": st.get("favicon") or "",
            "country": st.get("country") or "", "countrycode": (st.get("countrycode") or "").upper(),
            "tags": [t for t in (st.get("tags") or "").split(",") if t][:4], "hls": bool(st.get("hls"))}


def public(it):
    return {k: it[k] for k in ("id", "uuid", "title", "fmt", "q", "path", "favicon", "country", "countrycode", "tags", "hls")}


# ---------------------------------------------------------------- catalog

def countries():
    def fetch():
        rows = rb_get("countries", {"hidebroken": "true"})
        return sorted(({"code": r["iso_3166_1"].upper(), "name": r["name"], "count": r["stationcount"]}
                       for r in rows if r.get("iso_3166_1") and r.get("stationcount")), key=lambda r: r["name"])
    return _cached("countries", fetch)


# Radio Browser's most used tags are noisy ("fm", "méxico", "estación"...), so offer a curated list of genres
GENRES = ["pop", "rock", "mpb", "sertanejo", "samba", "pagode", "forró", "funk", "gospel", "jazz", "blues",
          "classical", "electronic", "dance", "hip hop", "reggae", "country", "latin", "80s", "90s",
          "oldies", "lofi", "ambient", "news", "talk", "sports"]


def tags():
    return GENRES


def search(q="", country="", tag=""):
    """Stations matching the filters, most popular first. The filters are remembered for next time."""
    db.kv_set("radio_filters", {"country": country, "tag": tag})
    params = {"order": "clickcount", "reverse": "true", "hidebroken": "true", "limit": 60}
    if q:
        params["name"] = q
    if country:
        params["countrycode"] = country
    if tag:
        params["tag"], params["tagExact"] = tag, "true"
    items = [station_item(st) for st in rb_get("stations/search", params) if st.get("stationuuid")]
    for it in items:
        _seen[it["uuid"]] = it
    return [public(it) for it in items]


# ---------------------------------------------------------------- favorites, recent, playing

def _stored(key):
    return db.kv_get(key, [])


def load():
    """Registers favorite and recent stations, so a saved queue with a radio can be restored."""
    with lock:
        for it in _stored("radio_favorites") + _stored("radio_recent"):
            radios[it["id"]] = it


def overview():
    fav = _stored("radio_favorites")
    favs = {it["uuid"] for it in fav}
    return {"filters": db.kv_get("radio_filters", {"country": "", "tag": ""}),
            "favorites": [public(it) for it in fav],
            "recent": [{**public(it), "favorite": it["uuid"] in favs} for it in _stored("radio_recent")]}


def _find(uuid):
    for it in [_seen.get(uuid)] + _stored("radio_favorites") + _stored("radio_recent"):
        if it and it["uuid"] == uuid:
            return it
    rows = rb_get("stations/byuuid", {"uuids": uuid})
    return station_item(rows[0]) if rows else None


def resolve_stream(url):
    """Opens a playlist file (.pls/.m3u) and returns the first stream in it; other links are returned as they are.

    Some stations publish a playlist that hands out a signed link valid for a few days (e.g. KBS, in Korea).
    Radio Browser stores the link it found on its last check, which may already have expired (403), so the
    playlist is read again each time the station is played."""
    path = urllib.parse.urlsplit(url).path.lower()
    if not path.endswith((".pls", ".m3u")):
        return url
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=6) as r:
        text = r.read(65536).decode("utf-8", "replace")          # a playlist is small; never read a stream
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"File\d+\s*=\s*(.+)", line, re.I) if path.endswith(".pls") else None
        cand = m.group(1).strip() if m else (line if not path.endswith(".pls") and not line.startswith("#") else "")
        if cand.startswith(("http://", "https://")):
            return cand
    return url


def _fresh(it):
    """The station with its current link: Radio Browser's latest data, with the playlist read again."""
    try:
        rows = rb_get("stations/byuuid", {"uuids": it["uuid"]}, timeout=6)
        if rows:
            it = {**it, **{k: v for k, v in station_item(rows[0]).items() if k in ("path", "src", "hls", "fmt", "q")}}
    except Exception:
        pass
    if it.get("src"):
        try:
            it = {**it, "path": resolve_stream(it["src"])}
        except Exception as e:
            print("[rádio] playlist:", it["src"], e, flush=True)
    return it


def select(uuid):
    """Prepares a station to be played: registers it, adds it to "recent" and reports the click."""
    it = _find(uuid)
    if not it:
        return None
    it = _fresh(it)
    with lock:
        radios[it["id"]] = it
    recent = [it] + [r for r in _stored("radio_recent") if r["uuid"] != uuid]
    db.kv_set("radio_recent", recent[:MAX_RECENT])
    fav = _stored("radio_favorites")
    if any(r["uuid"] == uuid for r in fav):                     # keep the favorite's link fresh too
        db.kv_set("radio_favorites", [it if r["uuid"] == uuid else r for r in fav])
    threading.Thread(target=_click, args=(uuid,), daemon=True).start()
    return public(it)


def icon(rid):
    """Station logo, downloaded once and cached with the covers (None if there is none)."""
    with lock:
        it = radios.get(rid)
    img, miss = os.path.join(cfg.covers_dir, rid + ".img"), os.path.join(cfg.covers_dir, rid + ".none")
    if os.path.exists(img):
        with open(img, "rb") as fh:
            return fh.read()
    if not it or os.path.exists(miss) or not it["favicon"].startswith(("http://", "https://")):
        return None
    os.makedirs(cfg.covers_dir, exist_ok=True)
    try:
        data = http_get(it["favicon"], timeout=8)
    except Exception:
        open(miss, "w").close()
        return None
    with open(img, "wb") as fh:
        fh.write(data)
    return data


def _click(uuid):
    try:
        rb_get(f"url/{uuid}")
    except Exception:
        pass


def favorite(uuid, on):
    fav = [r for r in _stored("radio_favorites") if r["uuid"] != uuid]
    if on:
        it = _find(uuid)
        if it:
            fav.insert(0, it)
            with lock:
                radios[it["id"]] = it
    db.kv_set("radio_favorites", fav)
    return [public(it) for it in fav]
