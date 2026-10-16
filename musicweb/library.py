"""Music library: scans the music folder and groups the tracks into albums.

Tags are read with mutagen only for new or changed files; everything else comes
from the scan cache in SQLite, so restarts and rescans of large libraries are fast.
"""
import json, os, re, time

from . import db
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
    """E.g. ("FLAC", "24/96"), ("MP3", "320k")."""
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


META_VERSION = 1      # bump when read_meta() changes, to re-read every file once


def read_meta(path):
    """Everything scan() needs from the file itself (the slow part: opens the file)."""
    audio = None
    if mutagen:
        try:
            audio = mutagen.File(path, easy=True)
        except Exception:
            pass
    fmt, q = audio_format(path, audio)
    return {"v": META_VERSION, "m": bool(mutagen),
            "title": tag(audio, "title"), "artist": tag(audio, "artist"), "albumartist": tag(audio, "albumartist"),
            "album": tag(audio, "album"), "track": tag(audio, "tracknumber"), "disc": tag(audio, "discnumber"),
            "year": tag(audio, "date", "originaldate")[:4],
            "dur": round(getattr(getattr(audio, "info", None), "length", 0) or 0), "fmt": fmt, "q": q}


def cached_meta(found):
    """path -> meta for every found file, reading only new/changed files. Returns (metas, files_read)."""
    cache = db.files_load()
    metas, changed = {}, {}
    for path in found:
        try:
            st = os.stat(path)
        except OSError:
            continue
        sig = (st.st_mtime_ns, st.st_size)
        c = cache.get(path)
        # also re-read if the cache was built without mutagen and it is installed now
        if c and c[:2] == sig and c[2].get("v") == META_VERSION and c[2].get("m") == bool(mutagen):
            metas[path] = c[2]
        else:
            metas[path] = read_meta(path)
            changed[path] = (*sig, metas[path])
    db.files_update(changed, set(cache) - set(metas))
    return metas, len(changed)


def scan(root):
    found = []
    for dp, _, files in os.walk(root):
        for f in files:
            if os.path.splitext(f)[1].lower() in EXTS:
                found.append(os.path.join(dp, f))
    metas, read = cached_meta(sorted(found))

    new_tracks, groups = {}, {}
    for path, m in metas.items():
        stem = os.path.splitext(os.path.basename(path))[0]
        adir, dir_disc = os.path.dirname(path), 0
        if DISC_DIR.match(os.path.basename(adir)):          # Album/CD1/track.mp3
            dir_disc = num(re.sub(r"\D*", "", os.path.basename(adir), count=1))
            adir = os.path.dirname(adir)
        folder = os.path.basename(adir) if adir != root else "Sem álbum"
        parent = os.path.dirname(adir)
        folder_artist = os.path.basename(parent) if parent.startswith(root) and parent != root else ""
        t = {
            "id": sid(os.path.relpath(path, root)),
            "path": os.path.realpath(path),
            "title": m["title"] or re.sub(r"^\d+[\s.\-_]*", "", stem) or stem,
            "artist": m["artist"],
            "albumartist": m["albumartist"] or m["artist"] or folder_artist,
            "n": num(m["track"]) or num(stem),
            "disc": num(m["disc"]) or dir_disc or 1,
            "year": m["year"],
            "dur": m["dur"],
            "fmt": m["fmt"],
            "q": m["q"],
        }
        album_name = m["album"] or folder
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

    # Use the cleaned-up name only when there is no other version of the same album by the same artist
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
    return len(metas), read


def library_json():
    with lock:
        out = []
        for a in sorted(albums.values(), key=lambda a: (a["artist"].lower(), a["year"], a["name"].lower())):
            out.append({**{k: a[k] for k in ("id", "name", "full", "artist", "year", "dur")},
                        "cv": cover_ver.get(a["id"], 0),
                        "tracks": [{k: tracks[i][k] for k in ("id", "title", "artist", "n", "disc", "dur", "fmt", "q")}
                                   for i in a["tracks"]]})
        yt = [yt_public(y) for y in reversed(list(yt_items.values()))]
    return json.dumps({"api": 2, "lib": state["lib"], "player": cfg.player_name, "albums": out, "yt": yt,
                       "history": cfg.history_enabled, "play_min": cfg.history_min_seconds})


# ---------------------------------------------------------------- automatic rescan


def folder_signature(root):
    """Modification time of every folder: changes when files are added or removed."""
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
                time.sleep(5)                      # give a copy in progress time to finish
                _, read = scan(cfg.root)
                last = folder_signature(cfg.root)
                print(f"[biblioteca] atualizada: {len(tracks)} faixas em {len(albums)} álbuns "
                      f"({read} arquivos lidos)", flush=True)
        except Exception as e:
            print("[biblioteca] erro ao reescanear:", e, flush=True)
