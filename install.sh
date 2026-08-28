#!/usr/bin/env bash
# Bootstrap for omarchy-setup.
#
#   curl -fsSL https://raw.githubusercontent.com/iryzhkov/omarchy-setup/main/install.sh | bash -s -- --profile client
#
# Fetches the repo, runs it, then removes the clone again -- a fresh machine is
# left with the configured system and no build litter. State that must survive
# (chosen profile, last run log) lives in ~/.local/state/omarchy-setup.
#
# Everything is wrapped in a function invoked on the last line, so a truncated
# download cannot execute a half-script.

set -euo pipefail

main() {
  # Derived from the account name so a fork only overrides one value.
  local gh_user="${OMARCHY_SETUP_GH_USER:-iryzhkov}"
  local repo="${OMARCHY_SETUP_REPO:-https://github.com/$gh_user/omarchy-setup.git}"
  # Pin to a tag or commit; an unfinished push should never run on a fresh box.
  local ref="${OMARCHY_SETUP_REF:-main}"
  local dest="${OMARCHY_SETUP_DIR:-$HOME/.local/share/omarchy-setup}"
  local keep="${OMARCHY_SETUP_KEEP:-0}"

  command -v omarchy >/dev/null 2>&1 ||
    { echo "error: this does not look like an Omarchy system" >&2; exit 1; }
  (( EUID != 0 )) ||
    { echo "error: run as your normal user, not root" >&2; exit 1; }

  # A checkout that was already here is yours -- never delete it.
  local pre_existing=0
  [[ -d $dest/.git ]] && pre_existing=1

  if ! command -v git >/dev/null 2>&1; then
    echo "==> installing git"
    sudo pacman -S --noconfirm --needed git
  fi

  if (( pre_existing )); then
    echo "==> using existing checkout at $dest"
  else
    echo "==> cloning $repo ($ref)"
    rm -rf "$dest"
    mkdir -p "$(dirname "$dest")"
    git clone --quiet --depth 1 --branch "$ref" "$repo" "$dest"
  fi

  # `curl ... | bash` leaves stdin pointing at the already-consumed script, so
  # any prompt (profile choice, `bw unlock`) would read EOF. Reconnect to the
  # controlling terminal when there is one; stay non-interactive when there
  # isn't, and let run.sh skip what it cannot ask about.
  if [[ ! -t 0 ]] && : </dev/tty 2>/dev/null; then
    exec </dev/tty
  fi

  # Deliberately not exec: we need to run cleanup once run.sh returns.
  local status=0
  "$dest/run.sh" "$@" || status=$?

  if (( pre_existing )); then
    echo "==> keeping your existing checkout at $dest"
  elif (( keep )); then
    echo "==> OMARCHY_SETUP_KEEP=1, leaving $dest in place"
  else
    echo "==> cleaning up $dest"
    rm -rf "$dest"
  fi

  exit "$status"
}

main "$@"
