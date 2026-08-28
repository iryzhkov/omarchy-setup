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
