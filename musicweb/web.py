"""HTTP server: the page, the JSON API, streaming and downloads."""
import json, os, re, urllib.error, urllib.parse, urllib.request, zipfile
from http.server import BaseHTTPRequestHandler

from . import radio
from .config import cfg
from .covers import cover_candidates, cover_from_url, get_cover, set_cover
from .editor import edit_album, remove_album
from .history import record_play, stats
from .i18n import _
from .library import library_json, scan
from .lyrics import get_lyrics
from .player import mpv_cmd, pause, play_pos, resume, seek, status, stop
from .retro import periods as retro_periods, retro
from .state import albums, item, lock, state, tracks, yt_items, yt_playlists
from .util import MIME, safe_name, sniff, zip_name
from .youtube import pl_public, yt_add, yt_check, yt_direct, yt_remove

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
STATIC_TYPES = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8"}
STATIC_REF = re.compile(rb'(?:src|href)="/static/([^"?]+)"')


def static_path(name):
    """File inside static/ (None for anything else, e.g. "../")."""
    path = os.path.realpath(os.path.join(STATIC, name))
    if not path.startswith(os.path.realpath(STATIC) + os.sep) or not os.path.isfile(path):
        return None
    return path


def versioned(page):
    """Adds ?v=<modification time> to the page's CSS/JS links, so a browser never keeps an old copy
    after an update (the files themselves can then be cached for a long time)."""
    def add(m):
        path = static_path(m.group(1).decode())
        v = int(os.path.getmtime(path)) if path else 0
        return m.group(0)[:-1] + f"?v={v}\"".encode()
    return STATIC_REF.sub(add, page)


MAX_UPLOAD = 20 * 1024 * 1024


class _Counter:
    """Counts bytes written (zipfile needs tell() on a non-seekable stream)."""
    def __init__(self, w):
        self.w, self.n = w, 0

    def write(self, b):
        self.w.write(b)
        self.n += len(b)
        return len(b)

    def tell(self):
        return self.n

    def flush(self):
        self.w.flush()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, body, ctype="application/json; charset=utf-8", code=200, cache=False):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "max-age=604800" if cache else "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        p, _sep, qs = self.path.partition("?")
        q = urllib.parse.parse_qs(qs)
        if p == "/":
            with open(os.path.join(STATIC, "index.html"), "rb") as fh:
                page = fh.read()
            # the page reads the interface language from <html lang>
            page = versioned(page.replace(b'<html lang="pt-BR">', f'<html lang="{cfg.lang}">'.encode(), 1))
            self.send(page, "text/html; charset=utf-8")
        elif p.startswith("/static/"):
            path = static_path(urllib.parse.unquote(p[len("/static/"):]))
            ctype = STATIC_TYPES.get(os.path.splitext(path or "")[1].lower())
            if not path or not ctype:
                return self.send("{}", code=404)
            with open(path, "rb") as fh:
                data = fh.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "max-age=31536000, immutable" if "v=" in qs else "no-cache")
            self.end_headers()
            self.wfile.write(data)
        elif p == "/api/library":
            self.send(library_json())
        elif p == "/api/status":
            self.send(json.dumps(status()))
        elif p == "/api/cover_search":
            self.send(json.dumps(cover_candidates(q.get("q", [""])[0])))
        elif p == "/api/lyrics":
            self.send(json.dumps(get_lyrics(q.get("id", [""])[0], q.get("artist", [""])[0], q.get("title", [""])[0])))
        elif p == "/api/yt_check":
            self.send(json.dumps(yt_check(q.get("id", [""])[0])))
        elif p == "/api/yt_playlist":
            pl = yt_playlists.get(q.get("id", [""])[0])
            self.send(json.dumps(pl_public(pl, entries=True) if pl else {"error": _("não encontrado")}), code=200 if pl else 404)
        elif p == "/api/retro":
            period = q.get("period", [""])[0]
            self.send(json.dumps(retro(period) if period else retro_periods()))
        elif p.startswith("/api/radio"):
            self.radio_get(p, q)
        elif p == "/api/stats":
            try:
                days = int(q.get("days", ["0"])[0])
            except ValueError:
                days = 0
            self.send(json.dumps(stats(days)))
        elif p.startswith("/api/stream/yt_"):
            self.yt_stream(p.rsplit("/", 1)[1], "dl" in q)
        elif p.startswith("/api/stream/"):
            self.stream(p.rsplit("/", 1)[1], "dl" in q)
        elif p.startswith("/api/download/"):
            self.download(p.rsplit("/", 1)[1])
        elif p.startswith("/api/cover/"):
            data = get_cover(p.rsplit("/", 1)[1])
            if data:
                self.send(data, sniff(data), cache=True)
            else:
                self.send(b"", "text/plain", 404)
        else:
            self.send("{}", code=404)

    def stream(self, tid, attachment=False):
        t = tracks.get(tid)
        if not t or not os.path.isfile(t["path"]):
            return self.send("{}", code=404)
        size = os.path.getsize(t["path"])
        start, end = 0, size - 1
        m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1))
                end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
            else:                                   # "bytes=-500": last 500 bytes
                start = max(0, size - int(m.group(2)))
            if start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        ext = os.path.splitext(t["path"])[1].lower()
        self.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if attachment:
            fname = os.path.basename(t["path"])
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(fname))
        self.end_headers()
        try:
            with open(t["path"], "rb") as fh:
                fh.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = fh.read(min(65536, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass                                    # the browser cancelled (normal when seeking)

    def radio_get(self, p, q):
        arg = lambda k: q.get(k, [""])[0]
        try:
            if p == "/api/radio":
                data = radio.overview()
            elif p == "/api/radio/countries":
                data = radio.countries()
            elif p == "/api/radio/tags":
                data = radio.tags()
            elif p == "/api/radio/search":
                data = radio.search(arg("q").strip(), arg("country"), arg("tag"))
            else:
                return self.send("{}", code=404)
        except Exception as e:
            print("[rádio]", e, flush=True)
            return self.send(json.dumps({"error": _("Não consegui falar com o Radio Browser")}), code=502)
        self.send(json.dumps(data))

    def yt_stream(self, tid, attachment=False):
        """Relays the YouTube audio (with Range, so seeking works)."""
        if tid not in yt_items:
            return self.send("{}", code=404)
        r = None
        for attempt in range(2):                     # 2nd attempt asks for a new link (the old one expired)
            try:
                url, headers, _fetched = yt_direct(tid, force=attempt > 0)
            except Exception as e:
                return self.send(json.dumps({"error": str(e)}), code=502)
            h = dict(headers)
            if self.headers.get("Range"):
                h["Range"] = self.headers["Range"]
            try:
                r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=20)
                break
            except urllib.error.HTTPError as e:
                if e.code == 416:
                    self.send_response(416)
                    if e.headers.get("Content-Range"):
                        self.send_header("Content-Range", e.headers["Content-Range"])
                    self.end_headers()
                    return
                if attempt == 1:
                    return self.send("{}", code=502)
            except Exception:
                if attempt == 1:
                    return self.send("{}", code=502)
        with r:
            ctype = r.headers.get("Content-Type", "audio/mp4")
            self.send_response(r.status)
            self.send_header("Content-Type", ctype)
            for k in ("Content-Length", "Content-Range"):
                if r.headers.get(k):
                    self.send_header(k, r.headers[k])
            self.send_header("Accept-Ranges", "bytes")
            if attachment:
                fname = safe_name(yt_items[tid]["title"]) + (".webm" if "webm" in ctype else ".m4a")
                self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(fname))
            self.end_headers()
            try:
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            except OSError:
                pass                                 # the browser/mpv cancelled (normal when seeking)

    def download(self, aid):
        with lock:
            a = albums.get(aid)
            files = [tracks[t]["path"] for t in a["tracks"]] if a else []
        if not a:
            return self.send("{}", code=404)
        folder = zip_name(f"{a['artist']} - {a['full']}")
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(folder + ".zip"))
        self.send_header("Connection", "close")
        self.end_headers()
        base = os.path.realpath(a["dir"])
        try:
            # ZIP_STORED: audio is already compressed, and this spares the phone CPU
            with zipfile.ZipFile(_Counter(self.wfile), "w", zipfile.ZIP_STORED, allowZip64=True) as z:
                for f in files:
                    rel = os.path.relpath(f, base) if f.startswith(base + os.sep) else os.path.basename(f)
                    z.write(f, f"{folder}/{rel}")
                cover = get_cover(aid)
                if cover:
                    ext = {"image/png": ".png", "image/webp": ".webp"}.get(sniff(cover), ".jpg")
                    z.writestr(f"{folder}/cover{ext}", cover)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        p, _sep, qs = self.path.partition("?")
        if p == "/api/cover_upload":                 # body = the image itself
            if n > MAX_UPLOAD:
                return self.send(json.dumps({"ok": False, "error": _("imagem grande demais")}), code=413)
            data = self.rfile.read(n)
            try:
                set_cover(urllib.parse.parse_qs(qs).get("album", [""])[0], data)
                return self.send('{"ok":true}')
            except Exception as e:
                return self.send(json.dumps({"ok": False, "error": str(e)}))
        try:
            body = json.loads(self.rfile.read(n)) if n else {}
        except ValueError:
            body = {}
        p = self.path
        if p == "/api/play":
            with lock:
                if body.get("album") in albums:
                    queue, pos = albums[body["album"]]["tracks"], 0
                elif body.get("id") in tracks:
                    queue = albums[tracks[body["id"]]["album"]]["tracks"]
                    pos = queue.index(body["id"])
                elif body.get("playlist") in yt_playlists:      # YouTube playlist, optionally from a given video
                    queue = yt_playlists[body["playlist"]]["entries"]
                    pos = min(max(int(body.get("pos") or 0), 0), len(queue) - 1)
                elif isinstance(body.get("queue"), list) and body["queue"]:   # any list of known ids
                    queue = [i for i in body["queue"] if item(i)]
                    pos = min(max(int(body.get("pos") or 0), 0), max(len(queue) - 1, 0))
                    if not queue:
                        return self.send(json.dumps({"error": _("não encontrado")}), code=404)
                elif item(body.get("id")):                       # YouTube video or radio station
                    queue, pos = [body["id"]], 0
                else:
                    return self.send(json.dumps({"error": _("não encontrado")}), code=404)
                state["queue"] = list(queue)
            play_pos(pos, float(body.get("t") or 0))
        elif p == "/api/pause":
            pause()
        elif p == "/api/resume":
            resume()
        elif p == "/api/stop":
            stop()
        elif p == "/api/next":
            play_pos(state["pos"] + 1)
        elif p == "/api/prev":
            with lock:
                restored = None if state["active"] else state["restored"]
            t = restored if restored is not None else (mpv_cmd(["get_property", "time-pos"])[0] or 0)
            if t > 5:                                    # like any player: back to the start of the track
                seek(0)
            else:
                play_pos(max(0, state["pos"] - 1))
        elif p == "/api/seek":
            seek(float(body.get("t", 0)))
        elif p == "/api/radio/select":                   # before playing a station (either output)
            try:
                st = radio.select(str(body.get("uuid", "")))
            except Exception:
                st = None
            return self.send(json.dumps({"ok": bool(st), "station": st} if st else
                                        {"ok": False, "error": _("Rádio não encontrada")}))
        elif p == "/api/radio/favorite":
            try:
                return self.send(json.dumps({"ok": True, "favorites": radio.favorite(str(body.get("uuid", "")), bool(body.get("on")))}))
            except Exception:
                return self.send(json.dumps({"ok": False, "error": _("Não consegui falar com o Radio Browser")}))
        elif p == "/api/played":                         # the browser ("this device") listened to a track
            return self.send(json.dumps({"ok": record_play(str(body.get("id", "")), "local")}))
        elif p == "/api/volume":
            if "delta" in body:
                v = (mpv_cmd(["get_property", "volume"])[0] or 100) + float(body["delta"])
            else:
                v = float(body.get("v", 100))
            mpv_cmd(["set_property", "volume", max(0, min(100, v))])
        elif p == "/api/rescan":
            scan(cfg.root)
        elif p == "/api/edit":
            return self.send(json.dumps(edit_album(body)))
        elif p == "/api/cover_set":
            try:
                set_cover(body.get("album", ""), cover_from_url(body.get("url", "")))
                return self.send('{"ok":true}')
            except Exception as e:
                return self.send(json.dumps({"ok": False, "error": str(e)}))
        elif p == "/api/delete":
            return self.send(json.dumps(remove_album(body.get("album", ""), bool(body.get("permanent")))))
        elif p == "/api/yt":
            return self.send(json.dumps(yt_add(body.get("url", ""))))
        elif p == "/api/yt_remove":
            return self.send(json.dumps(yt_remove(body.get("id", ""))))
        else:
            return self.send("{}", code=404)
        self.send(json.dumps(status()))
