"""Estado compartilhado: biblioteca, histórico do YouTube e fila de reprodução."""
import threading


tracks = {}      # id -> faixa
albums = {}      # id -> álbum
lock = threading.Lock()
state = {"queue": [], "pos": -1, "active": False, "error": "", "lib": 0, "seek": None}


yt_items = {}    # id ("yt_" + id do vídeo) -> item, do mais antigo para o mais recente


def item(tid):
    """Faixa da biblioteca ou vídeo do YouTube."""
    return tracks.get(tid) or yt_items.get(tid)
