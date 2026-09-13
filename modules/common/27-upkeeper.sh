#!/usr/bin/env bash
# Final machine-bootstrap handoff. Fleet installation belongs to UpKeeper.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

checkout="$HOME/.local/share/dev-fleet"
repository=${UPKEEPER_REPOSITORY:-https://github.com/iryzhkov/dev-fleet.git}
export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND="ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10"

ensure_cmd python3 python
ensure_cmd git git
ensure_cmd uv uv

if (( ! DRY_RUN )); then
  require_cmd python3
  require_cmd git
  require_cmd uv
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' ||
    die "UpKeeper requires Python 3.11 or newer"
fi

if [[ -e $checkout || -L $checkout ]]; then
  [[ ! -L $checkout && -d $checkout/.git ]] || die "UpKeeper checkout is not a regular Git checkout"
  [[ -z $(git -C "$checkout" status --porcelain --untracked-files=all) ]] ||
    die "UpKeeper checkout is dirty; preserve the local work before bootstrap"
  [[ $(git -C "$checkout" remote get-url origin) == "$repository" ]] ||
    die "UpKeeper origin differs from the configured repository"
  [[ $(git -C "$checkout" branch --show-current) == main ]] ||
    die "UpKeeper checkout must be on main"
  # Dry run must not fetch or move a checkout.
  if (( ! DRY_RUN )); then
    git -C "$checkout" pull --ff-only --quiet
  fi
else
  if (( DRY_RUN )); then
    info "would clone $repository (main) to $checkout"
    info "would install ~/.local/bin/upkeeper and run upkeeper pull --self"
    exit 0
  fi
  mkdir -p "$(dirname "$checkout")"
  stage=$(mktemp -d "$(dirname "$checkout")/.upkeeper-bootstrap.XXXXXX")
  register_cleanup "$stage"
  git clone --quiet --branch main --single-branch "$repository" "$stage/repo"
  [[ ! -e $checkout && ! -L $checkout ]] || die "UpKeeper checkout appeared during clone"
  mv -T "$stage/repo" "$checkout"
fi

entry="$checkout/scripts/upkeeper"
[[ -f $entry ]] || die "UpKeeper entry point missing"
destination="$HOME/.local/bin/upkeeper"
if [[ -e $destination || -L $destination ]]; then
  # A development installation may point into ~/Work; do not replace it.
  if [[ $(readlink -f "$destination") != "$entry" ]]; then
    info "keeping existing upkeeper command; invoking the bootstrap checkout explicitly"
  fi
else
  run mkdir -p "$(dirname "$destination")"
  run ln -s "$entry" "$destination"
fi

if (( DRY_RUN )); then
  PYTHONDONTWRITEBYTECODE=1 python3 "$entry" pull --self --dry-run
else
  PYTHONDONTWRITEBYTECODE=1 python3 "$entry" pull --self
fi
