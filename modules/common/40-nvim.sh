#!/usr/bin/env bash
# Neovim + my config repo. Safe to re-run: pulls instead of re-cloning.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

NVIM_REPO="${NVIM_REPO:-https://github.com/iryzhkov/nvim-configuration.git}"
NVIM_CONFIG="$HOME/.config/nvim"

# Both are Omarchy base packages: the base list entry is `nvim`, which the
# `neovim` package provides.
ensure_cmd nvim neovim
ensure_cmd git

# omarchy-nvim (also in the base list) ships Omarchy's default nvim config. It
# resolves to nothing in the aarch64 repos so it is absent here, but on x86 it
# installs and may seed ~/.config/nvim -- which the clone below then moves
# aside. That is handled, just noisy; nothing is lost.

if [[ -d $NVIM_CONFIG/.git ]]; then
  info "nvim config already cloned; fetching"
  run git -C "$NVIM_CONFIG" pull --ff-only || warn "could not fast-forward nvim config; leaving as-is"
elif [[ -e $NVIM_CONFIG ]]; then
  stamp="$NVIM_CONFIG.omarchy-setup.bak.$(date +%s)"
  warn "$NVIM_CONFIG exists and is not a git checkout; moving to $(basename "$stamp")"
  run mv "$NVIM_CONFIG" "$stamp"
  run git clone "$NVIM_REPO" "$NVIM_CONFIG"
else
  run git clone "$NVIM_REPO" "$NVIM_CONFIG"
fi

# Install plugins headlessly so the first interactive launch is not a wall of
# lazy.nvim progress bars.
if (( ! DRY_RUN )); then
  nvim --headless "+Lazy! sync" +qa 2>/dev/null || warn "lazy sync reported a problem"
fi
ok "neovim ready"
