#!/usr/bin/env bash
# Retire the old independent TV watchdog on the one host that uses the coordinator.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

[[ $SETUP_HOST == omarchy-pc ]] || exit 0
[[ -x $HOME/.local/bin/display-controller ]] || exit 0

step "single display coordinator"
if [[ $DRY_RUN != 1 ]]; then
  display_daemon="$HOME/.local/libexec/display-controller/hyprmoncfgd"
  if [[ ! -x $display_daemon ]] || ! "$display_daemon" --help | grep -q -- --ipc-only; then
    fail "Install the reviewed IPC-only display daemon before restarting display management."
    exit 1
  fi
fi
if systemctl --user cat tv-output-guard.timer >/dev/null 2>&1; then
  run systemctl --user disable --now tv-output-guard.timer
fi
run systemctl --user daemon-reload
run systemctl --user try-restart hyprmoncfgd.service
