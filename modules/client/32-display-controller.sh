#!/usr/bin/env bash
# Retire the old independent TV watchdog on the one host that uses the coordinator.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

[[ $SETUP_HOST == omarchy-pc ]] || exit 0
[[ -x $HOME/.local/bin/display-controller ]] || exit 0

step "single display coordinator"
if systemctl --user cat tv-output-guard.timer >/dev/null 2>&1; then
  run systemctl --user disable --now tv-output-guard.timer
fi
run systemctl --user daemon-reload
run systemctl --user try-restart hyprmoncfgd.service
