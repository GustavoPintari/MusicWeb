#!/data/data/com.termux/files/usr/bin/sh
# Termux:Boot: inicia o musicweb quando o celular liga.
# Instalado em ~/.termux/boot/ pelo termux/install.sh (que preenche MUSICWEB_DIR).
# Para instalar à mão: copie para ~/.termux/boot/, ajuste MUSICWEB_DIR e dê chmod +x.

MUSICWEB_DIR="$HOME/MusicWeb"

exec sh "$MUSICWEB_DIR/termux/start.sh"
