#!/usr/bin/env bash
# Per-machine files: everything under hosts/<hostname>/ that is not a Hyprland
# fragment (30-hypr handles those). Nothing runs on a machine that has no
# directory here. The layout mirrors where each file lands:
#
#   hosts/<host>/bin/<name>          -> ~/.local/bin/<name>            (owned, 0755)
#   hosts/<host>/config/<path>       -> ~/.config/<path>               (owned)
#   hosts/<host>/share/<path>        -> ~/.local/share/<path>          (owned)
#   hosts/<host>/systemd/user/<unit> -> ~/.config/systemd/user/<unit>  (owned, enabled)
#   hosts/<host>/root/<path>         -> /<path>                        (sudo install, root:root)
#
# Files under root/ keep their mode from the repo (patches and hooks 0644,
# scripts 0755) and are only written when they differ, so a run with nothing to
# change never asks for a password. System units under root/ are enabled after
# a daemon-reload; pacman hooks and the local omarchy patches are picked up by
# pacman on the next transaction.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

HOST_DIR="$OMARCHY_SETUP_ROOT/hosts/$SETUP_HOST"
if [[ ! -d $HOST_DIR ]]; then
  info "no hosts/$SETUP_HOST directory; nothing machine-specific to install"
  exit 0
fi

# install_tree <source-dir> <dest-dir> [mode]
# Owned copies of every file in a tree, keeping the relative path.
install_tree() {
  local src=$1 dest=$2 mode=${3:-} f rel m
  [[ -d $src ]] || return 0
  while IFS= read -r -d '' f; do
    rel=${f#"$src"/}
    m=$mode
    [[ -z $m ]] && { [[ -x $f ]] && m=0755 || m=0644; }
    write_owned_file "$dest/$rel" "$m" <"$f"
  done < <(find "$src" -type f -print0 | sort -z)
}

step "machine-specific files for $SETUP_HOST"
install_tree "$HOST_DIR/bin"    "$HOME/.local/bin"   0755
install_tree "$HOST_DIR/config" "$HOME/.config"
install_tree "$HOST_DIR/share"  "$HOME/.local/share"

# ---- user units --------------------------------------------------------------
if [[ -d $HOST_DIR/systemd/user ]]; then
  install_tree "$HOST_DIR/systemd/user" "$HOME/.config/systemd/user" 0644
  run systemctl --user daemon-reload
  for f in "$HOST_DIR"/systemd/user/*.service; do
    [[ -f $f ]] || continue
    unit=$(basename "$f")
    grep -q '^\[Install\]' "$f" || continue
    if systemctl --user is-enabled -q "$unit" 2>/dev/null; then
      info "$unit: already enabled"
    else
      run systemctl --user enable --now "$unit"
    fi
  done
fi

# ---- root-owned files --------------------------------------------------------
# Compared before touching sudo, so an unchanged machine needs no password.
if [[ -d $HOST_DIR/root ]]; then
  changed=()
  while IFS= read -r -d '' f; do
    rel=${f#"$HOST_DIR/root"}
    if [[ -f $rel ]] && cmp -s "$f" "$rel"; then
      info "$(basename "$rel"): already current"
    else
      changed+=("$f")
    fi
  done < <(find "$HOST_DIR/root" -type f -print0 | sort -z)

  if (( ${#changed[@]} )); then
    for f in "${changed[@]}"; do
      rel=${f#"$HOST_DIR/root"}
      [[ -x $f ]] && m=0755 || m=0644
      run sudo install -D -m "$m" -o root -g root "$f" "$rel"
      ok "$(basename "$rel"): written to $(dirname "$rel")"
    done
    if compgen -G "$HOST_DIR/root/etc/systemd/system/*.service" >/dev/null; then
      run sudo systemctl daemon-reload
    fi
  fi

  for f in "$HOST_DIR"/root/etc/systemd/system/*.service; do
    [[ -f $f ]] || continue
    unit=$(basename "$f")
    grep -q '^\[Install\]' "$f" || continue
    if systemctl is-enabled -q "$unit" 2>/dev/null; then
      info "$unit: already enabled"
    else
      run sudo systemctl enable --now "$unit"
    fi
  done
fi
