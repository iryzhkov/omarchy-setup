#!/usr/bin/env bash
# Omarchy shell plugins, from config/plugins.txt.
#
# Client-only: these are bar widgets and desktop UI, so they have nothing to do
# on a headless box.
#
# Installing a plugin does not place it on the bar. Bar layout is a non-goal
# for this repo -- `omarchy plugin enable` writes shell.json -- so enabling is
# opt-in per plugin via an explicit id in the config.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

PLUGIN_DIR="$HOME/.config/omarchy/plugins"

# Match on the git remote rather than the plugin id: the id is only knowable
# after installing, but the URL is what we have up front.
plugin_installed_from() {
  local url=$1 d
  for d in "$PLUGIN_DIR"/*/; do
    [[ -d ${d}.git ]] || continue
    [[ $(git -C "$d" remote get-url origin 2>/dev/null) == "$url" ]] && return 0
  done
  return 1
}

installed=0 added=0
while read -r url marker; do
  [[ -n $url ]] || continue
  # Only an explicit `enable:<id>` opts into touching the bar.
  id=""
  [[ $marker == enable:* ]] && id=${marker#enable:}
  if plugin_installed_from "$url"; then
    info "plugin already installed: ${id:-$(basename "$url" .git)}"
    installed=$((installed + 1))
  else
    step "installing plugin: ${id:-$url}"
    # </dev/null: stdin is the list being looped over; a child that reads it
    # would swallow the remaining lines.
    run omarchy plugin add "$url" --yes </dev/null || { warn "could not add $url"; continue; }
    added=$((added + 1))
  fi

  if [[ -n $id ]]; then
    if omarchy plugin list 2>/dev/null | grep -qF "$id"; then
      step "enabling on the bar: $id"
      run omarchy plugin enable "$id" || warn "could not enable $id"
    else
      warn "plugin id not found after install: $id"
    fi
  fi
done < <(read_list "$OMARCHY_SETUP_ROOT/config/plugins.txt")

info "plugins: $installed already present, $added added"
