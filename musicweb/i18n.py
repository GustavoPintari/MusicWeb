"""Interface language for texts the server sends to the page (errors, special names).

Portuguese is the source text and the key; EN maps it to English. Terminal/log output
stays in Portuguese.
"""
from .config import cfg

EN = {
    # special names created by the library scan
    "Sem álbum": "No album",
    "Vários artistas": "Various artists",
    "Desconhecido": "Unknown",
    # lyrics
    "arquivo .lrc": ".lrc file",
    "arquivo .txt": ".txt file",
    "Faixa não encontrada": "Track not found",
    "A busca de letras na internet está desligada ([lyrics] online no config.toml)":
        "Online lyrics lookup is turned off ([lyrics] online in config.toml)",
    "O LRCLIB pediu para esperar um pouco. Tente de novo daqui a alguns segundos.":
        "LRCLIB asked us to wait a bit. Try again in a few seconds.",
    "Não consegui falar com o LRCLIB": "Couldn't reach LRCLIB",
    # Receiver in use by another device
    "outro dispositivo": "another device",
    "{player} está tocando para {who}. Para ouvir sem atrapalhar, toque em \"{player}\" e escolha este dispositivo.":
        "{player} is playing for {who}. To listen without interrupting, tap \"{player}\" to play on this device.",
    # radio
    "Não consegui falar com o Radio Browser": "Couldn't reach Radio Browser",
    "Rádio não encontrada": "Station not found",
    # covers
    "álbum não encontrado": "album not found",
    "o arquivo não parece ser uma imagem": "the file doesn't look like an image",
    "pasta do álbum fora da biblioteca": "album folder is outside the library",
    "endereço de imagem não permitido": "image address not allowed",
    "imagem grande demais": "image too large",
    # editing / removing
    "formato não suportado": "unsupported format",
    "Instale o mutagen para editar tags: pip install mutagen": "Install mutagen to edit tags: pip install mutagen",
    "Álbum não encontrado (a biblioteca mudou?)": "Album not found (did the library change?)",
    "Álbum não encontrado": "Album not found",
    "{path}: fora da biblioteca, ignorado": "{path}: outside the library, skipped",
    # playback
    "não encontrado": "not found",
    "mpv não conseguiu tocar: {err}": "mpv couldn't play: {err}",
    "erro": "error",
}

SPECIAL_NAMES = ("Sem álbum", "Vários artistas", "Desconhecido")


def _(text, **kw):
    """Translates `text` to the configured language and fills {placeholders}."""
    s = EN.get(text, text) if cfg.lang == "en" else text
    return s.format(**kw) if kw else s


def name(s):
    """Translates only the special album/artist names, leaving real names untouched."""
    return _(s) if s in SPECIAL_NAMES else s
