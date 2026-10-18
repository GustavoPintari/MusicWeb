"""mpv control (the "Receiver" output): queue, events, playback state, saved queue and play counting."""
import itertools, json, os, random, socket, subprocess, tempfile, threading, time

from . import db
from .config import cfg
from .history import min_listen, record_play
from .i18n import _, name
from .state import albums, item, lock, state


MPV_SOCK = os.path.join(tempfile.gettempdir(), "musicweb-mpv.sock")


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
        ["mpv", "--idle=yes", "--no-video", "--no-terminal", f"--ao={cfg.mpv_ao}",
         f"--input-ipc-server={MPV_SOCK}",
         # gapless: the next track is appended to mpv's playlist ahead of time (see queue_next)
         f"--gapless-audio={'yes' if cfg.mpv_gapless else 'no'}", f"--prefetch-playlist={'yes' if cfg.mpv_gapless else 'no'}",
         f"--replaygain={cfg.mpv_replaygain}"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _try in range(50):
        if os.path.exists(MPV_SOCK):
            return
        time.sleep(0.1)


def mpv_cmd(*cmds):
    """Sends commands to mpv and returns the list of replies (data or None)."""
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
                if msg.get("request_id") in ids:          # skip events
                    out[msg["request_id"]] = msg.get("data")
    except OSError:
        pass
    c.close()
    return [out.get(i) for i in ids]


def mpv_events():
    """Listens to mpv events: when a track ends, plays the next one in the queue."""
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
                        state["error"] = _("mpv não conseguiu tocar: {err}", err=ev.get("file_error", _("erro")))
                    if ev.get("reason") in ("eof", "error") and state["active"]:
                        threading.Thread(target=track_ended, daemon=True).start()
        except OSError:
            pass
        time.sleep(1)


def media_path(it):
    """What mpv opens: the music file or the radio stream."""
    return it["path"]


def play_pos(pos, start=0):
    with lock:
        state["restored"], state["appended"] = None, None
        if not 0 <= pos < len(state["queue"]):
            state["active"] = False
            end = True
        else:
            end = False
            state["pos"] = pos
            state["active"] = True
            state["gen"] += 1
            it = item(state["queue"][pos])
            if it is None:
                state["active"] = False
                return
            path = media_path(it)
    if end:                                    # queue finished: nothing to resume after a restart
        db.kv_delete("queue")
        return
    if it.get("radio"):
        start = 0                              # live stream: nothing to seek to
    state["error"] = ""
    save_queue(start)
    mpv_start()
    state["seek"] = start if start and start > 1 else None
    mpv_cmd(["playlist-clear"], ["loadfile", path, "replace"], ["set_property", "pause", False])
    queue_next()


def queue_next():
    """Gapless: appends the next queue item to mpv's playlist, so mpv preloads it and goes on without a pause."""
    if not cfg.mpv_gapless:
        return
    with lock:
        nxt = state["pos"] + 1
        if not state["active"] or nxt >= len(state["queue"]) or state["appended"] == nxt:
            return
        it = item(state["queue"][nxt])
        if it is None or it.get("radio"):
            return
        state["appended"] = nxt
        path = media_path(it)
    mpv_cmd(["loadfile", path, "append"])


def track_ended():
    """mpv finished the current track: follow mpv onto the appended one, or load the next one ourselves."""
    with lock:
        followed = state["active"] and state["appended"] == state["pos"] + 1
        if followed:
            state["pos"] += 1
            state["gen"] += 1
            state["appended"] = None
        nxt = state["pos"] + 1
    if followed:
        save_queue(0)
        queue_next()
    else:
        play_pos(nxt)


# ---------------------------------------------------------------- shuffle

def _shuffled(queue, pos):
    """The track at pos first, then all the others in random order."""
    rest = queue[:pos] + queue[pos + 1:]
    random.shuffle(rest)
    return [queue[pos]] + rest


def set_queue(queue, pos=None):
    """A new queue to play (call with the lock held); in shuffle mode it is shuffled, starting at pos.
    pos None: from the start (a random track in shuffle mode). Returns the position to play."""
    queue = list(queue)
    state["order"] = queue
    if pos is None:
        pos = random.randrange(len(queue)) if state["shuffle"] and queue else 0
    if state["shuffle"] and 0 <= pos < len(queue):
        queue, pos = _shuffled(queue, pos), 0
    state["queue"] = queue
    return pos


def set_shuffle(on):
    """Turns shuffle on (the rest of the queue gets a random order) or off (back to the original order),
    without interrupting the track that is playing."""
    with lock:
        if on == state["shuffle"]:
            return
        state["shuffle"] = on
        queue, pos = state["queue"], state["pos"]
        if not 0 <= pos < len(queue):
            return
        cur = queue[pos]
        if on:
            state["order"] = list(queue)
            state["queue"], state["pos"] = _shuffled(queue, pos), 0
        elif state["order"] and cur in state["order"]:
            state["queue"], state["pos"] = state["order"], state["order"].index(cur)
        active = state["active"]
        if active:
            state["appended"] = None
        restored = state["restored"]
    db.kv_set("shuffle", on)
    if active:                                 # gapless: the next track already sent to mpv is not the next one anymore
        mpv_cmd(["playlist-clear"])            # (it removes everything but the current file)
        queue_next()
        save_position()
    else:
        save_queue(restored or 0)


def stop():
    with lock:
        state["active"], state["restored"], state["appended"] = False, None, None
    mpv_cmd(["stop"])
    db.kv_delete("queue")


def pause():
    mpv_cmd(["set_property", "pause", True])
    save_position()


def resume():
    with lock:
        restored = None if state["active"] else state["restored"]
        pos = state["pos"]
    if restored is not None:                   # first "play" after a restart
        play_pos(pos, restored)
    else:
        mpv_cmd(["set_property", "pause", False])


def seek(t):
    with lock:
        restored = not state["active"] and state["restored"] is not None
        if restored:
            state["restored"] = t
    if restored:
        save_queue(t)
    else:
        mpv_cmd(["seek", t, "absolute"])


# ---------------------------------------------------------------- saved queue (survives restarts)

def save_queue(t=0):
    with lock:
        queue, pos, order = list(state["queue"]), state["pos"], state["order"]
    if queue and 0 <= pos < len(queue):
        db.kv_set("queue", {"queue": queue, "pos": pos, "t": round(t or 0, 1), "saved": int(time.time()),
                            "order": list(order) if order and order != queue else None})


def save_position():
    with lock:
        active = state["active"]
    if active:
        save_queue(mpv_cmd(["get_property", "time-pos"])[0] or 0)


def restore_queue():
    """Loads the queue saved before the last shutdown. It stays paused unless resume_on_start is set."""
    state["shuffle"] = bool(db.kv_get("shuffle", False))
    saved = db.kv_get("queue")
    if not saved:
        return False
    old, pos = saved.get("queue") or [], saved.get("pos", 0)
    with lock:
        queue = [t for t in old if item(t)]            # tracks may have been removed meanwhile
    if not queue:
        db.kv_delete("queue")
        return False
    cur = old[pos] if 0 <= pos < len(old) else None
    if cur in queue:
        pos, t = queue.index(cur), saved.get("t", 0)
    else:                                              # current track is gone: continue with the next one
        pos, t = min(len([x for x in old[:pos] if x in queue]), len(queue) - 1), 0
    with lock:
        order = [x for x in saved.get("order") or queue if item(x)] or queue
        state["queue"], state["pos"], state["active"], state["restored"] = queue, pos, False, t
        state["order"] = order + [x for x in queue if x not in order]
    if cfg.resume_on_start:
        play_pos(pos, t)
    return True


# ---------------------------------------------------------------- play counting (remote output)

def monitor():
    """Counts plays on mpv (by time actually listened, so seeking doesn't count) and saves the position."""
    key, listened, counted, last, last_save = None, 0.0, False, time.time(), 0.0
    while True:
        time.sleep(2)
        try:
            with lock:
                active, gen = state["active"], state["gen"]
                tid = state["queue"][state["pos"]] if active and 0 <= state["pos"] < len(state["queue"]) else None
            now = time.time()
            if tid is None:
                key, last = None, now
                continue
            idle, paused, t, dur = mpv_cmd(["get_property", "idle-active"], ["get_property", "pause"],
                                           ["get_property", "time-pos"], ["get_property", "duration"])
            if (tid, gen) != key:
                key, listened, counted = (tid, gen), 0.0, False
            elif idle is False and paused is False:
                listened += min(now - last, 5)        # cap: a stalled loop shouldn't count as listening
            last = now
            if not counted and listened >= min_listen(dur or (item(tid) or {}).get("dur", 0)):
                record_play(tid, "remote")
                counted = True
            if idle is False and paused is False and now - last_save >= 10:
                save_queue(t)
                last_save = now
        except Exception as e:
            print("[player] monitor:", e, flush=True)


def status():
    idle, paused, t, dur, vol, live = mpv_cmd(["get_property", "idle-active"], ["get_property", "pause"],
                                              ["get_property", "time-pos"], ["get_property", "duration"],
                                              ["get_property", "volume"],
                                              ["get_property", "metadata/by-key/icy-title"])   # radio: song on air
    with lock:
        cur, restored = None, False
        if 0 <= state["pos"] < len(state["queue"]):
            if state["active"]:
                cur = item(state["queue"][state["pos"]])
            elif state["restored"] is not None:            # saved queue, not started yet: show it as paused
                cur, restored = item(state["queue"][state["pos"]]), True
        if restored and cur:
            st, t, dur = "paused", state["restored"], None
        elif cur is None or idle in (True, None):
            st = "stopped"
        else:
            st = "paused" if paused else "playing"
        alb = cur and albums.get(cur["album"])
        radio = bool(cur and cur.get("radio"))
        return {"state": st, "pos": state["pos"], "total": len(state["queue"]),
                "time": t or 0, "dur": dur or (cur["dur"] if cur else 0), "error": state["error"],
                "volume": round(vol) if vol is not None else None, "lib": state["lib"], "shuffle": state["shuffle"],
                "track": cur and {**{k: cur[k] for k in ("id", "title", "artist", "album", "fmt", "q")},
                                  "album_name": name(alb["name"]) if alb else (cur["country"] if radio else ""),
                                  "album_artist": name(alb["artist"]) if alb else cur["artist"],
                                  "radio": radio, "live": (live or "") if radio and st != "stopped" else ""}}
