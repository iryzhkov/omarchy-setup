#!/usr/bin/env bash
# Brave Origin, and make it the default browser.
#
# Not an Omarchy base package, but Omarchy ships a first-class installer that
# picks the right build for the platform, so use it rather than naming the
# package directly. The installer deliberately does not set the default
# ("make it the default via Setup > Defaults > Browser"), so that is a second,
# separate step here.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

if command -v brave-origin >/dev/null 2>&1; then
  info "brave-origin already installed"
else
  step "installing brave-origin"
  run omarchy install browser brave-origin
fi

# `omarchy default browser` with no argument prints the current default;
# with one it writes the XDG handlers (text/html, http, https) via xdg-settings.
# Its exit status is that of the desktop notification it sends last, which
# fails without a display, so the result is verified by re-querying instead.
current=$(omarchy default browser 2>/dev/null || true)
if [[ $current == brave-origin ]]; then
  info "default browser already brave-origin"
elif (( DRY_RUN )); then
  run omarchy default browser brave-origin
else
  step "setting default browser: brave-origin (was: ${current:-unset})"
  omarchy default browser brave-origin >/dev/null 2>&1 || true
  [[ $(omarchy default browser 2>/dev/null) == brave-origin ]] ||
    die "default browser is still '$(omarchy default browser 2>/dev/null)'"
  ok "default browser set to brave-origin"
fi
