#!/usr/bin/env bash
# Themes. Omarchy can install a theme straight from a git repo, so custom ones
# live as URLs here rather than as vendored copies.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

THEME="${OMARCHY_THEME:-kanagawa}"

# Custom themes to install from git before selecting one.
THEME_REPOS=(
  # https://github.com/someone/omarchy-sometheme.git
)

for url in "${THEME_REPOS[@]}"; do
  name=$(basename "$url" .git)
  if omarchy theme list 2>/dev/null | grep -qix -- "$name"; then
    info "theme already installed: $name"
  else
    step "installing theme: $name"
    run omarchy theme install "$url"
  fi
done

current=$(omarchy theme current 2>/dev/null || true)
if [[ ${current,,} == "${THEME,,}" ]]; then
  info "theme already set to $current"
else
  step "setting theme: $THEME"
  run omarchy theme set "$THEME"
fi

# Optional per-host background, e.g. hosts/<host>/background.jpg
if bg=$(host_file background.jpg); then
  run omarchy theme bg set "$bg"
fi
