#!/usr/bin/env bash
# Omarchy hooks, installed as owned files:
#   config/hooks/<event>.d/<name>.hook -> ~/.config/omarchy/hooks/<event>.d/<name>.hook
#
# Hook directories are include-by-design: Omarchy runs every executable *.hook
# in them, so nothing of Omarchy's is edited. Today this carries
# post-update.d/omarchy-setup.hook, which re-runs this repo after an update.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

SRC="$OMARCHY_SETUP_ROOT/config/hooks"
DEST="$HOME/.config/omarchy/hooks"

for f in "$SRC"/*.d/*.hook; do
  [[ -f $f ]] || continue
  event=$(basename "$(dirname "$f")")
  write_owned_file "$DEST/$event/$(basename "$f")" 0755 <"$f"
done
