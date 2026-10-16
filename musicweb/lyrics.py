"""Letras: arquivo .lrc/.txt, tags da música ou LRCLIB (lrclib.net)."""
import json, os, re, time
import urllib.error, urllib.parse

from .config import cfg
from .state import albums, item, yt_items
from .util import clean_album, http_get, mutagen


LRC_LINE = re.compile(r"^\s*\[\d+:\d+(?:[.:]\d+)?\]", re.M)
TITLE_JUNK = re.compile(r"\s*(?:[(\[][^)\]]*(?:remaster|bonus|mono|stereo|version|versão|edit\b|feat\.|ft\.)[^)\]]*[)\]]"
                        r"|\s[-–]\s[^-–]*(?:remaster|version|versão|mono|stereo|edit\b)[^-–]*)$", re.I)


def clean_title(s):
    prev = None
    while prev != s:
        prev, s = s, TITLE_JUNK.sub("", s)
    return s.strip() or prev


def lyr_pack(text, src):
    text = text.replace("\r\n", "\n").strip()
    synced = text if LRC_LINE.search(text) else ""
    return {"ok": True, "synced": synced, "plain": "" if synced else text, "src": src}


def lyrics_local(t):
    """Arquivo .lrc/.txt com o mesmo nome da música, ou letra gravada nas tags."""
    stem = os.path.splitext(t["path"])[0]
    for ext in (".lrc", ".LRC", ".txt"):
        if os.path.isfile(stem + ext):
            with open(stem + ext, encoding="utf-8-sig", errors="replace") as fh:
                text = fh.read()
            if text.strip():
                return lyr_pack(text, "arquivo " + ext.lower())
    if not mutagen:
        return None
    try:
        tags = mutagen.File(t["path"]).tags
    except Exception:
        return None
    if tags is None:
        return None
    if hasattr(tags, "getall"):                                    # MP3 (ID3)
        for fr in tags.getall("USLT"):
            if str(fr.text).strip():
                return lyr_pack(str(fr.text), "tags")
        return None
    for k in ("LYRICS", "UNSYNCEDLYRICS", "\xa9lyr"):              # FLAC/OGG, M4A
        try:
            v = tags.get(k) or tags.get(k.lower())
        except Exception:
            v = None
        if v and str(v[0]).strip():
            return lyr_pack(str(v[0]), "tags")
    return None


def lrclib_get(url):
    """GET no LRCLIB; se ele pedir para esperar (429), espera e tenta mais uma vez."""
    try:
        return http_get(url, True)
    except urllib.error.HTTPError as e:
        if e.code != 429:
            raise
        time.sleep(min(3.0, float(e.headers.get("Retry-After") or 1)))
        return http_get(url, True)


def lrclib(artist, title, album="", dur=0):
    base = "https://lrclib.net/api/"
    has = lambda r: r.get("syncedLyrics") or r.get("plainLyrics") or r.get("instrumental")

    def pack(r):
        synced = r.get("syncedLyrics") or ""
        return {"ok": True, "synced": synced, "plain": "" if synced else (r.get("plainLyrics") or ""),
                "instrumental": bool(r.get("instrumental")) and not synced and not r.get("plainLyrics"), "src": "LRCLIB"}

    if artist and dur:                                             # busca exata (artista + faixa + duração)
        p = {"artist_name": artist, "track_name": title, "duration": dur}
        if album:
            p["album_name"] = album
        try:
            r = lrclib_get(base + "get?" + urllib.parse.urlencode(p))
            if has(r):
                return pack(r)
        except urllib.error.HTTPError as e:
            if e.code not in (400, 404, 429):       # sem resultado exato: tenta a busca
                raise
    searches = ([{"track_name": title, "artist_name": artist}] if artist else []) + [{"q": f"{artist} {title}".strip()}]
    for p in searches:
        cands = [r for r in lrclib_get(base + "search?" + urllib.parse.urlencode(p)) if has(r)]
        # prefere duração parecida (mesma versão) e letra sincronizada
        cands.sort(key=lambda r: (bool(dur) and abs((r.get("duration") or 0) - dur) > 3, not r.get("syncedLyrics")))
        if cands:
            return pack(cands[0])
    return None


def get_lyrics(tid, artist="", title=""):
    t = item(tid)
    if not t:
        return {"ok": False, "error": "Faixa não encontrada"}
    yt, manual = tid in yt_items, bool(artist or title)
    cache = os.path.join(cfg.lyrics_dir, tid + ".json")
    if not manual:
        if not yt:
            res = lyrics_local(t)
            if res:
                return res
        try:
            with open(cache) as fh:
                return json.load(fh)
        except (OSError, ValueError):
            pass
    alb = albums.get(t["album"])
    if yt:
        da, dt, album = t.get("l_artist", t["artist"]), t.get("l_title", t["title"]), ""
    else:
        da = t["artist"] or (alb["artist"] if alb and alb["artist"] not in ("Vários artistas", "Desconhecido") else "")
        dt, album = t["title"], clean_album(alb["full"]) if alb else ""
    artist, title = (artist or da).strip(), clean_title((title or dt).strip())
    if not cfg.lyrics_online:
        return {"ok": False, "artist": artist, "title": title,
                "error": "A busca de letras na internet está desligada ([lyrics] online no config.toml)"}
    try:
        res = lrclib(artist, title, album, t["dur"])
    except Exception as e:
        print("[letra] lrclib:", e, flush=True)
        busy = isinstance(e, urllib.error.HTTPError) and e.code == 429
        return {"ok": False, "artist": artist, "title": title,
                "error": "O LRCLIB pediu para esperar um pouco. Tente de novo daqui a alguns segundos."
                if busy else "Não consegui falar com o LRCLIB"}
    if not res:
        return {"ok": False, "artist": artist, "title": title}
    os.makedirs(cfg.lyrics_dir, exist_ok=True)
    with open(cache, "w") as fh:
        json.dump(res, fh)
    return res
