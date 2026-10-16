#!/usr/bin/env python3
"""Servidor web para tocar músicas no Termux usando o mpv.

Uso: python server.py [PASTA_DE_MUSICAS] [--port 8080]

Só usa a biblioteca padrão. Com o `mutagen` instalado (pip install mutagen),
lê as tags (álbum, artista, faixa, ano, duração) e as capas embutidas.

Variáveis de ambiente:
  MPV_AO=opensles      saída de áudio do mpv
  COVERS_ONLINE=0      não busca capas na internet (MusicBrainz / iTunes)
  RESCAN_EVERY=60      a cada quantos segundos procura músicas novas (0 desliga)
  PLAYER_NAME=Receiver nome da saída de áudio do celular, mostrado na página
"""
import argparse, base64, hashlib, itertools, json, os, re, shutil, socket, subprocess, tempfile, threading, time, zipfile
import urllib.error, urllib.parse, urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

try:
    import mutagen
except ImportError:
    mutagen = None

EXTS = {".mp3", ".flac", ".m4a", ".ogg", ".opus", ".wav", ".aac", ".wma"}
IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")
MPV_AO = os.environ.get("MPV_AO", "opensles")
MPV_SOCK = os.path.join(tempfile.gettempdir(), "musicweb-mpv.sock")
COVERS_ONLINE = os.environ.get("COVERS_ONLINE", "1") != "0"
CACHE = os.path.expanduser("~/.cache/musicweb/covers")
HERE = os.path.dirname(os.path.abspath(__file__))
UA = "musicweb/1.0 (self-hosted personal music player)"
PLAYER_NAME = os.environ.get("PLAYER_NAME", "Receiver")
MIME = {".mp3": "audio/mpeg", ".flac": "audio/flac", ".m4a": "audio/mp4", ".aac": "audio/aac", ".ogg": "audio/ogg",
        ".opus": "audio/ogg", ".wav": "audio/wav", ".wma": "audio/x-ms-wma"}

tracks = {}      # id -> faixa
albums = {}      # id -> álbum
lock = threading.Lock()
state = {"queue": [], "pos": -1, "active": False, "error": "", "lib": 0, "seek": None}


# ---------------------------------------------------------------- biblioteca

# Sufixos como "(2003 Reissue)", "[Remastered]", " - Deluxe Edition"
KW = (r"remaster|reissue|deluxe|edition|expanded|anniversary|bonus|version|mono|stereo|"
      r"special|collector|legacy|edição|remasterizad|disc|disk|cd\s*\d")
SUFFIX_PAREN = re.compile(rf"\s*[(\[][^)\]]*(?:{KW})[^)\]]*[)\]]\s*$", re.I)
SUFFIX_PAREN_YEAR = re.compile(r"\s*[(\[]\s*\d{4}\s*[)\]]\s*$")
SUFFIX_DASH = re.compile(rf"\s+[-–]\s+[^-–]*(?:{KW})[^-–]*$", re.I)
DISC_DIR = re.compile(r"^(cd|disc|disk|disco)\s*\d+", re.I)


def clean_album(full):
    name, prev = full, None
    while prev != name:
        prev = name
        name = SUFFIX_PAREN.sub("", name)
        name = SUFFIX_PAREN_YEAR.sub("", name)
        name = SUFFIX_DASH.sub("", name)
    return name.strip() or full


def tag(audio, *keys):
    for k in keys:
        try:
            v = audio.get(k) if audio else None
        except Exception:
            v = None
        if v:
            return str(v[0]).strip()
    return ""


def num(s):
    m = re.match(r"\d+", s or "")
    return int(m.group()) if m else 0


def audio_format(path, audio):
    """Ex.: ("FLAC", "24/96"), ("MP3", "320k")."""
    ext = os.path.splitext(path)[1].lower()
    fmt = ext[1:].upper()
    info = getattr(audio, "info", None)
    if info is None:
        return fmt, ""
    codec = str(getattr(info, "codec", "") or "").lower()
    if ext == ".m4a":
        fmt = "ALAC" if "alac" in codec else "AAC"
    elif ext == ".ogg" and type(info).__name__.lower().startswith("opus"):
        fmt = "OPUS"
    bits = getattr(info, "bits_per_sample", 0) or 0
    rate = getattr(info, "sample_rate", 0) or 0
    if fmt in ("FLAC", "ALAC", "WAV") and bits and rate:
        khz = rate / 1000
        return fmt, f"{bits}/{khz:g}"
    br = getattr(info, "bitrate", 0) or 0
    return fmt, (f"{round(br / 1000)}k" if br else "")


def sid(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


def scan(root):
    found = []
    for dp, _, files in os.walk(root):
        for f in files:
            if os.path.splitext(f)[1].lower() in EXTS:
                found.append(os.path.join(dp, f))

    new_tracks, groups = {}, {}
    for path in sorted(found):
        audio = None
        if mutagen:
            try:
                audio = mutagen.File(path, easy=True)
            except Exception:
                pass
        stem = os.path.splitext(os.path.basename(path))[0]
        adir, dir_disc = os.path.dirname(path), 0
        if DISC_DIR.match(os.path.basename(adir)):          # Album/CD1/faixa.mp3
            dir_disc = num(re.sub(r"\D*", "", os.path.basename(adir), count=1))
            adir = os.path.dirname(adir)
        folder = os.path.basename(adir) if adir != root else "Sem álbum"
        parent = os.path.dirname(adir)
        folder_artist = os.path.basename(parent) if parent.startswith(root) and parent != root else ""
        album_tag = tag(audio, "album")
        t = {
            "id": sid(os.path.relpath(path, root)),
            "path": os.path.realpath(path),
            "title": tag(audio, "title") or re.sub(r"^\d+[\s.\-_]*", "", stem) or stem,
            "artist": tag(audio, "artist"),
            "albumartist": tag(audio, "albumartist") or tag(audio, "artist") or folder_artist,
            "n": num(tag(audio, "tracknumber")) or num(stem),
            "disc": num(tag(audio, "discnumber")) or dir_disc or 1,
            "year": tag(audio, "date", "originaldate")[:4],
            "dur": round(getattr(getattr(audio, "info", None), "length", 0) or 0),
        }
        t["fmt"], t["q"] = audio_format(path, audio)
        album_name = album_tag or folder
        key = (album_name.lower(), adir)
        g = groups.setdefault(key, {"full": album_name, "dir": adir, "tracks": []})
        g["tracks"].append(t)
        new_tracks[t["id"]] = t

    new_albums = {}
    for (_, adir), g in groups.items():
        ts = sorted(g["tracks"], key=lambda x: (x["disc"], x["n"], x["title"].lower()))
        artists = {x["albumartist"] for x in ts if x["albumartist"]}
        artist = artists.pop() if len(artists) == 1 else ("Vários artistas" if artists else "Desconhecido")
        aid = sid(g["full"] + "\0" + adir)
        years = sorted(x["year"] for x in ts if x["year"])
        new_albums[aid] = {"id": aid, "full": g["full"], "name": clean_album(g["full"]),
                           "artist": artist, "year": years[0] if years else "", "dir": adir,
                           "tracks": [x["id"] for x in ts], "dur": sum(x["dur"] for x in ts)}
        for x in ts:
            x["album"] = aid

    per_dir = {}
    for a in new_albums.values():
        per_dir[a["dir"]] = per_dir.get(a["dir"], 0) + 1
    for a in new_albums.values():
        a["shared"] = per_dir[a["dir"]] > 1

    # Nome limpo só quando não há outra versão do mesmo álbum do mesmo artista
    seen = {}
    for a in new_albums.values():
        seen.setdefault((a["artist"].lower(), a["name"].lower()), []).append(a)
    for dups in seen.values():
        if len(dups) > 1:
            for a in dups:
                a["name"] = a["full"]

    with lock:
        tracks.clear(); tracks.update(new_tracks)
        albums.clear(); albums.update(new_albums)
        state["lib"] += 1


def library_json():
    with lock:
        out = []
        for a in sorted(albums.values(), key=lambda a: (a["artist"].lower(), a["year"], a["name"].lower())):
            out.append({**{k: a[k] for k in ("id", "name", "full", "artist", "year", "dur")},
                        "cv": cover_ver.get(a["id"], 0),
                        "tracks": [{k: tracks[i][k] for k in ("id", "title", "artist", "n", "disc", "dur", "fmt", "q")}
                                   for i in a["tracks"]]})
    return json.dumps({"api": 2, "lib": state["lib"], "player": PLAYER_NAME, "albums": out})


# ---------------------------------------------------------------- capas

mb_lock = threading.Lock()         # MusicBrainz: no máximo 1 requisição por segundo
mb_last = [0.0]
it_lock = threading.Lock()         # iTunes: ~20 buscas por minuto
it_bucket = {"tokens": 20.0, "t": time.time()}


VERSIONS = os.path.join(CACHE, "versions.json")
try:
    with open(VERSIONS) as fh:
        cover_ver = json.load(fh)
except (OSError, ValueError):
    cover_ver = {}


def bump_cover(aid):
    cover_ver[aid] = cover_ver.get(aid, 0) + 1
    for ext in (".img", ".none"):
        try:
            os.remove(os.path.join(CACHE, aid + ext))
        except OSError:
            pass
    os.makedirs(CACHE, exist_ok=True)
    with open(VERSIONS, "w") as fh:
        json.dump(cover_ver, fh)


def sniff(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:3] == b"GIF":
        return "image/gif"
    if data[:2] == b"BM":
        return "image/bmp"
    return "image/jpeg"


ART_DIRS = {"artwork", "art", "covers", "cover", "scans", "scan", "images", "imagens", "capa", "capas"}


def cover_score(fname, album, shared):
    n = os.path.splitext(fname)[0].lower()
    alb = album.lower()
    if n == "cover" and not shared or n == alb:
        return 1000                # capa definida explicitamente (inclusive pela página)
    score = 0
    if alb and alb in n:
        score += 100
    elif shared:                  # pasta com vários álbuns: só aceita imagem com o nome do álbum
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
    """Procura imagem de capa na pasta do álbum (e em subpastas como Artwork/Scans)."""
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
    cands.sort(reverse=True)               # maior pontuação, depois maior arquivo
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


def http_get(url, accept_json=False, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    return json.loads(data) if accept_json else data


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
    """Devolve (imagem, certeza_de_que_não_existe)."""
    name = clean_album(a["full"])
    artist = "" if a["artist"] in ("Vários artistas", "Desconhecido") else a["artist"]
    net_ok = True
    # 1) iTunes: rápido, boa cobertura
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
    # 2) MusicBrainz + Cover Art Archive (mais lento)
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
    a = albums.get(aid)
    if not a:
        return None
    data = cover_from_folder(a)
    if data:
        return data
    os.makedirs(CACHE, exist_ok=True)
    img, miss = os.path.join(CACHE, aid + ".img"), os.path.join(CACHE, aid + ".none")
    if os.path.exists(img):
        with open(img, "rb") as fh:
            return fh.read()
    if os.path.exists(miss):
        return None
    data, sure = cover_embedded(a), True
    if not data and COVERS_ONLINE:
        data, sure = cover_online(a)
    if data:
        with open(img, "wb") as fh:
            fh.write(data)
    elif sure:                     # só lembra "sem capa" se a busca não falhou por rede
        open(miss, "w").close()
    return data


# ---------------------------------------------------------------- mpv

mpv = {"proc": None}
req_id = itertools.count(1)


def mpv_start():
    p = mpv["proc"]
    if p is not None and p.poll() is None:
        return
    try:
        os.remove(MPV_SOCK)
    except OSError:
        pass
    mpv["proc"] = subprocess.Popen(
        ["mpv", "--idle=yes", "--no-video", "--no-terminal", f"--ao={MPV_AO}",
         f"--input-ipc-server={MPV_SOCK}"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        if os.path.exists(MPV_SOCK):
            return
        time.sleep(0.1)


def mpv_cmd(*cmds):
    """Envia comandos ao mpv e devolve a lista de respostas (data ou None)."""
    try:
        c = socket.socket(socket.AF_UNIX)
        c.settimeout(2)
        c.connect(MPV_SOCK)
    except OSError:
        return [None] * len(cmds)
    ids = []
    for cmd in cmds:
        ids.append(next(req_id))
        c.sendall((json.dumps({"command": cmd, "request_id": ids[-1]}) + "\n").encode())
    out, buf = {}, b""
    try:
        while len(out) < len(ids):
            chunk = c.recv(65536)
            if not chunk:
                break
            buf += chunk
            *lines, buf = buf.split(b"\n")
            for line in lines:
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if msg.get("request_id") in ids:          # ignora eventos
                    out[msg["request_id"]] = msg.get("data")
    except OSError:
        pass
    c.close()
    return [out.get(i) for i in ids]


def mpv_events():
    """Escuta eventos do mpv: quando a faixa termina, toca a próxima da fila."""
    while True:
        try:
            c = socket.socket(socket.AF_UNIX)
            c.connect(MPV_SOCK)
            buf = b""
            while True:
                chunk = c.recv(65536)
                if not chunk:
                    break
                buf += chunk
                *lines, buf = buf.split(b"\n")
                for line in lines:
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    if ev.get("event") == "file-loaded" and state["seek"]:
                        t, state["seek"] = state["seek"], None
                        threading.Thread(target=mpv_cmd, args=(["seek", t, "absolute"],), daemon=True).start()
                        continue
                    if ev.get("event") != "end-file":
                        continue
                    if ev.get("reason") == "error":
                        state["error"] = "mpv não conseguiu tocar: " + str(ev.get("file_error", "erro"))
                    if ev.get("reason") in ("eof", "error") and state["active"]:
                        threading.Thread(target=play_pos, args=(state["pos"] + 1,), daemon=True).start()
        except OSError:
            pass
        time.sleep(1)


def play_pos(pos, start=0):
    with lock:
        if not 0 <= pos < len(state["queue"]):
            state["active"] = False
            return
        state["pos"] = pos
        state["active"] = True
        path = tracks[state["queue"][pos]]["path"]
    mpv_start()
    state["error"] = ""
    state["seek"] = start if start and start > 1 else None
    mpv_cmd(["loadfile", path, "replace"], ["set_property", "pause", False])


def status():
    idle, paused, t, dur, vol = mpv_cmd(["get_property", "idle-active"], ["get_property", "pause"],
                                        ["get_property", "time-pos"], ["get_property", "duration"],
                                        ["get_property", "volume"])
    with lock:
        cur = None
        if state["active"] and 0 <= state["pos"] < len(state["queue"]):
            cur = tracks.get(state["queue"][state["pos"]])
        if cur is None or idle in (True, None):
            st = "stopped"
        else:
            st = "paused" if paused else "playing"
        return {"state": st, "pos": state["pos"], "total": len(state["queue"]),
                "time": t or 0, "dur": dur or (cur["dur"] if cur else 0), "error": state["error"],
                "volume": round(vol) if vol is not None else None, "lib": state["lib"],
                "track": cur and {**{k: cur[k] for k in ("id", "title", "artist", "album", "fmt", "q")},
                                  "album_name": albums[cur["album"]]["name"],
                                  "album_artist": albums[cur["album"]]["artist"]}}


# ---------------------------------------------------------------- atualização automática

RESCAN_EVERY = int(os.environ.get("RESCAN_EVERY", "60"))      # segundos; 0 desliga


def folder_signature(root):
    """Data de modificação de cada pasta: muda quando arquivos são adicionados/removidos."""
    sig = []
    for dp, dns, _ in os.walk(root):
        try:
            sig.append((dp, os.stat(dp).st_mtime_ns))
        except OSError:
            pass
    return hash(tuple(sorted(sig)))


def watch_library():
    last = folder_signature(ROOT)
    while True:
        time.sleep(RESCAN_EVERY)
        try:
            sig = folder_signature(ROOT)
            if sig != last:
                time.sleep(5)                      # dá tempo de terminar de copiar
                scan(ROOT)
                last = folder_signature(ROOT)
                print(f"[biblioteca] atualizada: {len(tracks)} faixas em {len(albums)} álbuns", flush=True)
        except Exception as e:
            print("[biblioteca] erro ao reescanear:", e, flush=True)


# ---------------------------------------------------------------- edição de tags

EDITABLE_ALBUM = ("album", "albumartist", "date")
EDITABLE_TRACK = ("title", "artist", "tracknumber")


def write_tags(path, fields):
    f = mutagen.File(path, easy=True)
    if f is None:
        raise ValueError("formato não suportado")
    if f.tags is None:
        f.add_tags()
    for k, v in fields.items():
        v = str(v).strip()
        if v:
            f[k] = [v]
        elif k in f:
            del f[k]
    f.save()


def edit_album(body):
    if not mutagen:
        return {"ok": False, "errors": ["Instale o mutagen para editar tags: pip install mutagen"]}
    with lock:
        a = albums.get(body.get("album"))
        if not a:
            return {"ok": False, "errors": ["Álbum não encontrado (a biblioteca mudou?)"]}
        tids = list(a["tracks"])
        paths = {t: tracks[t]["path"] for t in tids}
    album_fields = {k: v for k, v in (body.get("fields") or {}).items() if k in EDITABLE_ALBUM}
    per_track = body.get("tracks") or {}
    errors = []
    for t in tids:
        fields = dict(album_fields)
        fields.update({k: v for k, v in (per_track.get(t) or {}).items() if k in EDITABLE_TRACK})
        if not fields:
            continue
        try:
            write_tags(paths[t], fields)
        except Exception as e:
            errors.append(f"{os.path.basename(paths[t])}: {e}")
    scan(ROOT)
    with lock:
        new_id = tracks[tids[0]]["album"] if tids[0] in tracks else None
    return {"ok": not errors, "errors": errors, "album": new_id}


# ---------------------------------------------------------------- trocar capa

COVER_HOSTS = ("mzstatic.com", "dzcdn.net")       # de onde a página pode mandar baixar capas
MAX_UPLOAD = 20 * 1024 * 1024


def inside_root(path):
    root = os.path.realpath(ROOT)
    return os.path.realpath(path).startswith(root + os.sep) or os.path.realpath(path) == root


def safe_name(s):
    return re.sub(r'[\\/:*?"<>|]+', "_", s).strip(" .") or "cover"


def set_cover(aid, data):
    with lock:
        a = albums.get(aid)
    if not a:
        raise ValueError("álbum não encontrado")
    kind = sniff(data)
    if not (data[:2] == b"\xff\xd8" or kind != "image/jpeg"):
        raise ValueError("o arquivo não parece ser uma imagem")
    if not inside_root(a["dir"]):
        raise ValueError("pasta do álbum fora da biblioteca")
    ext = {"image/png": ".png", "image/webp": ".webp", "image/gif": ".gif", "image/bmp": ".bmp"}.get(kind, ".jpg")
    stem = safe_name(a["full"]) if a["shared"] else "cover"
    ts = time.strftime("%Y%m%d-%H%M%S")
    for f in os.listdir(a["dir"]):                       # guarda a capa anterior como .bak
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
        raise ValueError("endereço de imagem não permitido")
    return http_get(url, timeout=20)


# ---------------------------------------------------------------- remover álbum

def trash_dir():
    t = os.environ.get("TRASH")
    if t:
        return t
    return os.path.join(os.path.dirname(os.path.realpath(ROOT)), ".musicweb-lixeira")


def remove_album(aid, permanent=False):
    with lock:
        a = albums.get(aid)
        if not a:
            return {"ok": False, "errors": ["Álbum não encontrado"]}
        tids = list(a["tracks"])
        paths = [tracks[t]["path"] for t in tids]
        playing = state["active"] and state["queue"] and state["queue"][state["pos"]] in tids
    if playing:
        state["active"] = False
        mpv_cmd(["stop"])
    root = os.path.realpath(ROOT)
    adir = os.path.realpath(a["dir"])
    # a pasta inteira só vai junto se for exclusiva deste álbum
    own_dir = (not a["shared"] and adir != root and inside_root(adir)
               and all(os.path.realpath(p).startswith(adir + os.sep) for p in paths))
    other_audio = False
    if own_dir:
        mine = {os.path.realpath(p) for p in paths}
        for dp, _, fs in os.walk(adir):
            if any(os.path.splitext(f)[1].lower() in EXTS and os.path.realpath(os.path.join(dp, f)) not in mine for f in fs):
                other_audio = True
                break
    targets = [adir] if own_dir and not other_audio else list(paths)
    if targets != [adir]:                     # leva junto a capa com o nome do álbum
        names = {safe_name(a["full"]).lower(), a["name"].lower(), a["full"].lower()}
        try:
            for f in os.listdir(a["dir"]):
                if os.path.splitext(f)[0].lower() in names and f.lower().endswith(IMG_EXTS):
                    targets.append(os.path.join(adir, f))
        except OSError:
            pass
    errors, dest = [], None
    if not permanent:
        dest = os.path.join(trash_dir(), time.strftime("%Y%m%d-%H%M%S") + " " + safe_name(a["full"]))
        os.makedirs(dest, exist_ok=True)
    for p in targets:
        if not inside_root(p):
            errors.append(f"{p}: fora da biblioteca, ignorado")
            continue
        try:
            if permanent:
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
            else:
                shutil.move(p, os.path.join(dest, os.path.relpath(p, root).replace(os.sep, " - ")
                                            if p != adir else os.path.basename(p)))
        except Exception as e:
            errors.append(f"{os.path.basename(p)}: {e}")
    # apaga pastas que ficaram vazias (ex.: pasta do artista)
    d = os.path.dirname(adir if targets == [adir] else paths[0])
    while d != root and inside_root(d):
        try:
            os.rmdir(d)
        except OSError:
            break
        d = os.path.dirname(d)
    cover_ver.pop(aid, None)
    scan(ROOT)
    return {"ok": not errors, "errors": errors, "trash": dest}


# ---------------------------------------------------------------- streaming e download

def zip_name(s):
    return safe_name(s)[:120]


class _Counter:
    """Conta bytes escritos (zipfile precisa de tell() em fluxo não-pesquisável)."""
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


# ---------------------------------------------------------------- HTTP

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
        p, _, qs = self.path.partition("?")
        q = urllib.parse.parse_qs(qs)
        if p == "/":
            with open(os.path.join(HERE, "index.html"), "rb") as fh:
                self.send(fh.read(), "text/html; charset=utf-8")
        elif p == "/api/library":
            self.send(library_json())
        elif p == "/api/status":
            self.send(json.dumps(status()))
        elif p == "/api/cover_search":
            self.send(json.dumps(cover_candidates(q.get("q", [""])[0])))
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
            else:                                   # "bytes=-500": últimos 500 bytes
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
            pass                                    # o navegador cancelou (normal ao pular trechos)

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
            # ZIP_STORED: áudio já é comprimido, e assim o celular não gasta CPU
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
        p, _, qs = self.path.partition("?")
        if p == "/api/cover_upload":                 # corpo = a imagem em si
            if n > MAX_UPLOAD:
                return self.send('{"ok":false,"error":"imagem grande demais"}', code=413)
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
                else:
                    return self.send('{"error":"não encontrado"}', code=404)
                state["queue"] = list(queue)
            play_pos(pos, float(body.get("t") or 0))
        elif p == "/api/pause":
            mpv_cmd(["set_property", "pause", True])
        elif p == "/api/resume":
            mpv_cmd(["set_property", "pause", False])
        elif p == "/api/stop":
            state["active"] = False
            mpv_cmd(["stop"])
        elif p == "/api/next":
            play_pos(state["pos"] + 1)
        elif p == "/api/prev":
            t = mpv_cmd(["get_property", "time-pos"])[0] or 0
            if t > 5:                                    # como num player comum: volta ao início
                mpv_cmd(["seek", 0, "absolute"])
            else:
                play_pos(max(0, state["pos"] - 1))
        elif p == "/api/seek":
            mpv_cmd(["seek", float(body.get("t", 0)), "absolute"])
        elif p == "/api/volume":
            if "delta" in body:
                v = (mpv_cmd(["get_property", "volume"])[0] or 100) + float(body["delta"])
            else:
                v = float(body.get("v", 100))
            mpv_cmd(["set_property", "volume", max(0, min(100, v))])
        elif p == "/api/rescan":
            scan(ROOT)
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
        else:
            return self.send("{}", code=404)
        self.send(json.dumps(status()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=os.path.expanduser("~/storage/music"))
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="0.0.0.0")
    a = ap.parse_args()
    ROOT = os.path.abspath(a.root)
    scan(ROOT)
    print(f"{len(tracks)} faixas em {len(albums)} álbuns ({ROOT}); mutagen={'sim' if mutagen else 'não'}")
    mpv_start()
    threading.Thread(target=mpv_events, daemon=True).start()
    if RESCAN_EVERY > 0:
        threading.Thread(target=watch_library, daemon=True).start()
    print(f"Abra http://<ip-do-celular>:{a.port}")
    ThreadingHTTPServer((a.host, a.port), H).serve_forever()
