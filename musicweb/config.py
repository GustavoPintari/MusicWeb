"""Configuração: valores padrão < config.toml < variáveis de ambiente < linha de comando."""
import os
from dataclasses import dataclass

try:
    import tomllib                     # Python 3.11+
except ImportError:
    tomllib = None

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (seção, chave do config.toml) -> (atributo, tipo)
FILE_KEYS = {
    ("server", "host"): ("host", str),
    ("server", "port"): ("port", int),
    ("server", "player_name"): ("player_name", str),
    ("library", "music_dir"): ("music_dir", str),
    ("library", "rescan_every"): ("rescan_every", int),
    ("library", "trash_dir"): ("trash_dir", str),
    ("mpv", "audio_output"): ("mpv_ao", str),
    ("covers", "online"): ("covers_online", bool),
    ("lyrics", "online"): ("lyrics_online", bool),
    ("youtube", "cookies"): ("yt_cookies", str),
    ("youtube", "max_history"): ("yt_max_history", int),
    ("youtube", "format"): ("yt_format", str),
    ("cache", "dir"): ("cache_dir", str),
}

# variáveis de ambiente aceitas (as antigas continuam funcionando)
ENV_KEYS = {
    "MPV_AO": ("mpv_ao", str),
    "COVERS_ONLINE": ("covers_online", bool),
    "LYRICS_ONLINE": ("lyrics_online", bool),
    "RESCAN_EVERY": ("rescan_every", int),
    "PLAYER_NAME": ("player_name", str),
    "YT_COOKIES": ("yt_cookies", str),
    "TRASH": ("trash_dir", str),
    "MUSIC_DIR": ("music_dir", str),
}


def _conv(kind, v):
    if kind is bool and isinstance(v, str):
        return v.strip().lower() not in ("0", "false", "no", "nao", "não", "off", "")
    return kind(v)


@dataclass
class Config:
    host: str = "0.0.0.0"
    port: int = 8080
    player_name: str = "Receiver"            # nome da saída de áudio do celular, mostrado na página
    music_dir: str = "~/storage/music"
    rescan_every: int = 60                   # segundos entre buscas por músicas novas; 0 desliga
    trash_dir: str = ""                      # vazio = pasta .musicweb-lixeira ao lado da biblioteca
    mpv_ao: str = "opensles"                 # saída de áudio do mpv
    covers_online: bool = True               # busca capas no iTunes / MusicBrainz
    lyrics_online: bool = True               # busca letras no LRCLIB
    yt_cookies: str = ""                     # cookies.txt, se o YouTube pedir login
    yt_max_history: int = 50
    yt_format: str = "bestaudio[ext=m4a]/bestaudio[acodec^=mp4a]/bestaudio/best"   # m4a toca em qualquer navegador
    cache_dir: str = "~/.cache/musicweb"
    source: str = ""                         # de qual arquivo a configuração veio

    # ---- caminhos derivados
    @property
    def root(self):
        return os.path.abspath(os.path.expanduser(self.music_dir))

    @property
    def local_host(self):
        """Endereço pelo qual o mpv acessa o próprio servidor (para tocar o YouTube)."""
        return self.host if self.host not in ("", "0.0.0.0", "::") else "127.0.0.1"

    @property
    def cache(self):
        return os.path.expanduser(self.cache_dir)

    @property
    def covers_dir(self):
        return os.path.join(self.cache, "covers")

    @property
    def lyrics_dir(self):
        return os.path.join(self.cache, "lyrics")

    @property
    def yt_history_file(self):
        return os.path.join(self.cache, "youtube.json")

    @property
    def trash(self):
        if self.trash_dir:
            return os.path.expanduser(self.trash_dir)
        return os.path.join(os.path.dirname(os.path.realpath(self.root)), ".musicweb-lixeira")

    # ---- carregamento
    def load(self, path=None):
        path = path or os.environ.get("MUSICWEB_CONFIG") or self._find()
        if path:
            self._load_file(path)
        for env, (attr, kind) in ENV_KEYS.items():
            if os.environ.get(env) is not None:
                setattr(self, attr, _conv(kind, os.environ[env]))
        return self

    @staticmethod
    def _find():
        for p in (os.path.join(PROJECT_DIR, "config.toml"), os.path.expanduser("~/.config/musicweb/config.toml")):
            if os.path.isfile(p):
                return p
        return None

    def _load_file(self, path):
        if tomllib is None:
            raise SystemExit("Ler o config.toml precisa do Python 3.11 ou mais novo.")
        try:
            with open(path, "rb") as fh:
                data = tomllib.load(fh)
        except OSError as e:
            raise SystemExit(f"Não consegui abrir a configuração {path}: {e}")
        except tomllib.TOMLDecodeError as e:
            raise SystemExit(f"Erro no arquivo de configuração {path}: {e}")
        for section, values in data.items():
            if not isinstance(values, dict):
                print(f"[config] ignorando '{section}': esperava uma seção [{section}]")
                continue
            for key, v in values.items():
                if (section, key) not in FILE_KEYS:
                    print(f"[config] opção desconhecida ignorada: [{section}] {key}")
                    continue
                attr, kind = FILE_KEYS[(section, key)]
                try:
                    setattr(self, attr, _conv(kind, v))
                except (TypeError, ValueError):
                    raise SystemExit(f"[config] valor inválido para [{section}] {key}: {v!r}")
        self.source = path


cfg = Config()        # única instância; os outros módulos leem dela na hora do uso
