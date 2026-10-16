"""Small helpers used by several modules."""
import hashlib, json, os, re, urllib.request

from .config import cfg

try:
    import mutagen
except ImportError:
    mutagen = None


EXTS = {".mp3", ".flac", ".m4a", ".ogg", ".opus", ".wav", ".aac", ".wma"}
IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")
UA = "musicweb/1.0 (self-hosted personal music player)"
MIME = {".mp3": "audio/mpeg", ".flac": "audio/flac", ".m4a": "audio/mp4", ".aac": "audio/aac", ".ogg": "audio/ogg",
        ".opus": "audio/ogg", ".wav": "audio/wav", ".wma": "audio/x-ms-wma"}


# Suffixes such as "(2003 Reissue)", "[Remastered]", " - Deluxe Edition"
KW = (r"remaster|reissue|deluxe|edition|expanded|anniversary|bonus|version|mono|stereo|"
      r"special|collector|legacy|edição|remasterizad|disc|disk|cd\s*\d")
SUFFIX_PAREN = re.compile(rf"\s*[(\[][^)\]]*(?:{KW})[^)\]]*[)\]]\s*$", re.I)
SUFFIX_PAREN_YEAR = re.compile(r"\s*[(\[]\s*\d{4}\s*[)\]]\s*$")
SUFFIX_DASH = re.compile(rf"\s+[-–]\s+[^-–]*(?:{KW})[^-–]*$", re.I)


def clean_album(full):
    name, prev = full, None
    while prev != name:
        prev = name
        name = SUFFIX_PAREN.sub("", name)
        name = SUFFIX_PAREN_YEAR.sub("", name)
        name = SUFFIX_DASH.sub("", name)
    return name.strip() or full


def num(s):
    m = re.match(r"\d+", s or "")
    return int(m.group()) if m else 0


def sid(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


def sniff(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:3] == b"GIF":
        return "image/gif"
    if data[:2] == b"BM":
        return "image/bmp"
    return "image/jpeg"


def http_get(url, accept_json=False, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    return json.loads(data) if accept_json else data


def inside_root(path):
    root = os.path.realpath(cfg.root)
    return os.path.realpath(path).startswith(root + os.sep) or os.path.realpath(path) == root


def safe_name(s):
    return re.sub(r'[\\/:*?"<>|]+', "_", s).strip(" .") or "cover"


def zip_name(s):
    return safe_name(s)[:120]
