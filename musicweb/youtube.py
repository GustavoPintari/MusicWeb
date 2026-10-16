"""YouTube: resolves links and playlists with yt-dlp and keeps the history of played videos/playlists."""
import importlib.util, json, os, re, shutil, subprocess, sys, threading, time

from . import pot
from .config import cfg
from .i18n import _
from .state import lock, state, yt_items, yt_playlists
from .util import http_get


YT_ID = re.compile(r"(?:[?&]v=|youtu\.be/|/shorts/|/live/|/embed/|/v/)([A-Za-z0-9_-]{11})")
YT_LIST = re.compile(r"[?&]list=([A-Za-z0-9_-]+)")
MAX_PLAYLISTS = 10      # playlists kept in "recently played"

yt_urls = {}     # id -> (direct audio link, headers, when it was fetched)
yt_locks, yt_locks_lock = {}, threading.Lock()


def load_history():
    try:
        with open(cfg.yt_history_file) as fh:
            data = json.load(fh)
        if isinstance(data, list):                 # old format: just the videos
            data = {"items": data, "playlists": []}
        for y in data.get("items", []):
            yt_items[y["id"]] = y
        for pl in data.get("playlists", []):
            yt_playlists[pl["id"]] = pl
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass


def yt_public(y):
    return {k: y[k] for k in ("id", "vid", "title", "artist", "dur", "fmt", "q")}


def pl_public(pl, entries=False):
    out = {k: pl[k] for k in ("id", "title", "artist", "count", "at")}
    if entries:
        with lock:
            out["entries"] = [yt_public(yt_items[t]) for t in pl["entries"] if t in yt_items]
    return out


def history_public():
    """Videos added on their own plus playlists, most recent first (for "recently played")."""
    with lock:
        vids = [{**yt_public(y), "at": y.get("at", 0)} for y in yt_items.values() if y.get("hist", True)]
        pls = [{**pl_public(p), "playlist": True} for p in yt_playlists.values()]
    return sorted(vids + pls, key=lambda x: x["at"], reverse=True)


def yt_save():
    os.makedirs(os.path.dirname(cfg.yt_history_file), exist_ok=True)
    with lock:
        data = {"items": list(yt_items.values()), "playlists": list(yt_playlists.values())}
    with open(cfg.yt_history_file, "w") as fh:
        json.dump(data, fh)


def prune():
    """Keeps the history bounded. Call with the lock held."""
    playing = set(state["queue"]) if state["active"] or state["restored"] is not None else set()
    hist = [k for k, y in yt_items.items() if y.get("hist", True) and k not in playing]
    for old in hist[:max(0, len(hist) - cfg.yt_max_history)]:
        yt_items[old]["hist"] = False              # still needed if it is in a playlist
    for old in list(yt_playlists)[:max(0, len(yt_playlists) - MAX_PLAYLISTS)]:
        yt_playlists.pop(old)
    in_playlists = {t for pl in yt_playlists.values() for t in pl["entries"]}
    for k in [k for k, y in yt_items.items() if not y.get("hist", True) and k not in in_playlists and k not in playing]:
        yt_items.pop(k)


def yt_vid(url):
    url = (url or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url
    m = YT_ID.search(url)
    return m.group(1) if m else None


def ytdlp_cmd():
    p = shutil.which("yt-dlp")
    if p:
        return [p]
    if importlib.util.find_spec("yt_dlp"):
        return [sys.executable, "-m", "yt_dlp"]
    return None


def run_ytdlp(args, timeout=90):
    """Runs yt-dlp and returns its JSON output; raises ValueError with a readable message."""
    cmd = ytdlp_cmd()
    if not cmd:
        raise ValueError(_("yt-dlp não está instalado no servidor (pip install yt-dlp)"))
    try:
        extra = (["--cookies", os.path.expanduser(cfg.yt_cookies)] if cfg.yt_cookies else []) + pot.ytdlp_args(cmd)
        r = subprocess.run(cmd + extra + ["--no-warnings"] + args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ValueError(_("o YouTube demorou demais para responder"))
    if r.returncode != 0:
        errs = [l for l in r.stderr.splitlines() if "ERROR" in l] or r.stderr.strip().splitlines() or ["erro desconhecido"]
        if "confirm you" in errs[-1] and "bot" in errs[-1]:
            raise ValueError(_("o YouTube pediu login para confirmar que não é um robô. Atualize o yt-dlp "
                               "(pip install -U yt-dlp), instale o gerador de PO token (./pot-setup.sh) "
                               "ou configure [youtube] cookies no config.toml"))
        if "Private video" in errs[-1] or "unavailable" in errs[-1].lower():
            raise ValueError(_("este vídeo é privado ou não está disponível"))
        raise ValueError(re.sub(r"^ERROR:\s*(\[[^\]]*\]\s*)?(\S+:\s*)?", "", errs[-1]))
    return json.loads(r.stdout)


def yt_resolve(vid):
    """Asks yt-dlp for the video data and the direct audio link."""
    info = run_ytdlp(["-j", "--no-playlist", "-f", cfg.yt_format, "https://www.youtube.com/watch?v=" + vid])
    url = info.get("url") or (info.get("requested_formats") or [{}])[0].get("url")
    if not url:
        raise ValueError(_("não achei o áudio deste vídeo"))
    return info, url, info.get("http_headers") or {}


def yt_direct(tid, force=False):
    """Direct audio link; YouTube's expires after a few hours, so it is renewed."""
    with yt_locks_lock:
        lk = yt_locks.setdefault(tid, threading.Lock())
    with lk:
        c = yt_urls.get(tid)
        if c and not force and time.time() - c[2] < 3 * 3600:
            return c
        _info, url, headers = yt_resolve(yt_items[tid]["vid"])
        c = yt_urls[tid] = (url, headers, time.time())
        return c


# "(Official Video)", "[Clipe Oficial]", "(Lyrics)", "| Ao Vivo no ..."
YT_JUNK = re.compile(r"\s*[(\[][^)\]]*(?:official|oficial|video|vídeo|clipe|clip|audio|áudio|lyric|letra|legendad|"
                     r"visuali|\bhd\b|\b4k\b|\bmv\b)[^)\]]*[)\]]", re.I)


def guess_artist_title(title, uploader):
    t = YT_JUNK.sub("", title)
    t = re.sub(r"\s*[|｜].*$", "", t).strip()
    parts = re.split(r"\s+[-–—]\s+", t, maxsplit=1)
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[0].strip(), parts[1].strip(' "\'')
    return uploader, t.strip(' "\'')


def clean_uploader(s):
    return re.sub(r"\s*-\s*Topic$|VEVO$", "", s or "").strip()


def yt_add(url):
    if YT_LIST.search(url or ""):
        return yt_add_playlist(url)
    vid = yt_vid(url)
    if not vid:
        return {"ok": False, "error": _("Não reconheci esse link do YouTube")}
    tid = "yt_" + vid
    with lock:
        y = yt_items.get(tid)
    if not y:
        try:
            info, direct, headers = yt_resolve(vid)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        yt_urls[tid] = (direct, headers, time.time())
        title = info.get("title") or vid
        uploader = clean_uploader(info.get("uploader") or info.get("channel"))
        if info.get("track") and info.get("artist"):          # YouTube Music videos carry artist/track metadata
            la, lt = info["artist"].split(",")[0].strip(), info["track"]
        else:
            la, lt = guess_artist_title(title, uploader)
        abr = info.get("abr") or 0
        y = {"id": tid, "vid": vid, "title": info.get("track") or title, "artist": info.get("artist") or uploader,
             "dur": round(info.get("duration") or 0), "fmt": "YT", "q": f"{round(abr)}k" if abr else "",
             "album": tid, "n": 0, "disc": 1, "l_artist": la, "l_title": lt}
    with lock:
        yt_items.pop(tid, None)
        yt_items[tid] = {**y, "hist": True, "at": int(time.time())}     # moves to the end = most recent
        prune()
        state["lib"] += 1
    yt_save()
    return {"ok": True, "item": yt_public(y)}


def yt_add_playlist(url):
    """Lists a playlist without resolving its videos (each one is resolved when its turn comes)."""
    lid, vid = YT_LIST.search(url).group(1), yt_vid(url)
    # mixes ("RD...") only exist next to a video, so keep the video in the link when there is one
    link = f"https://www.youtube.com/watch?v={vid}&list={lid}" if vid else f"https://www.youtube.com/playlist?list={lid}"
    try:
        info = run_ytdlp(["-J", "--flat-playlist", "--playlist-end", str(cfg.yt_playlist_max), link], timeout=120)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    plid = "ytpl_" + lid
    entries = []
    with lock:
        for e in info.get("entries") or []:
            v, title = e.get("id"), e.get("title") or ""
            if not v or len(v) != 11 or title in ("[Private video]", "[Deleted video]"):
                continue
            tid = "yt_" + v
            if tid not in yt_items:
                artist = clean_uploader(e.get("channel") or e.get("uploader"))
                la, lt = guess_artist_title(title, artist)
                yt_items[tid] = {"id": tid, "vid": v, "title": title, "artist": artist,
                                 "dur": round(e.get("duration") or 0), "fmt": "YT", "q": "", "album": tid,
                                 "n": 0, "disc": 1, "l_artist": la, "l_title": lt, "hist": False}
            if tid not in entries:
                entries.append(tid)
        if not entries:
            return {"ok": False, "error": _("Não achei vídeos nessa playlist")}
        yt_playlists.pop(plid, None)
        yt_playlists[plid] = {"id": plid, "list": lid, "title": info.get("title") or lid,
                              "artist": clean_uploader(info.get("uploader") or info.get("channel")),
                              "count": len(entries), "entries": entries, "at": int(time.time())}
        prune()
        state["lib"] += 1
    yt_save()
    start = entries.index("yt_" + vid) if vid and "yt_" + vid in entries else 0
    return {"ok": True, "playlist": pl_public(yt_playlists[plid], entries=True), "start": start}


def yt_remove(tid):
    """Removes a video or a playlist from "recently played"."""
    with lock:
        if tid in yt_playlists:
            yt_playlists.pop(tid)
        elif tid in yt_items:
            yt_items[tid]["hist"] = False              # prune() drops it unless a playlist still has it
        else:
            return {"ok": False}
        prune()
        gone = tid not in yt_items
        state["lib"] += 1
    if not gone:
        yt_save()
        return {"ok": True}
    yt_urls.pop(tid, None)
    for p in (os.path.join(cfg.covers_dir, tid + ".img"), os.path.join(cfg.lyrics_dir, tid + ".json")):
        try:
            os.remove(p)
        except OSError:
            pass
    yt_save()
    return {"ok": True}


def yt_thumb(tid):
    if tid in yt_playlists:                        # playlist: the first video's thumbnail
        entries = yt_playlists[tid]["entries"]
        return yt_thumb(entries[0]) if entries else None
    p = os.path.join(cfg.covers_dir, tid + ".img")
    if os.path.exists(p):
        with open(p, "rb") as fh:
            return fh.read()
    try:
        data = http_get(f"https://i.ytimg.com/vi/{yt_items[tid]['vid']}/mqdefault.jpg")
    except Exception:
        return None
    os.makedirs(cfg.covers_dir, exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(data)
    return data
