#!/usr/bin/env bash
# Pull environment secrets from Bitwarden and render them to a 0600 env file.
#
# The vault is the source of truth. Nothing secret is stored in this repo, and
# nothing long-lived is left on the machine: the run unlocks interactively,
# reads what config/secrets/*.map asks for, and then re-locks -- or logs out
# entirely if this script was what logged in.
#
# Skip with --skip-secrets. Skipped automatically when there is no terminal to
# type a master password into, so an unattended run still succeeds.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

if [[ ${SKIP_SECRETS:-0} == 1 ]]; then
  info "skipping secrets"
  exit 0
fi

# ---- what to fetch --------------------------------------------------------
declare -a entries=()
for scope in common "$SETUP_PROFILE"; do
  while read -r line; do
    [[ -n $line ]] && entries+=("$line")
  done < <(read_list "$OMARCHY_SETUP_ROOT/config/secrets/$scope.map")
done

if (( ! ${#entries[@]} )); then
  info "no secrets declared for profile '$SETUP_PROFILE'"
  exit 0
fi

# ---- non-secret settings --------------------------------------------------
# BW_SERVER comes from config/defaults.conf via common.sh (--bw-server).
SECRETS_ENV_FILE="$HOME/.config/omarchy-setup/secrets.env"
conf="$OMARCHY_SETUP_ROOT/config/secrets/bitwarden.conf"
[[ -f $conf ]] && source "$conf"

if (( DRY_RUN )); then
  info "would unlock Bitwarden and fetch ${#entries[@]} secret(s) into $SECRETS_ENV_FILE:"
  for e in "${entries[@]}"; do
    read -r var item _ <<<"$e"
    printf '    %-24s <- vault item %s\n' "$var" "$item" >&2
  done
  exit 0
fi

# ---- fetch ----------------------------------------------------------------
# bw comes from mise (config/mise-tools.txt, applied by 25-mise which runs
# first) so the client matches the server's API version. The Arch package is
# only a fallback if mise has not provided one.
ensure_cmd bw bitwarden-cli
source "$OMARCHY_SETUP_LIB/secrets.sh"
on_exit bw_finish

bw_configure_server "$BW_SERVER"
bw_unlock || die "could not unlock the vault (re-run with --skip-secrets to continue without secrets)"

tmp=$(mktemp); register_cleanup "$tmp"; chmod 600 "$tmp"
{
  echo "# Written by omarchy-setup from Bitwarden. Do not edit; do not commit."
  echo "# Re-run the setup to refresh after a rotation."
} >"$tmp"

missing=0
for e in "${entries[@]}"; do
  read -r var item field <<<"$e"
  field=${field:-password}
  if value=$(bw_read "$item" "$field") && [[ -n $value ]]; then
    # %q keeps arbitrary values safe to source; the value is never logged.
    printf 'export %s=%q\n' "$var" "$value" >>"$tmp"
    info "fetched $var"
  else
    warn "not in vault: item '$item' (for $var)"
    missing=1
  fi
done
unset value

# ---- install atomically ---------------------------------------------------
dir=$(dirname "$SECRETS_ENV_FILE")
mkdir -p "$dir" && chmod 700 "$dir"
if [[ -f $SECRETS_ENV_FILE ]] && cmp -s "$tmp" "$SECRETS_ENV_FILE"; then
  info "secrets unchanged"
else
  install -m 0600 "$tmp" "$SECRETS_ENV_FILE"
  ok "wrote $(basename "$SECRETS_ENV_FILE") ($(grep -c '^export ' "$SECRETS_ENV_FILE") values, mode 0600)"
fi

# ---- make them available to shells ----------------------------------------
write_managed_block "$HOME/.bashrc" secrets '#' <<EOF
[ -f "$SECRETS_ENV_FILE" ] && . "$SECRETS_ENV_FILE"
EOF

(( missing )) && warn "some secrets were missing from the vault; see above"
exit 0
