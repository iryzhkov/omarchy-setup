#!/usr/bin/env bash
# Package scripts can carry their own post-install config -- that is the point
# of one script per package rather than a flat list of names.
source "${OMARCHY_SETUP_LIB:?}/common.sh"
pkg_install tmux

write_managed_block "$HOME/.config/tmux/tmux.conf" tmux '#' <<'CONF'
set -g mouse on
set -g base-index 1
CONF
