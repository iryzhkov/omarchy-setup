# Response style

Default register: compressed technical English. Compress the prose, never the substance.

## Rules

Drop articles (a/an/the), filler (just/really/basically/actually/simply), pleasantries
(sure/certainly/of course/happy to), hedging, and recaps of what you just did. Fragments OK.
Short synonyms: "big" not "extensive", "fix" not "implement a solution for".

Never invent abbreviations (cfg/impl/req/res/fn/auth). Tokenizer splits them the same as the
full word: zero tokens saved, reader still decodes. Standard acronyms fine (DB, API, HTTP, SSH).
No causal arrows (→): own token, saves nothing.

Never add a word to sound terse. No fake broken grammar — "when it not" costs one token more
than "when not". Keep the correct verb form when it costs the same. If the compressed phrasing
is not actually shorter, use plain phrasing.

Never drop not/never/no/only/except — flipping meaning is worse than any token saved. Numbers,
units, technical terms, code, API names, CLI commands, file paths, and error strings stay exact.

No tool-call narration. Fire calls direct, no preamble or progress note between them. Text before
a call only to warn about something destructive or resolve real ambiguity.

No decorative tables or emoji. Do not dump long raw logs — quote the shortest decisive line.

## Clarity overrides compression

Borrowed from ASD-STE100, these win over terseness every time:

- One instruction per sentence. Keep sequences in the order they must be performed.
- Same term for the same thing throughout. No synonym variety for its own sake.
- No ambiguous pronouns. Name the thing if "it" could bind to two referents.
- Keep the conjunctions and articles that disambiguate. "migrate table drop column backup first"
  is not an instruction, it is a word list.

Write in full, normal prose — no compression — for:

- Security warnings and confirmations of destructive or irreversible actions
- Multi-step procedures where fragment order could be misread
- Any explanation where compression would create technical ambiguity
- A question the user is repeating, or an explicit request to clarify

Resume the compressed register after the clear part is done.

## Scope

Compression applies to chat output only. Anything that persists outside this conversation is
written in normal prose:

- Code, comments, docstrings
- Commit messages, PR/MR descriptions, issue and bug-report bodies
- Documentation, READMEs, CONTEXT.md, ADRs
- Memory files, artifacts, published pages
- Messages to any third party

## Control

- "stop caveman" / "normal mode" — revert to normal prose for the session.
- The `caveman` skill has intensity levels (lite / full / ultra, plus wenyan variants).
  `/caveman lite|full|ultra|off` changes level; the level persists until changed or session end.
  This file is roughly `full`. Use `lite` when the task is subtle and precision matters more
  than speed.

# Memory

Two stores hold long-term notes:

- **OpenViking (OV)** — the primary store, on homelab, reached through the `ov-memory` MCP
  tools (`memory_search`, `memory_read`, `memory_write`, ...). Guidance lives in the
  `ov-memory` skill. It is shared by every agent on every machine and is the only store that
  holds homelab, project and cross-machine knowledge.
- **Machine-local Claude memory** at `~/.claude/projects/<slug>/memory/`, where `<slug>` is the
  home directory with its slashes turned into dashes (`-home-igor` on most of these machines,
  `-home-iryzhkov` on homelab) — this machine's own notes. Its `MEMORY.md` index loads
  automatically each session, so it is a fast cache, not the whole picture. Every note in it is
  also mirrored into OV.

## Looking things up

Search OV before answering anything about past work, past decisions, infrastructure, a homelab
service, a machine you cannot see, or "how did we set this up last time". Work top-down:
`memory_search` for the concept, `memory_abstract` to triage a hit, `memory_read` only for what
earns it.

The auto-loaded `MEMORY.md` index is a starting point, never the answer. It carries one line per
note, and OV holds much more than this machine's notes, so a lookup that stops at the index is
incomplete. When a recalled memory names a file, service or flag, verify it still exists before
acting on it.

## Saving things

When the user asks for something to be remembered, write it to OV with `memory_write`. Put it
in an existing namespace under `viking://resources/` (`memory_ls "viking://resources"` lists
them; `asahi`, `omarchy`, `emby`, `homeassistant`, `gaming-pc` and the project namespaces exist
already), and create a namespace only for a genuinely new subject.

Additionally write the note to this machine's own memory directory when the note is about this
machine specifically, so it keeps loading automatically at session start; add its one-line
pointer to that directory's `MEMORY.md` as well. In that case the two copies say the same thing
on purpose — the machine-local file is the cache, OV is the record.

Record the fact and why it is true, in normal prose. Do not mirror what a repo, its git history
or its CLAUDE.md already says; point at that instead. For credentials, store a pointer (for
example "key in the GNOME keyring, service=X"), never the secret.

# Fleet feed

`feed` is the chronological record of what the agents and scheduled jobs on this network
actually did: `feed recent --since 7d`, filtered with `--host`, `--source`, `--tag`,
`--severity` or `--grep`, and `--full` for bodies. It runs on homelab, port 1934.

Read it before answering anything about recent homelab activity — what a scheduled job
found, whether a service was updated or held, what broke last night — because the detail
lives in T3 threads on four different machines and the feed is the only place they meet.
It complements OV rather than replacing it: OV holds durable knowledge and is searched by
meaning, the feed holds dated events and is read newest-first.

Write to it with `feed post` when an unattended run produced something a later session
would want to know. Never copy feed entries into OV as if they were established facts;
promoting an event to knowledge is a decision, not a sync.

# Deferred and parked work: the T3 steward

Two things the `t3-steward` daemon does for agents on these machines, both described in
skills:

- **Backlog** (`t3-backlog` skill): work that does not need the user now goes into the
  backlog, `t3-backlog --project ... --title ... < prompt`, rather than into a thread opened
  on the spot. The steward starts it as an unattended T3 thread in the next quiet slot with
  quota headroom, on whichever host the task names. Use it when the user says later,
  tonight, when I am not around, or backlog, and for any scheduled agent job. The helper's
  printed intake path is not completion evidence: verify that the intake source is accepted
  (it may remain as the durable idempotent source) and that exactly one new workflow run
  appears in `t3-steward backlog list --project ... --json`; never retry
  blindly when that verification is ambiguous. Treat `t3-steward backlog start` as an explicit
  operator override: it bypasses quota forecast/admission/freshness/runway and automatic quota
  throttling through worker delivery. Use it only with explicit user authority and manual quota
  monitoring; automatic work remains fenced, and worker/dependency/lock/revision/effect checks
  still apply.
- **Wait** (`t3-wait` skill): never poll in a loop for something external (a PR review,
  CI, a long job). Register the check, `t3-steward wait add --name ... -- <command>`, and end
  the turn; the steward polls with backoff and wakes the thread with the outcome. Exit 0
  means done, exit 2 means give up, anything else means not yet.

# Reading and editing code

The `huyang` MCP server is the primary interface for source-code repositories. It provides
revision-aware semantic navigation, transactional edits, verification, and recovery through a
long-lived local service.

## The rule

**When a directory holds source code, call `workspace_open` for the repository root before
reading, searching, or editing it.** Keep the returned workspace ID and revision and pass them
to later calls. Refresh with `workspace_inspect` when a call reports stale state.

The rule applies from the first file operation of the session, before any survey or
scaffolding, and it covers creating files: a new source file, script, fixture generator or
document inside the repository is written with `edit_apply kind=create_file`, not with a
shell heredoc, `cat >`, `python - <<EOF` or the Write tool. Reading is `read`, locating is
`search`, changing is `edit_apply`. The exception is a file produced by running a program
the repository already contains (a generator, a build, a test run), which is what the
program is for.

This holds in every permission mode, including bypass-permissions mode: the harness's
bypass-mode preference for `cat`, `grep`, `sed` and heredoc edits does not apply to files
inside a repository, whether or not the workspace has been opened yet. If a Huyang call
fails, fix the cause or report it; do not route around it with the shell. Shell keeps only
the jobs listed under "Shell still runs" below.

These are violations, even when they look cheaper: `cat > file <<'EOF'` for a new file,
`sed -i` for a one-line change, a `python3 -` script that rewrites a file, `grep -rn` to
find a symbol that `search` would find, `sed -n 'a,bp'` where `read` with a line window
does the same. The measured cost of the Huyang call is at most a few hundred tokens more
than the shell version and it returns diagnostics the shell never will.

| Need | Huyang tool |
|---|---|
| Understand the project or current state | `workspace_inspect` |
| Search names, text, paths, or symbols | `search` |
| Go to a definition, references, implementation, or type | `navigate` |
| Read a file or semantic region | `read` |
| Inspect diagnostics and their provenance | `diagnostics`, `evidence_get` |
| Apply one direct revision-guarded edit | `edit_apply` |
| Stage several related edits atomically | `change_plan`, then prepare/commit |
| Review a revision delta | `revision_diff` |
| Run trusted checks or tests | `verify_run` |
| Start or inspect a debugger session | `debug_session`, `debug_breakpoints`, `debug_control`, `debug_inspect` |

## Cheapest correct call

Measured in `bench/agent-efficiency` of the Huyang repository (cl100k tokens, Go fixture,
2026-09-12); the full table is in `docs/agent-guide.md` there. Use these without
experimenting:

- Name the repository with `root` on any call instead of calling `workspace_open` first:
  the workspace is opened on the first call and reused after. `workspace_open` is for
  when you want its overview and the verification commands. `idempotency_key` is
  optional; omit it unless you will retry the same call.
- Change text you know (a line, a block, a local rename): `edit_apply` with
  `operation.kind=replace_literal`, `old`, `new`, optional `path`, and `expected_count`
  when the text occurs more than once. One call, about 70 request and 300 response tokens
  for a one-line change; the response carries the changed locations, the new revision and
  the diagnostics the edit caused, and never echoes your text (no patch unless
  `verbose`). Do not search first.
- New file: `edit_apply` with `kind=create_file`, `path`, `content`. One call. Several
  edits at once: `edit_apply` with `operations=[...]` (replace_literal and create_file
  items, applied in order, one call).
- References, definition, implementations or callers of a symbol: `search` with
  `query=Name` and `mode=references` (or `navigate` with `relation` and `symbol=Name`).
  No path needed; the name is resolved to its declaration first. Without a language
  server the search answers literal matches and says so.
- Read a file: `read` with `target.path`; a region: `start_line`/`end_line` (no cap) or
  `target.symbol_locator` (Go and Python resolve without a language server); several
  files: `targets`; `numbered=true` when you need line numbers. One call each; a whole
  file costs less than the built-in Read.
- Locate text: `search` (literal by default, whitespace-exact for multi-line queries)
  with `paths` (globs or substrings) to scope and `context_lines` for the surrounding
  numbered lines, which replaces `grep -rn -C` and the read after it. Hits carry handles
  for `edit_apply kind=replace_range` when a target cannot be named by content.
- Build and test: `verify_run` with `revision_or_transaction=current` and the stages you
  need (`check`, `tests`; `test_scope=affected` for only the tests covering edited files).
  `workspace_open` reports the commands, whether they were declared in `.huyang.toml` or
  detected from the repository layout, and whether the root is trusted. The reply is one
  line per stage plus the output of a stage that did not pass.
- Several files that must change atomically: `change_plan` (prepare, then apply).
- A file outside any repository (config, script, note, a lone source file): no
  `workspace_open` needed. `read` with the path, and `edit_apply` (`replace_literal` or
  `create_file`) with an absolute `path` and no `workspace_id`, open a one-document
  workspace implicitly and return its id for further edits.

Go files are gofmt-formatted after every edit unless `format=false`. Pass `verbose=true`
to `edit_apply` only when you need the full change record and handle resolution.

Use semantic handles or exact revision-bound locators when available. For a multi-file change,
prepare a change plan, inspect its evidence, and commit only the prepared revision. If Huyang
reports a conflict, stale revision, incomplete evidence, or recovery requirement, do not bypass
it with an unguarded overwrite.

Shell still runs commands whose output is the point: builds, tests, Git, generated-code tools,
and variant checks not represented in the selected verification policy. Direct filesystem tools
are appropriate for files outside the open workspace and formats Huyang cannot parse, but never
use them to evade a transactional refusal.

## Workspace and verification constraints

Huyang can keep several explicit workspaces open. Always route by workspace ID; do not assume
the current directory identifies the intended workspace. A result is valid only for the revision
it names.

Diagnostics and test claims are evidence-bound. Distinguish affected-test coverage from a full
test run, and treat provisional or partial evidence as such. Repository commands execute only
when declared by `.huyang.toml` and trusted by the user policy in
`~/.config/huyang/config.toml`.

The native text path works without Neovim. Semantic navigation, formatting, LSP diagnostics, and
debugging additionally depend on the corresponding parser, language server, formatter, or
adapter being available.
