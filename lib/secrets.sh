#!/usr/bin/env bash
# Bitwarden helpers.
#
# The vault is the single source of truth; nothing secret is ever stored in
# this repo. A run unlocks the vault interactively, reads what the manifest
# asks for, writes it out, and then re-locks -- or logs out entirely if it was
# this script that logged in, so a machine we touched is left holding no vault
# data at all.
#
# BW_SESSION is exported rather than passed as --session, because command-line
# arguments are visible to every process on the box via ps.

[[ -n "${_OMARCHY_SETUP_SECRETS:-}" ]] && return 0
_OMARCHY_SETUP_SECRETS=1

source "${OMARCHY_SETUP_LIB:?}/common.sh"

_BW_WE_LOGGED_IN=0

# ---------------------------------------------------------- which bw ------
# The client must match the API version the server advertises (see README):
# an older CLI fails to unlock inside bitwarden_crypto with an error that reads
# like a wrong master password. config/mise-tools.txt pins the right one, but
# Omarchy appends the mise shims *after* the system paths, so a
# pacman-installed bitwarden-cli shadows the pinned build on PATH.
#
# Every bw call in this file goes through the resolved binary, never PATH.
BW_BIN="${BW_BIN:-}"

bw_resolve() {
  local mise_bw path_bw
  mise_bw=$(mise which bw 2>/dev/null || true)
  path_bw=$(command -v bw 2>/dev/null || true)
  if [[ -n $mise_bw ]]; then
    BW_BIN=$mise_bw
    if [[ -n $path_bw && $path_bw != "$mise_bw" ]]; then
      info "using the pinned bw $("$mise_bw" --version 2>/dev/null); $path_bw ($("$path_bw" --version 2>/dev/null)) would shadow it on PATH"
    fi
  elif [[ -n $path_bw ]]; then
    BW_BIN=$path_bw
    warn "no mise-managed bw; using $path_bw, which may not match the server's API version"
  else
    return 1
  fi
  export BW_BIN
  return 0
}

bw() { command "${BW_BIN:?bitwarden CLI not resolved; call bw_resolve first}" "$@"; }

bw_status() { bw status 2>/dev/null | sed -n 's/.*"status":"\([a-z]*\)".*/\1/p'; }

# Point the CLI at a self-hosted server before any login attempt.
bw_configure_server() {
  local want=${1:-}
  [[ -n $want ]] || return 0
  local have
  have=$(bw config server 2>/dev/null || true)
  if [[ $have == "$want" ]]; then
    info "bitwarden server already set"
    return 0
  fi
  [[ $(bw_status) == "unauthenticated" ]] ||
    { warn "logged in against $have; not switching server"; return 0; }
  run bw config server "$want"
}

# Leaves BW_SESSION exported on success.
bw_unlock() {
  local state; state=$(bw_status)

  if [[ $state == "unauthenticated" ]]; then
    [[ -t 0 ]] || { warn "vault needs login but there is no terminal"; return 1; }
    step "logging in to Bitwarden (this machine is not yet authenticated)"
    bw login --raw >/dev/null || { fail "bw login failed"; return 1; }
    _BW_WE_LOGGED_IN=1
    state=$(bw_status)
  fi

  if [[ $state == "unlocked" && -n ${BW_SESSION:-} ]]; then
    info "vault already unlocked"
  else
    [[ -t 0 ]] || { warn "vault is locked but there is no terminal to unlock it"; return 1; }
    step "unlocking Bitwarden vault"
    local session
    session=$(bw unlock --raw) || { fail "bw unlock failed"; return 1; }
    export BW_SESSION="$session"
  fi

  bw sync >/dev/null 2>&1 || warn "bw sync failed; using cached vault"
  return 0
}

# bw_read <item> [field]   -- prints the value, never logs it
bw_read() {
  local item=$1 field=${2:-password}
  bw get "$field" "$item" 2>/dev/null
}

# Leave the machine holding as little as possible.
bw_finish() {
  if (( _BW_WE_LOGGED_IN )); then
    info "logging out of Bitwarden (leaving no vault data on this machine)"
    bw logout >/dev/null 2>&1 || true
  else
    bw lock >/dev/null 2>&1 || true
  fi
  unset BW_SESSION
}
