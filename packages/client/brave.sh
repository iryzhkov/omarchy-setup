#!/usr/bin/env bash
# Brave. Not an Omarchy base package, but Omarchy ships a first-class installer
# that picks the right build for the platform (brave-bin on aarch64), so use it
# rather than naming the package directly.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

if command -v brave >/dev/null 2>&1; then
  info "brave already installed"
  exit 0
fi

step "installing brave"
run omarchy install browser brave
