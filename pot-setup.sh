#!/usr/bin/env sh
# Installs the YouTube PO token provider (bgutil-ytdlp-pot-provider), so yt-dlp passes the
# "Sign in to confirm you're not a bot" check without cookies. Two parts:
#   - the yt-dlp plugin (pip);
#   - its Node.js server, in ~/bgutil-ytdlp-pot-provider (MusicWeb starts it by itself; see [youtube] pot_server).
#
#   ./pot-setup.sh            install, or update to the latest version
#   ./pot-setup.sh DIR        install the server somewhere else (then set [youtube] pot_server = "DIR/server")
#
# Plugin and server must be the same version; running this again updates both.
set -e

DEST=${1:-$HOME/bgutil-ytdlp-pot-provider}
REPO=https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git
PY=${PYTHON:-$(command -v python || command -v python3 || true)}
[ -n "$PY" ] || { echo "Python não encontrado." >&2; exit 1; }

if [ -n "$TERMUX_VERSION" ] || [ -d /data/data/com.termux ]; then
    echo "==> Pacotes do Termux (Node.js, git e o necessário para compilar o 'canvas')"
    command -v node >/dev/null 2>&1 || pkg install -y nodejs-lts
    pkg install -y git build-essential python pkg-config libcairo pango libjpeg-turbo giflib librsvg
    # node-gyp on Termux stops with "Undefined variable android_ndk_path" without this
    if [ ! -f "$HOME/.gyp/include.gypi" ]; then
        mkdir -p "$HOME/.gyp"
        echo "{'variables':{'android_ndk_path':''}}" > "$HOME/.gyp/include.gypi"
    fi
fi

for c in node npm git; do
    command -v $c >/dev/null 2>&1 || { echo "Falta o comando '$c'. Instale o Node.js 22 ou mais novo e o git." >&2; exit 1; }
done
NODE_MAJOR=$(node -p 'process.versions.node.split(".")[0]')
if [ "$NODE_MAJOR" -lt 22 ]; then
    echo "O servidor precisa do Node.js 22 ou mais novo (este é o $(node --version))." >&2
    exit 1
fi

echo "==> Plugin do yt-dlp (pip)"
"$PY" -m pip install -U yt-dlp bgutil-ytdlp-pot-provider
VER=$("$PY" -m pip show bgutil-ytdlp-pot-provider | sed -n 's/^Version: //p')
[ -n "$VER" ] || { echo "Não consegui ver a versão do plugin instalado." >&2; exit 1; }

echo "==> Servidor $VER em $DEST"
if [ -d "$DEST/.git" ]; then
    git -C "$DEST" fetch --depth 1 origin tag "$VER"
    git -C "$DEST" checkout -q "$VER"
else
    git -c advice.detachedHead=false clone --depth 1 --branch "$VER" "$REPO" "$DEST"
fi
cd "$DEST/server"
npm ci
npx tsc

echo
echo "Pronto: plugin e servidor $VER instalados."
if [ "$DEST/server" != "$HOME/bgutil-ytdlp-pot-provider/server" ]; then
    echo "Coloque no config.toml, em [youtube]:  pot_server = \"$DEST/server\""
fi
echo "Reinicie o MusicWeb (./musicweb.sh restart); no log deve aparecer \"PO token=sim\"."
