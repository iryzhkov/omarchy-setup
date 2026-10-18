# Agent tooling ownership

[iryzhkov/chaldea-fleet-config](https://github.com/iryzhkov/chaldea-fleet-config)
is the canonical public source for shared agent instructions, skills, harness
configuration, OpenCode's Huyang plugin and fleet tooling.

omarchy-setup prepares fresh Omarchy machines and keeps personal desktop,
shell and Neovim setup. Module 31 prints this ownership pointer. It does not
install, regenerate, remove or converge agent files. The post-update hook and
uninstall leave fleet instructions and configuration alone.

Edit fleet-owned sources in chaldea-fleet-config and use its reviewed validation
and distribution workflow. Installed files are outputs, never publication inputs.
Source publication and host convergence are separate steps.

The former `agents-instructions-gen` and `agents-role-project` are retired.
Fleet copies its authoritative CLAUDE, AGENTS, skill and reference files
directly. Legacy Steward policy generation has no replacement here. Existing
installed generator copies are not removed by setup; retire those through a
separately authorized fleet migration before using them again.

The optional laptop-worker staging helper and scratch reaper, with their
configuration, tests and historical documentation, are preserved in fleet's
`tooling/legacy-bootstrap/` with provenance. They are not activated by this
repository. General fresh-machine prerequisites and the module 27 UpKeeper
bootstrap handoff remain here.
