"""Configuration: defaults < config.toml < environment variables < command line."""
import os
from dataclasses import dataclass

try:
    import tomllib                     # Python 3.11+
except ImportError:
    tomllib = None

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (config.toml section, key) -> (attribute, type)
FILE_KEYS = {
    ("server", "host"): ("host", str),
    ("server", "port"): ("port", int),
    ("server", "player_name"): ("player_name", str),
    ("interface", "language"): ("language", str),
    ("library", "music_dir"): ("music_dir", str),
    ("library", "rescan_every"): ("rescan_every", int),
    ("library", "trash_dir"): ("trash_dir", str),
    ("mpv", "audio_output"): ("mpv_ao", str),
    ("mpv", "gapless"): ("mpv_gapless", bool),
    ("mpv", "replaygain"): ("mpv_replaygain", str),
    ("covers", "online"): ("covers_online", bool),
    ("lyrics", "online"): ("lyrics_online", bool),
    ("youtube", "cookies"): ("yt_cookies", str),
    ("youtube", "max_history"): ("yt_max_history", int),
    ("youtube", "format"): ("yt_format", str),
    ("youtube", "playlist_max"): ("yt_playlist_max", int),
    ("cache", "dir"): ("cache_dir", str),
    ("data", "dir"): ("data_dir", str),
    ("history", "enabled"): ("history_enabled", bool),
    ("history", "min_seconds"): ("history_min_seconds", int),
    ("player", "resume_on_start"): ("resume_on_start", bool),
}

# accepted environment variables (the older ones keep working)
ENV_KEYS = {
    "MPV_AO": ("mpv_ao", str),
    "COVERS_ONLINE": ("covers_online", bool),
    "LYRICS_ONLINE": ("lyrics_online", bool),
    "RESCAN_EVERY": ("rescan_every", int),
    "PLAYER_NAME": ("player_name", str),
    "YT_COOKIES": ("yt_cookies", str),
    "TRASH": ("trash_dir", str),
    "MUSIC_DIR": ("music_dir", str),
    "MUSICWEB_LANGUAGE": ("language", str),
}

# accepted spellings for [interface] language
LANGUAGES = {"pt-br": "pt-BR", "pt_br": "pt-BR", "pt": "pt-BR", "portugues": "pt-BR", "português": "pt-BR",
             "en": "en", "en-us": "en", "en_us": "en", "en-gb": "en", "english": "en", "ingles": "en", "inglês": "en"}


def _conv(kind, v):
    if kind is bool and isinstance(v, str):
        return v.strip().lower() not in ("0", "false", "no", "nao", "não", "off", "")
    return kind(v)


@dataclass
class Config:
    host: str = "0.0.0.0"
    port: int = 8080
    player_name: str = "Receiver"            # name of the phone audio output, shown on the page
    language: str = "pt-BR"                  # interface language: "pt-BR" or "en"
    music_dir: str = "~/storage/music"
    rescan_every: int = 60                   # seconds between checks for new music; 0 disables
    trash_dir: str = ""                      # empty = .musicweb-lixeira folder next to the library
    mpv_ao: str = "opensles"                 # mpv audio output
    mpv_gapless: bool = True                 # no pause between tracks (mpv output only)
    mpv_replaygain: str = "album"            # volume leveling from ReplayGain tags: "album", "track" or "no"
    covers_online: bool = True               # look up covers on iTunes / MusicBrainz
    lyrics_online: bool = True               # look up lyrics on LRCLIB
    yt_cookies: str = ""                     # cookies.txt, if YouTube asks to sign in
    yt_max_history: int = 50
    yt_playlist_max: int = 200               # videos read from a playlist link
    yt_format: str = "bestaudio[ext=m4a]/bestaudio[acodec^=mp4a]/bestaudio/best"   # m4a plays in every browser
    cache_dir: str = "~/.cache/musicweb"     # disposable: covers, lyrics, YouTube history
    data_dir: str = "~/.local/share/musicweb"   # kept: SQLite database (scan cache, play history, queue)
    history_enabled: bool = True             # record plays for history / most played
    history_min_seconds: int = 30            # listening time before a track counts as played
    resume_on_start: bool = False            # start playing the saved queue right away after a restart
    source: str = ""                         # which file the configuration came from

    # ---- derived values
    @property
    def lang(self):
        """Normalized interface language: "pt-BR" or "en"."""
        return LANGUAGES.get(self.language.strip().lower(), "pt-BR")

    @property
    def root(self):
        return os.path.abspath(os.path.expanduser(self.music_dir))

    @property
    def local_host(self):
        """Address mpv uses to reach this server (to play YouTube)."""
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
    def db_file(self):
        return os.path.join(os.path.expanduser(self.data_dir), "musicweb.db")

    @property
    def trash(self):
        if self.trash_dir:
            return os.path.expanduser(self.trash_dir)
        return os.path.join(os.path.dirname(os.path.realpath(self.root)), ".musicweb-lixeira")

    # ---- loading
    def load(self, path=None):
        path = path or os.environ.get("MUSICWEB_CONFIG") or self._find()
        if path:
            self._load_file(path)
        for env, (attr, kind) in ENV_KEYS.items():
            if os.environ.get(env) is not None:
                setattr(self, attr, _conv(kind, os.environ[env]))
        if self.mpv_replaygain not in ("album", "track", "no"):
            print(f"[config] valor inválido em [mpv] replaygain: {self.mpv_replaygain!r} (use album, track ou no); usando album")
            self.mpv_replaygain = "album"
        if self.language.strip().lower() not in LANGUAGES:
            print(f"[config] idioma desconhecido em [interface] language: {self.language!r} (use \"pt-BR\" ou \"en\"); usando pt-BR")
            self.language = "pt-BR"
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


cfg = Config()        # single instance; other modules read it at call time
