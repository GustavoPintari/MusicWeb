#!/data/data/com.termux/files/usr/bin/sh
# Prepara o musicweb no Termux: pacotes, dependências Python e início automático (Termux:Boot).
# Uso: sh termux/install.sh            (pode rodar de novo para atualizar)
#      sh termux/install.sh --no-boot  (não configura o início automático)
set -e

DIR=$(cd "$(dirname "$0")/.." && pwd)
BOOT=1
[ "$1" = "--no-boot" ] && BOOT=0

echo "==> Pacotes do Termux (python, mpv)"
pkg install -y python mpv

echo "==> Dependências Python (requirements.txt)"
pip install -U -r "$DIR/requirements.txt"

if [ ! -d "$HOME/storage" ]; then
    echo "==> Acesso ao armazenamento (aceite a permissão que vai aparecer)"
    termux-setup-storage || true
fi

if [ ! -f "$DIR/config.toml" ]; then
    cp "$DIR/config.example.toml" "$DIR/config.toml"
    echo "==> Criado $DIR/config.toml (ajuste a pasta de músicas e o resto, se quiser)"
fi

chmod +x "$DIR/termux/start.sh" "$DIR/termux/stop.sh"

if [ "$BOOT" = 1 ]; then
    echo "==> Início automático (Termux:Boot)"
    mkdir -p "$HOME/.termux/boot"
    # copia o script trocando a pasta padrão pela pasta real do projeto
    sed "s|^MUSICWEB_DIR=.*|MUSICWEB_DIR=\"$DIR\"|" "$DIR/termux/boot/musicweb.sh" > "$HOME/.termux/boot/musicweb.sh"
    chmod +x "$HOME/.termux/boot/musicweb.sh"
    echo "    Instalado em ~/.termux/boot/musicweb.sh"
    echo "    Falta: instalar o app Termux:Boot (da mesma loja do Termux: F-Droid ou GitHub) e abri-lo uma vez."
fi

echo
echo "Pronto. Para iniciar agora:  $DIR/termux/start.sh"
echo "Para parar:                  $DIR/termux/stop.sh"
