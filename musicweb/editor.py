"""Alterações na biblioteca: editar tags e remover álbuns."""
import os, shutil, time

from .config import cfg
from .covers import cover_ver
from .library import scan
from .player import mpv_cmd
from .state import albums, lock, state, tracks
from .util import EXTS, IMG_EXTS, inside_root, mutagen, safe_name


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
    scan(cfg.root)
    with lock:
        new_id = tracks[tids[0]]["album"] if tids[0] in tracks else None
    return {"ok": not errors, "errors": errors, "album": new_id}


# ---------------------------------------------------------------- remover álbum


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
    root = os.path.realpath(cfg.root)
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
        dest = os.path.join(cfg.trash, time.strftime("%Y%m%d-%H%M%S") + " " + safe_name(a["full"]))
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
    scan(cfg.root)
    return {"ok": not errors, "errors": errors, "trash": dest}
