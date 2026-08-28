#!/usr/bin/env bash
# Git identity on a fresh machine.
#
# Without this, the first commit on a new box fails with "Author identity
# unknown", which is a silly thing to hit halfway through setting one up.
#
# Values come from config/defaults.conf: --git-name / --git-email, or the
# GIT_NAME / GIT_EMAIL environment variables.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

pkg_install git

[[ -n ${GIT_NAME:-} && -n ${GIT_EMAIL:-} ]] ||
  { warn "GIT_NAME/GIT_EMAIL not set; leaving git identity alone"; exit 0; }

current_name=$(git config --global user.name 2>/dev/null || true)
current_email=$(git config --global user.email 2>/dev/null || true)

if [[ $current_name == "$GIT_NAME" && $current_email == "$GIT_EMAIL" ]]; then
  info "git identity already set to $GIT_NAME <$GIT_EMAIL>"
  exit 0
fi

# Only ever fills in a blank. An identity you set deliberately -- including a
# per-repo one, which --global does not touch -- is left as it is.
if [[ -n $current_name || -n $current_email ]]; then
  warn "global git identity already set to ${current_name:-?} <${current_email:-?}>; not overwriting"
  exit 0
fi

step "setting global git identity: $GIT_NAME <$GIT_EMAIL>"
run git config --global user.name "$GIT_NAME"
run git config --global user.email "$GIT_EMAIL"
