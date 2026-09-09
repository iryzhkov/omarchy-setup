#!/usr/bin/env bash
# Undo the file management: remove every fence this repo writes and every
# owned file it installs, leaving Omarchy's own files as they were. Honours
# --dry-run. Usually reached as `omarchy-setup --uninstall`.
#
# Deliberately NOT undone, because each was an addition the user may rely on:
# packages, mise tools, shell plugins, agent skills, the ov-mcp checkout and
# its MCP registration, the merged settings.json keys, the nvim checkout,
# secrets.env, the git identity. Remove those by hand if wanted.
set -euo pipefail

OMARCHY_SETUP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OMARCHY_SETUP_LIB="$OMARCHY_SETUP_ROOT/lib"
export OMARCHY_SETUP_ROOT OMARCHY_SETUP_LIB
source "$OMARCHY_SETUP_LIB/common.sh"

while (( $# )); do
  case $1 in
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) sed -n '2,10p' "$0" >&2; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done
export DRY_RUN

remove_owned() {
  local p=$1
  [[ -e $p || -L $p ]] || return 0
  if (( DRY_RUN )); then
    printf '%s  would remove%s %s\n' "$C_DIM" "$C_RESET" "$p" >&2
  else
    rm -rf -- "$p"
    ok "removed $p"
  fi
}

# Every fence, whatever its id, in the files this repo writes into.
sweep_fences() {
  local file=$1 cp=$2 cs=${3:-}
  [[ -f $file ]] || return 0
  local re="^${cp} >>> omarchy-setup:\\([^ ]*\\) >>>"
  [[ -n $cs ]] && re="$re $cs"
  local id
  while read -r id; do
    remove_managed_block "$file" "$id" "$cp" "$cs"
  done < <(sed -n "s/${re}\$/\\1/p" "$file")
}

step "hyprland"
for f in "$HOME"/.config/hypr/*.lua; do sweep_fences "$f" '--'; done
remove_owned "$HOME/.config/hypr/omarchy-setup"

step "shell"
sweep_fences "$HOME/.bashrc" '#'
remove_owned "$HOME/.config/bash/omarchy-setup"
remove_owned "$HOME/.config/uwsm/env.d/90-local-bin-first"

step "scripts"
for f in "$OMARCHY_SETUP_ROOT"/config/bin/*; do
  [[ -f $f ]] && remove_owned "$HOME/.local/bin/$(basename "$f")"
done

step "host files"
# User-side copies only. Files under hosts/<host>/root/ (pacman hooks, local
# patches, system units) stay: they were installed with sudo and removing them
# is a decision to make by hand on that machine.
HOST_DIR="$OMARCHY_SETUP_ROOT/hosts/$SETUP_HOST"
if [[ -d $HOST_DIR ]]; then
  for f in "$HOST_DIR"/systemd/user/*.service; do
    [[ -f $f ]] || continue
    systemctl --user disable --now "$(basename "$f")" >/dev/null 2>&1 || true
  done
  while IFS= read -r -d '' f; do
    rel=${f#"$HOST_DIR"/}
    case $rel in
      bin/*)          remove_owned "$HOME/.local/bin/${rel#bin/}" ;;
      config/*)       remove_owned "$HOME/.config/${rel#config/}" ;;
      share/*)        remove_owned "$HOME/.local/share/${rel#share/}" ;;
      systemd/user/*) remove_owned "$HOME/.config/systemd/user/${rel#systemd/user/}" ;;
    esac
  done < <(find "$HOST_DIR" -type f -print0)
fi

step "hooks"
for f in "$OMARCHY_SETUP_ROOT"/config/hooks/*.d/*.hook; do
  [[ -f $f ]] && remove_owned "$HOME/.config/omarchy/hooks/$(basename "$(dirname "$f")")/$(basename "$f")"
done

step "agents"
sweep_fences "$HOME/.claude/CLAUDE.md" '<!--' '-->'
remove_owned "$HOME/.claude/omarchy-setup"

step "t3 update timer"
# t3code.service and t3-steward.service stay: they are the running system, not
# file management. The timer that checks for a newer pair is ours, and a unit
# left enabled after the checkout is gone would fail every morning.
if command -v systemctl >/dev/null 2>&1 && [[ -f $HOME/.config/systemd/user/t3-update.timer ]]; then
  if (( DRY_RUN )); then
    printf '%s  would run:%s systemctl --user disable --now t3-update.timer\n' "$C_DIM" "$C_RESET" >&2
  else
    systemctl --user disable --now t3-update.timer >/dev/null 2>&1 || true
  fi
fi
remove_owned "$HOME/.config/systemd/user/t3-update.timer"
remove_owned "$HOME/.config/systemd/user/t3-update.service"

step "state"
remove_owned "$OMARCHY_SETUP_STATE/root"
# The T3 pair itself stays installed, like every other package this repo added;
# only the record of which versions it resolved is ours to remove.
remove_owned "$OMARCHY_SETUP_STATE/t3-versions.conf"

hypr_reload
ok "uninstalled what this repo manages; see the header of uninstall.sh for what it leaves"
