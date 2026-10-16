"""Controle do mpv (saída "Receiver"): fila, eventos e estado da reprodução."""
import itertools, json, os, socket, subprocess, tempfile, threading, time

from .config import cfg
from .state import albums, item, lock, state
from .youtube import yt_direct


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
        it = item(state["queue"][pos])
        if it is None:
            state["active"] = False
            return
        # vídeos do YouTube passam pelo próprio servidor (/api/stream), que renova o link quando expira
        path = it.get("path") or f"http://{cfg.local_host}:{cfg.port}/api/stream/{it['id']}"
    state["error"] = ""
    if not it.get("path"):
        try:
            yt_direct(it["id"])                    # já deixa o link pronto e mostra o erro, se houver
        except Exception as e:
            state["error"], state["active"] = f"YouTube: {e}", False
            return
    mpv_start()
    state["seek"] = start if start and start > 1 else None
    mpv_cmd(["loadfile", path, "replace"], ["set_property", "pause", False])


def status():
    idle, paused, t, dur, vol = mpv_cmd(["get_property", "idle-active"], ["get_property", "pause"],
                                        ["get_property", "time-pos"], ["get_property", "duration"],
                                        ["get_property", "volume"])
    with lock:
        cur = None
        if state["active"] and 0 <= state["pos"] < len(state["queue"]):
            cur = item(state["queue"][state["pos"]])
        if cur is None or idle in (True, None):
            st = "stopped"
        else:
            st = "paused" if paused else "playing"
        alb = cur and albums.get(cur["album"])
        return {"state": st, "pos": state["pos"], "total": len(state["queue"]),
                "time": t or 0, "dur": dur or (cur["dur"] if cur else 0), "error": state["error"],
                "volume": round(vol) if vol is not None else None, "lib": state["lib"],
                "track": cur and {**{k: cur[k] for k in ("id", "title", "artist", "album", "fmt", "q")},
                                  "album_name": alb["name"] if alb else "YouTube",
                                  "album_artist": alb["artist"] if alb else cur["artist"]}}
