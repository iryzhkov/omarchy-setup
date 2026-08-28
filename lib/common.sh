#!/usr/bin/env bash
# Shared helpers for omarchy-setup modules.
#
# Every module sources this, so modules stay runnable on their own:
#     source "${OMARCHY_SETUP_LIB:?}/common.sh"

[[ -n "${_OMARCHY_SETUP_COMMON:-}" ]] && return 0
_OMARCHY_SETUP_COMMON=1

set -euo pipefail

# ------------------------------------------------------------------ paths --
OMARCHY_SETUP_LIB="${OMARCHY_SETUP_LIB:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
OMARCHY_SETUP_ROOT="${OMARCHY_SETUP_ROOT:-$(cd "$OMARCHY_SETUP_LIB/.." && pwd)}"
OMARCHY_SETUP_STATE="${OMARCHY_SETUP_STATE:-$HOME/.local/state/omarchy-setup}"

# ------------------------------------------------------------- personal ----
# Sourced here rather than in run.sh so a module run on its own still has them.
# Every entry uses ${VAR:-default}, so anything already exported wins.
[[ -f "$OMARCHY_SETUP_ROOT/config/defaults.conf" ]] && source "$OMARCHY_SETUP_ROOT/config/defaults.conf"

# --------------------------------------------------------------- identity --
SETUP_PROFILE="${SETUP_PROFILE:-}"
SETUP_HOST="${SETUP_HOST:-$(hostnamectl hostname 2>/dev/null || hostname)}"
SKIP_SECRETS="${SKIP_SECRETS:-0}"
SETUP_ARCH="${SETUP_ARCH:-$(uname -m)}"
DRY_RUN="${DRY_RUN:-0}"
ASSUME_YES="${ASSUME_YES:-0}"

# ----------------------------------------------------------------- output --
if [[ -t 2 && -z "${NO_COLOR:-}" ]]; then
  C_RESET=$'\033[0m'; C_DIM=$'\033[2m';    C_RED=$'\033[31m'
  C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_BLUE=$'\033[34m'
else
  C_RESET=; C_DIM=; C_RED=; C_GREEN=; C_YELLOW=; C_BLUE=
fi

_log() {
  local color=$1 label=$2; shift 2
  printf '%s%-6s%s %s\n' "$color" "$label" "$C_RESET" "$*" >&2
  if [[ -n "${OMARCHY_SETUP_LOGFILE:-}" ]]; then
    printf '%s %-6s %s\n' "$(date -Is)" "$label" "$*" >>"$OMARCHY_SETUP_LOGFILE"
  fi
  return 0
}
info() { _log "$C_BLUE"   "info"  "$@"; }
warn() { _log "$C_YELLOW" "warn"  "$@"; }
fail() { _log "$C_RED"    "error" "$@"; }
ok()   { _log "$C_GREEN"  "ok"    "$@"; }
step() { printf '\n%s==>%s %s\n' "$C_BLUE" "$C_RESET" "$*" >&2; }
die()  { fail "$@"; exit 1; }

# Run a command, honouring --dry-run.
run() {
  if [[ $DRY_RUN == 1 ]]; then
    printf '%s  would run:%s %s\n' "$C_DIM" "$C_RESET" "$*" >&2
    return 0
  fi
  "$@"
}

confirm() {
  [[ $ASSUME_YES == 1 ]] && return 0
  [[ -t 0 ]] || die "needs confirmation but stdin is not a terminal: $*"
  local reply
  read -r -p "$(printf '%s?%s %s [y/N] ' "$C_YELLOW" "$C_RESET" "$*")" reply
  [[ $reply == [yY]* ]]
}

# --------------------------------------------------------------- guards ----
require_cmd()     { command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"; }
require_omarchy() { command -v omarchy >/dev/null 2>&1 || die "this does not look like an Omarchy system"; }
require_not_root(){ (( EUID != 0 )) || die "run as your normal user; sudo is invoked per-command"; }
is_profile()      { [[ $SETUP_PROFILE == "$1" ]]; }

# ---------------------------------------------------------------- cleanup --
# Modules that clone or build something should use mktempdir, so the work area
# is removed when the module exits however it exits.
declare -a _CLEANUP_PATHS=() _CLEANUP_CMDS=()
_run_cleanup() {
  local p c
  for c in "${_CLEANUP_CMDS[@]:-}"; do [[ -n ${c:-} ]] && eval "$c" || true; done
  for p in "${_CLEANUP_PATHS[@]:-}"; do
    [[ -n ${p:-} && -e ${p:-} ]] && rm -rf -- "$p"
  done
  return 0
}
trap _run_cleanup EXIT

register_cleanup() { _CLEANUP_PATHS+=("$1"); }
# Run a command when the module exits, however it exits.
on_exit() { _CLEANUP_CMDS+=("$*"); }

mktempdir() {
  local d; d=$(mktemp -d)
  register_cleanup "$d"
  printf '%s\n' "$d"
}

# ------------------------------------------------------------------ files --
backup_file() {
  local f=$1
  [[ -f $f ]] || return 0
  local b="$f.omarchy-setup.bak.$(date +%s)" n=0
  # date +%s is 1-second granularity; two writes in the same second must not
  # clobber each other's backup.
  while [[ -e $b ]]; do n=$((n + 1)); b="$f.omarchy-setup.bak.$(date +%s).$n"; done
  run cp -a "$f" "$b"
  info "backed up $(basename "$f") -> $(basename "$b")"
}

# Back up only the first time we ever touch a file, so the kept copy is the
# pristine original rather than one of our own earlier edits.
backup_once() {
  local f=$1
  [[ -f $f ]] || return 0
  compgen -G "$f.omarchy-setup.bak.*" >/dev/null 2>&1 && return 0
  backup_file "$f"
}

# Path to a host-specific override, if one exists for this machine.
#   host_file hypr/monitors.lua
host_file() {
  local p="$OMARCHY_SETUP_ROOT/hosts/$SETUP_HOST/$1"
  [[ -e $p ]] && printf '%s\n' "$p"
}

# ---------------------------------------------------------- managed block --
# Own a fenced region inside a file Omarchy also manages, so `omarchy update`
# migrations can keep patching everything outside our fences. Modelled on the
# block Omaland already writes into ~/.config/hypr/looknfeel.lua.
#
#   write_managed_block <file> <id> [comment-prefix]   # content on stdin
#
# Idempotent: rewrites only between the fences, and skips the write entirely
# when nothing changed, so hot-reloading configs are not needlessly touched.
write_managed_block() {
  local file=$1 id=$2 cp=${3:-#}
  local start="$cp >>> omarchy-setup:$id >>>"
  local end="$cp <<< omarchy-setup:$id <<<"
  local content; content=$(cat)

  # A managed block is delimited by exact lines; content containing one would
  # produce a file we can no longer parse back, and a later rewrite would
  # strand whatever followed the forged marker.
  if grep -qxF -e "$start" -e "$end" <<<"$content"; then
    die "refusing to write block '$id' into $file: content contains a fence marker"
  fi

  # Write through a symlink rather than replacing it -- these files are often
  # symlinked out to a dotfiles checkout, and mv would silently break the link
  # and leave the real file without the block.
  [[ -L $file ]] && file=$(readlink -f "$file")

  local tmp; tmp=$(mktemp)
  local start_ln= end_ln=

  if [[ -f $file ]]; then
    start_ln=$(grep -nxF -- "$start" "$file" 2>/dev/null | head -1 | cut -d: -f1) || true
    end_ln=$(grep -nxF -- "$end" "$file" 2>/dev/null | head -1 | cut -d: -f1) || true
  fi

  {
    if [[ -n $start_ln && -n $end_ln && $start_ln -lt $end_ln ]]; then
      head -n "$((start_ln - 1))" "$file"
      printf '%s\n%s\n%s\n' "$start" "$content" "$end"
      tail -n "+$((end_ln + 1))" "$file"
    else
      if [[ -f $file ]]; then
        cat "$file"
        [[ -s $file && -n $(tail -c1 "$file") ]] && printf '\n'
        printf '\n'
      fi
      printf '%s\n%s\n%s\n' "$start" "$content" "$end"
    fi
  } >"$tmp"

  if [[ -f $file ]] && cmp -s "$tmp" "$file"; then
    rm -f "$tmp"
    info "$(basename "$file"): block '$id' already current"
    return 0
  fi

  if [[ $DRY_RUN == 1 ]]; then
    printf '%s  would update%s block %s in %s\n' "$C_DIM" "$C_RESET" "$id" "$file" >&2
    diff -u "${file:-/dev/null}" "$tmp" 2>/dev/null | sed 's/^/      /' >&2 || true
    rm -f "$tmp"
    return 0
  fi

  mkdir -p "$(dirname "$file")"
  # Preserve the pristine original: once per file, not once per block.
  backup_once "$file"
  mv "$tmp" "$file"
  ok "$(basename "$file"): block '$id' written"
}

remove_managed_block() {
  local file=$1 id=$2 cp=${3:-#}
  [[ -f $file ]] || return 0
  local start="$cp >>> omarchy-setup:$id >>>"
  local end="$cp <<< omarchy-setup:$id <<<"
  local s e
  s=$(grep -nxF -- "$start" "$file" | head -1 | cut -d: -f1) || return 0
  e=$(grep -nxF -- "$end" "$file" | head -1 | cut -d: -f1) || return 0
  [[ -n $s && -n $e && $s -lt $e ]] || return 0
  local tmp; tmp=$(mktemp)
  { head -n "$((s - 1))" "$file"; tail -n "+$((e + 1))" "$file"; } >"$tmp"
  run mv "$tmp" "$file"
  ok "$(basename "$file"): block '$id' removed"
}

# Read a newline-delimited list file, stripping '#' comments and blank lines.
read_list() {
  local f=$1
  [[ -f $f ]] || return 0
  # A '#' only starts a comment at the beginning of a line or after
  # whitespace, so a URL fragment (repo.git#ref) survives intact.
  sed -e 's/^[[:space:]]*#.*//' -e 's/[[:space:]]#.*//' \
      -e 's/[[:space:]]*$//' -e '/^[[:space:]]*$/d' "$f"
}

# -------------------------------------------------------------- packages --
# Wrap Omarchy's own helpers: idempotent, --noconfirm, and on the aarch64 fork
# they skip packages missing from the repos instead of hard-failing.
pkg_present() { omarchy pkg present "$@" >/dev/null 2>&1; }

# For tools Omarchy ships in its base install. Silent when present, installs
# only if something removed it -- avoids a pointless "already installed" line
# on every run while still being self-healing.
ensure_cmd() {
  local cmd=$1 pkg=${2:-$1}
  command -v "$cmd" >/dev/null 2>&1 && return 0
  warn "$cmd missing though Omarchy ships it; installing $pkg"
  pkg_install "$pkg"
}

pkg_install() {
  (( $# )) || return 0
  if pkg_present "$@"; then info "already installed: $*"; return 0; fi
  step "installing: $*"
  run omarchy pkg add "$@"
}

aur_install() {
  (( $# )) || return 0
  if pkg_present "$@"; then info "already installed: $*"; return 0; fi
  step "installing from AUR: $*"
  run omarchy pkg aur add "$@"
}

# Refuses to remove anything another package depends on -- several Omarchy
# preinstalls are pulled in by the meta-package and removing them breaks
# `omarchy update`.
pkg_remove() {
  local pkg reqby; local -a targets=()
  for pkg in "$@"; do
    if ! pacman -Qq "$pkg" &>/dev/null; then
      info "not installed, skipping: $pkg"
      continue
    fi
    reqby=$(pacman -Qi "$pkg" 2>/dev/null | awk -F': +' '/^Required By/{print $2; exit}')
    if [[ -n $reqby && $reqby != "None" ]]; then
      warn "keeping '$pkg': required by $reqby"
      continue
    fi
    targets+=("$pkg")
  done
  (( ${#targets[@]} )) || return 0
  step "removing: ${targets[*]}"
  run omarchy pkg drop "${targets[@]}"
}

# ----------------------------------------------------------------- state --
mark_ran() {
  mkdir -p "$OMARCHY_SETUP_STATE"
  printf '%s %s\n' "$(date -Is)" "$1" >>"$OMARCHY_SETUP_STATE/history"
}
