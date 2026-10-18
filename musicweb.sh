#!/data/data/com.termux/files/usr/bin/sh
# musicweb control script for Termux.
#
#   ./musicweb.sh [start]          start in the background (default; Termux:Boot runs it with no arguments)
#   ./musicweb.sh stop | restart | status
#   ./musicweb.sh log [-f]         last lines of the log (-f: follow)
#   ./musicweb.sh install [--no-boot]
#   ./musicweb.sh boot on | off    start (or not) when the phone boots
#
# ~/.termux/boot/musicweb.sh is a symlink to this file, so there is a single copy to keep up to date.

RUN="$HOME/.cache/musicweb"
PIDFILE="$RUN/server.pid"
LOG="$RUN/server.log"
BOOT="$HOME/.termux/boot/musicweb.sh"

# Real path of this script, following symlinks (e.g. ~/.termux/boot/musicweb.sh -> project).
resolve() {
    r=$(readlink -f "$1" 2>/dev/null) && [ -n "$r" ] && { echo "$r"; return; }
    r=$(realpath "$1" 2>/dev/null) && [ -n "$r" ] && { echo "$r"; return; }
    p=$1 i=0
    while [ -L "$p" ] && [ $i -lt 20 ]; do       # no readlink -f / realpath: follow the links by hand
        t=$(readlink "$p")
        case $t in /*) p=$t ;; *) p=$(dirname "$p")/$t ;; esac
        i=$((i+1))
    done
    echo "$p"
}
SELF=$(resolve "$0")
DIR=$(cd "$(dirname "$SELF")" 2>/dev/null && pwd)
# Not in the project (e.g. a plain copy in ~/.termux/boot): use $MUSICWEB_DIR or the folder of the last run.
if [ ! -f "$DIR/server.py" ]; then
    for d in "$MUSICWEB_DIR" "$(cat "$RUN/project_dir" 2>/dev/null)"; do
        if [ -n "$d" ] && [ -f "$d/server.py" ]; then
            DIR=$d SELF=$d/musicweb.sh
            break
        fi
    done
fi
if [ ! -f "$DIR/server.py" ]; then
    echo "Não achei a pasta do MusicWeb (procurei server.py em ${DIR:-?})." >&2
    echo "Rode de dentro da pasta do projeto, por exemplo: cd ~/MusicWeb && ./musicweb.sh boot on" >&2
    exit 1
fi
mkdir -p "$RUN"
echo "$DIR" > "$RUN/project_dir"                 # remembered for the fallback above

python_bin() {
    PY=${PYTHON:-$(command -v python || command -v python3)}
    if [ -z "$PY" ]; then
        echo "Python não encontrado. No Termux: pkg install python" >&2
        exit 1
    fi
}

running() {
    [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

do_start() {
    mkdir -p "$RUN"
    if running; then
        echo "musicweb já está rodando (pid $(cat "$PIDFILE"))."
        return 0
    fi
    python_bin
    # keep the log from growing forever: only the previous run is kept
    if [ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt 1048576 ]; then
        mv "$LOG" "$LOG.1"
    fi
    # keep Android from sleeping and killing the server
    command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

    # Loop that keeps the server up. It runs detached from the terminal (nohup), so it
    # keeps going after the Termux (or Termux:Boot) session ends.
    nohup sh -c '
        echo $$ > "$1"
        # mpv is started by the server; without this it would be left running on its own
        # ([.] keeps the pattern from matching the text of this very script)
        stop_mpv() { pkill -f "musicweb-mpv[.]sock" 2>/dev/null; }
        trap "kill \$child 2>/dev/null; stop_mpv; rm -f \"$1\"; exit 0" TERM INT
        # at boot the shared storage may take a while to show up
        i=0
        while [ ! -r /storage/emulated/0 ] && [ -d /storage/emulated ] && [ $i -lt 60 ]; do sleep 1; i=$((i+1)); done
        while :; do
            echo "=== $(date "+%Y-%m-%d %H:%M:%S") iniciando musicweb"
            PYTHONUNBUFFERED=1 "$2" "$3/server.py" &
            child=$!
            wait $child
            code=$?
            echo "=== $(date "+%Y-%m-%d %H:%M:%S") musicweb saiu (código $code); reiniciando em 5 s"
            stop_mpv
            sleep 5
        done
    ' musicweb "$PIDFILE" "$PY" "$DIR" >> "$LOG" 2>&1 &

    sleep 1
    if running; then
        echo "musicweb iniciado (pid $(cat "$PIDFILE")). Log: $LOG"
    else
        echo "Não consegui iniciar o musicweb; veja $LOG" >&2
        return 1
    fi
}

do_stop() {
    if running; then
        pid=$(cat "$PIDFILE")
        kill "$pid"
        i=0
        while kill -0 "$pid" 2>/dev/null && [ $i -lt 20 ]; do sleep 0.5; i=$((i+1)); done
        echo "musicweb parado."
    else
        echo "musicweb não estava rodando."
    fi
    rm -f "$PIDFILE"
    command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock
    return 0
}

do_status() {
    if running; then
        pid=$(cat "$PIDFILE")
        up=$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ')
        echo "musicweb: rodando (pid $pid${up:+, há $up})"
    else
        echo "musicweb: parado"
    fi
    if [ -L "$BOOT" ]; then
        echo "início com o celular: ativado ($BOOT -> $(readlink "$BOOT"))"
    elif [ -f "$BOOT" ]; then
        echo "início com o celular: ativado, mas $BOOT é uma cópia; troque por um link: ./musicweb.sh boot on"
    else
        echo "início com o celular: desativado  (./musicweb.sh boot on)"
    fi
    python_bin
    # config, address and what is playing (asks the running server, if any)
    (cd "$DIR" && "$PY" -m musicweb.info)
}

do_boot() {
    case "$1" in
        on)
            mkdir -p "$(dirname "$BOOT")"
            chmod +x "$DIR/musicweb.sh"
            rm -f "$BOOT"                          # replaces an old copy or link
            ln -s "$DIR/musicweb.sh" "$BOOT"
            echo "Início com o celular ativado: $BOOT -> $DIR/musicweb.sh"
            echo "Precisa do app Termux:Boot (da mesma loja do Termux: F-Droid ou GitHub), aberto uma vez."
            ;;
        off)
            rm -f "$BOOT"
            echo "Início com o celular desativado."
            ;;
        *)
            echo "Uso: $0 boot on|off" >&2
            return 1
            ;;
    esac
}

do_install() {
    set -e
    echo "==> Pacotes do Termux (python, mpv)"
    pkg install -y python mpv
    echo "==> Dependências Python (requirements.txt)"
    pip install -U -r "$DIR/requirements.txt"
    if [ ! -d "$HOME/storage" ]; then
        echo "==> Acesso ao armazenamento (aceite a permissão que vai aparecer)"
        termux-setup-storage || true
    fi
    # only create a config if there is none in either place the server looks
    if [ ! -f "$DIR/config.toml" ] && [ ! -f "$HOME/.config/musicweb/config.toml" ]; then
        cp "$DIR/config.example.toml" "$DIR/config.toml"
        echo "==> Criado $DIR/config.toml (ajuste a pasta de músicas e o resto, se quiser)"
    fi
    chmod +x "$SELF"
    set +e
    if [ "$1" != "--no-boot" ]; then
        echo "==> Início automático (Termux:Boot)"
        do_boot on
    fi
    echo
    echo "Pronto. Para iniciar agora: $0 start"
}

case "${1:-start}" in
    start)   do_start ;;
    stop)    do_stop ;;
    restart) do_stop; do_start ;;
    status)  do_status ;;
    log|logs)
        if [ "$2" = "-f" ]; then tail -n 40 -f "$LOG"; else tail -n 40 "$LOG"; fi ;;
    install) do_install "$2" ;;
    boot)    do_boot "$2" ;;
    help|-h|--help)
        sed -n '2,10p' "$SELF" | sed 's/^# \{0,1\}//' ;;
    *)
        echo "Comando desconhecido: $1  (use: start, stop, restart, status, log, install, boot, help)" >&2
        exit 1 ;;
esac
