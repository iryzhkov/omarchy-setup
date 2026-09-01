#!/usr/bin/env bash
# Helper scripts the Hyprland bindings call, installed to ~/.local/bin as
# owned copies: config/bin/<name> -> ~/.local/bin/<name>, overwritten on every
# run. Runs before 30-hypr so a binding never points at a script that is not
# there yet.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

SRC="$OMARCHY_SETUP_ROOT/config/bin"
DEST="$HOME/.local/bin"

for f in "$SRC"/*; do
  [[ -f $f ]] || continue
  write_owned_file "$DEST/$(basename "$f")" 0755 <"$f"
done
