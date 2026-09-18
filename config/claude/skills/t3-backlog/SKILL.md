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

Every T3 host runs `t3-steward`. The fleet's coordinator dispatches a task to a
worker as a new T3 session in the project's checkout, when the quota of the
route it is to run on has room. The agent that runs it gets no input from
anyone.

The way to start one is `t3-steward task run`; `t3-backlog` is a compatibility
wrapper over it. One task, one outcome: that is what this skill is for. Work
that is more than one task, or whose tasks depend on each other or pass files
between them, is a campaign; see the `t3-campaign` skill.

## Start a task

From a checkout, one call:

```sh
t3-steward task run --model claude-haiku-4-5 -- "...the prompt..."
t3-steward task run --model t3-primary/opus --prompt-file plan.md --json
t3-steward task run --model opus --fan-out prompts/*.md      # one run, one task per file
```

It derives what you would otherwise invent, and prints every derived value:
the fleet project from this checkout's origin remote, the ref from the current
branch, the route from `--model`, the idempotency key from a digest of all of
them plus the prompt, and the wake. The run id is printed, so nothing has to
poll to find out whether the task exists.

Flags: `--project NAME` (when the remote matches no project or several),
`--ref REF`, `--fresh`, `--model [INSTANCE/]MODEL`, `--worker WORKER`,
`--name TEXT`, `--outputs a.md,b.md`, `--verify "CMD"` (repeatable),
`--class surplus|required`, `--max-turns N`, `--idempotency-key KEY`,
`--no-notify`, `--json`. The prompt is exactly one of an argument after `--`,
`--prompt-file FILE`, `--prompt-file -`, or stdin.

What the fleet can run right now:

```sh
t3-steward models [--project NAME]    # instance/model, pool, quota phase, workers
t3-steward backlog projects           # projects, their repositories, eligible workers
```

Refusals are the point of the derivation and each says what to pass instead: a
remote no project matches, a model several instances offer, a detached HEAD or
an unpushed branch ("push first or pass --ref"), more than one prompt source,
and no route with no `defaults.model` configured. A dirty tree is a warning,
not a refusal: uncommitted changes are not sent, the worker fetches the ref.

The calling thread is woken when the run ends, so **end the turn after
starting a task**. On wake, collect the result in one call:

```sh
t3-steward task result <run>            # writes ./.t3/results/<run>/<task>/
t3-steward task result <run> --json     # the final message inlined
```

It exits 0 when the task succeeded, 2 when it failed or was cancelled (writing
whatever exists), and 1 when it is not terminal yet.

### The t3-backlog wrapper

`t3-backlog` still exists for the scripts that call it and is a thin wrapper
over `t3-steward task run`:

```sh
t3-backlog --project steward --title "Refactor the auth module" \
  --model claude-haiku-4-5 <<'PROMPT'
...the prompt...
PROMPT
```

`--title` and `--name` become `--name`, `--instance` is folded into `--model
INSTANCE/MODEL` and is refused without one, `--host` is the worker it always
was and is passed as `--worker`, `--ungated` becomes `--class required`, and
the prompt still comes from stdin. There is no default provider instance any
more. `--importance`, `--difficulty`, `--deadline` and `--not-before` are
accepted and reported as ignored: the fleet no longer schedules by them. Prefer
`t3-steward task run` in anything you write now.

There is nothing to verify afterwards. Both commands submit synchronously and
print the run id, and a refusal is a non-zero exit with the reason; a start
that printed a run is a run that exists. Re-running the same command replays
the same run and says `replayed: true`, so a retry after an ambiguous failure
is safe and never starts a second run.

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

## Choose the worker

A worker is a fleet host the coordinator dispatches to, named by its worker id
and not by an SSH alias. Leave it unset and the coordinator picks any eligible
worker that advertises the project and the route, which is what you want unless
the task needs one machine's own state: normandy for the homelab Docker stacks
and OpenViking curation, homelab for things that must run on the server itself.
`t3-steward backlog projects` lists each project's eligible workers and what
they advertise; `--worker NAME` (`--host` in the wrapper) pins one.

## Watch it

```sh
t3-steward backlog status --json
t3-steward backlog list --project "laptop home" --json
t3-steward backlog show <workflow-run> --json
t3-steward backlog commands <workflow-run> --json
```

Use the revision-fenced admin controls shown by `t3-steward backlog --help`
for recovery. To stop a run, `t3-steward campaign cancel <run> --reason TEXT`
cancels every non-terminal task of it with one command; the `<run>/<task>`
form cancels one task and its dependents.

```sh
t3-steward backlog start <workflow-run>/<task> --reason TEXT [--command-id ID] [--json]
```

`backlog start` is an explicit operator override. It bypasses quota forecast,
admission, freshness, runway, and automatic quota throttling through worker
delivery. Use it only under explicit user authority while the user is manually
monitoring quota. Automatic backlog work must remain fenced; worker health,
dependency, lock, revision, and effect-safety checks still apply.

## Talking to the coordinator

The legacy task-file helpers (`backlog new`, `path`, `check`, `receive`,
`list --all`) are offline. Everything else above reaches the coordinator:
through its owner-only socket on the coordinator host, and on any other host
through an SSH session to its restricted `coordinator-exchange` command,
selected by a coordinator client in `backlog_v2.coordinator_client` or in the
UpKeeper-owned `~/.config/t3-steward/coordinator-client.json` (mode 0600), whose
credential is a `secretref:f03-admin/<client>` reference resolved at use.

**Never run `ssh <coordinator> t3-steward ...`.** The client transport is the
authority boundary; opening a shell on the coordinator host goes around it. The
one exception is `t3-steward worker enroll`, an operator action that must run on
the coordinator host; the `t3-campaign` skill describes it.

```sh
t3-steward coordinator identity --json   # which coordinator answers, and how
```

Branch on the exit code, not on the message: 0 answered, 3 client
configuration, 4 authentication, 5 unavailable, 6 timeout, 7 protocol, 8 refused
by the coordinator, 1 anything else. 3, 4 and 8 are permanent until something
changes; 5 and 6 are usually temporary. With `--json`, a failure that reached
the transport also prints
`{"version":"backlog.admin/v1","kind":"error","class":"...","operation":"...","message":"..."}`
on standard output. Re-running with the same `--idempotency-key`, `--request-id`
or `--command-id` is always safe: it returns the first answer rather than doing
the work twice.

## When a queued task never appears

This is about the file-based intake only. `t3-steward task run` and the
`t3-backlog` wrapper submit synchronously and a refusal is their exit code, so
they cannot leave this behind. A task file the coordinator can never accept —
one naming a project no alias maps, one naming no provider route at all, or one
whose content changed after its key was accepted — is recorded as quarantined,
reported once, and then skipped silently on every later cycle. The symptom is a
queued file and no new workflow run, with nothing being logged any more.

```sh
t3-steward backlog quarantine [--json]
```

That is a read. It reports every marker with its intake key, the namespaced key
its record is stored under, the content digest it was recorded for, when it was
quarantined, the reason, and the retry rule. The quarantine names no workflow
run, so `backlog events` cannot show it.

Usually the fix is the file: change its content, the digest changes, the marker
is released and intake tries again. For a refusal the file cannot fix — adding
the missing project alias changes no byte of it, so intake would stay silent
forever — clear it deliberately after fixing the configuration:

```sh
t3-steward backlog quarantine release <key> --reason TEXT [--json]
```

Pass the intake key, not the namespaced record key. `--reason` is required and
audited, because the operator and not the file is what changed. The release
creates nothing: the next cycle reads the file again and refuses it again if it
is still impossible. Releasing a key that holds no marker reports exactly that
instead of failing, so an ambiguous response is safe to retry. Both verbs work
from a host that is not the coordinator.

## Waiting inside a backlog task

A running task that has to wait for something external — CI, a review, a long
build, a time, a quota window — must not poll and must not finish. It registers
a task-bound wait of the matching kind, which parks the attempt, and ends the
turn:

```sh
t3-steward wait add --task current --github run "$(gh run list --branch "$(git branch --show-current)" --limit 1 --json databaseId --jq '.[0].databaseId')" --timeout 2h
t3-steward wait add --task current --github pr 123 --state reviewed
t3-steward wait add --task current --for 30m --or-timeout
t3-steward wait add --task current --quota claude-main --phase normal
```

The wake begins with `t3-steward-wait kind=... outcome=... wait=...`; branch on
`outcome` (`met`, `failed`, `gave-up`, `cancelled`, `timed-out`). A shell
check (`-- <command>`) is for what no kind covers.

`--request-id` defaults to `park-<attempt>-<revision>` from the task's identity;
a custom one may use `$(t3-steward task env --get revision)`. The
`T3_STEWARD_*` variables are not in the shell environment unless
`t3.send_thread_environment` is on (off by default).

While that wait is live the task is not complete, not verified and not failed:
no output is collected, no verification runs, and the run cannot settle. **End
the turn as soon as it registers.** Read the `t3-wait` skill before using it.

## Scheduled jobs

A `t3-job` file with `gated: true` is queued by its timer instead of run, so
weekly agent jobs take the next quiet slot. Scripts that used to open a thread
with `t3-run` use `t3-steward task run` when the work can wait; keep `t3-run`
only for something the user is waiting on right now.
