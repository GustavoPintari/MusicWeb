"""Covers: from the album folder, the tags or online (iTunes / MusicBrainz / Deezer)."""
import base64, json, os, re, threading, time
import urllib.error, urllib.parse

from .config import cfg
from .i18n import _
from .state import albums, lock, tracks, yt_items
from .util import IMG_EXTS, clean_album, http_get, inside_root, mutagen, safe_name, sniff
from .youtube import yt_thumb


mb_lock = threading.Lock()         # MusicBrainz: at most 1 request per second
mb_last = [0.0]
it_lock = threading.Lock()         # iTunes: ~20 searches per minute
it_bucket = {"tokens": 20.0, "t": time.time()}


cover_ver = {}     # album id -> cover version (changes when the cover is replaced)


def versions_file():
    return os.path.join(cfg.covers_dir, "versions.json")


def load_versions():
    try:
        with open(versions_file()) as fh:
            cover_ver.update(json.load(fh))
    except (OSError, ValueError):
        pass


def bump_cover(aid):
    cover_ver[aid] = cover_ver.get(aid, 0) + 1
    for ext in (".img", ".none"):
        try:
            os.remove(os.path.join(cfg.covers_dir, aid + ext))
        except OSError:
            pass
    os.makedirs(cfg.covers_dir, exist_ok=True)
    with open(versions_file(), "w") as fh:
        json.dump(cover_ver, fh)


ART_DIRS = {"artwork", "art", "covers", "cover", "scans", "scan", "images", "imagens", "capa", "capas"}


def cover_score(fname, album, shared):
    n = os.path.splitext(fname)[0].lower()
    alb = album.lower()
    if n == "cover" and not shared or n == alb:
        return 1000                # cover set explicitly (including from the page)
    score = 0
    if alb and alb in n:
        score += 100
    elif shared:                  # folder with several albums: only accept images named after the album
        return None
    if n in ("cover", "folder", "front", "capa", "album", "albumart", "albumartlarge"):
        score += 60
    elif re.search(r"cover|front|folder|capa|albumart", n):
        score += 40
    if re.search(r"back|verso|inlay|inside|booklet|tray|label|disc|\bcd\b|contra", n):
        score -= 60
    if "small" in n:
        score -= 10
    return score


def cover_from_folder(a):
    """Looks for a cover image in the album folder (and subfolders such as Artwork/Scans)."""
    dirs = {a["dir"]} | {os.path.dirname(tracks[t]["path"]) for t in a["tracks"] if t in tracks}
    cands = []
    for d in dirs:
        try:
            entries = os.listdir(d)
        except OSError:
            continue
        for f in entries:
            p = os.path.join(d, f)
            if f.lower() in ART_DIRS and os.path.isdir(p):
                try:
                    entries2 = os.listdir(p)
                except OSError:
                    continue
                for f2 in entries2:
                    if f2.lower().endswith(IMG_EXTS):
                        sc = cover_score(f2, a["name"], a["shared"])
                        if sc is not None:
                            cands.append((sc - 5, os.path.getsize(os.path.join(p, f2)), os.path.join(p, f2)))
            elif f.lower().endswith(IMG_EXTS):
                sc = cover_score(f, a["name"], a["shared"])
                if sc is not None:
                    cands.append((sc, os.path.getsize(p), p))
    if not cands:
        return None
    cands.sort(reverse=True)               # highest score, then largest file
    with open(cands[0][2], "rb") as fh:
        return fh.read()


def cover_embedded(a):
    if not mutagen:
        return None
    for tid in a["tracks"][:3]:
        try:
            f = mutagen.File(tracks[tid]["path"])
        except Exception:
            continue
        if f is None:
            continue
        if getattr(f, "pictures", None):                       # FLAC
            return f.pictures[0].data
        tags = f.tags
        if tags is None:
            continue
        if hasattr(tags, "getall"):                            # MP3 (ID3)
            apic = tags.getall("APIC")
            if apic:
                return apic[0].data
        try:
            if "covr" in tags:                                 # M4A
                return bytes(tags["covr"][0])
            if "metadata_block_picture" in tags:               # OGG/Opus
                from mutagen.flac import Picture
                return Picture(base64.b64decode(tags["metadata_block_picture"][0])).data
        except Exception:
            pass
    return None


def itunes_wait():
    with it_lock:
        b = it_bucket
        b["tokens"] = min(20.0, b["tokens"] + (time.time() - b["t"]) / 3)
        b["t"] = time.time()
        if b["tokens"] < 1:
            time.sleep((1 - b["tokens"]) * 3)
            b["tokens"], b["t"] = 1.0, time.time()
        b["tokens"] -= 1


def cover_online(a):
    """Returns (image, sure_it_does_not_exist)."""
    name = clean_album(a["full"])
    artist = "" if a["artist"] in ("Vários artistas", "Desconhecido") else a["artist"]
    net_ok = True
    # 1) iTunes: fast, good coverage
    try:
        itunes_wait()
        term = urllib.parse.quote(f"{artist} {name}".strip())
        res = http_get(f"https://itunes.apple.com/search?entity=album&limit=10&term={term}", True)
        for r in res.get("results", []):
            cn = clean_album(r.get("collectionName", "")).lower()
            an = r.get("artistName", "").lower()
            if (cn == name.lower() or name.lower() in cn) and (not artist or artist.lower() in an or an in artist.lower()):
                return http_get(r["artworkUrl100"].replace("100x100bb", "300x300bb")), False
    except Exception as e:
        net_ok = False
        print("[capa] itunes:", e, flush=True)
    # 2) MusicBrainz + Cover Art Archive (slower)
    try:
        with mb_lock:
            wait = 1.1 - (time.time() - mb_last[0])
            if wait > 0:
                time.sleep(wait)
            mb_last[0] = time.time()
            q = 'releasegroup:"%s"' % name.replace('"', "")
            if artist:
                q += ' AND artist:"%s"' % artist.replace('"', "")
            res = http_get("https://musicbrainz.org/ws/2/release-group/?fmt=json&limit=3&query="
                           + urllib.parse.quote(q), True)
        for rg in res.get("release-groups", []):
            if rg.get("score", 0) < 90:
                break
            try:
                return http_get(f"https://coverartarchive.org/release-group/{rg['id']}/front-250", timeout=30), False
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    net_ok = False
            except Exception:
                net_ok = False
    except Exception as e:
        net_ok = False
        print("[capa] musicbrainz:", e, flush=True)
    return None, net_ok


def get_cover(aid):
    if aid in yt_items:
        return yt_thumb(aid)
    a = albums.get(aid)
    if not a:
        return None
    data = cover_from_folder(a)
    if data:
        return data
    os.makedirs(cfg.covers_dir, exist_ok=True)
    img, miss = os.path.join(cfg.covers_dir, aid + ".img"), os.path.join(cfg.covers_dir, aid + ".none")
    if os.path.exists(img):
        with open(img, "rb") as fh:
            return fh.read()
    if os.path.exists(miss):
        return None
    data, sure = cover_embedded(a), True
    if not data and cfg.covers_online:
        data, sure = cover_online(a)
    if data:
        with open(img, "wb") as fh:
            fh.write(data)
    elif sure:                     # only remember "no cover" if the lookup did not fail because of the network
        open(miss, "w").close()
    return data


# ---------------------------------------------------------------- change cover


COVER_HOSTS = ("mzstatic.com", "dzcdn.net")       # hosts the page may ask us to download covers from


def set_cover(aid, data):
    with lock:
        a = albums.get(aid)
    if not a:
        raise ValueError(_("álbum não encontrado"))
    kind = sniff(data)
    if not (data[:2] == b"\xff\xd8" or kind != "image/jpeg"):
        raise ValueError(_("o arquivo não parece ser uma imagem"))
    if not inside_root(a["dir"]):
        raise ValueError(_("pasta do álbum fora da biblioteca"))
    ext = {"image/png": ".png", "image/webp": ".webp", "image/gif": ".gif", "image/bmp": ".bmp"}.get(kind, ".jpg")
    stem = safe_name(a["full"]) if a["shared"] else "cover"
    ts = time.strftime("%Y%m%d-%H%M%S")
    for f in os.listdir(a["dir"]):                       # keep the previous cover as .bak
        base, e = os.path.splitext(f)
        if base.lower() == stem.lower() and e.lower() in IMG_EXTS:
            os.rename(os.path.join(a["dir"], f), os.path.join(a["dir"], f"{f}.{ts}.bak"))
    with open(os.path.join(a["dir"], stem + ext), "wb") as fh:
        fh.write(data)
    bump_cover(aid)


def cover_candidates(term):
    out = []
    try:
        itunes_wait()
        res = http_get("https://itunes.apple.com/search?entity=album&limit=12&term=" + urllib.parse.quote(term), True)
        for r in res.get("results", []):
            u = r.get("artworkUrl100", "")
            if u:
                out.append({"src": "iTunes", "title": r.get("collectionName", ""), "artist": r.get("artistName", ""),
                            "thumb": u.replace("100x100bb", "200x200bb"), "url": u.replace("100x100bb", "1000x1000bb")})
    except Exception as e:
        print("[capa] busca itunes:", e, flush=True)
    try:
        res = http_get("https://api.deezer.com/search/album?limit=12&q=" + urllib.parse.quote(term), True)
        for r in res.get("data", []):
            if r.get("cover_xl"):
                out.append({"src": "Deezer", "title": r.get("title", ""), "artist": r.get("artist", {}).get("name", ""),
                            "thumb": r.get("cover_medium") or r["cover_xl"], "url": r["cover_xl"]})
    except Exception as e:
        print("[capa] busca deezer:", e, flush=True)
    return out


def cover_from_url(url):
    host = urllib.parse.urlparse(url).hostname or ""
    if not url.startswith("https://") or not any(host == h or host.endswith("." + h) for h in COVER_HOSTS):
        raise ValueError(_("endereço de imagem não permitido"))
    return http_get(url, timeout=20)
