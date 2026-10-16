"""YouTube PO tokens with bgutil-ytdlp-pot-provider, so yt-dlp can pass the "not a bot" check without cookies.

The provider has two parts (installed by pot-setup.sh):
- a yt-dlp plugin (pip install bgutil-ytdlp-pot-provider), which asks for a token when YouTube wants one;
- a small Node.js server that makes the token (bgutil-ytdlp-pot-provider/server).

If [youtube] pot_server points to the server's folder, MusicWeb starts it together with itself, restarts it
if it stops and stops it on exit. If something already answers on [youtube] pot_url (e.g. the Docker image),
that one is used and nothing is started.
"""
import atexit, importlib.util, os, shutil, socket, subprocess, threading, time, urllib.parse

from .config import cfg

DEFAULT_URL = "http://127.0.0.1:4416"

_proc = [None]
_stopping = threading.Event()


def plugin_installed():
    """Whether the yt-dlp plugin is installed for this Python (the one MusicWeb runs yt-dlp with)."""
    try:
        return importlib.util.find_spec("yt_dlp_plugins.extractor.getpot_bgutil_http") is not None
    except (ImportError, ValueError):
        return False


def _addr():
    u = urllib.parse.urlsplit(cfg.yt_pot_url or DEFAULT_URL)
    return u.hostname or "127.0.0.1", u.port or 4416


def answering():
    """Whether something is listening on the provider's address."""
    try:
        with socket.create_connection(_addr(), timeout=1):
            return True
    except OSError:
        return False


_js = []                # cached --js-runtimes option


def _js_runtime(cmd):
    """yt-dlp needs a JavaScript runtime for YouTube and only looks for Deno by default; use Node.js if that's
    what is installed (it is, when the PO token server is). The option exists since yt-dlp 2025.11."""
    if not _js:
        opt = []
        if not shutil.which("deno") and shutil.which("node"):
            try:
                ver = subprocess.run(cmd + ["--version"], capture_output=True, text=True, timeout=20).stdout.strip()
                if ver >= "2025.11":
                    opt = ["--js-runtimes", "node"]
            except (OSError, subprocess.TimeoutExpired):
                pass
        _js.append(opt)
    return _js[0]


def ytdlp_args(cmd):
    """Extra yt-dlp options: the JavaScript runtime and the provider's address, when it isn't the default."""
    url = (cfg.yt_pot_url or DEFAULT_URL).rstrip("/")
    return _js_runtime(cmd) + ([] if url == DEFAULT_URL else ["--extractor-args", f"youtubepot-bgutilhttp:base_url={url}"])


def _server_dir():
    d = os.path.expanduser(cfg.yt_pot_server) if cfg.yt_pot_server else ""
    return d if d and os.path.isfile(os.path.join(d, "build", "main.js")) else ""


def _spawn(d, node):
    host, port = _addr()
    os.makedirs(cfg.cache, exist_ok=True)
    log = open(os.path.join(cfg.cache, "pot-server.log"), "ab")
    # host is always a loopback address here: the server has no authentication, so it must not be exposed
    return subprocess.Popen([node, os.path.join("build", "main.js"), "--port", str(port), "--host", host],
                            cwd=d, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)


def _keep_alive(d, node):
    fails = 0
    while not _stopping.is_set():
        t0 = time.time()
        _proc[0] = p = _spawn(d, node)
        p.wait()
        if _stopping.is_set():
            return
        fails = fails + 1 if time.time() - t0 < 60 else 1
        if fails >= 5:
            print(f"[pot] o servidor de PO token parou {fails} vezes seguidas; desisti "
                  f"(veja {os.path.join(cfg.cache, 'pot-server.log')})", flush=True)
            return
        print(f"[pot] o servidor de PO token parou (código {p.returncode}); reiniciando", flush=True)
        _stopping.wait(min(30, 2 ** fails))


def _stop():
    _stopping.set()
    p = _proc[0]
    if p and p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            p.kill()


def start():
    """Starts the provider server if configured and not already running. Returns a short status for the log."""
    if not plugin_installed():
        return "não (plugin não instalado)"
    if answering():
        return f"sim ({cfg.yt_pot_url or DEFAULT_URL})"
    d = _server_dir()
    if not d:
        return "não (servidor não encontrado; rode ./pot-setup.sh)" if cfg.yt_pot_server else "não"
    if _addr()[0] not in ("127.0.0.1", "localhost", "::1"):
        return f"não (pot_url {cfg.yt_pot_url} não é deste aparelho; inicie o servidor lá)"
    node = shutil.which("node")
    if not node:
        return "não (Node.js não instalado)"
    threading.Thread(target=_keep_alive, args=(d, node), daemon=True).start()
    atexit.register(_stop)
    return f"sim (iniciado de {d})"
