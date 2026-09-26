#!/usr/bin/env bash
# Override only the crash watcher's command; keep Omarchy's unit lifecycle.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

src="$OMARCHY_SETUP_ROOT/config/systemd/user/omarchy-crash-watch.service.d/timeout.conf"
dest="$HOME/.config/systemd/user/omarchy-crash-watch.service.d/timeout.conf"

changed=0
[[ -f $dest ]] && cmp -s "$src" "$dest" || changed=1
write_owned_file "$dest" 0644 <"$src"

if (( ! DRY_RUN )); then
  (( ! changed )) || systemctl --user daemon-reload
  # The wrapper or packaged watcher may have changed without a unit change.
  if systemctl --user is-active -q omarchy-crash-watch.service; then
    systemctl --user restart omarchy-crash-watch.service
  fi
fi
