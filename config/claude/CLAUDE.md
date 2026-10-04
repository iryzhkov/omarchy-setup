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

# Interactive work and the T3 steward

Read the matching steward skill before its first command.

Stay interactive while exploring, designing, answering contract questions and making
decisions turn by turn. Hand off to a campaign once Igor has agreed a plan; never
submit exploration that is not yet a plan. Use a subagent for quick same-provider
reading or sub-work inside either an interactive session or a steward task.
Subagents are never in place of a declared task or review.

Agree the plan, write it to Jocasta, turn it into a campaign with the
`t3-campaign` skill, and submit with the session as notify thread
(`--notify-thread current`). Once Igor has agreed the plan in the session,
agents may submit it without another approval: say that the campaign started and
give the run id and ledger reference. Ask first when the estimated cost is large,
the work needs operator-level access, or it releases to the fleet. After handoff,
keep only the run id and Jocasta ledger reference in the session's working set;
fetch detailed evidence when needed.

Use `task run` for one independent outcome and `campaign submit` for an agreed
workflow; recurring timing belongs to `schedules`. Routine authorized cancellation
uses `campaign cancel <run>[/<task>] --reason TEXT`. Legacy Markdown file intake
and wrapper submission are permanently retired in the new source: local runner,
coordinator intake and file forwarding cannot execute Markdown work. Old true
enable flags are rejected; false values are parsed for compatibility. Retained
`backlog` diagnostics and fenced operator controls remain available. Historic
quarantine release is authenticated marker-only cleanup; it creates nothing and
cannot retry intake. Preserve files and quarantine evidence under rollout lead
custody. Source publication does not prove runtime deployment; the rollout lead
owns immutable rollback bundles, never scanner reenablement. The `t3-campaign`
skill documents the authority and rollback boundary.

With explicit `agents-instructions-gen --policy FILE`, the generated imported
Claude artifact replaces the manual fallback below with Claude-specific policy roles;
Codex receives its own policy projection. Without that deployment, keep the manual
guidance and explicit routes. Native roles cover bounded same-provider work only.
Operator/session provider or effort restrictions require explicit pins in Steward.

Model roles are assigned by hand until a generated policy replaces them:
Opus 5.5 or Sol 6.1 at high effort for planning and execution; Fable 5.1 or Astra
at medium effort for critical review, including plan review; Sonnet 5.5 or Luna 6
at medium effort for reading. Never use max effort or above. Check
`t3-steward models` for available routes; role names are guidance, not CLI flags.
In Claude Code, bulk reading (many files, long logs, large diffs or codebase
searches) goes to a reader subagent (`model: sonnet`) with a focused question and
a bounded answer. Codex sessions use Luna 6 (`codex/gpt-6-luna`) at medium effort for the same.
Read a quick lookup in a known file directly.

Inside a steward task, `t3-steward ask` is the one way to get a decision from Igor:
give options, a deadline and a safe default, end the turn after parking, and read
`ask-answer.json` on resume. Approver-required asks take no default and fail
unanswered. Outside a task, use the session's own question tool.
Use `t3-steward review` for cross-provider plan or diff review; the
`t3-campaign` skill describes file inputs and the review digestion loop.

- **One task** (`t3-task` skill): one independent unattended outcome uses
  `t3-steward task run --model [INSTANCE/]MODEL -- "<prompt>"` from a checkout.
  Use `--input FILE` for pinned inputs and `--dry-run` before submission.
  The start is synchronous; a refusal is its exit code. Take the run id from
  the first line (`run <id>`) or JSON, never from the closing result command.
  Follow the record's closing instruction: end the turn only when it promises
  a wake; collect immediately when the run already ended.
- **Campaign** (`t3-campaign` skill): dependent tasks, artifact handoffs,
  declared reviews and recurring schedules use a version 2 workflow directory.
  Run `campaign validate`, `campaign plan` and read-only `campaign check`;
  submit with an idempotency key and the session as notify thread.
  Tasks keep `continuation.md` current; details and the milestone ledger template
  live in the skill. A caller intentionally wanting no wake uses `--no-notify`;
  unresolved notify threads are refused before submission.
- **Wait** (`t3-wait` skill): use a foreground blocking command such as
  `t3-steward task result <run> --wait` or `campaign show <run> --wait` in a plain CLI.
  In a steward task, register `wait add --task current` for external waits and
  end the turn immediately. Conditions are `--at`/`--for` time, `--github`,
  `--node`, `--quota`, or `-- COMMAND` (0 met, 2 give up, else not yet).
  `--or-timeout` makes a deadline an outcome. Ordinary sessions register a
  thread wait and end the turn. Never poll in an agent loop.
  Use `t3-steward triage` for operator attention and ready-to-run recovery commands.

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
