---
name: t3-backlog
description: >
  Queue work for the t3-steward backlog: an unattended T3 Code thread
  that starts in a quiet slot when the provider quota has room, on this machine
  or another host. Use when the user says to do something later, tonight, over
  the weekend, when they are not around, in the background, or to add it to the
  backlog or queue; when a task is big enough to eat a large share of the 5-hour
  window and does not need them; and for anything scheduled that used to open a
  T3 thread directly. Triggers: backlog, queue it, later, tonight, overnight,
  when I'm not using it, off-peak, async task, defer, schedule for a quiet time.
---

# t3-backlog

Every T3 host runs `t3-steward`, which watches the Codex and Claude
quota windows and keeps a backlog of markdown tasks. A task becomes a new T3
thread in its project when no interactive session has run for 30 minutes and
the watchdog's forecast of the user's own usage leaves room before the next
reset. The agent that runs it gets no input from anyone.

## Queue a task

Write the prompt to stdin of `t3-backlog`:

```sh
t3-backlog --project "laptop home" --title "Refactor the auth module" \
  --importance 4 --difficulty 3 --deadline 2d <<'PROMPT'
...the prompt...
PROMPT
```

Options: `--project` (T3 project title or id: the workspace; required),
`--title` (required), `--importance 1-5` (higher runs first), `--difficulty
1-5` (seeds the quota estimate: 5/10/20/35/50% of a window), `--deadline`
(`12h`, `2d` or RFC 3339; inside 24 h the task runs regardless of the
forecast), `--not-before`, `--model` with `--instance` (default: the
project's default model), `--max-turns` (default 3), `--host` (which
machine's T3 runs it), `--ungated` (run as soon as quota is healthy).

The script checks the task before queueing it: the project must exist on
the target host, the provider instance must be enabled and signed in, the
model must be one that instance offers, and the options must be ones the
model knows. A failed check prints what is wrong and queues nothing.

The path printed by `t3-backlog` proves only that the task reached the
configured intake directory. It does not prove that a workflow or T3 session
was created. After queueing, verify that the intake source is accepted (it may
remain as the durable idempotent source) and that
`t3-steward backlog list --project "<project>" --json` contains exactly one new
workflow run. Record its run id and, once dispatched, its thread id. If either
check fails, inspect `t3-steward backlog status --json` and the service journal;
do not blindly submit a duplicate.

Without `t3-backlog` on PATH, do not guess an intake directory. Establish the
active host's configured `backlog.dir`, write the file there only after
`t3-steward backlog check <file>` passes, and perform the same acceptance and
workflow-run verification. The old `~/.config/t3-steward/backlog/` directory may be a
legacy archive and must not be treated as active merely because it exists.

The compatibility input format is:

```markdown
---
project: laptop home
title: Refactor the auth module
importance: 4
difficulty: 3
model: claude-opus-5        # optional, with instance
instance: claudeAgent
options: {effort: high, contextWindow: 1m}
deadline: 2026-09-12T00:00:00-07:00
max_turns: 3
host: normandy              # optional
---
prompt
```

## Write the prompt for nobody

The runner prepends a preamble that forbids questions, asks for a handoff
when blocked, and requires a final `BACKLOG STATUS: done|continue|needs-input`
line. Your prompt still has to make that possible:

- Say what "done" looks like and how the agent can tell.
- Say where things are: repository, branch, files, the commands to run.
- Say what to leave behind: a branch and commit, a summary file, a PR, a
  feed post. The user reads results from the T3 app, so the final message
  matters.
- Decide the decisions now. Anything you leave open becomes `needs-input`
  and parks the task until the user answers in T3.
- One task, one outcome. Split big work into several tasks with
  `--importance` expressing the order; the runner runs one per provider at
  a time.

## Choose the host

`--host` names the machine (SSH alias) whose T3 server runs the task; the
project must exist there. Omit it to use the watchdog's `default_host`,
which is the local machine unless configured otherwise. Pick the host that
holds the workspace and the tools the task needs: normandy for the homelab
Docker stacks and OpenViking curation, the laptop for its own projects,
homelab for things that must run on the server itself.

## Watch it

```sh
t3-steward backlog status --json
t3-steward backlog list --project "laptop home" --json
t3-steward backlog show <workflow-run> --json
t3-steward backlog commands <workflow-run> --json
```

Use the revision-fenced admin controls shown by `t3-steward backlog --help`
for recovery. A successful helper exit without a corresponding workflow run
is an intake failure, not a completed queue operation.

`t3-steward backlog start` is an explicit operator override. It bypasses quota
forecast, admission, freshness, runway, and automatic quota throttling through
worker delivery. Use it only under explicit user authority while the user is
manually monitoring quota. Automatic backlog work must remain fenced; worker
health, dependency, lock, revision, and effect-safety checks still apply.

## Scheduled jobs

A `t3-job` file with `gated: true` is queued by its timer instead of run, so
weekly agent jobs take the next quiet slot. Scripts that used to open a
thread with `t3-run` use `t3-backlog` when the work can wait; keep `t3-run`
only for something the user is waiting on right now.
