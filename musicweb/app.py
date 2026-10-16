"""Entry point: reads the configuration, loads the library and starts the server."""
import argparse, threading, time
from http.server import ThreadingHTTPServer

from . import covers, db, youtube
from .config import cfg
from .library import scan, watch_library
from .player import monitor, mpv_events, mpv_start, restore_queue
from .state import albums, state, tracks
from .util import mutagen
from .web import H


def main(argv=None):
    ap = argparse.ArgumentParser(prog="musicweb", description="Servidor web para tocar músicas no Termux usando o mpv.")
    ap.add_argument("root", nargs="?", help="pasta de músicas (padrão: [library] music_dir do config.toml)")
    ap.add_argument("--port", type=int, help="porta (padrão: [server] port)")
    ap.add_argument("--host", help="endereço (padrão: [server] host)")
    ap.add_argument("--config", help="arquivo de configuração (padrão: ./config.toml ou ~/.config/musicweb/config.toml)")
    a = ap.parse_args(argv)

    cfg.load(a.config)
    if a.root:
        cfg.music_dir = a.root
    if a.port:
        cfg.port = a.port
    if a.host:
        cfg.host = a.host

    db.open_db(cfg.db_file)
    covers.load_versions()
    youtube.load_history()
    t0 = time.time()
    _, read = scan(cfg.root)
    print(f"{len(tracks)} faixas em {len(albums)} álbuns ({cfg.root}) em {time.time() - t0:.1f}s, "
          f"{read} arquivos lidos; mutagen={'sim' if mutagen else 'não'}; "
          f"yt-dlp={'sim' if youtube.ytdlp_cmd() else 'não'}; config={cfg.source or 'padrão'}")
    mpv_start()
    threading.Thread(target=mpv_events, daemon=True).start()
    threading.Thread(target=monitor, daemon=True).start()
    if restore_queue():
        print(f"Fila restaurada: {len(state['queue'])} faixas"
              f"{' (tocando)' if cfg.resume_on_start else ' (pausada; aperte play para continuar)'}")
    if cfg.rescan_every > 0:
        threading.Thread(target=watch_library, daemon=True).start()
    print(f"Abra http://<ip-do-celular>:{cfg.port}")
    ThreadingHTTPServer((cfg.host, cfg.port), H).serve_forever()
