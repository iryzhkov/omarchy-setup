#!/usr/bin/env bash
# Exercises the file-managing modules against a throwaway HOME and a copy of
# the repo, so fixtures can be added freely. Needs bash, coreutils and diff;
# luac is used when present. No Omarchy, no Hyprland: hyprctl is stubbed.
#
#   test/run.sh            run everything
#   VERBOSE=1 test/run.sh  show module output
set -uo pipefail

SRC_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT

# A private copy of the repo, minus .git, so tests can add and remove config.
ROOT="$T/repo"
mkdir -p "$ROOT"
(cd "$SRC_ROOT" && tar --exclude=.git -cf - .) | tar -xf - -C "$ROOT"

export HOME="$T/home"
export OMARCHY_SETUP_ROOT="$ROOT" OMARCHY_SETUP_LIB="$ROOT/lib"
export OMARCHY_SETUP_STATE="$HOME/.local/state/omarchy-setup"
export SETUP_PROFILE=client SETUP_HOST=testhost DRY_RUN=0 ASSUME_YES=1 NO_COLOR=1
mkdir -p "$HOME/.config/hypr" "$T/bin"

# hyprctl stub: reload succeeds, no config errors, no instances.
printf '#!/bin/sh\ncase "$1" in configerrors) echo "no errors";; esac\nexit 0\n' >"$T/bin/hyprctl"
chmod +x "$T/bin/hyprctl"
export PATH="$T/bin:$PATH"
# hypr_reload addresses the session through this variable; pin it so the stub
# path is taken the same way on a desktop and in CI.
export HYPRLAND_INSTANCE_SIGNATURE=stub

HYPR="$HOME/.config/hypr"
for n in hyprland bindings input autostart looknfeel monitors; do
  printf -- '-- Omarchy default %s.lua\n' "$n" >"$HYPR/$n.lua"
done
printf '# bashrc\n[[ $- != *i* ]] && return\n' >"$HOME/.bashrc"

pass=0 fail=0
ok()   { pass=$((pass + 1)); printf '  ok    %s\n' "$*"; }
bad()  { fail=$((fail + 1)); printf '  FAIL  %s\n' "$*" >&2; }
check(){ local d=$1; shift; if "$@" >/dev/null 2>&1; then ok "$d"; else bad "$d"; fi; }
section(){ printf '\n== %s\n' "$*"; }

module() {
  if [[ ${VERBOSE:-0} == 1 ]]; then
    bash "$ROOT/modules/$1" 2>&1 | tee "$T/last.log"
    return "${PIPESTATUS[0]}"
  fi
  bash "$ROOT/modules/$1" >"$T/last.log" 2>&1
}
log_has() { grep -qF -- "$1" "$T/last.log"; }
count()   { grep -cF -- "$1" "$2" 2>/dev/null || true; }
mode()    { stat -c %a "$1"; }

# ------------------------------------------------------------------ syntax
section "bash -n over every script"
while IFS= read -r f; do
  head -c 64 "$f" | grep -qE '^#!.*\b(ba)?sh\b' || continue   # python helpers, pacman hooks
  check "bash -n ${f#"$ROOT"/}" bash -n "$f"
done < <(find "$ROOT" -type f \( -name '*.sh' -o -name '*.hook' -o -path '*/bin/*' -o -path '*/root/usr/local/bin/*' \) | sort)

# -------------------------------------------------------- managed blocks --
section "write_managed_block"
(
  source "$ROOT/lib/common.sh"
  f="$T/mb.conf"; printf 'keep me\n' >"$f"; chmod 0600 "$f"
  printf 'one\n' | write_managed_block "$f" t >/dev/null 2>&1
  printf 'two\n' | write_managed_block "$f" t >/dev/null 2>&1
  [[ $(count '>>> omarchy-setup:t >>>' "$f") == 1 ]] || exit 1
  grep -qx two "$f" || exit 2
  grep -qx one "$f" && exit 3
  grep -qx 'keep me' "$f" || exit 4
  [[ $(mode "$f") == 600 ]] || exit 5
  compgen -G "$f.omarchy-setup.bak.*" >/dev/null || exit 6
  # suffix form
  m="$T/mb.md"; : >"$m"
  printf '@x\n' | write_managed_block "$m" c '<!--' '-->' >/dev/null 2>&1
  grep -qxF -- '<!-- >>> omarchy-setup:c >>> -->' "$m" || exit 7
  remove_managed_block "$m" c '<!--' '-->' >/dev/null 2>&1
  grep -q omarchy-setup "$m" && exit 8
  # symlink target is written, link survives
  real="$T/real.conf"; ln="$T/link.conf"; : >"$real"; ln -s "$real" "$ln"
  printf 'x\n' | write_managed_block "$ln" s >/dev/null 2>&1
  [[ -L $ln ]] || exit 9
  grep -q omarchy-setup:s "$real" || exit 10
  # forged marker refused
  printf '# >>> omarchy-setup:t >>>\n' | write_managed_block "$f" t >/dev/null 2>&1 && exit 11
  exit 0
)
case $? in
  0) ok "rewrite in place, mode kept, backup once, suffix, symlink, forged marker refused" ;;
  *) bad "write_managed_block step $?" ;;
esac

section "write_owned_file"
(
  source "$ROOT/lib/common.sh"
  f="$T/owned/bin"
  printf 'a\n' | write_owned_file "$f" 0755 >/dev/null 2>&1
  [[ $(mode "$f") == 755 ]] || exit 1
  printf 'a\n' | write_owned_file "$f" 0755 2>&1 | grep -q 'already current' || exit 2
  printf 'b\n' | write_owned_file "$f" 2>&1 | grep -q written || exit 3
  [[ $(mode "$f") == 644 ]] || exit 4
)
case $? in 0) ok "mode honoured, idempotent, rewritten on change" ;; *) bad "write_owned_file step $?" ;; esac

# Fleet software moved to UpKeeper; setup must never recreate these entry points.
section "UpKeeper owns fleet software"
check "T3 module removed" test ! -e "$ROOT/modules/common/26-t3.sh"
check "agent module removed" test ! -e "$ROOT/modules/common/45-agents.sh"
check "updater entry point removed" test ! -e "$ROOT/bin/t3-update"

# ----------------------------------------------------- UpKeeper bootstrap --
section "27-upkeeper: clone, self handoff and no-write preview"
origin="$T/fleet-origin"
mkdir -p "$origin/scripts"
git -C "$origin" init -q -b main
git -C "$origin" config user.name Test
git -C "$origin" config user.email test@example.com
cat >"$origin/scripts/upkeeper" <<'PY'
import os
import sys
with open(os.environ["UPKEEPER_TEST_LOG"], "a") as stream:
    stream.write(" ".join(sys.argv[1:]) + "\n")
PY
git -C "$origin" add .
git -C "$origin" commit -qm "Fixture self entry point"
printf '#!/bin/sh\nexit 0\n' >"$T/bin/uv"
printf '#!/bin/sh\nexit 0\n' >"$T/bin/omarchy"
chmod +x "$T/bin/uv" "$T/bin/omarchy"
export UPKEEPER_REPOSITORY="$origin" UPKEEPER_TEST_LOG="$T/self-calls"
check "missing checkout preview" env DRY_RUN=1 bash "$ROOT/modules/common/27-upkeeper.sh"
check "dry run did not clone" test ! -e "$HOME/.local/share/dev-fleet"
check "dry run did not install command" test ! -e "$HOME/.local/bin/upkeeper"
check "bootstrap clones and hands over" module common/27-upkeeper.sh
check "bootstrap clone exists" test -d "$HOME/.local/share/dev-fleet/.git"
check "command points at clone" test "$(readlink "$HOME/.local/bin/upkeeper")" = "$HOME/.local/share/dev-fleet/scripts/upkeeper"
check "real self pull invoked" grep -qx 'pull --self' "$T/self-calls"
check "existing checkout dry run" env DRY_RUN=1 bash "$ROOT/modules/common/27-upkeeper.sh"
check "dry run reaches self" grep -qx 'pull --self --dry-run' "$T/self-calls"
printf 'keep local work\n' >"$HOME/.local/share/dev-fleet/untracked.txt"
check "dirty checkout refused" bash -c '! bash "$1"' _ "$ROOT/modules/common/27-upkeeper.sh"
check "dirty work preserved" grep -qx 'keep local work' "$HOME/.local/share/dev-fleet/untracked.txt"
rm "$HOME/.local/share/dev-fleet/untracked.txt"
# The numeric name is stable, but execution order puts the seam after host setup.
check "selected handoff listed last" bash -c '
  out=$(bash "$1/run.sh" --profile remote --only 27-upkeeper --only 85-hooks --list 2>&1) || exit
  [[ $(printf "%s\n" "$out" | tail -n 1) == *27-upkeeper* ]]
' _ "$ROOT"
# The list command records setup state; later hook tests require no recorded checkout.
rm -f "$HOME/.local/state/omarchy-setup/root" "$HOME/.local/state/omarchy-setup/profile"
unset UPKEEPER_REPOSITORY UPKEEPER_TEST_LOG
rm "$T/bin/uv" "$T/bin/omarchy"

# ------------------------------------------------------------------- hypr --
section "30-hypr: first run"
check "module exits 0" module client/30-hypr.sh
OWNED="$HYPR/omarchy-setup"
check "owned bindings.lua written" test -f "$OWNED/bindings.lua"
check "owned input.lua written" test -f "$OWNED/input.lua"
check "owned header names its source" grep -q 'Source: config/hypr/bindings.lua' "$OWNED/bindings.lua"
check "one fence in bindings.lua" [ "$(count '>>> omarchy-setup:bindings >>>' "$HYPR/bindings.lua")" = 1 ]
check "fence carries the require line" grep -qF 'require("default.hypr.require_optional").module("hypr.omarchy-setup.bindings")' "$HYPR/bindings.lua"
check "Omarchy content kept" grep -q 'Omarchy default bindings' "$HYPR/bindings.lua"
check "untouched files stay untouched" [ ! -e "$HYPR/looknfeel.lua.omarchy-setup.bak."* ]
check "system file mode 0644" [ "$(mode "$HYPR/bindings.lua")" = 644 ]
check "owned file mode 0644" [ "$(mode "$OWNED/bindings.lua")" = 644 ]
check "hyprctl reload ran" log_has "hyprland reloaded cleanly"
if command -v luac >/dev/null; then
  for f in "$OWNED"/*.lua; do check "luac -p $(basename "$f")" luac -p "$f"; done
fi

section "30-hypr: idempotent"
before=$(cat "$HYPR"/*.lua "$OWNED"/*.lua | md5sum)
check "second run exits 0" module client/30-hypr.sh
check "nothing rewritten" log_has "block 'bindings' already current"
check "content identical" [ "$(cat "$HYPR"/*.lua "$OWNED"/*.lua | md5sum)" = "$before" ]

section "30-hypr: host overlay"
mkdir -p "$ROOT/hosts/testhost/hypr"
printf 'hl.config({ misc = { vrr = 1 } })\n' >"$ROOT/hosts/testhost/hypr/input.lua"
check "run" module client/30-hypr.sh
check "host content appended after base" grep -q 'vrr = 1' "$OWNED/input.lua"
check "host marker present" grep -q -- '-- host: testhost' "$OWNED/input.lua"
check "system input.lua still one fence" [ "$(count '>>> omarchy-setup:input >>>' "$HYPR/input.lua")" = 1 ]

section "30-hypr: prune a dropped name"
printf 'hl.config({})\n' >"$ROOT/config/hypr/monitors.lua"
check "add: run" module client/30-hypr.sh
check "add: owned monitors.lua" test -f "$OWNED/monitors.lua"
check "add: fence in monitors.lua" grep -q 'omarchy-setup:monitors' "$HYPR/monitors.lua"
rm "$ROOT/config/hypr/monitors.lua"
check "drop: run" module client/30-hypr.sh
check "drop: owned file removed" [ ! -e "$OWNED/monitors.lua" ]
check "drop: fence removed" [ "$(count 'omarchy-setup' "$HYPR/monitors.lua")" = 0 ]
check "drop: Omarchy content kept" grep -q 'Omarchy default monitors' "$HYPR/monitors.lua"

section "30-hypr: sweep pre-include-model fences"
printf '\n-- >>> omarchy-setup:herdr >>>\no.launch_on_start("herdr server")\n-- <<< omarchy-setup:herdr <<<\n' >>"$HYPR/autostart.lua"
printf '\n-- >>> omarchy-setup:looknfeel >>>\nhl.config({})\n-- <<< omarchy-setup:looknfeel <<<\n' >>"$HYPR/looknfeel.lua"
check "run" module client/30-hypr.sh
check "herdr fence swept" [ "$(count 'omarchy-setup' "$HYPR/autostart.lua")" = 0 ]
check "looknfeel fence swept" [ "$(count 'omarchy-setup' "$HYPR/looknfeel.lua")" = 0 ]
check "current input fence kept" [ "$(count 'omarchy-setup:input' "$HYPR/input.lua")" = 2 ]

if command -v luac >/dev/null; then
  section "30-hypr: syntax guard"
  printf 'this is not lua\n' >"$ROOT/hosts/testhost/hypr/bindings.lua"
  before=$(md5sum "$OWNED/bindings.lua")
  if module client/30-hypr.sh; then bad "module should fail on bad Lua"; else ok "module fails on bad Lua"; fi
  check "names the line" log_has "syntax error"
  check "owned file untouched" [ "$(md5sum "$OWNED/bindings.lua")" = "$before" ]
  rm "$ROOT/hosts/testhost/hypr/bindings.lua"
fi

# ------------------------------------------------------------------- bash --
section "35-bash"
check "run" module common/35-bash.sh
B="$HOME/.config/bash/omarchy-setup"
check "snippets installed" test -f "$B/10-local-bin-first.sh" -a -f "$B/20-bottom-bar.sh" -a -f "$B/starship-bar.toml"
check "uwsm env.d owned file" test -f "$HOME/.config/uwsm/env.d/90-local-bin-first"
check "one fence in .bashrc" [ "$(count '>>> omarchy-setup:bash >>>' "$HOME/.bashrc")" = 1 ]
check "bashrc return line kept" grep -q 'return' "$HOME/.bashrc"
touch "$B/99-stale.sh"
check "rerun" module common/35-bash.sh
check "stale snippet pruned" [ ! -e "$B/99-stale.sh" ]
check "fence not rewritten" log_has "block 'bash' already current"
check "sourcing the snippets in bash works" bash -c 'source "$1"/10-local-bin-first.sh && source "$1"/20-bottom-bar.sh' _ "$B"

# --------------------------------------------------------- scripts, hooks --
section "28-scripts / 85-hooks"
check "scripts run" module common/28-scripts.sh
check "omarchy-setup wrapper executable" test -x "$HOME/.local/bin/omarchy-setup"
check "layout cycle script executable" test -x "$HOME/.local/bin/omarchy-workspace-layout-cycle"
check "hooks run" module common/85-hooks.sh
check "post-update hook executable" test -x "$HOME/.config/omarchy/hooks/post-update.d/omarchy-setup.hook"
check "hook is a no-op without a recorded checkout" bash "$HOME/.config/omarchy/hooks/post-update.d/omarchy-setup.hook"
check "wrapper refuses without a recorded checkout" env -u OMARCHY_SETUP_ROOT bash -c '! "$1"' _ "$HOME/.local/bin/omarchy-setup"

# ------------------------------------------------------------ host files --
section "29-host-files"
check "no host directory is a no-op" env SETUP_HOST=nohost bash -c 'bash "$1" >"$2" 2>&1' _ "$ROOT/modules/common/29-host-files.sh" "$T/last.log"
check "no-op says so" log_has "nothing machine-specific"
HF="$ROOT/hosts/testhost"
mkdir -p "$HF/bin" "$HF/config/app/sub" "$HF/share/tool" "$HF/systemd/user"
printf '#!/bin/sh\necho hi\n' >"$HF/bin/hosttool"; chmod +x "$HF/bin/hosttool"
printf 'key = 1\n' >"$HF/config/app/sub/settings.conf"
printf 'data\n' >"$HF/share/tool/data.txt"
printf '[Unit]\nDescription=t\n[Service]\nExecStart=/bin/true\n[Install]\nWantedBy=default.target\n' >"$HF/systemd/user/hosttool.service"
printf '#!/bin/sh\necho "systemctl $*" >>"%s/systemctl.log"\ncase "$*" in *is-enabled*) exit 1;; esac\nexit 0\n' "$T" >"$T/bin/systemctl"; chmod +x "$T/bin/systemctl"
check "host files run" module common/29-host-files.sh
check "script installed executable" test -x "$HOME/.local/bin/hosttool"
check "config keeps its relative path" test -f "$HOME/.config/app/sub/settings.conf"
check "share file installed" test -f "$HOME/.local/share/tool/data.txt"
check "unit installed 0644" [ "$(mode "$HOME/.config/systemd/user/hosttool.service")" = 644 ]
check "unit enabled" grep -q 'enable --now hosttool.service' "$T/systemctl.log"
check "second run rewrites nothing" module common/29-host-files.sh && ! log_has ': written'
rm -f "$T/bin/systemctl"

# -------------------------------------------------- resident instructions --
# The layer every agent session holds before it reads anything. Nothing used to
# install it, and the generator used to read the installed copies back, so a
# host-local edit became the fleet's instructions. These two sections assert the
# replacement: a module derives the host copies from the checkout, and a check
# reports every installed copy that no longer matches it.
section "31-agent-instructions"
mkdir -p "$HOME/.codex"
check "module runs" module common/31-agent-instructions.sh
check "CLAUDE.md installed from the checkout" cmp -s "$ROOT/config/claude/CLAUDE.md" "$HOME/.claude/omarchy-setup/CLAUDE.md"
check "shared pointer generated" test -f "$HOME/.config/agents/AGENTS.md"
check "reference files generated" test -f "$HOME/.config/agents/t3-steward.md"
check "campaign brief guidance generated" grep -qF "A task prompt is a self-contained execution contract" "$HOME/.config/agents/t3-steward.md"
check "campaign brief link rewritten for shared reference" grep -qF "](t3-campaign-executor-briefs.md)" "$HOME/.config/agents/t3-steward.md"
check "campaign brief reference generated" cmp -s "$ROOT/config/claude/skills/t3-campaign/references/executor-briefs.md" "$HOME/.config/agents/t3-campaign-executor-briefs.md"
check "codex block written" grep -q '<!-- fleet:start -->' "$HOME/.codex/AGENTS.md"
check "second run rewrites nothing" module common/31-agent-instructions.sh && ! log_has ': written'

# A host whose copy drifted is brought back, and a dry run in that state still
# changes nothing.
printf 'stale\n' >"$HOME/.claude/omarchy-setup/CLAUDE.md"
before=$(find "$HOME" -type f -exec md5sum {} + | sort | md5sum)
check "dry run exits 0" env DRY_RUN=1 bash "$ROOT/modules/common/31-agent-instructions.sh"
check "dry run changed nothing" [ "$(find "$HOME" -type f -exec md5sum {} + | sort | md5sum)" = "$before" ]
check "a drifted copy is rewritten" module common/31-agent-instructions.sh
check "and matches the checkout again" cmp -s "$ROOT/config/claude/CLAUDE.md" "$HOME/.claude/omarchy-setup/CLAUDE.md"

section "agents-instructions-gen: the checkout is the only source"
GEN="$ROOT/config/bin/agents-instructions-gen"
check "no checkout is a loud failure" env -u OMARCHY_SETUP_ROOT bash -c '! bash "$1" >"$2" 2>&1' _ "$HOME/.local/bin/agents-instructions-gen" "$T/gen.log"
check "the failure names what it looked for" grep -q 'config/claude/CLAUDE.md' "$T/gen.log"
check "and refuses to read \$HOME" grep -q 'never falls' "$T/gen.log"

section "agents-instructions-gen --check"
# UpKeeper publishes skills from the pinned source checkout; this setup check owns only
# the generated resident instruction artifacts.
check "a converged host passes" bash "$GEN" --root "$ROOT" --check
printf 'stale\n' >"$HOME/.claude/omarchy-setup/CLAUDE.md"
rm -f "$HOME/.config/agents/jocasta.md"
printf 'leftover\n' >"$HOME/.config/agents/agent99.md"
before=$(find "$HOME" -type f -exec md5sum {} + | sort | md5sum)
bash "$GEN" --root "$ROOT" --check >"$T/check.log" 2>&1
check_rc=$?
check "a diverged host exits 3" [ "$check_rc" = 3 ]
check "the check changed nothing" [ "$(find "$HOME" -type f -exec md5sum {} + | sort | md5sum)" = "$before" ]
check "the stale CLAUDE.md is named" grep -q 'omarchy-setup/CLAUDE.md: the host copy differs' "$T/check.log"
check "the missing reference file is named" grep -q 'agents/jocasta.md: absent on this host' "$T/check.log"
check "the file nothing generates is named" grep -q 'agents/agent99.md: present on this host' "$T/check.log"
module common/31-agent-instructions.sh
check "converging clears every difference" bash "$GEN" --root "$ROOT" --check

# ------------------------------------------------------------------ sshd --
# 35-sshd against fakes. sudo runs its command (install without -o/-g, so the
# drop-in lands in a fixture /etc/ssh). ufw keeps its rules in a file, renders
# `status numbered` the way ufw 0.36 does, and follows real ufw's matching:
# insert skips a rule that differs only by comment, delete with a comment
# removes only the rule carrying that comment, delete by number is refused so
# a test fails if the module ever uses one. sshd -t and the reload fail on
# demand.
section "35-sshd: trusted-subnet exemption from the SSH rate limit"
SB="$T/sshbin" UFW_STATE="$T/ufw.rules" SSHD_T="$T/sshd-T" SSH_LOG="$T/ssh-calls"
SSHD_DIR="$T/etc/ssh"
DROPIN="$SSHD_DIR/sshd_config.d/50-omarchy-setup.conf"
mkdir -p "$SB" "$SSHD_T" "$HOME/.ssh" "$SSHD_DIR/sshd_config.d"
printf 'ssh-ed25519 AAAA test\n' >"$HOME/.ssh/authorized_keys"
cat >"$SB/sudo" <<'SH'
#!/usr/bin/env bash
echo "sudo $*" >>"$SSH_LOG"
if [[ $1 == install ]]; then
  args=() skip=0
  for a in "$@"; do
    if (( skip )); then skip=0; continue; fi
    case $a in -o|-g) skip=1 ;; *) args+=("$a") ;; esac
  done
  exec "${args[@]}"
fi
exec "$@"
SH
cat >"$SB/sshd" <<'SH'
#!/usr/bin/env bash
echo "sshd $*" >>"$SSH_LOG"
case $1 in
  -t) [[ ! -e $SSHD_T/t-fail ]] ;;
  -T) cat "$SSHD_T/effective" ;;
  *) exit 1 ;;
esac
SH
cat >"$SB/systemctl" <<'SH'
#!/usr/bin/env bash
echo "systemctl $*" >>"$SSH_LOG"
[[ $1 == reload && -e $SSHD_T/reload-fail ]] && exit 1
exit 0
SH
cat >"$SB/ufw" <<'SH'
#!/usr/bin/env bash
echo "ufw $*" >>"$SSH_LOG"
[[ $1 == --force ]] && shift
unexpected() { echo "fake ufw: unexpected: $*" >&2; exit 1; }
# proto tcp from <subnet> to any port 22 [comment <text>]
spec() {
  [[ $# == 8 || ( $# == 10 && $9 == comment ) ]] || unexpected "$@"
  [[ "$1 $2 $3 $5 $6 $7 $8" == "proto tcp from to any port 22" ]] || unexpected "$@"
  from=$4 comment=${10:-}
}
matching() {   # rules for port 22 from $from, any comment
  awk -F'|' -v f="$from" '$1 == "22/tcp" && $2 == "ALLOW" && $3 == f' "$UFW_STATE"
}
case $1 in
  status)
    [[ -e $UFW_STATE.inactive ]] && { echo 'Status: inactive'; exit 0; }
    printf 'Status: active\n\n     To                         Action      From\n     --                         ------      ----\n'
    n=0
    while IFS='|' read -r to action src comment; do
      n=$((n + 1))
      line=$(printf '[%2d] %-26s %-11s %-26s' "$n" "$to" "$action IN" "$src")
      [[ -n $comment ]] && line+=" # $comment"
      printf '%s\n' "$line"
    done <"$UFW_STATE"
    ;;
  insert)
    pos=$2; [[ $3 == allow ]] || unexpected "$@"; shift 3; spec "$@"
    [[ -n $(matching) ]] && { echo 'Skipping inserting existing rule'; exit 0; }
    (( pos >= 1 && pos <= $(wc -l <"$UFW_STATE") )) || { echo 'ERROR: Invalid position' >&2; exit 1; }
    awk -v p="$pos" -v r="22/tcp|ALLOW|$from|$comment" 'NR == p { print r } { print }' "$UFW_STATE" >"$UFW_STATE.new"
    mv "$UFW_STATE.new" "$UFW_STATE"; echo 'Rule inserted'
    ;;
  delete)
    [[ $2 == allow ]] || unexpected "$@"; shift 2; spec "$@"
    awk -F'|' -v f="$from" -v c="$comment" '
      !done && $1 == "22/tcp" && $2 == "ALLOW" && $3 == f && (c == "" || $4 == c) { done = 1; next }
      { print }' "$UFW_STATE" >"$UFW_STATE.new"
    if cmp -s "$UFW_STATE" "$UFW_STATE.new"; then echo 'Could not delete non-existent rule'; else echo 'Rule deleted'; fi
    mv "$UFW_STATE.new" "$UFW_STATE"
    ;;
  *) unexpected "$@" ;;
esac
SH
printf '#!/bin/sh\necho "ssh-ed25519 AAAA test"\n' >"$SB/curl"
printf '#!/bin/sh\necho "omarchy $*" >>"$SSH_LOG"\n' >"$SB/omarchy"
chmod +x "$SB"/*
export UFW_STATE SSHD_T SSH_LOG OMARCHY_SETUP_SSHD_DIR="$SSHD_DIR"

SSH_CONF="$ROOT/config/ssh.conf"
cp "$SSH_CONF" "$T/ssh.conf.orig"
OWNED=omarchy-sshd-trusted
V4_LIMIT='22/tcp|LIMIT|Anywhere|omarchy-sshd'
V6_LIMIT='22/tcp (v6)|LIMIT|Anywhere (v6)|omarchy-sshd'
# A hardened host with no drop-in of ours yet and the default subnet list.
sshd_reset() {
  rm -f "$SSHD_T"/* "$SSHD_DIR"/sshd_config.d/*
  printf 'passwordauthentication no\nkbdinteractiveauthentication no\npermitrootlogin no\npubkeyauthentication yes\n' >"$SSHD_T/effective"
  printf 'Include sshd_config.d/*.conf\nPort 22\n' >"$SSHD_DIR/sshd_config"
  cp "$T/ssh.conf.orig" "$SSH_CONF"
}
# The rules omarchy's sshd setup leaves on normandy, before any exemption.
ufw_omarchy() {
  rm -f "$UFW_STATE.inactive"
  printf '%s\n' '53317/udp|ALLOW|Anywhere|' "$V4_LIMIT" 'Anywhere on nebula1|ALLOW|Anywhere|' "$V6_LIMIT" >"$UFW_STATE"
}
# Puts a hand-added rule at the top, where an operator would insert it.
ufw_hand_added() { { printf '22/tcp|ALLOW|%s|%s\n' "$1" "$2"; cat "$UFW_STATE"; } >"$T/ufw.new"; mv "$T/ufw.new" "$UFW_STATE"; }
subnets() { cp "$T/ssh.conf.orig" "$SSH_CONF"; printf 'SSH_TRUSTED_SUBNETS=(%s)\n' "$*" >>"$SSH_CONF"; }
sshd_module() { : >"$SSH_LOG"; PATH="$SB:$PATH" module remote/35-sshd.sh; }
refused() { ! sshd_module; }
rule_at() {   # line of the first ALLOW from $1, with comment $2 when given
  awk -F'|' -v f="$1" -v c="${2-}" -v any="${2+no}" \
    '$1 == "22/tcp" && $2 == "ALLOW" && $3 == f && (any != "no" || $4 == c) { print NR; exit }' "$UFW_STATE"
}
limit_at() { grep -nxF -- "$V4_LIMIT" "$UFW_STATE" | head -n 1 | cut -d: -f1; }
owned_ahead() { local a; a=$(rule_at "$1" "$OWNED"); [[ -n $a && $a -lt $(limit_at) ]]; }
no_owned() { ! grep -q "|$OWNED\$" "$UFW_STATE"; }
no_rule_change() { ! grep -qE '^ufw (--force )?(insert|allow|delete)' "$SSH_LOG"; }
only_spec_mutations() { ! grep -qE '^ufw (--force )?(allow|delete [0-9])' "$SSH_LOG"; }
unchanged() { [ "$(md5sum <"$UFW_STATE")" = "$1" ]; }
limits_kept() { grep -qxF -- "$V4_LIMIT" "$UFW_STATE" && grep -qxF -- "$V6_LIMIT" "$UFW_STATE" && [ "$(grep -c '^22/tcp|LIMIT|Anywhere|' "$UFW_STATE")" = 1 ]; }
reloaded() { grep -qx 'sshd -t' "$SSH_LOG" && grep -qx 'systemctl reload sshd' "$SSH_LOG"; }

sshd_reset; ufw_omarchy
check "first apply exits 0" sshd_module
check "VLAN 70 owned ALLOW ahead of the LIMIT" owned_ahead 192.168.70.0/24
check "VLAN 90 owned ALLOW ahead of the LIMIT" owned_ahead 192.168.90.0/24
check "configured order kept" [ "$(rule_at 192.168.70.0/24)" -lt "$(rule_at 192.168.90.0/24)" ]
check "IPv4 LIMIT kept once, IPv6 LIMIT row survives" limits_kept
check "nebula rule untouched" grep -qx 'Anywhere on nebula1|ALLOW|Anywhere|' "$UFW_STATE"
check "no append, no numbered delete" only_spec_mutations
check "drop-in installed" grep -qx 'PasswordAuthentication no' "$DROPIN"
check "validated and reloaded" reloaded
before=$(md5sum <"$UFW_STATE")
check "second apply exits 0" sshd_module
check "second apply changes no rule" no_rule_change
check "no duplicates, order kept" unchanged "$before"
check "unchanged drop-in: still validated and reloaded" reloaded

# normandy as Igor left it on 2026-10-01: untagged hand-added rules, 90
# before 70, with their own comments. They are reported, never adopted.
sshd_reset; ufw_omarchy
ufw_hand_added 192.168.70.0/24 'ssh trusted VLAN 70'; ufw_hand_added 192.168.90.0/24 'ssh gaming VLAN 90'
before=$(md5sum <"$UFW_STATE")
check "hand-added rules: apply exits 0" sshd_module
check "hand-added rules: nothing changed" unchanged "$before"
check "hand-added rules: reported as unmanaged" log_has "unmanaged exemption: 192.168.90.0/24"

# The gate: Match blocks anywhere in the configuration, or any of the three
# settings not "no", refuse the exemption outright.
sshd_reset; ufw_omarchy; before=$(md5sum <"$UFW_STATE")
printf 'Match Address 10.0.0.0/8\n  PasswordAuthentication yes\n' >"$SSHD_DIR/sshd_config.d/60-lan.conf"
check "Match in a drop-in: refused" refused
check "refusal names the file" log_has "60-lan.conf"
check "refusal says what to remove" log_has "remove every Match block"
check "refusal explains the trade-off" log_has "removes brute-force limiting"
check "Match: no rule change" unchanged "$before"
sshd_reset; printf '  match user git\n    ForceCommand true\n' >>"$SSHD_DIR/sshd_config"
check "indented lower-case Match in sshd_config: refused" refused
check "Match in sshd_config: no rule change" unchanged "$before"
sshd_reset; printf 'passwordauthentication yes\nkbdinteractiveauthentication no\npermitrootlogin no\n' >"$SSHD_T/effective"
check "password auth on: refused" refused
check "refusal names the setting" log_has "passwordauthentication is yes, not no"
sshd_reset; printf 'passwordauthentication no\nkbdinteractiveauthentication no\npermitrootlogin prohibit-password\n' >"$SSHD_T/effective"
check "root login by key: refused" refused
check "refusal names root login" log_has "permitrootlogin is prohibit-password, not no"
check "gate refusals: no rule change" unchanged "$before"

# The running daemon, not the disk: validation and reload happen in this run.
sshd_reset; ufw_omarchy; sshd_module; ufw_omarchy; cp "$DROPIN" "$T/dropin.before"
touch "$SSHD_T/reload-fail"
check "reload failure, unchanged drop-in: refused" refused
check "reload failure: no exemption granted" no_owned
check "reload failure: refusal names the reload" log_has "reload sshd failed"
check "reload failure: drop-in as it was" cmp -s "$DROPIN" "$T/dropin.before"
sshd_reset; ufw_omarchy; printf '# an older drop-in\nPasswordAuthentication no\n' >"$DROPIN"; cp "$DROPIN" "$T/dropin.before"
touch "$SSHD_T/t-fail"
check "validation failure after a drop-in change: refused" refused
check "validation failure: previous drop-in restored" cmp -s "$DROPIN" "$T/dropin.before"
check "validation failure: never reloaded" bash -c '! grep -qx "systemctl reload sshd" "$1"' _ "$SSH_LOG"
check "validation failure: no exemption granted" no_owned
sshd_reset; ufw_omarchy; touch "$SSHD_T/t-fail"
check "validation failure with no previous drop-in: refused" refused
check "validation failure: new drop-in removed" test ! -e "$DROPIN"

# Revocation: owned rules follow the desired set; untagged rules stay.
sshd_reset; ufw_omarchy; sshd_module
subnets 192.168.70.0/24
check "subnet removed: apply exits 0" sshd_module
check "subnet removed: kept subnet still owned ahead" owned_ahead 192.168.70.0/24
check "subnet removed: its owned rule revoked" [ -z "$(rule_at 192.168.90.0/24)" ]
check "subnet removed: deleted by specification" only_spec_mutations
ufw_hand_added 10.20.0.0/24 'hand added'
subnets
check "list emptied: apply exits 0" sshd_module
check "list emptied: owned rules revoked" no_owned
check "list emptied: untagged rule kept" grep -qx '22/tcp|ALLOW|10.20.0.0/24|hand added' "$UFW_STATE"
check "list emptied: untagged rule reported" log_has "unmanaged exemption: 10.20.0.0/24"
check "list emptied: LIMIT rows kept" limits_kept
sshd_reset; ufw_omarchy; sshd_module; ufw_hand_added 10.20.0.0/24 'hand added'
printf 'passwordauthentication yes\nkbdinteractiveauthentication no\npermitrootlogin no\n' >"$SSHD_T/effective"
check "gate failing after a prior apply: refused" refused
check "gate failing: owned rules revoked" no_owned
check "gate failing: untagged rule kept" grep -qx '22/tcp|ALLOW|10.20.0.0/24|hand added' "$UFW_STATE"
check "gate failing: untagged rule reported" log_has "unmanaged exemption: 10.20.0.0/24"
check "gate failing: LIMIT rows kept" limits_kept

# Fail closed on the firewall baseline.
sshd_reset; printf '%s\n' '53317/udp|ALLOW|Anywhere|' 'Anywhere on nebula1|ALLOW|Anywhere|' >"$UFW_STATE"
check "missing LIMIT: refused" refused
check "missing LIMIT: nothing appended" no_rule_change
check "missing LIMIT: refusal names it" log_has "22/tcp LIMIT Anywhere"
sshd_reset; ufw_omarchy; printf '22|LIMIT|Anywhere|\n' >>"$UFW_STATE"
check "two LIMIT rules: refused" refused
check "two LIMIT rules: no rule change" no_rule_change
sshd_reset; ufw_omarchy; ufw_hand_added Anywhere ''
check "port 22 already open to Anywhere: refused" refused
sshd_reset; ufw_omarchy; printf '22/tcp|ALLOW|192.168.70.0/24|%s\n' "$OWNED" >>"$UFW_STATE"
check "owned rule behind the LIMIT: refused" refused
check "owned rule behind the LIMIT: nothing deleted" no_rule_change
sshd_reset; ufw_omarchy; touch "$UFW_STATE.inactive"
check "ufw inactive: refused" refused
check "ufw inactive: no rule change" no_rule_change
rm -f "$UFW_STATE.inactive"

# The subnet list is validated whole before anything is touched.
for bad_subnet in 192.168.70.0/33 256.168.70.0/24 192.168.70.5/24 10.0.0.0/8 192.168.70.0 '"1.2.3.0/24;reboot"'; do
  sshd_reset; ufw_omarchy; subnets 192.168.90.0/24 "$bad_subnet"
  check "invalid subnet $bad_subnet: refused" refused
  check "invalid subnet $bad_subnet: refused before any change" bash -c '! grep -qE "^(omarchy|ufw (insert|delete)|sudo install)" "$1"' _ "$SSH_LOG"
done
sshd_reset; ufw_omarchy; subnets 192.168.070.0/24 192.168.70.0/24
check "leading zeros and duplicates: apply exits 0" sshd_module
check "canonical subnet owned once" [ "$(grep -c '|192.168.70.0/24|' "$UFW_STATE")" = 1 ]
check "canonical form used" bash -c '! grep -q 070 "$1"' _ "$UFW_STATE"

sshd_reset; ufw_omarchy; before=$(md5sum <"$UFW_STATE")
check "dry run exits 0" env DRY_RUN=1 bash -c 'PATH="$1:$PATH" bash "$2"' _ "$SB" "$ROOT/modules/remote/35-sshd.sh"
check "dry run changes no rule" unchanged "$before"
check "dry run writes no drop-in" test ! -e "$DROPIN"
sshd_reset

# ---------------------------------------------------------------- dry run --
section "dry run changes nothing"
rm -rf "$HOME/.config/hypr/omarchy-setup"
printf -- '-- Omarchy default bindings.lua\n' >"$HYPR/bindings.lua"
before=$(find "$HOME" -type f -exec md5sum {} + | sort | md5sum)
check "dry run exits 0" env DRY_RUN=1 bash "$ROOT/modules/client/30-hypr.sh"
check "no file changed" [ "$(find "$HOME" -type f -exec md5sum {} + | sort | md5sum)" = "$before" ]
check "owned dir not created" [ ! -e "$HOME/.config/hypr/omarchy-setup" ]

# -------------------------------------------------------------- uninstall --
section "uninstall"
module client/30-hypr.sh; module common/35-bash.sh; module common/28-scripts.sh; module common/85-hooks.sh
mkdir -p "$HOME/.claude"; printf '# mine\n' >"$HOME/.claude/CLAUDE.md"
printf '@x\n' | (source "$ROOT/lib/common.sh"; write_managed_block "$HOME/.claude/CLAUDE.md" claude '<!--' '-->') >/dev/null 2>&1
before=$(find "$HOME" -type f -exec md5sum {} + | sort | md5sum)
check "dry run exits 0" bash "$ROOT/uninstall.sh" --dry-run
check "dry run changed nothing" [ "$(find "$HOME" -type f -exec md5sum {} + | sort | md5sum)" = "$before" ]
check "uninstall exits 0" bash "$ROOT/uninstall.sh"
check "host files gone" [ ! -e "$HOME/.local/bin/hosttool" ] && [ ! -e "$HOME/.config/app/sub/settings.conf" ] && [ ! -e "$HOME/.config/systemd/user/hosttool.service" ]
check "no setup fence left" [ -z "$(grep -rl 'omarchy-setup:' "$HOME/.config/hypr" "$HOME/.bashrc" 2>/dev/null)" ]
check "UpKeeper agent import preserved" grep -q 'omarchy-setup:claude' "$HOME/.claude/CLAUDE.md"
check "owned dirs gone" [ ! -e "$HYPR/omarchy-setup" ] && [ ! -e "$HOME/.config/bash/omarchy-setup" ]
check "scripts and hook gone" [ ! -e "$HOME/.local/bin/omarchy-setup" ] && [ ! -e "$HOME/.config/omarchy/hooks/post-update.d/omarchy-setup.hook" ]
check "Omarchy content kept" grep -q 'Omarchy default bindings' "$HYPR/bindings.lua"
check "user CLAUDE.md content kept" grep -qx '# mine' "$HOME/.claude/CLAUDE.md"
check "bashrc return kept" grep -q return "$HOME/.bashrc"

printf '\n%d passed, %d failed\n' "$pass" "$fail"
(( fail == 0 ))
