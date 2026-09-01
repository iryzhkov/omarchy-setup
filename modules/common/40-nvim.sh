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

# Build tools the config's plugins need (telescope-fzf-native, LuaSnip's
# jsregexp, tree-sitter parsers). Neither is in Omarchy's base list, though
# gcc usually arrives as a dependency of something else.
for pair in make:make cc:gcc; do
  command -v "${pair%%:*}" >/dev/null 2>&1 || pkg_install "${pair#*:}"
done

# Let the config repo finish its own setup: my config ships a setup.sh that
# restores plugins from lazy-lock.json, installs tree-sitter parsers and Mason
# packages, and links its Omarchy theme-set hook. Its output is a wall of
# lazy.nvim progress, so it goes to a log; a failure names the log.
#
# A config without setup.sh gets the old inline plugin install. `restore` and
# not `sync`: the lockfile is the pin, and `sync` would both ignore it and
# leave the checkout dirty, which is what stops the next run from pulling.
if [[ -x $NVIM_CONFIG/setup.sh ]]; then
  step "running the nvim config's setup.sh"
  nvim_log="$OMARCHY_SETUP_STATE/nvim-setup.log"
  if (( DRY_RUN )); then
    run "$NVIM_CONFIG/setup.sh"
  else
    mkdir -p "$OMARCHY_SETUP_STATE"
    "$NVIM_CONFIG/setup.sh" >"$nvim_log" 2>&1 ||
      warn "nvim setup.sh reported a problem; see $nvim_log"
  fi
elif (( ! DRY_RUN )) && [[ -d $NVIM_CONFIG ]]; then
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
