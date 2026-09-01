#!/usr/bin/env bash
# spotify-player, the TUI behind the SUPER+SHIFT+M binding in
# config/hypr/bindings.lua. Spotify's own client has no aarch64 Linux build,
# so this is the one music client every machine gets.
#
# app.toml is owned outright: it is the whole configuration file and has no
# include directive. The client_id in it is Spotify's public OAuth client id
# for the app, not a credential; login happens interactively on first launch.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

pkg_install spotify-player
write_owned_file "$HOME/.config/spotify-player/app.toml" \
  <"$OMARCHY_SETUP_ROOT/config/spotify-player/app.toml"
