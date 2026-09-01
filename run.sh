#!/usr/bin/env bash
# Orchestrator: resolves the profile, then runs the applicable modules in order.
#
# Modules are plain scripts in modules/{common,<profile>}/, merged and ordered
# by their numeric prefix, so a remote-only 35-sshd.sh slots between the shared
# 30- and 40- steps. Each module is idempotent and independently runnable.

set -euo pipefail

OMARCHY_SETUP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OMARCHY_SETUP_LIB="$OMARCHY_SETUP_ROOT/lib"
export OMARCHY_SETUP_ROOT OMARCHY_SETUP_LIB
source "$OMARCHY_SETUP_LIB/common.sh"

usage() {
  cat >&2 <<'USAGE'
usage: run.sh [options]

  --profile client|remote   which kind of machine this is (remembered after
                            the first run; asked interactively if unset)
  --host <name>             override the detected hostname for hosts/ lookups
  --only <pattern>...       run only modules whose name matches
  --skip <pattern>...       skip modules whose name matches
  --list                    show what would run, then exit
  --dry-run                 print actions without changing anything
  --yes                     assume yes for confirmations
  --skip-secrets            do not touch the vault or write any secrets
  --remove-packages         uninstall what config/remove/*.txt lists (default: report only)
  --uninstall               remove every fence and owned file this repo wrote, then exit

  Personal values (defaults in config/defaults.conf; env vars also work):
  --bw-server <url>         Bitwarden/Vaultwarden server ('' for the cloud)
  --github-user <name>      GitHub user whose SSH keys to authorize
  --git-name <name>         git user.name
  --git-email <addr>        git user.email
  --nvim-repo <url>         Neovim config repo
  -h, --help                this message
USAGE
}

declare -a ONLY=() SKIP=()
LIST=0
while (( $# )); do
  case $1 in
    --profile) SETUP_PROFILE=${2:?}; shift 2 ;;
    --host)    SETUP_HOST=${2:?};    shift 2 ;;
    --only)    ONLY+=("${2:?}");     shift 2 ;;
    --skip)    SKIP+=("${2:?}");     shift 2 ;;
    --list)    LIST=1;               shift ;;
    --dry-run) DRY_RUN=1;            shift ;;
    --yes|-y)  ASSUME_YES=1;         shift ;;
    --skip-secrets) SKIP_SECRETS=1;  shift ;;
    --remove-packages) REMOVE_PACKAGES=1; shift ;;
    --uninstall) shift; exec "$OMARCHY_SETUP_ROOT/uninstall.sh" "$@" ;;
    --bw-server)   BW_SERVER=${2?};   shift 2 ;;
    --github-user) GITHUB_USER=${2:?};shift 2 ;;
    --git-name)    GIT_NAME=${2:?};   shift 2 ;;
    --git-email)   GIT_EMAIL=${2:?};  shift 2 ;;
    --nvim-repo)   NVIM_REPO=${2:?};  shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
done

require_not_root
require_omarchy

# ---- profile: remembered across runs so re-running needs no flags ----------
PROFILE_FILE="$OMARCHY_SETUP_STATE/profile"
if [[ -z $SETUP_PROFILE && -f $PROFILE_FILE ]]; then
  SETUP_PROFILE=$(<"$PROFILE_FILE")
fi
if [[ -z $SETUP_PROFILE ]]; then
  [[ -t 0 ]] || die "no profile set; pass --profile client|remote"
  printf '\n  1) client  - workstation you sit at (GUI, theming, secrets)\n' >&2
  printf '  2) remote  - headless box reached over ssh\n\n' >&2
  read -r -p "profile [1/2] " reply
  case $reply in
    1) SETUP_PROFILE=client ;;
    2) SETUP_PROFILE=remote ;;
    *) die "pick 1 or 2" ;;
  esac
fi
[[ $SETUP_PROFILE == client || $SETUP_PROFILE == remote ]] ||
  die "unknown profile: $SETUP_PROFILE"
if (( ! DRY_RUN )); then
  mkdir -p "$OMARCHY_SETUP_STATE"
  printf '%s\n' "$SETUP_PROFILE" >"$PROFILE_FILE"
fi

mkdir -p "$OMARCHY_SETUP_STATE"
# Where this checkout lives, for the omarchy-setup wrapper and the
# post-update hook. Recorded on every real run so a moved checkout is found.
(( DRY_RUN )) || printf '%s\n' "$OMARCHY_SETUP_ROOT" >"$OMARCHY_SETUP_STATE/root"
OMARCHY_SETUP_LOGFILE="$OMARCHY_SETUP_STATE/last-run.log"
: >"$OMARCHY_SETUP_LOGFILE"
# Secrets need a terminal to unlock the vault; skip rather than fail without
# one. A dry run touches no vault, so it still previews the plan.
if [[ ${SKIP_SECRETS:-0} != 1 && $DRY_RUN != 1 && ! -t 0 ]]; then
  warn "no terminal available; skipping secrets (vault cannot be unlocked)"
  SKIP_SECRETS=1
fi
REMOVE_PACKAGES=${REMOVE_PACKAGES:-0}
export SETUP_PROFILE SETUP_HOST SETUP_ARCH DRY_RUN ASSUME_YES SKIP_SECRETS OMARCHY_SETUP_LOGFILE OMARCHY_SETUP_STATE REMOVE_PACKAGES
export BW_SERVER GITHUB_USER GIT_NAME GIT_EMAIL NVIM_REPO

# ---- discover modules: common + profile, interleaved by numeric prefix -----
declare -a MODULES=()
while IFS=$'\t' read -r _ path; do
  MODULES+=("$path")
done < <(
  for d in "$OMARCHY_SETUP_ROOT/modules/common" "$OMARCHY_SETUP_ROOT/modules/$SETUP_PROFILE"; do
    [[ -d $d ]] || continue
    for f in "$d"/*.sh; do
      [[ -f $f ]] && printf '%s\t%s\n' "$(basename "$f")" "$f"
    done
  done | sort -t$'\t' -k1,1
)

matches() {
  local name=$1; shift
  local p
  for p in "$@"; do [[ $name == *"$p"* ]] && return 0; done
  return 1
}

declare -a SELECTED=()
for m in "${MODULES[@]}"; do
  name=$(basename "$m" .sh)
  (( ${#ONLY[@]} )) && ! matches "$name" "${ONLY[@]}" && continue
  (( ${#SKIP[@]} )) &&   matches "$name" "${SKIP[@]}" && continue
  SELECTED+=("$m")
done

printf '\n%sprofile%s %s   %shost%s %s   %sarch%s %s\n' \
  "$C_DIM" "$C_RESET" "$SETUP_PROFILE" "$C_DIM" "$C_RESET" "$SETUP_HOST" \
  "$C_DIM" "$C_RESET" "$SETUP_ARCH" >&2
(( DRY_RUN )) && warn "dry run: nothing will be changed"

if (( LIST )); then
  printf '\nmodules that would run:\n' >&2
  for m in "${SELECTED[@]}"; do
    printf '  %-28s %s\n' "$(basename "$m" .sh)" "${m#"$OMARCHY_SETUP_ROOT"/}" >&2
  done
  exit 0
fi

(( ${#SELECTED[@]} )) || die "no modules matched"

declare -a FAILED=()
for m in "${SELECTED[@]}"; do
  name=$(basename "$m" .sh)
  step "$name"
  if bash "$m"; then
    mark_ran "$name"
  else
    fail "module failed: $name"
    FAILED+=("$name")
    # An unattended run has nobody to ask, and stopping at the first failure
    # would hide every later one. Carry on and report them all at the end.
    if [[ $ASSUME_YES == 1 || ! -t 0 ]]; then
      warn "continuing with the remaining modules"
    elif ! confirm "continue with the remaining modules?"; then
      break
    fi
  fi
done

echo >&2
if (( ${#FAILED[@]} )); then
  die "finished with failures: ${FAILED[*]} (log: $OMARCHY_SETUP_LOGFILE)"
fi
ok "done (log: $OMARCHY_SETUP_LOGFILE)"
