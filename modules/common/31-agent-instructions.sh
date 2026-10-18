#!/usr/bin/env bash
# Agent tooling is owned by chaldea-fleet-config. This bootstrap step only
# points operators at the owner; it must not write installed agent files.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

step "agent tooling"
info "Shared instructions, skills and harness configuration are managed by chaldea-fleet-config."
info "See https://github.com/iryzhkov/chaldea-fleet-config and docs/agent-instruction-ownership.md."
