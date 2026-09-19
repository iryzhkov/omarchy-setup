#!/usr/bin/env bash
# The resident instruction layer: the text an agent session on this machine
# already holds before it reads anything, and the generated files the harnesses
# that do not read ~/.claude/CLAUDE.md load instead.
#
#   config/claude/CLAUDE.md  ->  ~/.claude/omarchy-setup/CLAUDE.md   (owned copy)
#   then agents-instructions-gen --root $OMARCHY_SETUP_ROOT rebuilds
#   ~/.config/agents/*.md, the fleet block of ~/.codex/AGENTS.md and OpenCode's
#   instruction list from the same checkout.
#
# This module exists because nothing installed config/claude/CLAUDE.md. The host
# copies were written by hand, months of commits apart, and the generator read
# those host copies back, so a hand-edit on one machine was laundered into the
# generated files and then captured into an UpKeeper release for the whole
# fleet. The checkout is the source; a host copy is a derived artifact.
#
# Two files are deliberately not written here:
#
#   ~/.claude/CLAUDE.md    UpKeeper's, and merged rather than replaced, which is
#                          how each machine keeps its own "# This machine"
#                          section. It imports the file this module writes.
#   ~/.claude/skills/      published by UpKeeper from config/claude/skills/.
#                          `agents-instructions-gen --check` compares them
#                          against this checkout and reports any that differ.
#
# Runs after 28-scripts, which installs agents-instructions-gen into
# ~/.local/bin. Ownership in full: docs/agent-instruction-ownership.md.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

step "resident agent instructions"

write_owned_file "$HOME/.claude/omarchy-setup/CLAUDE.md" 0644 \
  <"$OMARCHY_SETUP_ROOT/config/claude/CLAUDE.md"

# The installed copy is what a person runs by hand, so it is what runs here; a
# checkout that has not installed its scripts yet still converges.
gen="$HOME/.local/bin/agents-instructions-gen"
[[ -x $gen ]] || gen="$OMARCHY_SETUP_ROOT/config/bin/agents-instructions-gen"
run "$gen" --root "$OMARCHY_SETUP_ROOT"
