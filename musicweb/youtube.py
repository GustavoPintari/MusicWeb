"""YouTube: resolves links with yt-dlp and keeps the history of played videos."""
import importlib.util, json, os, re, shutil, subprocess, sys, threading, time

from .config import cfg
from .i18n import _
from .state import lock, state, yt_items
from .util import http_get


YT_ID = re.compile(r"(?:[?&]v=|youtu\.be/|/shorts/|/live/|/embed/|/v/)([A-Za-z0-9_-]{11})")

yt_urls = {}     # id -> (direct audio link, headers, when it was fetched)
yt_locks, yt_locks_lock = {}, threading.Lock()


def load_history():
    try:
        with open(cfg.yt_history_file) as fh:
            for y in json.load(fh):
                yt_items[y["id"]] = y
    except (OSError, ValueError, KeyError, TypeError):
        pass


def yt_public(y):
    return {k: y[k] for k in ("id", "vid", "title", "artist", "dur", "fmt", "q")}


def yt_save():
    os.makedirs(os.path.dirname(cfg.yt_history_file), exist_ok=True)
    with lock:
        data = list(yt_items.values())
    with open(cfg.yt_history_file, "w") as fh:
        json.dump(data, fh)


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


def yt_resolve(vid):
    """Asks yt-dlp for the video data and the direct audio link."""
    cmd = ytdlp_cmd()
    if not cmd:
        raise ValueError(_("yt-dlp não está instalado no servidor (pip install yt-dlp)"))
    try:
        extra = ["--cookies", os.path.expanduser(cfg.yt_cookies)] if cfg.yt_cookies else []
        r = subprocess.run(cmd + extra + ["-j", "--no-playlist", "--no-warnings", "-f", cfg.yt_format,
                                          "https://www.youtube.com/watch?v=" + vid],
                           capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        raise ValueError(_("o YouTube demorou demais para responder"))
    if r.returncode != 0:
        errs = [l for l in r.stderr.splitlines() if "ERROR" in l] or r.stderr.strip().splitlines() or ["erro desconhecido"]
        if "confirm you" in errs[-1] and "bot" in errs[-1]:
            raise ValueError(_("o YouTube pediu login para confirmar que não é um robô. Atualize o yt-dlp "
                               "(pip install -U yt-dlp) ou configure [youtube] cookies no config.toml"))
        if "Private video" in errs[-1] or "unavailable" in errs[-1].lower():
            raise ValueError(_("este vídeo é privado ou não está disponível"))
        raise ValueError(re.sub(r"^ERROR:\s*(\[[^\]]*\]\s*)?(\S+:\s*)?", "", errs[-1]))
    info = json.loads(r.stdout)
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


def yt_add(url):
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
        uploader = re.sub(r"\s*-\s*Topic$|VEVO$", "", info.get("uploader") or info.get("channel") or "").strip()
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
        yt_items[tid] = y                         # moves to the end = most recent
        playing = state["queue"][state["pos"]] if state["active"] and state["queue"] else None
        for old in [k for k in yt_items if k not in (tid, playing)][:max(0, len(yt_items) - cfg.yt_max_history)]:
            yt_items.pop(old)
        state["lib"] += 1
    yt_save()
    return {"ok": True, "item": yt_public(y)}


def yt_remove(tid):
    with lock:
        if yt_items.pop(tid, None) is None:
            return {"ok": False}
        state["lib"] += 1
    yt_urls.pop(tid, None)
    for p in (os.path.join(cfg.covers_dir, tid + ".img"), os.path.join(cfg.lyrics_dir, tid + ".json")):
        try:
            os.remove(p)
        except OSError:
            pass
    yt_save()
    return {"ok": True}


def yt_thumb(tid):
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
