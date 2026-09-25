---
name: t3-task
description: >
  Queue one independent unattended task with t3-steward so it runs on an
  eligible fleet worker when its quota pool has room. Use for a single outcome
  that can run without the user now, including requests to do it later, tonight,
  off-peak or in the background. Use t3-campaign instead for dependent tasks,
  artifact handoffs, plan-review-implementation pipelines, or recurring
  schedules. Triggers: queued task, single unattended task, backlog, queue it,
  later, tonight, overnight, when I'm not using it, off-peak, async task, defer.
---

# t3-task

Every T3 host runs `t3-steward`. The fleet's coordinator dispatches a task to a
worker as a new T3 session in the project's checkout, when the quota of the
route it is to run on has room. The agent that runs it gets no input from
anyone.

The way to start one is `t3-steward task run`; `t3-backlog` remains only as a
compatibility wrapper over it. One task, one outcome: that is what this skill is
for. Work with dependent tasks, artifact handoffs, a review pipeline or a
recurring schedule is a campaign; see the `t3-campaign` skill.

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
them plus the prompt, and the wake. The run exists as soon as the command
exits 0, so nothing has to poll to find out whether it does.

What it prints is a record, not a bare id. Its **first** line is `run <id>`;
then `tasks`, `project`, `ref`, `route` and `idempotency-key ... (replayed:
...)`; its **last** line is the indented `t3-steward task result <run>` command
under `next:`. Take the id from the first line, or pass `--json` and read
`.run`. A caller that took the last line took the hint, not the id.

What comes between depends on what the start did. A fresh start says `check
<outcome>` and then `notify thread ... (wait ...) delivery= host=`. A start
whose key replayed onto an existing run says `progress <state> (this run
already exists; nothing new was started)` instead of `check`, or `progress
unknown: <cause>` when the coordinator could not be asked, and it carries no
`notify` line at all when that run has already ended.

Flags: `--project NAME` (when the remote matches no project or several),
`--ref REF`, `--fresh`, `--model [INSTANCE/]MODEL`, `--worker WORKER`,
`--name TEXT`, `--outputs a.md,b.md`, `--verify "CMD"` (repeatable),
`--class surplus|required` (default `surplus`), `--max-turns N` (default 3),
`--idempotency-key KEY`, `--notify-thread current|THREAD-ID` (default
`current`), `--no-notify`, `--json`. The prompt is exactly one of an argument
after `--`, `--prompt-file FILE`, `--prompt-file -`, or stdin.

`--fresh` runs the task in a new empty directory instead of a checkout, for
research or spike work whose result is files rather than commits. It needs no
checkout and derives no ref; the project is the catalog's one project of type
fresh, or `--project NAME` naming one. Name what it writes with `--outputs`,
because only declared outputs are collected:

```sh
t3-steward task run --fresh --model claude-sonnet-5 --outputs findings.md -- "..."
```

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

The calling thread is normally woken when the run ends, so the usual thing to
do after a start is to end the turn. **Do what the record's closing line says**
rather than ending it by habit: it says `End this turn now` only when a wait
exists that will fire for this thread, and otherwise it says that no wake is
attached, or that this run has already ended and the result is there to collect
now, and names the command to run instead. On wake, or on being told to collect,
it is one call:

```sh
t3-steward task result <run>            # writes <state>/results/<run>/<task>/
t3-steward task result <run> --json     # the final message inlined
t3-steward task result <run> --output . # under the working directory instead
```

The default is outside every checkout, so collecting a result never dirties a
working tree, and the absolute path it wrote to is printed.

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

It becomes exactly one `t3-steward task run --prompt-file - --class
surplus|required ...`, carrying only the options you passed, and execs it: the
output and the exit code are t3-steward's own, and there is no second call.

`--title` and `--name` become `--name` (default: the prompt's first line),
`--instance` is folded into `--model INSTANCE/MODEL` and is refused both
without `--model` and when `--model` already names an instance, `--host` is the
worker it always was and is passed as `--worker` (which the wrapper also
accepts under its own name), `--ungated` becomes `--class required` where the
default is `--class surplus`, and the prompt still comes from stdin.
`--project` is a fleet project name, never a T3 project title. `--ref`,
`--outputs`, `--max-turns`, `--idempotency-key`, `--no-notify` and `--json`
pass straight through with their `task run` meanings; anything else is refused
as an unknown option, and that includes `--notify-thread`. A caller that has to
name the thread to wake calls `t3-steward task run` directly. There is no
default provider instance any more.
`--importance`, `--difficulty`, `--deadline` and `--not-before` are accepted
and reported as ignored: the fleet no longer schedules by them. Prefer
`t3-steward task run` in anything you write now.

A caller that runs unattended, with no thread of its own to be woken, has two
answers, because `task run` refuses a start nobody would hear about:
`--no-notify` when nobody is meant to be woken, and `--notify-thread <id>` when
somebody is. A script on another host, in cron or in CI wants the second.

There is nothing to verify afterwards. Both commands submit synchronously, both
print the same record whose first line is `run <id>`, and a refusal is a
non-zero exit with the reason; a start that printed a run is a run that exists.
Re-running the same command replays the same run and says `replayed: true`, so
a retry after an ambiguous failure is safe and never starts a second run. A
replay also reports that run's own progress, and when the run has already
ended it tells you to collect the result rather than to end the turn. The
idempotency key does not include `--name` or `--host`, so two starts that
differ only in those are refused as one key with two contents; pass a distinct
`--idempotency-key` when they are meant to be two runs.

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
- One task, one outcome. Split big work into several tasks, each with its own
  prompt and its own finish. Nothing here expresses an order between them:
  what decides when a task runs is `--class`, which is `surplus` by default
  and consumes only forecast headroom, against `required`, which draws on
  reserved capacity and still waits for a quota pool that has closed. Work
  where one task must finish before another starts is a campaign with a
  `needs` edge, not two starts in the order you happened to send them.

## Choose the worker

A worker is a fleet host the coordinator dispatches to, named by its worker id
and not by an SSH alias. Leave it unset and the coordinator picks any eligible
worker that advertises the project and the route, which is what you want unless
the one-off task genuinely needs one machine's own state. Recurring operational
jobs are campaigns and should normally let `resources.preset` choose placement.
`t3-steward backlog projects` lists the projects with a worker and route count
each; add `--project NAME` for one project's eligible workers and everything
they advertise, or `--verbose` for all of them. `--worker NAME` (`--host` in
the wrapper) pins one.

## Watch it

```sh
t3-steward backlog status --json
t3-steward backlog list --project steward --json
t3-steward backlog show <workflow-run> --json
t3-steward backlog commands <workflow-run> --json
```

`--project` here is the fleet project name, the one `t3-steward backlog
projects` lists and `task run --project` takes, never a T3 project title. A
name no project has is not refused: the list comes back empty.

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
monitoring quota. Automatic queued work must remain fenced; worker health,
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

## Legacy file-intake quarantine

This applies only to compatibility file intake, not `t3-steward task run`,
recurring schedules or campaign submission. `t3-steward task run` and the
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

## Waiting inside a task

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

## Recurring schedules use campaigns

A recurring operational job is not a repeated `t3-task`. Author it as a version
2 campaign, submit the immutable bundle to establish its workflow, and point a
coordinator schedule at that workflow. The coordinator owns cron timing,
run history, failure policy and overlap prevention. Read the `t3-campaign`
skill for the schedule workflow and revision-fenced controls.

Use `t3-steward task run` for a one-off independent job that can wait for quota.
Do not recreate recurring jobs with local timers, compatibility task files or
scripts that repeatedly open T3 threads.
