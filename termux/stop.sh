#!/data/data/com.termux/files/usr/bin/sh
# Para o musicweb iniciado por termux/start.sh (e libera o wake lock).

PIDFILE="$HOME/.cache/musicweb/server.pid"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    pid=$(cat "$PIDFILE")
    kill "$pid"
    i=0
    while kill -0 "$pid" 2>/dev/null && [ $i -lt 10 ]; do sleep 0.5; i=$((i+1)); done
    rm -f "$PIDFILE"
    echo "musicweb parado."
else
    rm -f "$PIDFILE"
    echo "musicweb não estava rodando."
fi
command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock
exit 0
