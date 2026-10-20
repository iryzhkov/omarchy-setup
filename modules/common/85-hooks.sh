#!/usr/bin/env bash
# Omarchy hooks, installed as owned files:
#   config/hooks/<event>.d/<name>.hook -> ~/.config/omarchy/hooks/<event>.d/<name>.hook
#
# Setup is bootstrap-only; UpKeeper owns ongoing convergence.
# Remove the legacy update hook on existing installations.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

SRC="$OMARCHY_SETUP_ROOT/config/hooks"
DEST="$HOME/.config/omarchy/hooks"
LEGACY="$DEST/post-update.d/omarchy-setup.hook"
if [[ -f $LEGACY ]]; then
  backup_file "$LEGACY"
  run rm -- "$LEGACY"
fi

for f in "$SRC"/*.d/*.hook; do
  [[ -f $f ]] || continue
  event=$(basename "$(dirname "$f")")
  write_owned_file "$DEST/$event/$(basename "$f")" 0755 <"$f"
done
