#!/usr/bin/env bash
# All cleanup roots are private; stubs prove argument handling precedes scanning.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SCRIPT=${1:-$ROOT/hosts/omarchy-pc/bin/agent-scratch-reap}
T=$(mktemp -d)
trap 'rm -rf -- "$T"' EXIT
mkdir -p "$T/home/.cache/codex-x-target" "$T/tmp/go-build-old" "$T/tmp/go-build-fresh" "$T/stubs"
touch -d '20 days ago' "$T/home/.cache/codex-x-target" "$T/tmp/go-build-old"
export HOME="$T/home" AGENT_SCRATCH_REAP_TMP="$T/tmp"
export STUB_LOG="$T/calls"
real_path=$PATH
for cmd in rm find git df; do
  # shellcheck disable=SC2016 # Expanded by the stub, not this test.
  printf '#!/bin/sh\nprintf "%%s\\n" "%s $*" >>"$STUB_LOG"\nexit 1\n' "$cmd" >"$T/stubs/$cmd"
  chmod +x "$T/stubs/$cmd"
done
fail=0
probe() {
  local expected=$1 stream=$2 rc=0; shift 2
  : >"$STUB_LOG"
  PATH="$T/stubs:$real_path" bash "$SCRIPT" "$@" >"$T/out" 2>"$T/err" || rc=$?
  if [[ $rc != "$expected" ]] || ! grep -q 'Usage: agent-scratch-reap' "$T/$stream" ||
     [[ -s $STUB_LOG ]] || [[ ! -d $T/tmp/go-build-old || ! -d $HOME/.cache/codex-x-target ]]; then
    printf 'FAIL argument probe: %q ' "$@"; printf '(exit %s, expected %s)\n' "$rc" "$expected"
    fail=$((fail + 1))
  fi
  local other=err; [[ $stream == err ]] && other=out
  if [[ -s $T/$other ]]; then
    printf 'FAIL unexpected %s for: %s\n' "$other" "$*"; fail=$((fail + 1))
  fi
  if [[ $expected == 2 ]] && ! grep -qE '^agent-scratch-reap: (unknown option|unexpected argument): ' "$T/err"; then
    printf 'FAIL missing diagnostic: %s\n' "$*"; fail=$((fail + 1))
  fi
}
probe 0 out --help
probe 0 out -h
probe 0 out --dry-run --help
probe 0 out --help --dry-run
probe 0 out --bogus --help
probe 2 err --bogus
probe 2 err -x
probe 2 err --help=x
probe 2 err extra
probe 2 err 'two words'
probe 2 err -- extra
probe 2 err -- --help
# Do not execute real commands against an implementation that failed the guards.
(( fail == 0 )) || exit 1
PATH=$real_path bash "$SCRIPT" --dry-run >"$T/dry"
grep -qF "would remove (go build cache): $T/tmp/go-build-old" "$T/dry"
grep -qF "would remove (codex cargo target): $HOME/.cache/codex-x-target" "$T/dry"
[[ -d $T/tmp/go-build-old && -d $HOME/.cache/codex-x-target && -d $T/tmp/go-build-fresh ]]
PATH=$real_path bash "$SCRIPT" >"$T/reap"
[[ ! -e $T/tmp/go-build-old && ! -e $HOME/.cache/codex-x-target && -d $T/tmp/go-build-fresh ]]
grep -q 'agent-scratch-reap: 2 path(s) removed;' "$T/reap"
# Bare -- is valid and reaps nothing after the preceding cleanup.
PATH=$real_path bash "$SCRIPT" -- >"$T/end"
grep -q 'agent-scratch-reap: 0 path(s) removed;' "$T/end"
printf 'PASS agent-scratch-reap arguments, dry run and cleanup\n'
