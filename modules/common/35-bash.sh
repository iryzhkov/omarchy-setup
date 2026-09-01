#!/usr/bin/env bash
# Shell extras, with the include model:
#
#   config/bash/NN-<name>.sh   ->  ~/.config/bash/omarchy-setup/NN-<name>.sh
#   config/bash/*.toml         ->  ~/.config/bash/omarchy-setup/*.toml
#   ~/.bashrc                  gets one fenced loop that sources the *.sh files
#
# The owned directory is fully replaced on every run, and the fence in .bashrc
# is constant, so adding a shell snippet never touches .bashrc again.
#
# What lives there today:
#   10-local-bin-first.sh   ~/.local/bin ahead of /usr/bin (Omarchy appends it)
#   20-bottom-bar.sh        terminal bottom status line, driven by starship
#                           against starship-bar.toml alongside it
#
# Ordering caveat: the fence is appended at the end of .bashrc, after Omarchy's
# `[[ $- != *i* ]] && return`, so it runs for interactive shells only. The PATH
# reorder still reaches the whole graphical session through
# ~/.config/uwsm/env.d/90-local-bin-first, which uwsm sources at login -- that
# file is owned outright too, since env.d is include-by-design.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

SRC="$OMARCHY_SETUP_ROOT/config/bash"
OWNED="$HOME/.config/bash/omarchy-setup"

declare -A keep=()
for f in "$SRC"/*.sh "$SRC"/*.toml; do
  [[ -f $f ]] || continue
  name=$(basename "$f")
  keep[$name]=1
  write_owned_file "$OWNED/$name" <"$f"
done

# Stale snippets would keep being sourced by the loop below; remove them.
for f in "$OWNED"/*; do
  [[ -f $f ]] || continue
  name=$(basename "$f")
  [[ -n ${keep[$name]:-} ]] && continue
  info "removing stale shell snippet: $name"
  run rm -f -- "$f"
done

write_owned_file "$HOME/.config/uwsm/env.d/90-local-bin-first" <"$SRC/uwsm-90-local-bin-first"

write_managed_block "$HOME/.bashrc" bash '#' <<'BASH'
for __f in "$HOME"/.config/bash/omarchy-setup/*.sh; do [ -r "$__f" ] && . "$__f"; done; unset __f
BASH
