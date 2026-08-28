#!/usr/bin/env bash
# Start the herdr server with the Hyprland session, so agent sessions are
# already up and survive closing the terminal you launched them from.
#
# The remote profile achieves the same thing differently -- see
# modules/remote/45-herdr.sh, which enables lingering so the user manager (and
# the server with it) outlives an ssh logout.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

command -v herdr >/dev/null 2>&1 || { warn "herdr not installed; skipping autostart"; exit 0; }

write_managed_block "$HOME/.config/hypr/autostart.lua" herdr '--' <<'LUA'
-- Run the herdr server at login so sessions persist across terminal windows.
o.launch_on_start("herdr server")
LUA

if (( ! DRY_RUN )) && command -v hyprctl >/dev/null && [[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} ]]; then
  hyprctl reload >/dev/null 2>&1 || true
fi
