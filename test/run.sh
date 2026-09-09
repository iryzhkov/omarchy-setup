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

# ---------------------------------------------------------------- lib/t3.sh --
# The half of the T3 module that decides which versions to run: no network, no
# npm, no GitHub -- just the text those sources return.
section "lib/t3.sh"
(
  source "$ROOT/lib/t3.sh"
  t3_ver_ge 0.0.40 0.0.38 || exit 1
  t3_ver_ge 0.0.38 0.0.38 || exit 2
  t3_ver_ge 0.0.9 0.0.10 && exit 3
  t3_ver_gt 0.10.1 0.10.1 && exit 4
  [[ $(t3_ver_max 0.9.3 0.10.1) == 0.10.1 ]] || exit 5

  ver='t3-steward 0.10.1 (commit abc, built 2026-09-09T06:23:09Z, linux/amd64, tested with T3 0.0.38..0.0.41)'
  [[ $(t3_steward_range <<<"$ver") == "0.0.38 0.0.41" ]] || exit 6
  # A steward too old to declare a range must yield nothing, not a guess.
  [[ -z $(t3_steward_range <<<'t3-steward 0.8.0 (commit abc, linux/amd64)') ]] || exit 7

  versions=$'0.0.37\n0.0.38\n0.0.40\n0.0.41\n0.0.42\n0.0.43-rc.1'
  [[ $(t3_pick_version 0.0.38 0.0.41 <<<"$versions") == 0.0.41 ]] || exit 8
  [[ $(t3_pick_version 0.0.38 0.0.38 <<<"$versions") == 0.0.38 ]] || exit 9
  [[ -z $(t3_pick_version 0.0.44 0.0.50 <<<"$versions") ]] || exit 10
  [[ $(t3_pick_version 0.0.42 0.0.43 <<<"$versions") == 0.0.42 ]] || exit 11

  check='ok    T3 server 0.0.38 (omarchy-pc, linux/x64): supported
ok    shell snapshot: 11 threads, 2 running, provider instances: map[claudeAgent:11]'
  [[ $(t3_server_version <<<"$check") == 0.0.38 ]] || exit 12
  [[ $(t3_running_threads <<<"$check") == 2 ]] || exit 13
  [[ -z $(t3_running_threads <<<'ok    server unreachable') ]] || exit 14
  exit 0
)
case $? in 0) ok "version compare, tested range, pick, check parsing" ;; *) bad "lib/t3.sh step $?" ;; esac

# A failed lookup must be an empty answer, not a failure: the module runs under
# `set -e` with `set -o pipefail`, so a registry that is down or an npm that
# cannot run would otherwise abort the whole update.
section "lib/t3.sh: a broken lookup is empty, not fatal"
printf '#!/bin/sh\nexit 1\n' >"$T/bin/npm"
printf '#!/bin/sh\nexit 7\n' >"$T/bin/curl"
chmod +x "$T/bin/npm" "$T/bin/curl"
(
  set -eo pipefail
  source "$ROOT/lib/t3.sh"
  [[ -z $(t3_npm_versions) ]] || exit 1
  [[ -z $(t3_github_releases owner/repo 1) ]] || exit 2
  # The shape the module uses: assignment from a pipeline, under set -e.
  cand=$(t3_npm_versions | t3_pick_version 0.0.1 9.9.9)
  [[ -z $cand ]] || exit 3
  newest=$(t3_github_releases owner/repo 1 | tail -1)
  [[ -z $newest ]] || exit 4
  exit 0
)
case $? in 0) ok "npm and GitHub failures leave the caller running" ;; *) bad "lib/t3.sh lookup step $?" ;; esac
rm -f "$T/bin/npm" "$T/bin/curl"

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
check "no fence left anywhere" [ -z "$(grep -rl 'omarchy-setup:' "$HOME/.config/hypr" "$HOME/.bashrc" "$HOME/.claude/CLAUDE.md" 2>/dev/null)" ]
check "owned dirs gone" [ ! -e "$HYPR/omarchy-setup" ] && [ ! -e "$HOME/.config/bash/omarchy-setup" ] && [ ! -e "$HOME/.claude/omarchy-setup" ]
check "scripts and hook gone" [ ! -e "$HOME/.local/bin/omarchy-setup" ] && [ ! -e "$HOME/.config/omarchy/hooks/post-update.d/omarchy-setup.hook" ]
check "Omarchy content kept" grep -q 'Omarchy default bindings' "$HYPR/bindings.lua"
check "user CLAUDE.md content kept" grep -qx '# mine' "$HOME/.claude/CLAUDE.md"
check "bashrc return kept" grep -q return "$HOME/.bashrc"

printf '\n%d passed, %d failed\n' "$pass" "$fail"
(( fail == 0 ))
