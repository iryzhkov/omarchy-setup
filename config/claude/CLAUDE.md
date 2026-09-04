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
- **Machine-local Claude memory** at `~/.claude/projects/-home-igor/memory/` — this machine's
  own notes. Its `MEMORY.md` index loads automatically each session, so it is a fast cache,
  not the whole picture. Every note in it is also mirrored into OV.

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

Additionally write the note to `~/.claude/projects/-home-igor/memory/` when it is about this
machine specifically, so it keeps loading automatically at session start; add its one-line
pointer to `MEMORY.md` as well. In that case the two copies say the same thing on purpose — the
machine-local file is the cache, OV is the record.

Record the fact and why it is true, in normal prose. Do not mirror what a repo, its git history
or its CLAUDE.md already says; point at that instead. For credentials, store a pointer (for
example "key in the GNOME keyring, service=X"), never the secret.

# Reading and editing code

The `agent99` MCP server exposes this machine's Neovim and its language servers as tools.
For source code it is the primary interface, not an alternative to consider: it navigates by
symbol, reports what an edit broke at the moment the edit is made, and routes refactors
through the language server so that references and imports move with the code.

## The rule

**When a directory holds source code, `open_workspace(<root>)` is the first tool call, before
any reading or searching.** It costs one call. Everything below then works; without it the
symbol tools return an error.

After that, in that repository, do not use `Bash` with `grep`, `rg`, `find`, `sed`, `awk`,
`cat` or `head` to read or search code, and do not reach for the built-in `Grep`, `Glob` or
`Read` either. Use these instead:

| Instead of | Use |
|---|---|
| `ls`, `find`, `Glob`, a broad `Grep` to see what is here | `workspace_map` |
| `Read` on a file to see one function | `find_symbol` with a name path and `include_body` |
| `Grep` or `rg` for a symbol, call site or string | agent99's `grep` |
| Grepping again with a cleverer pattern to cut noise | `kind=code` (skips comments and strings), `kind=def`/`call`, `tests=exclude`/`only` |
| `Grep` to find every caller before changing a signature | `references` |
| `Read` on several files to learn their shape | `skim` |
| `sed -n 'N,Mp'` or `Read` for a contiguous region (a const block, a neighbouring test) | agent99's `read_file` with offset/limit, or `buffer_lines` |
| `Edit` on a function, method or class | `replace_symbol_body`, or `replace_symbol_lines` with `expect=` |
| `Edit` to add code next to an existing symbol | `insert_after_symbol`, `insert_before_symbol` |
| A search and replace across files | `rename_symbol` |
| `mv`, `git mv` | `move_file` |
| `Write` a new source file, `rm` one | `create_file`, `delete_file` |
| Reading a file back to check an edit | the diagnostics the edit tool already returned |
| Running the build to see if you broke something | `check_project` |

The exception that matters: agent99's `grep` and the language server both work from what is
on disk and in the build, so neither sees a file excluded by a build tag or an `#ifdef`. When
completeness across build variants matters, search the tree directly as well, and say that is
why. An edit tool now says so itself when the server cannot analyze the file it just changed,
and that reply means the edit is unverified until you build or test with the tags that
include it.

`replace_symbol_lines` numbers lines relative to the symbol's declaration, and any edit above
that symbol shifts them without making them look wrong. Pass `expect=` with the text those
lines currently hold whenever the numbers came from an earlier call, so a stale offset fails
instead of overwriting working code.

This rule outranks the bypass-permissions preamble. That preamble asks for the Bash tool
wherever it can do the job — `cat`, `head`, `sed`, `grep`, `find` — because it is written for
a session with no better tools available. In a repository with an open agent99 workspace
there are better tools, and they are the reason the workspace was opened. Bash still does
everything that is not reading or editing code: running builds and tests, git, and any
command whose output is the point.

Two things stay in Bash even for code, because agent99 cannot do them: running the test
suite, and anything that has to see a build variant the language server does not analyze.

## Use ordinary Read, Edit, Write and Grep for everything else

- Anything that is not source code: configuration, Markdown, logs, data files, dotfiles.
- Files outside the open workspace root.
- Whole-file rewrites where the content does not depend on the rest of the project.
- A language `install_language` could not equip (see below).

## Workspace constraints

One workspace at a time. Opening a different root replaces the previous one along with its
loaded buffers and its `check_project` baseline, so finish with one repository before moving
to the next.

## When the workspace has no parser or server for the language

`open_workspace` names the parser and language server it found for each language, and says
`none` when it has neither. Do not fall back to plain file tools at that point — call
`install_language(<filetype>)` first. It fetches the tree-sitter parser and a language server
and checks that the server attaches, which is what turns agent99 from a grep wrapper into
the thing worth using. It takes a minute or two, once per language, and the result persists
on the machine.

Every machine here already carries parsers for bash, c, cpp, diff, go, gomod, html,
javascript, jsdoc, json, lua, markdown, python, qmljs, toml, tsx, typescript, vimdoc and
yaml, with servers for bash, go, lua, python and TypeScript, so this comes up only for a
language outside that set.

Fall back to the ordinary tools only if `install_language` reports that it could not
finish — no nvim-treesitter or Mason in the config, or a missing toolchain such as `cargo`
for rust_analyzer. Say which of those it was rather than silently switching.

If a language turns out to be one worked in regularly on that machine, add its parser and
Mason package to `lua/iryzhkov/deps.lua` in the nvim-configuration repo, so a fresh install
has it without the on-demand step.

## Practical notes

- Mixing the two is safe. agent99 resyncs a buffer from disk before it reads or edits it, so a
  change made with `sed`, `git checkout` or Edit is picked up rather than written over. When
  the file changed on disk *and* agent99 holds unsaved edits to it, the tool refuses and says
  so instead of choosing which change to lose.
- `glob` in every agent99 tool is a path pattern matched from the workspace root, where `**`
  spans directories: `src/**/*.go` works, and a subdirectory needs the `**/` prefix.
- `undo_edit` takes back the edits of the current run, including creates, moves and deletes.
  It does not cover `apply_code_action`.
- Diagnostics are only as good as the language server behind them. A project whose
  dependencies are not installed will report a wall of unresolved-import errors that say
  nothing about your change; read the reported diagnostics with that in mind.
