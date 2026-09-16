---
name: huyang
description: >
  How to spend the fewest tokens on a Huyang call that is still correct: which
  tool answers which need, what a call costs, and the workspace, revision and
  verification rules behind refusals. The always-on rule in CLAUDE.md says to use
  Huyang for every file inside a repository; this skill says how. Read it before
  the first file operation in an unfamiliar repository, when a call is refused for
  a stale revision, conflict or incomplete evidence, when planning a multi-file or
  atomic change, and when running builds or tests through verification. Triggers:
  huyang, workspace_open, edit_apply, change_plan, verify_run, stale revision,
  prepared revision, replace_literal, symbol_locator, diagnostics evidence.
---

# Huyang: the cheapest correct call

Costs below were measured in `bench/agent-efficiency` of the Huyang repository
(cl100k tokens, Go fixture, 2026-09-12); the full table is in `docs/agent-guide.md`
there. Use these without experimenting.

- Name the repository with `root` on any call instead of calling `workspace_open`
  first: the workspace is opened on the first call and reused after. `workspace_open`
  is for when you want its overview and the verification commands. `idempotency_key`
  is optional; omit it unless you will retry the same call.
- Change text you know (a line, a block, a local rename): `edit_apply` with
  `operation.kind=replace_literal`, `old`, `new`, optional `path`, and
  `expected_count` when the text occurs more than once. One call, about 70 request
  and 300 response tokens for a one-line change; the response carries the changed
  locations, the new revision and the diagnostics the edit caused, and never echoes
  your text (no patch unless `verbose`). Do not search first.
- New file: `edit_apply` with `kind=create_file`, `path`, `content`. One call; an
  existing path is refused with its `revision_id`, and `replace=true` with that
  revision overwrites it. Several edits at once: `edit_apply` with `operations=[...]`
  (every kind but replace_range, applied in order, one call; a refusal stops the list
  and earlier operations stay, so use `change_plan` for anything atomic).
- Move, copy or delete a file: `edit_apply` with `kind=move_file` (`from`, `to`),
  `kind=copy_file` (`from` may be an absolute path outside the repository, `to`) or
  `kind=delete_file` (`path` plus `revision_id` or `expected_sha256`). The bytes never
  pass through your context and are never reformatted. Huyang does not touch the Git
  index: the reply's `git` block gives each path's tracked state and `next` names the
  `git add` to run so Git records a rename; run it. Never `cp`, `mv` or `rm` inside a
  repository.
- References, definition, implementations or callers of a symbol: `search` with
  `query=Name` and `mode=references` (or `navigate` with `relation` and `symbol=Name`).
  No path needed; the name is resolved to its declaration first. Without a language
  server the search answers literal matches and says so.
- Read a file: `read` with `target.path`; a region: `start_line`/`end_line` (no cap) or
  `target.symbol_locator` (Go and Python resolve without a language server); several
  files: `targets`; `numbered=true` when you need line numbers. One call each; a whole
  file costs less than the built-in Read. A file over about 500 lines: `view=outline`
  first, or `max_lines` (per call or per target); a capped reply says `truncated` with
  the total, and a multi-target reply lists every target's size under `entries` before
  the bodies.
- Locate text: `search` (literal by default, whitespace-exact for multi-line queries)
  with `paths` (globs or substrings) to scope and `context_lines` for the surrounding
  numbered lines, which replaces `grep -rn -C` and the read after it. Hits carry handles
  for `edit_apply kind=replace_range` when a target cannot be named by content.
- Build and test: `verify_run` with `revision_or_transaction=current` and the stages you
  need (`check`, `tests`; `test_scope=affected` for only the tests covering edited files).
  `workspace_open` reports the commands, whether they were declared in `.huyang.toml` or
  detected from the repository (Makefile targets, `go.mod`, a Python project's pytest and
  ruff through its own venv or `uv run`), and whether the root is trusted. An untrusted
  root runs nothing; `huyang trust <root>` in the shell grants it, then retry. The reply
  is one line per stage plus the output of a stage that did not pass.
- Several files that must change atomically: `change_plan` (prepare, then apply).
- A file outside any repository (config, script, note, a lone source file): no
  `workspace_open` needed. `read` with the path, and `edit_apply` (`replace_literal`,
  `create_file`, `move_file`, `copy_file` or `delete_file`) with absolute paths and no
  `workspace_id`, open a documents workspace implicitly and return its id for further
  edits. Files that are not source and live outside any repository, such as the
  machine-local memory notes under `~/.claude/projects/`, may be written with either
  `edit_apply create_file` or the harness `Write` tool; both are one call and neither
  gains diagnostics there.

Go files are gofmt-formatted after every edit unless `format=false`. Pass `verbose=true`
to `edit_apply` only when you need the full change record and handle resolution.

## Workspace and verification constraints

Huyang can keep several explicit workspaces open. Always route by workspace ID; do not
assume the current directory identifies the intended workspace. A result is valid only
for the revision it names.

Use semantic handles or exact revision-bound locators when available. For a multi-file
change, prepare a change plan, inspect its evidence, and commit only the prepared
revision. If Huyang reports a conflict, stale revision, incomplete evidence, or recovery
requirement, do not bypass it with an unguarded overwrite.

Diagnostics and test claims are evidence-bound. Distinguish affected-test coverage from a
full test run, and treat provisional or partial evidence as such. Repository commands
execute only when declared by `.huyang.toml` and trusted by the user policy in
`~/.config/huyang/config.toml`.

The native text path works without Neovim. Semantic navigation, formatting, LSP
diagnostics, and debugging additionally depend on the corresponding parser, language
server, formatter, or adapter being available.
