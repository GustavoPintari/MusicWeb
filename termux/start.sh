#!/data/data/com.termux/files/usr/bin/sh
# Starts musicweb in the background and restarts it if it crashes.
# Usage: termux/start.sh          (Termux:Boot runs this script when the phone boots)
# Log: ~/.cache/musicweb/server.log    Stop: termux/stop.sh

DIR=$(cd "$(dirname "$0")/.." && pwd)
RUN="$HOME/.cache/musicweb"
PIDFILE="$RUN/server.pid"
LOG="$RUN/server.log"
mkdir -p "$RUN"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "musicweb já está rodando (pid $(cat "$PIDFILE"))."
    exit 0
fi

PY=${PYTHON:-$(command -v python || command -v python3)}
if [ -z "$PY" ]; then
    echo "Python não encontrado. No Termux: pkg install python" >&2
    exit 1
fi

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
if [ -f "$PIDFILE" ]; then
    echo "musicweb iniciado (pid $(cat "$PIDFILE")). Log: $LOG"
else
    echo "Não consegui iniciar o musicweb; veja $LOG" >&2
    exit 1
fi
