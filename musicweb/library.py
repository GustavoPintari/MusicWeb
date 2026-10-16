"""Leitura da biblioteca: varre a pasta de músicas e agrupa as faixas em álbuns."""
import json, os, re, time

from .config import cfg
from .covers import cover_ver
from .state import albums, lock, state, tracks, yt_items
from .util import EXTS, clean_album, mutagen, num, sid
from .youtube import yt_public


DISC_DIR = re.compile(r"^(cd|disc|disk|disco)\s*\d+", re.I)


def tag(audio, *keys):
    for k in keys:
        try:
            v = audio.get(k) if audio else None
        except Exception:
            v = None
        if v:
            return str(v[0]).strip()
    return ""


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
        yt = [yt_public(y) for y in reversed(list(yt_items.values()))]
    return json.dumps({"api": 2, "lib": state["lib"], "player": cfg.player_name, "albums": out, "yt": yt})


# ---------------------------------------------------------------- atualização automática


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
    last = folder_signature(cfg.root)
    while True:
        time.sleep(cfg.rescan_every)
        try:
            sig = folder_signature(cfg.root)
            if sig != last:
                time.sleep(5)                      # dá tempo de terminar de copiar
                scan(cfg.root)
                last = folder_signature(cfg.root)
                print(f"[biblioteca] atualizada: {len(tracks)} faixas em {len(albums)} álbuns", flush=True)
        except Exception as e:
            print("[biblioteca] erro ao reescanear:", e, flush=True)
