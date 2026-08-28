#!/usr/bin/env bash
# Agent CLIs and dev tools via mise.
#
# These are not pacman packages -- claude, codex, agy, pi and friends all live
# under ~/.local/share/mise/installs. mise-bin itself is an Omarchy base
# package, so it is already present.
#
# `mise use --global` edits ~/.config/mise/config.toml itself; this repo never
# hand-edits that TOML, which keeps the file valid and lets mise own its own
# format.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

pkg_install mise-bin

declare -a tools=()
while read -r tool; do
  [[ -n $tool ]] && tools+=("$tool")
done < <(read_list "$OMARCHY_SETUP_ROOT/config/mise-tools.txt")

(( ${#tools[@]} )) || { info "no mise tools declared"; exit 0; }

# Default to @latest so the config records an explicit request.
declare -a want=()
for t in "${tools[@]}"; do
  [[ $t == *@* ]] && want+=("$t") || want+=("$t@latest")
done

# Only ask mise to add what is missing, so a re-run is quiet.
declare -a missing=()
installed=$(mise ls --global 2>/dev/null | awk '{print $1}')
for t in "${want[@]}"; do
  name=${t%@*}
  grep -qx -- "$name" <<<"$installed" || missing+=("$t")
done

if (( ! ${#missing[@]} )); then
  info "all ${#want[@]} mise tools already configured"
else
  step "adding mise tools: ${missing[*]}"
  run mise use --global --yes "${missing[@]}"
fi

# Installs anything declared but not yet fetched; a no-op when all are present.
run mise install
