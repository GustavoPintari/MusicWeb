"""`./musicweb.sh status`: configuration, address and what the running server is playing."""
import json, socket, urllib.request

from .config import cfg


def local_ip():
    """IP of this phone or server on the network (no packet is sent: a UDP "connect" only picks the route)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "<ip-deste-aparelho>"


def main():
    try:
        cfg.load()
    except SystemExit as e:                       # config errors are reported, not raised
        print(f"configuração: ERRO — {e}")
        return
    print(f"configuração: {cfg.source or 'padrão (sem config.toml)'}")
    print(f"músicas: {cfg.root}")
    print(f"endereço: http://{local_ip()}:{cfg.port}")
    try:
        with urllib.request.urlopen(f"http://{cfg.local_host}:{cfg.port}/api/status", timeout=3) as r:
            st = json.load(r)
    except Exception:
        print("servidor: não respondeu")
        return
    t = st.get("track")
    if not t:
        print("tocando: nada")
        return
    icon = {"playing": "▶", "paused": "⏸"}.get(st["state"], "■")
    print(f"tocando: {icon} {t['title']} — {t['artist'] or t['album_artist']} ({st['pos'] + 1}/{st['total']})")


if __name__ == "__main__":
    main()
