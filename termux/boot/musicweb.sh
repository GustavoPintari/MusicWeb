#!/data/data/com.termux/files/usr/bin/sh
# Termux:Boot: starts musicweb when the phone boots.
# Installed in ~/.termux/boot/ by termux/install.sh (which fills in MUSICWEB_DIR).
# To install by hand: copy to ~/.termux/boot/, set MUSICWEB_DIR and chmod +x it.

MUSICWEB_DIR="$HOME/MusicWeb"

exec sh "$MUSICWEB_DIR/termux/start.sh"
