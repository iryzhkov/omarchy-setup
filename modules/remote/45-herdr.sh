#!/usr/bin/env bash
# Remote-side herdr setup.
#
# The client attaches with `herdr --remote <ssh-target>`, which reaches the
# headless server over SSH -- so a remote needs the package (installed by
# packages/common/herdr.sh), sshd (35-sshd.sh), and a user session that
# outlives the SSH connection. That last part is what this module does:
# without lingering, systemd tears the user manager down on logout and takes
# the herdr server with it.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

command -v herdr >/dev/null 2>&1 || die "herdr not installed (expected from packages/common/herdr.sh)"

if loginctl show-user "$USER" --property=Linger 2>/dev/null | grep -q 'Linger=yes'; then
  info "user lingering already enabled"
else
  step "enabling lingering so the herdr server survives logout"
  run sudo loginctl enable-linger "$USER"
fi

# Shared config, if any: config/herdr/config.toml becomes a managed block in
# ~/.config/herdr/config.toml, leaving herdr's own defaults outside the fence.
if [[ -f $OMARCHY_SETUP_ROOT/config/herdr/config.toml ]]; then
  write_managed_block "$HOME/.config/herdr/config.toml" herdr '#' \
    <"$OMARCHY_SETUP_ROOT/config/herdr/config.toml"
  (( DRY_RUN )) || herdr server reload-config >/dev/null 2>&1 || true
fi
