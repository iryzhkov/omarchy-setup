#!/usr/bin/env bash
# Neovim + my config repo. Safe to re-run: pulls instead of re-cloning.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

NVIM_REPO="${NVIM_REPO:-https://github.com/iryzhkov/nvim-configuration.git}"
NVIM_CONFIG="$HOME/.config/nvim"

# Both are Omarchy base packages: the base list entry is `nvim`, which the
# `neovim` package provides.
ensure_cmd nvim neovim
ensure_cmd git

# On x86 the `omarchy-nvim` package ships a full LazyVim config in
# /etc/skel/.config/nvim, so a fresh user already has ~/.config/nvim before we
# get here; the aarch64 repos have no such package, so there the directory is
# absent. Both are handled: the seeded config is moved aside once, and
# `omarchy-nvim-setup` will not re-seed over a directory that exists, so the
# move does not fight `omarchy update`.
#
# Migrations do still write into whatever lives at ~/.config/nvim -- the
# remote-clipboard migration installs a file there -- which leaves this
# checkout dirty. That is why the pull below refuses to run on a dirty tree
# rather than failing halfway through.

if [[ -d $NVIM_CONFIG/.git ]]; then
  if [[ -n $(git -C "$NVIM_CONFIG" status --porcelain 2>/dev/null) ]]; then
    warn "nvim config has local changes; leaving it alone (commit or discard them to resume updates)"
    git -C "$NVIM_CONFIG" status --short >&2
  else
    info "nvim config already cloned; fetching"
    run git -C "$NVIM_CONFIG" pull --ff-only || warn "could not fast-forward nvim config; leaving as-is"
  fi
else
  if [[ -e $NVIM_CONFIG ]]; then
    stamp="$NVIM_CONFIG.omarchy-setup.bak.$(date +%s)"
    warn "$NVIM_CONFIG exists and is not a git checkout; moving to $(basename "$stamp")"
    run mv "$NVIM_CONFIG" "$stamp"
  fi
  run git clone "$NVIM_REPO" "$NVIM_CONFIG"
fi

# Install plugins headlessly so the first interactive launch is not a wall of
# lazy.nvim progress bars.
#
# `restore` and not `sync`: the repo commits a lazy-lock.json, and that lockfile
# is the pin. `Lazy! sync` *updates* it, which both ignores the pin and leaves
# the checkout dirty -- and a dirty checkout is exactly what stops the next run
# from pulling. `restore` installs what is missing and checks each plugin out at
# the locked commit, so the tree stays clean.
#
# lazy.nvim writes its progress to stdout even with --headless, so both streams
# are dropped; a real failure still shows up as a non-zero exit.
if (( ! DRY_RUN )) && [[ -d $NVIM_CONFIG ]]; then
  if [[ -f $NVIM_CONFIG/lazy-lock.json ]]; then
    step "installing nvim plugins at their locked versions"
    nvim --headless "+Lazy! restore" +qa >/dev/null 2>&1 ||
      warn "lazy restore reported a problem"
  else
    step "installing nvim plugins"
    nvim --headless "+Lazy! sync" +qa >/dev/null 2>&1 ||
      warn "lazy sync reported a problem"
  fi
fi
ok "neovim ready"
