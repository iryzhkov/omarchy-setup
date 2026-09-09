#!/usr/bin/env bash
# T3 Code and its quota steward, installed and pinned as a matched pair.
#
# T3 Code is an npm package installed globally into mise's node rather than a
# mise tool. mise's npm backend refuses to resolve it: a transitive dependency,
# @pierre/theme, carried a provenance attestation up to 1.0.3 and none from
# 1.1.0 on, and mise's trust policy rejects that downgrade. npm makes no such
# check, which is how the tree already running on every host was installed.
# Declaring the tool in mise would mean recording a trust_policy_excludes entry
# for that package, so the install stays with npm and the pin lives here.
#
# The version is pinned rather than floating because t3-steward is written
# against T3's undocumented control protocol and refuses to warn, stop or
# resume when the server version is outside the range it was built against.
# config/t3.conf holds both versions and explains how to move them.
#
# `omarchy update` reaches this module through the post-update hook that
# re-runs run.sh, so an update re-asserts the pinned pair instead of drifting.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

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

BIN_DIR="$HOME/.local/bin"
UNIT_DIR="$HOME/.config/systemd/user"

# ---- T3 Code ---------------------------------------------------------------
# The server keeps every running agent thread in its own process, so a restart
# kills work in progress. This module installs the new version and says a
# restart is due; choosing the moment is the operator's, never a script's.
t3_restart_due=0

if [[ -z $T3_VERSION ]]; then
  info "no T3 version declared; skipping T3 Code"
elif ! command -v npm >/dev/null 2>&1; then
  warn "npm not found; skipping T3 Code (node comes from mise, see 25-mise)"
else
  current=$(npm ls -g --depth=0 --json t3 2>/dev/null | jq -r '.dependencies.t3.version // empty')
  if [[ $current == "$T3_VERSION" ]]; then
    info "t3 $T3_VERSION already installed"
  else
    step "installing t3@$T3_VERSION (was ${current:-none})"
    run npm install -g "t3@$T3_VERSION"
    # Global npm binaries live in the node install's bin directory, which mise
    # only exposes as a shim after a reshim; t3code.service calls the shim.
    command -v mise >/dev/null 2>&1 && run mise reshim
    t3_restart_due=1
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
  case $SETUP_ARCH in
  x86_64) steward_arch=amd64 ;;
  aarch64 | arm64) steward_arch=arm64 ;;
  *) steward_arch="" ;;
  esac

  current=$("$BIN_DIR/t3-steward" version 2>/dev/null | awk '{print $2}')
  if [[ -z $steward_arch ]]; then
    warn "no t3-steward release for $SETUP_ARCH; skipping"
  elif [[ $current == "$T3_STEWARD_VERSION" ]]; then
    info "t3-steward $T3_STEWARD_VERSION already installed"
  else
    step "installing t3-steward $T3_STEWARD_VERSION (was ${current:-none})"
    ensure_cmd curl
    tarball="t3-steward_${T3_STEWARD_VERSION}_linux_${steward_arch}.tar.gz"
    base="https://github.com/$T3_STEWARD_REPO/releases/download/v$T3_STEWARD_VERSION"

    if (( DRY_RUN )); then
      run curl -fsSL -o "<tmp>/$tarball" "$base/$tarball"
      run install -m 0755 "<tmp>/t3-steward" "$BIN_DIR/t3-steward"
    else
      tmp=$(mktempdir)
      curl -fsSL -o "$tmp/$tarball" "$base/$tarball" ||
        die "could not download $tarball from $base"
      curl -fsSL -o "$tmp/checksums.txt" "$base/checksums.txt" ||
        die "could not download checksums.txt from $base"
      # --ignore-missing: checksums.txt covers every platform's archive and
      # only this one was fetched. A tarball absent from the file would then
      # pass silently, so the grep confirms it is listed at all.
      grep -qF -- "$tarball" "$tmp/checksums.txt" ||
        die "$tarball is not listed in checksums.txt"
      (cd "$tmp" && sha256sum -c --ignore-missing --quiet checksums.txt) ||
        die "checksum mismatch for $tarball; not installing"
      tar -xzf "$tmp/$tarball" -C "$tmp" t3-steward ||
        die "could not extract t3-steward from $tarball"
      mkdir -p "$BIN_DIR"
      install -m 0755 "$tmp/t3-steward" "$BIN_DIR/t3-steward" ||
        die "could not install $BIN_DIR/t3-steward"
      ok "t3-steward $T3_STEWARD_VERSION installed"
    fi
    steward_changed=1
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

if (( t3_restart_due )); then
  warn "t3 was upgraded; restart when no thread is running: systemctl --user restart t3code"
fi

ok "T3 Code and steward ready"
