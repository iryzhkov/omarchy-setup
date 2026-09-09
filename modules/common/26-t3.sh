#!/usr/bin/env bash
# T3 Code and its quota steward, installed as a matched pair and kept current.
#
# T3 Code is an npm package installed globally into mise's node rather than a
# mise tool. mise's npm backend refuses to resolve it: a transitive dependency,
# @pierre/theme, carried a provenance attestation up to 1.0.3 and none from
# 1.1.0 on, and mise's trust policy rejects that downgrade. npm makes no such
# check, which is how the tree already running on every host was installed.
# Declaring the tool in mise would mean recording a trust_policy_excludes entry
# for that package, so the install stays with npm and the pin lives here.
#
# Because mise never sees T3, `mise up` and `omarchy update`'s mise step never
# moved it: that is what T3_AUTO_UPDATE is for. The two versions cannot float
# independently -- t3-steward is written against T3's undocumented control
# protocol and refuses to warn, stop or resume when the server version is
# outside the range it was built against -- so this module moves them together,
# asking a candidate steward binary which T3 versions it was tested with rather
# than trusting a hand-maintained table.
#
# `omarchy update` reaches this module through the post-update hook that
# re-runs run.sh, so an update carries the T3 pair forward alongside the mise
# tools instead of leaving it behind.
source "${OMARCHY_SETUP_LIB:?}/common.sh"
source "${OMARCHY_SETUP_LIB:?}/t3.sh"

conf="$OMARCHY_SETUP_ROOT/config/t3.conf"
if [[ ! -f $conf ]]; then
  info "no config/t3.conf; nothing to install"
  exit 0
fi
# shellcheck source=/dev/null
source "$conf"

T3_VERSION=${T3_VERSION:-}
T3_STEWARD_VERSION=${T3_STEWARD_VERSION:-}
T3_STEWARD_REPO=${T3_STEWARD_REPO:-iryzhkov/t3-steward}
T3_BIND=${T3_BIND:-127.0.0.1}
T3_PORT=${T3_PORT:-7391}
T3_AUTO_UPDATE=${T3_AUTO_UPDATE:-1}
T3_STEWARD_PRERELEASES=${T3_STEWARD_PRERELEASES:-1}
T3_RESTART_WHEN_IDLE=${T3_RESTART_WHEN_IDLE:-1}

BIN_DIR="$HOME/.local/bin"
UNIT_DIR="$HOME/.config/systemd/user"
STATE_FILE="$OMARCHY_SETUP_STATE/t3-versions.conf"

# The versions config/t3.conf declares, kept separately: they are the floor an
# auto-update may raise, and the signal that a deliberate change (including a
# rollback) has landed and this host's own resolution must be discarded.
BASE_T3=$T3_VERSION
BASE_STEWARD=$T3_STEWARD_VERSION

case $SETUP_ARCH in
x86_64) steward_arch=amd64 ;;
aarch64 | arm64) steward_arch=arm64 ;;
*) steward_arch="" ;;
esac

# What is installed right now, empty when nothing is. Both end in `|| true`:
# `set -o pipefail` is in force, so a missing binary would otherwise take the
# whole module down with it on a host where T3 has not been installed yet.
npm_t3_version() {
  npm ls -g --depth=0 --json t3 2>/dev/null | jq -r '.dependencies.t3.version // empty' || true
}

steward_installed_version() {
  "$BIN_DIR/t3-steward" version 2>/dev/null | awk '{print $2}' || true
}

# ---- what this host resolved for itself -------------------------------------
# A version this module worked out is recorded here rather than committed to
# config/t3.conf: the checkout has to stay clean for the post-update hook's
# `git pull --ff-only`, and four hosts bumping the same file would collide.
# The record carries the repo pins it was resolved from, so editing t3.conf --
# up for a fleet-wide bump, down for a rollback -- takes precedence again.
if [[ -f $STATE_FILE ]]; then
  # shellcheck source=/dev/null
  source "$STATE_FILE"
  if [[ ${T3_BASE_VERSION:-} == "$BASE_T3" && ${T3_BASE_STEWARD_VERSION:-} == "$BASE_STEWARD" ]]; then
    [[ -n ${T3_LOCAL_VERSION:-} ]] && T3_VERSION=$(t3_ver_max "$T3_VERSION" "$T3_LOCAL_VERSION")
    [[ -n ${T3_LOCAL_STEWARD_VERSION:-} ]] &&
      T3_STEWARD_VERSION=$(t3_ver_max "$T3_STEWARD_VERSION" "$T3_LOCAL_STEWARD_VERSION")
  else
    info "config/t3.conf declares a different pair; dropping this host's resolution"
    rm -f "$STATE_FILE"
  fi
fi

# ---- newest compatible pair -------------------------------------------------
# Downloads the release archive, checks it against the release's checksums.txt
# and extracts the binary into $1. Read-only with respect to this machine, so a
# dry run still resolves versions and reports the pair it would install.
steward_fetch() {
  local version=$1 dir=$2
  local tarball="t3-steward_${version}_linux_${steward_arch}.tar.gz"
  local base="https://github.com/$T3_STEWARD_REPO/releases/download/v$version"

  curl -fsSL --max-time 120 -o "$dir/$tarball" "$base/$tarball" ||
    { warn "could not download $tarball from $base"; return 1; }
  curl -fsSL --max-time 60 -o "$dir/checksums.txt" "$base/checksums.txt" ||
    { warn "could not download checksums.txt from $base"; return 1; }
  # --ignore-missing: checksums.txt covers every platform's archive and only
  # this one was fetched. A tarball absent from the file would then pass
  # silently, so the grep confirms it is listed at all.
  grep -qF -- "$tarball" "$dir/checksums.txt" ||
    { warn "$tarball is not listed in checksums.txt"; return 1; }
  (cd "$dir" && sha256sum -c --ignore-missing --quiet checksums.txt) ||
    { warn "checksum mismatch for $tarball"; return 1; }
  tar -xzf "$dir/$tarball" -C "$dir" t3-steward ||
    { warn "could not extract t3-steward from $tarball"; return 1; }
  return 0
}

# Set when a verified binary of $T3_STEWARD_VERSION is already unpacked, so the
# install below does not download the same archive a second time.
steward_staged=""

if (( ! T3_AUTO_UPDATE )); then
  info "auto-update off; keeping the declared pair"
elif [[ -z $T3_STEWARD_VERSION || -z $T3_VERSION ]]; then
  info "the pair is not fully declared; not resolving newer versions"
elif [[ -z $steward_arch ]]; then
  info "no t3-steward release for $SETUP_ARCH; not resolving newer versions"
elif ! command -v curl >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then
  warn "curl and jq are needed to resolve versions; keeping the declared pair"
elif ! command -v npm >/dev/null 2>&1; then
  warn "npm not found; keeping the declared pair (node comes from mise, see 25-mise)"
else
  newest_steward=$(t3_github_releases "$T3_STEWARD_REPO" "$T3_STEWARD_PRERELEASES" | tail -1)
  if [[ -z $newest_steward ]]; then
    warn "could not read the releases of $T3_STEWARD_REPO; keeping the declared pair"
    newest_steward=$T3_STEWARD_VERSION
  fi

  # Whichever steward is the candidate has to answer for itself which T3 it
  # supports, so a newer one is fetched before anything is decided. The
  # unpacked binary reaches the install step only once the pair is accepted:
  # a rejected candidate must not be installed under the older version's name.
  cand_steward=$T3_STEWARD_VERSION
  cand_path=""
  range=""
  if t3_ver_gt "$newest_steward" "$T3_STEWARD_VERSION"; then
    stage=$(mktempdir)
    if steward_fetch "$newest_steward" "$stage"; then
      range=$("$stage/t3-steward" version 2>/dev/null | t3_steward_range || true)
      cand_steward=$newest_steward
      cand_path="$stage/t3-steward"
    else
      warn "keeping t3-steward $T3_STEWARD_VERSION"
    fi
  fi
  if [[ -z $range && -x $BIN_DIR/t3-steward ]]; then
    range=$("$BIN_DIR/t3-steward" version 2>/dev/null | t3_steward_range || true)
  fi

  if [[ -z $range ]]; then
    # A steward that does not print its tested range cannot vouch for a T3
    # version, and moving T3 under it is exactly what disables the watchdog.
    warn "t3-steward does not declare a tested T3 range; leaving both pins alone"
  else
    read -r range_min range_max <<<"$range"
    # An unreachable registry yields no versions and no candidate, which lands
    # in the "keep the declared pair" branch below (see lib/t3.sh).
    cand_t3=$(t3_npm_versions | t3_pick_version "$range_min" "$range_max")

    if [[ -z $cand_t3 ]]; then
      warn "npm has no t3 in ${range_min}..${range_max} (t3-steward $cand_steward); keeping the declared pair"
    elif t3_ver_gt "$T3_VERSION" "$cand_t3"; then
      # Taking this steward would mean stepping T3 back. An upgrade path is
      # never a downgrade; wait for a release whose range has caught up.
      warn "t3-steward $cand_steward supports only ${range_min}..${range_max}, below the installed t3 $T3_VERSION; keeping the declared pair"
    else
      if t3_ver_gt "$cand_steward" "$T3_STEWARD_VERSION"; then
        step "t3-steward $T3_STEWARD_VERSION -> $cand_steward"
        T3_STEWARD_VERSION=$cand_steward
        steward_staged=$cand_path
      fi
      if t3_ver_gt "$cand_t3" "$T3_VERSION"; then
        step "t3 $T3_VERSION -> $cand_t3 (inside ${range_min}..${range_max})"
        T3_VERSION=$cand_t3
      else
        info "t3 $T3_VERSION with t3-steward $T3_STEWARD_VERSION is the newest compatible pair"
      fi
    fi
  fi
fi

# ---- T3 Code ---------------------------------------------------------------
# The server keeps every running agent thread in its own process, so a restart
# kills work in progress. This module installs the new version and restarts
# only when the steward reports no thread running; otherwise it says a restart
# is due and the next run picks it up.
if [[ -z $T3_VERSION ]]; then
  info "no T3 version declared; skipping T3 Code"
elif ! command -v npm >/dev/null 2>&1; then
  warn "npm not found; skipping T3 Code (node comes from mise, see 25-mise)"
else
  current=$(npm_t3_version)
  if [[ $current == "$T3_VERSION" ]]; then
    info "t3 $T3_VERSION already installed"
  else
    step "installing t3@$T3_VERSION (was ${current:-none})"
    run npm install -g "t3@$T3_VERSION"
    # Global npm binaries live in the node install's bin directory, which mise
    # only exposes as a shim after a reshim; t3code.service calls the shim.
    command -v mise >/dev/null 2>&1 && run mise reshim
  fi
fi

# ---- t3-steward ------------------------------------------------------------
# Installed from the project's GitHub release rather than built here: the
# releases carry linux/darwin amd64 and arm64 binaries plus checksums.txt, and
# no host in this fleet needs a Go toolchain for anything else.
steward_changed=0

if [[ -z $T3_STEWARD_VERSION ]]; then
  info "no steward version declared; skipping t3-steward"
else
  current=$(steward_installed_version)
  if [[ -z $steward_arch ]]; then
    warn "no t3-steward release for $SETUP_ARCH; skipping"
  elif [[ $current == "$T3_STEWARD_VERSION" ]]; then
    info "t3-steward $T3_STEWARD_VERSION already installed"
  else
    step "installing t3-steward $T3_STEWARD_VERSION (was ${current:-none})"
    ensure_cmd curl

    if (( DRY_RUN )); then
      run install -m 0755 "<verified>/t3-steward" "$BIN_DIR/t3-steward"
      steward_changed=1
    else
      if [[ -z $steward_staged ]]; then
        tmp=$(mktempdir)
        steward_fetch "$T3_STEWARD_VERSION" "$tmp" ||
          die "could not install t3-steward $T3_STEWARD_VERSION"
        steward_staged="$tmp/t3-steward"
      fi
      mkdir -p "$BIN_DIR"
      install -m 0755 "$steward_staged" "$BIN_DIR/t3-steward" ||
        die "could not install $BIN_DIR/t3-steward"
      ok "t3-steward $T3_STEWARD_VERSION installed"
      steward_changed=1
    fi
  fi
fi

# ---- record what this host now runs ----------------------------------------
# Written after the installs, so it states what is on disk rather than what was
# intended: a download that failed must not leave a version recorded as current.
if (( ! DRY_RUN )); then
  installed_t3=""
  if command -v npm >/dev/null 2>&1; then installed_t3=$(npm_t3_version); fi
  installed_steward=$(steward_installed_version)
  if [[ -n $installed_t3 || -n $installed_steward ]]; then
    mkdir -p "$OMARCHY_SETUP_STATE"
    {
      printf '# Written by modules/common/26-t3.sh: the T3 pair this host runs.\n'
      printf '# T3_BASE_* are the config/t3.conf pins it was resolved from; when\n'
      printf '# those change, this file is discarded and the repo pins win again.\n'
      printf 'T3_BASE_VERSION=%s\n' "$BASE_T3"
      printf 'T3_BASE_STEWARD_VERSION=%s\n' "$BASE_STEWARD"
      printf 'T3_LOCAL_VERSION=%s\n' "$installed_t3"
      printf 'T3_LOCAL_STEWARD_VERSION=%s\n' "$installed_steward"
    } >"$STATE_FILE"
  fi
fi

# ---- services --------------------------------------------------------------
# t3code.service is seeded once and never rewritten: a host may have tuned its
# bind address, its PATH or the credential files it reads, and none of that is
# recoverable from this repo. The steward's unit is the steward's own to write.
if [[ -x $BIN_DIR/t3-steward ]]; then
  if [[ -f $UNIT_DIR/t3-steward.service ]]; then
    if (( steward_changed )); then
      run systemctl --user restart t3-steward.service
    else
      info "t3-steward.service present"
    fi
  else
    step "installing t3-steward.service"
    run "$BIN_DIR/t3-steward" install-service
  fi
fi

if [[ -f $UNIT_DIR/t3code.service ]]; then
  info "t3code.service present, left alone"
elif [[ -n $T3_VERSION ]]; then
  step "seeding t3code.service"
  {
    printf '# Seeded by omarchy-setup (modules/common/26-t3.sh); yours to edit.\n'
    printf '[Unit]\n'
    printf 'Description=T3 Code server (agent control surface)\n'
    printf 'Documentation=https://github.com/pingdotgg/t3code\n'
    printf 'After=network-online.target\n'
    printf 'Wants=network-online.target\n\n'
    printf '[Service]\n'
    printf 'Type=simple\n'
    printf 'WorkingDirectory=%%h\n'
    printf 'ExecStart=%%h/.local/share/mise/shims/t3 serve --host %s --port %s --no-browser\n' \
      "$T3_BIND" "$T3_PORT"
    # t3 launches the agent CLIs (claude, codex, opencode), which are mise
    # shims, so the shim directory has to be on PATH for a non-login service.
    printf 'Environment=PATH=%%h/.local/share/mise/shims:%%h/.local/bin:/usr/local/bin:/usr/bin:/bin\n'
    printf 'Environment=HOME=%%h\n'
    # The provider credentials are per-host and never live in this repo. The
    # leading - makes a missing file a warning rather than a failed start.
    printf 'EnvironmentFile=-%%h/.config/claude/oauth.env\n'
    printf 'Restart=always\n'
    printf 'RestartSec=10\n\n'
    printf '[Install]\n'
    printf 'WantedBy=default.target\n'
  } | write_owned_file "$UNIT_DIR/t3code.service"

  if (( ! DRY_RUN )); then
    run systemctl --user daemon-reload
    run systemctl --user enable --now t3code.service
  fi
  [[ -f $HOME/.config/claude/oauth.env ]] ||
    warn "no ~/.config/claude/oauth.env; T3 will start unauthenticated until it is written"
fi

# ---- restart T3 when it is idle --------------------------------------------
# The running server keeps serving the version it started with, so an upgraded
# package changes nothing until the unit restarts -- and a restart kills every
# thread in flight, including the agent that may be running this update. The
# steward's own check reports both the served version and how many threads are
# running, so the restart waits for a moment when losing nothing is certain.
if (( ! DRY_RUN )) && [[ -x $BIN_DIR/t3-steward ]] &&
  systemctl --user is-active --quiet t3code.service 2>/dev/null; then
  installed_t3=""
  if command -v npm >/dev/null 2>&1; then installed_t3=$(npm_t3_version); fi
  check_out=$("$BIN_DIR/t3-steward" check 2>&1 || true)
  served=$(t3_server_version <<<"$check_out")
  running=$(t3_running_threads <<<"$check_out")

  if [[ -z $installed_t3 || -z $served ]]; then
    [[ -n $installed_t3 ]] &&
      warn "cannot tell which t3 the server is running; restart it yourself if it is behind"
  elif [[ $served == "$installed_t3" ]]; then
    info "t3code is serving $served"
  elif (( ! T3_RESTART_WHEN_IDLE )); then
    warn "t3code serves $served, t3 $installed_t3 is installed; restart when no thread is running: systemctl --user restart t3code"
  elif [[ -z $running ]]; then
    warn "t3code serves $served but the running-thread count is unknown; not restarting"
  elif (( running == 0 )); then
    step "restarting t3code: serving $served, t3 $installed_t3 installed, no thread running"
    run systemctl --user restart t3code.service
  else
    warn "t3code serves $served, t3 $installed_t3 installed; $running thread(s) running, restart deferred to the next run"
  fi
fi

ok "T3 Code and steward ready"
