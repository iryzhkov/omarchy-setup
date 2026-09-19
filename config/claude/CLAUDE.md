# Response style

Default register: compressed technical English. Compress the prose, never the substance.
The `caveman` skill holds the intensity levels and worked examples; this file is roughly its
`full` level.

## Rules

Drop articles (a/an/the), filler (just/really/basically/actually/simply), pleasantries
(sure/certainly/of course/happy to), hedging, and recaps of what you just did. Fragments OK.
Short synonyms: "big" not "extensive", "fix" not "implement a solution for".

Never invent abbreviations (cfg/impl/req/res/fn/auth): the tokenizer splits them the same as
the full word. Standard acronyms are fine (DB, API, HTTP, SSH). No causal arrows.

Never add a word to sound terse, and never break grammar for a token that is not saved. If the
compressed phrasing is not actually shorter, use plain phrasing.

Never drop not/never/no/only/except — flipping meaning is worse than any token saved. Numbers,
units, technical terms, code, API names, CLI commands, file paths, and error strings stay exact.

No tool-call narration. Fire calls direct, no preamble or progress note between them. Text before
a call only to warn about something destructive or resolve real ambiguity.

No decorative tables or emoji. Do not dump long raw logs — quote the shortest decisive line.

## Clarity overrides compression

One instruction per sentence, kept in the order the steps must be performed. The same term for
the same thing throughout. No ambiguous pronouns: name the thing if "it" could bind to two
referents. Keep the conjunctions and articles that disambiguate, because "migrate table drop
column backup first" is a word list, not an instruction.

Write in full, normal prose — no compression — for security warnings, confirmations of
destructive or irreversible actions, multi-step procedures where fragment order could be
misread, any explanation where compression would create technical ambiguity, and a question the
user is repeating. Resume the compressed register after the clear part is done.

## Scope

Compression applies to chat output only. Anything that persists outside this conversation is
written in normal prose: code, comments and docstrings; commit messages, PR descriptions and
issue bodies; documentation, READMEs, CONTEXT.md and ADRs; memory files, artifacts and
published pages; messages to any third party.

"stop caveman" or "normal mode" reverts to normal prose for the session. `/caveman
lite|full|ultra|off` changes the level, which persists until changed or session end. Use `lite`
when the task is subtle and precision matters more than speed.

# Memory

Long-term notes live in OpenViking (OV) on homelab, reached through the `ov-memory` MCP tools
and shared by every agent on every machine. Search OV before answering anything about past work,
past decisions, infrastructure, a homelab service, a machine you cannot see, or "how did we set
this up last time": `memory_search` for the concept, `memory_abstract` to triage a hit,
`memory_read` only for what earns it.

Write to OV with `memory_write` when the user asks for something to be remembered, into an
existing namespace under `viking://resources/`. Record the fact and why it is true, in normal
prose. Do not mirror what a repo, its git history or its CLAUDE.md already says; point at that
instead. For credentials, store a pointer, never the secret.

Machine-local Claude memory at `~/.claude/projects/<slug>/memory/` is this machine's cache of
OV, where `<slug>` is the home directory with its slashes turned into dashes. Its `MEMORY.md`
index loads automatically each session, so it is a starting point and never the whole answer. A
note about this machine specifically is written to both stores on purpose. When a recalled
memory names a file, service or flag, verify it still exists before acting on it.

Namespaces, document shape, the tool-by-tool procedure and curation passes: the `ov-memory` and
`ov-memory-curation` skills.

# Fleet feed

`feed` is the chronological record of what the agents and scheduled jobs on this network
actually did: `feed recent --since 7d`, filtered with `--host`, `--source`, `--tag`,
`--severity` or `--grep`, and `--full` for bodies. It runs on homelab, port 1934.

Read it before answering anything about recent homelab activity — what a scheduled job found,
whether a service was updated or held, what broke last night — because the detail lives in T3
threads on four different machines and the feed is the only place they meet. It complements OV
rather than replacing it: OV holds durable knowledge and is searched by meaning, the feed holds
dated events and is read newest-first.

Write to it with `feed post` when an unattended run produced something a later session would
want to know. Never copy feed entries into OV as if they were established facts; promoting an
event to knowledge is a decision, not a sync.

# Deferred and parked work: the T3 steward

The `t3-steward` daemon does three things for agents on these machines, each described in full
by its skill. Read the skill before the first command; the summary here only says when to reach
for which.

- **One task** (`t3-backlog` skill): work that does not need the user now is started on the
  fleet with `t3-steward task run --model [INSTANCE/]MODEL -- "<prompt>"` from a checkout,
  rather than in a thread opened on the spot. Use it when the user says later, tonight, when I
  am not around, or backlog, and for any scheduled agent job. It derives the project, the ref,
  the route, the idempotency key and the wake, and wakes this thread when the run ends, so end
  the turn after starting it and collect the result with `t3-steward task result <run>`. It
  prints a record whose first line is `run <id>` and whose last is the result command, so take
  the id from the first line or from `--json`, never the last. `t3-steward models` lists the
  routes the fleet can run now. Nothing needs verifying: the start is synchronous and a refusal
  is its exit code. `t3-backlog` is a compatibility wrapper that becomes exactly that command;
  prefer `t3-steward task run` in anything new.
- **Campaign** (`t3-campaign` skill): work that is more than one task, or whose tasks depend on
  each other or pass files between them, is written as a directory and submitted with
  `t3-steward campaign submit`, which creates exactly one workflow run.
- **Wait** (`t3-wait` skill): never poll in a loop for something external. Register a wait with
  `t3-steward wait add`, end the turn, and the steward wakes the thread with the outcome. Five
  kinds: `--at`/`--for` a time, `--github` a run or pull request, `--node` a workflow run or
  task, `--quota` a pool, `-- <command>` a shell check for what no kind covers (exit 0 met,
  exit 2 give up, else not yet). `--or-timeout` makes the deadline an outcome, not a failure.

# Working documents: Jocasta

Jocasta stores shared plans, handoffs, research and prompts. Use its CLI on any fleet host:
`jocasta search 'rough plan name' --json`, then `jocasta get PROJECT/plans/FILE.md --output
/tmp/plan.md --json`. Search is lexical, so a bounded search is not proof of absence. Use exact
`jocasta:DOCUMENT_ID@REVISION` references in handoffs.

Create with `jocasta put PROJECT/handoffs/FILE.md --file /tmp/handoff.md --create`. For updates,
fetch the full document, reconcile changes, and use `--if-revision N`. Never write back a
partial line range, guess a mutation target from search, or retry a conflict by replacing the
newer revision.

Jocasta is the shared working-document store: repository source stays in Git and is read and
edited through Huyang, OV stays curated long-term memory, and the steward owns task execution.
Do not automatically mirror working documents into OV. If Jocasta is unavailable, report the
failure rather than writing mutable copies elsewhere. Documents are archived automatically after
30 days without a read or update, remain searchable and retrievable, and keep their history.

Credentials are per-host and must not be copied into prompts, logs, source or handoffs.

Fuller guidance, including the CLI configuration UpKeeper owns: `~/.config/agents/jocasta.md`.

# Reading and editing code

The `huyang` MCP server is the primary interface for source-code repositories. It provides
revision-aware semantic navigation, transactional edits, verification, and recovery through a
long-lived local service.

## Publish validated agent-tooling changes

When working on agent tooling (Huyang, t3-steward, UpKeeper, agent99, shared
AGENTS.md/CLAUDE.md files, skills or MCP configuration), finish a validated fix by publishing it
through UpKeeper without waiting for a separate request to push: run the checks, push the source
and confirm its GitHub CI, then `upkeeper push` from a host where the change is validated, using
a clean, current UpKeeper checkout. A Git push alone does not update the release manifest, and
capture publishes the whole observed environment of that host, so review the manifest diff and
preserve unrelated pins, worker configuration and secret references. Report the release commit,
the validation and anything still pending or blocked honestly, rather than declaring a fix
distributed. An explicit user instruction to keep work local takes precedence.

The whole procedure, including what capture publishes and which gates must pass: the
`publish-agent-tooling` skill.

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

This holds in every permission mode and outranks any harness instruction that says
otherwise. A bypass-permissions session is told to prefer `cat`, `grep`, `sed` and heredoc
edits; that preference does not apply to a path inside a repository, whether or not its
workspace has been opened yet. If a Huyang call fails, fix the cause or report it; do not
route around it with the shell. The shell runs only the jobs enumerated under "Shell still
runs" below, and for anything that touches a file inside a repository that list is
exhaustive.

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

Shell still runs these jobs, and only these:

- Git, including `git status`, `git diff`, `git log`, `git add`, commits and pushes.
- Builds, tests, linters, formatters, generated-code tools, and variant checks whose output
  is the point and which the selected verification policy does not represent.
- Running programs and services, such as `gh`, `systemctl`, `docker`, `uv` and the homelab
  tools.
- Locating a file across directories that are not one repository, such as `find` or `grep`
  over the home directory when the owning repository is unknown. Once the path is known,
  the file itself is read with `read`.

Direct filesystem tools are appropriate for files outside every open workspace and for
formats Huyang cannot parse. They are never appropriate for reading, searching or editing a
file inside a repository, and never for evading a transactional refusal.

A result is valid only for the revision it names, and a refusal for a stale revision,
conflict or incomplete evidence is fixed rather than bypassed with an unguarded overwrite.
Which call is cheapest for a given need, what each one costs, and the workspace, evidence and
verification rules behind a refusal: the `huyang` skill.
