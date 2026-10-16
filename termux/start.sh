#!/data/data/com.termux/files/usr/bin/sh
# Inicia o musicweb em segundo plano, reiniciando-o se ele cair.
# Uso: termux/start.sh            (o Termux:Boot chama este script ao ligar o celular)
# Log: ~/.cache/musicweb/server.log    Parar: termux/stop.sh

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

# log não cresce para sempre: guarda só a execução anterior
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt 1048576 ]; then
    mv "$LOG" "$LOG.1"
fi

# não deixa o Android dormir e matar o servidor
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

# Laço que mantém o servidor de pé. Roda desligado do terminal (nohup), então
# continua depois que a sessão do Termux (ou do Termux:Boot) termina.
nohup sh -c '
    echo $$ > "$1"
    # o mpv é aberto pelo servidor; sem isto ele ficaria rodando sozinho
    # ([.] faz o padrão não casar com o texto deste próprio script)
    stop_mpv() { pkill -f "musicweb-mpv[.]sock" 2>/dev/null; }
    trap "kill \$child 2>/dev/null; stop_mpv; rm -f \"$1\"; exit 0" TERM INT
    # na inicialização do celular o armazenamento compartilhado pode demorar a aparecer
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
