#!/usr/bin/env bash
# Applies Hyprland config as fenced blocks appended to Omarchy's own files, so
# `omarchy update` migrations keep patching everything outside the fences.
#
# Content lives in real .lua files, not in this script:
#   config/hypr/<name>.lua          shared by every machine
#   hosts/<host>/hypr/<name>.lua    this machine only, appended after the base
#
# Each <name> becomes one managed block in ~/.config/hypr/<name>.lua.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

HYPR="$HOME/.config/hypr"
BASE_DIR="$OMARCHY_SETUP_ROOT/config/hypr"
HOST_DIR="$OMARCHY_SETUP_ROOT/hosts/$SETUP_HOST/hypr"

# Union of config names from the shared dir and this host's dir.
declare -A names=()
for d in "$BASE_DIR" "$HOST_DIR"; do
  [[ -d $d ]] || continue
  for f in "$d"/*.lua; do
    [[ -f $f ]] && names["$(basename "$f" .lua)"]=1
  done
done

(( ${#names[@]} )) || { info "no hypr config to apply"; exit 0; }

applied=0
for name in $(printf '%s\n' "${!names[@]}" | sort); do
  base="$BASE_DIR/$name.lua"
  host="$HOST_DIR/$name.lua"
  target="$HYPR/$name.lua"

  if [[ ! -f $target ]]; then
    warn "no such Omarchy config: $target (skipping '$name')"
    continue
  fi

  {
    [[ -f $base ]] && cat "$base"
    if [[ -f $host ]]; then
      [[ -f $base ]] && printf '\n'
      printf -- '-- host: %s\n' "$SETUP_HOST"
      cat "$host"
    fi
  } | write_managed_block "$target" "$name" '--'
  applied=1
done

if (( applied )); then
  hypr_reload
fi
