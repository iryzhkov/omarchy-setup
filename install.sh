#!/usr/bin/env bash
# Bootstrap for omarchy-setup.
#
#   curl -fsSL https://raw.githubusercontent.com/iryzhkov/omarchy-setup/main/install.sh | bash -s -- --profile client
#
# Fetches the repo to ~/.local/share/omarchy-setup and runs it. The clone is
# kept: the `omarchy-setup` command and the post-update hook re-run it from
# there. Set OMARCHY_SETUP_KEEP=0 to remove it afterwards instead. State
# (chosen profile, checkout path, last run log) lives in
# ~/.local/state/omarchy-setup.
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
  local keep="${OMARCHY_SETUP_KEEP:-1}"

  command -v omarchy >/dev/null 2>&1 ||
    { echo "error: this does not look like an Omarchy system" >&2; exit 1; }
  (( EUID != 0 )) ||
    { echo "error: run as your normal user, not root" >&2; exit 1; }

  # A checkout that was already here is yours -- never delete it.
  local pre_existing=0
  [[ -d $dest/.git ]] && pre_existing=1

  if ! command -v git >/dev/null 2>&1; then
    echo "==> installing git"
    omarchy pkg add git
  fi

  if (( pre_existing )); then
    echo "==> using existing checkout at $dest"
    # The kept clone from an earlier bootstrap: bring it up to date, but never
    # override local work -- --ff-only refuses anything that is not a plain
    # fast-forward, and a failure just runs what is there.
    git -C "$dest" pull --ff-only --quiet 2>/dev/null ||
      echo "==> could not fast-forward $dest; running it as it is"
  else
    echo "==> cloning $repo ($ref)"
    rm -rf "$dest"
    mkdir -p "$(dirname "$dest")"
    # --branch takes a branch or tag, never a commit SHA, so fall back to a
    # full clone and checkout. Pinning to a commit is exactly what you want on
    # a fresh machine, and the shallow form silently fails on one.
    if ! git clone --quiet --depth 1 --branch "$ref" "$repo" "$dest" 2>/dev/null; then
      rm -rf "$dest"
      git clone --quiet "$repo" "$dest"
      git -C "$dest" checkout --quiet "$ref"
    fi
  fi

  # `curl ... | bash` leaves stdin pointing at the already-consumed script, so
  # any prompt (profile choice, `bw unlock`) would read EOF. Reconnect to the
  # controlling terminal when there is one; stay non-interactive when there
  # isn't, and let run.sh skip what it cannot ask about.
  # `2>/dev/null` comes first on purpose: bash applies redirections left to
  # right, and a failure to open /dev/tty is reported by the shell itself. With
  # the order reversed, every run without a controlling terminal prints
  # "/dev/tty: No such device or address" before anything is suppressed.
  if [[ ! -t 0 ]] && : 2>/dev/null </dev/tty; then
    exec </dev/tty
  fi

  # Deliberately not exec: we need to run cleanup once run.sh returns.
  local status=0
  "$dest/run.sh" "$@" || status=$?

  if (( pre_existing )); then
    echo "==> keeping your existing checkout at $dest"
  elif (( keep )); then
    echo "==> checkout kept at $dest (re-run with: omarchy-setup)"
  else
    echo "==> OMARCHY_SETUP_KEEP=0, cleaning up $dest"
    rm -rf "$dest"
  fi

  exit "$status"
}

main "$@"
