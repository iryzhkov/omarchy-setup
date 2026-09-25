---
name: t3-wait
description: >
  Park a thread until something external happens, instead of polling in a loop:
  register a wait with the t3-steward (a time, a GitHub run or pull request, a
  workflow node, a quota pool, or a shell check), end the turn, and the steward
  wakes the thread with a parseable outcome line when it is met, fails, gives
  up, is cancelled or times out. Inside a backlog or campaign task, `--task
  current` parks the task attempt itself, so the turn must end there. Use
  whenever you would otherwise sleep and re-check: waiting for PR reviews or
  CI, a deploy or a long build, a time of day, another campaign, a quota window,
  a file or service to appear. Triggers: wait for, poll, check back later, until
  CI passes, when the PR is reviewed, once the job finishes, wait until, sleep
  and retry, park the task, waiting-external, quota reset.
---

# t3-wait

Polling from inside a thread burns quota for nothing and gets the thread
interrupted by the steward when the window runs low. Register the poll with the
steward instead and end the turn; the thread costs nothing while parked and
comes back with the result.

## First decide which kind of wait this is

They differ in what they wake and in what they are allowed to change, and
choosing the wrong one is the difference between a task that parks safely and a
task that is verified against work it has not done.

| | Task-bound wait | Interactive wait |
| --- | --- | --- |
| How | `wait add --task current` | `wait add` with no `--task`, or `--task <run>/<task>`, or `--run <run>` |
| Where | inside a backlog or campaign task | an ordinary session |
| Effect | **mutating**: parks the attempt in `waiting-external` | non-mutating: wakes a thread, changes no workflow state |
| After registering | **end the turn immediately** | end the turn |

`--task current` outside a task is an error that says so; it never silently
degrades into an interactive wait.

## Then pick the kind

Every wait has one condition, its kind. Both forms take every kind. Use the
primitive; do not rebuild it from `date`, `gh ... --jq` or `backlog show` in a
shell loop.

| Kind | Registration | Met when | Settled by |
| --- | --- | --- | --- |
| `time` | `--at 2026-09-18T22:00:00Z` or `--for 2h30m` | the instant passes | this host |
| `github` | `--github run <id>` (default `--state completed`), `--github pr <n> --state merged\|reviewed\|checks-passed`, `[--repo owner/name]`; from rc.96 the target may also be `owner/name#N` or a github.com PR/run URL, which sets the repository | a run completes with conclusion success (any other conclusion is `failed`); a PR is merged (`failed` when closed unmerged); every check succeeded (`failed` when any failed); the first review lands | this host, reading `gh` with fixed arguments |
| `node` | `--node <run>` (its sink) or `--node <run>/<task>`, `--state terminal\|succeeded\|paused\|waiting-external\|active` (default `terminal`) | the node reaches the state; `terminal` is met on any terminal progress except cancelled, `succeeded` is `failed` on a failed run | the coordinator, from its own records; no local check |
| `quota` | `--quota <pool> --below 50`, `--quota <pool> --phase normal`, `--quota <pool> --reset` | the pool is under the percent, every bucket is normal, or the window current at registration has reset | the coordinator, from the merged bucket observations |
| `shell` | `-- <command>` | the command exits 0 (exit 2 gives up, anything else is not yet) | this host |

`--timeout` bounds every kind (default 24h; a time wait's default covers its
instant). Add `--or-timeout` when the deadline is an acceptable end rather
than a failure: the wake still says `outcome=timed-out`, with
`or-timeout=true`, and nothing calls it a failure.

## Task-bound wait: registering it parks the task

```sh
t3-steward wait add --task current --github run "$(gh run list --branch "$(git branch --show-current)" --limit 1 --json databaseId --jq '.[0].databaseId')" --timeout 2h
t3-steward wait add --task current --github pr 123 --state reviewed --timeout 24h
t3-steward wait add --task current --for 30m --or-timeout
t3-steward wait add --task current --node run-abc/implement --state succeeded
t3-steward wait add --task current --quota claude-main --phase normal
t3-steward wait add --task current --name "deploy finished" -- ./scripts/deployed.sh
```

A `node` or `quota` wait registered this way parks the attempt with no check
on the worker at all: the coordinator settles it. A task cannot wait for its
own run's sink (the run cannot settle while the attempt is parked); wait for a
sibling task instead.

No `--request-id` is needed: it defaults to `park-<attempt>-<revision>` from the
task's identity, which is stable for a retry of the same park and different for
every later park.

On success the command prints `This task is now parked.` **That is an
instruction. End the turn there.** The task is not complete, not verified and
not failed. While the wait is live:

- the worker collects no declared outputs;
- no verification command runs;
- no dependent task is released and the run sink cannot settle;
- the executor slot, the CPU, memory and scratch reservation, the provider slot
  and the quota tally are released;
- the attempt, the thread, the workspace, the artifacts, the dependency mounts,
  the assignment ownership, the resource locks and the directory bindings are
  held.

An agent that keeps working after registering one is the exact failure this
mechanism exists to prevent: a turn that ends with outputs half written, a
`done` marker the coordinator rejects, and a thread still producing effects
nobody owns.

### How `current` knows which task it is

The worker writes the execution identity into the prepared workspace as
`.t3-steward/task.env` (mode 0600), and the command finds that file by searching
upward from the working directory. The six variables it holds are:

```text
T3_STEWARD_WORKFLOW_RUN_ID  T3_STEWARD_TASK_ID     T3_STEWARD_ATTEMPT_ID
T3_STEWARD_ATTEMPT_REVISION T3_STEWARD_ASSIGNMENT_ID T3_STEWARD_THREAD_ID
```

They are **not in the shell environment** unless `t3.send_thread_environment`
is on in the steward configuration (off by default):
`$T3_STEWARD_ATTEMPT_REVISION` expands to nothing, and a command line built
with it silently loses the value. To read
the identity, run `t3-steward task env`, which prints `export NAME=value` lines
from the file (`eval "$(t3-steward task env)"` exports them), or
`t3-steward task env --get revision` for one value (`revision`, `attempt`,
`task`, `run`, `assignment`, `thread`, or the full variable name). Outside a
task it exits 1 and says so.

The registration is fenced on the attempt revision in that file. Two refusals
are ordinary command errors: report them, do not retry blindly.

- `attempt is terminal (<progress>); task-bound waits are refused` — the turn
  already completed. The task is over; do not keep working.
- a stale attempt revision — the attempt moved on since this process started.

### `--request-id` names one park, not a standing permission

Repeating a request ID while that wait is still live and holding this attempt
returns the same wait, which is what makes a retried registration safe.
Repeating it after that wait settled is **refused**: the ID names one park.
The default, `park-<attempt>-<revision>`, already gives every park of the same
task its own ID. A custom ID that must differ per park can include
`$(t3-steward task env --get revision)`; an ID that ends in `-` is warned about,
because it almost always means an empty variable was interpolated. A repeated ID
with different contents is also refused.

### What happens on wake

The same thread and the same attempt resume, with the wait result in the initial
context. Placement, capacity and locks are reacquired through the normal paths;
it is a new turn on the existing attempt, not a new attempt. Outputs written
after waking are the outputs that are collected, and verification runs once, at
the end of the turn that ends with no live wait.

A failed or timed-out wait still wakes the task, with structured evidence: which
wait, which condition, which exit status, how long it ran. Silence is not an
outcome. A timeout releases the attempt to finish or fail honestly; it never
leaves the task parked. Cancelling the task settles its live wait as
`cancelled`. Handle the failure or produce an honest final failure — do not
treat a wake as proof the condition was met: read the trailer.

Re-read the current state before continuing; other things may have moved while
the thread was parked.

## Reading the wake: the trailer

The first line of every wake message, every kind, interactive and task-bound,
is one parseable line:

```text
t3-steward-wait kind=<kind> outcome=<outcome> wait=<id> <key>=<value> ...
```

`outcome` is one of `met`, `failed`, `gave-up`, `cancelled`, `timed-out`.
Branch on `outcome`, then read the kind's pairs:

| Kind | Pairs |
| --- | --- |
| `shell` | `exit=` |
| `time` | `at=` (RFC 3339) |
| `github` | `target=run:<id>\|pr:<n> state= conclusion= url=` |
| `node` | `run= task= attempt= revision= progress=`, `control=` and `pauseReason=` for the attempt states, and for a terminal run `failed=<comma list>` and `result="t3-steward task result <run>"` (the command to fetch the run's result) |
| `quota` | `pool= phase= percent=` (and `resetsAt=` when known) |

Values with a space are quoted; ignore keys you do not know; do not depend on
the order of the pairs after the first three. A wake that carries several
waits (a `--wake all` group) names the earliest and adds `count=`. A blank
line and the prose follow. Examples:

```text
t3-steward-wait kind=github outcome=met wait=tw-park-a1-9 conclusion=success state=completed target=run:123 url=https://github.com/o/r/actions/runs/123
t3-steward-wait kind=node outcome=met wait=nw-campaign-k1 failed=implement progress=failed result="t3-steward task result run-abc" revision=14 run=run-abc task=sink:run-abc
t3-steward-wait kind=time outcome=timed-out wait=w-1a2b or-timeout=true
```

The second line is a campaign notification for a run that failed: `--state
terminal` is met because the run ended, and `progress=` and `failed=` say
how. A `--state succeeded` wait on the same run would say `outcome=failed`.

## Interactive wait

For an ordinary session: it wakes the selected thread and creates or alters
nothing else. Every kind is available.

```sh
t3-steward wait add --github pr 123 --state reviewed --name "PR 123 reviewed"
t3-steward wait add --at 2026-09-19T06:00:00Z --name "morning"
t3-steward wait add --node run-abc --name "campaign settled"      # the run's sink
t3-steward wait add --node run-abc/review --state paused
t3-steward wait add --quota claude-main --reset
t3-steward wait add --name "deploy finished" -- ./scripts/deployed.sh
```

Then finish the turn with a short note of what is parked and what you will do
when woken. The thread is resolved from the caller's provider session
(`CLAUDE_CODE_SESSION_ID`, `CODEX_THREAD_ID` or `OPENCODE_SESSION_ID`). A
provider session ID is an input to that resolution and never a thread ID; if it
is ambiguous the candidates are named and `--thread <T3 thread id>` is required.

`--run <run>` and `--task <run>/<task>` are the older spellings of `--node`
and still work. A node or quota wait is held by the coordinator; a time, github
or shell wait is a local check on this host. That is where each one lives, not
where you look for it: plain `wait list` now reads both places and joins them,
and `wait list --native` asks the coordinator alone.

## `each` versus `all`

`--wake each` (the default) wakes on the first settlement. `--wake all` waits
until every member has settled.

- Interactive: `--wake all` requires `--group NAME`, and the group is the set.
- Task-bound: there is no `--group`; `all` is scoped to the attempt. Mixing
  `each` and `all` on one attempt is defined — any `each` that settles wakes
  the attempt.
- A group, and a task's `all` set, is all local kinds (`shell`, `time`,
  `github`) or all coordinator kinds (`node`, `quota`). A registration that
  would mix the two is refused and names both members; use another group or
  `--wake each`.

```sh
t3-steward wait add --group deploy --wake all --github run 123
t3-steward wait add --group deploy --wake all --name "image built" -- ./scripts/image-ready.sh
t3-steward wait add --group fanout --wake all --node run-a
t3-steward wait add --group fanout --wake all --node run-b
```

## The shell check protocol

For the `shell` kind only; the other kinds carry their own mapping.

- `0`: condition met. The steward wakes the thread.
- `2`: give up. The steward wakes the thread with `outcome=gave-up`.
- anything else: not yet, keep polling.
- `--timeout` elapsed: the steward wakes the thread with `outcome=timed-out`.

The check is run once at registration and refused if it cannot run, already
exits 0 (nothing to park for) or exits 2. Write it so a "not yet" is a non-zero,
non-2 exit; `test`, `grep -q` and `jq -e` all do that naturally. Put anything
longer in a script under the project and call it. Reach for a shell check only
when no other kind fits: a time, a GitHub run or PR, a workflow node and a
quota pool are kinds of their own, and a github or time wait registered as a
shell idiom wakes late and reports nothing structured.

Flags on `add`: `--name`, `--every` (default 30s, minimum 30s; doubles after
each "not yet"; a time wait polls from the remaining time instead),
`--max-every` (default 10m), `--timeout` (default 24h; for `--task current` it
is the maximum duration the coordinator enforces), `--or-timeout`,
`--run-timeout` (default 1m, bounds one shell run), `--dir`, `--wake each|all`,
`--request-id`, and `--json`. Interactive `add` also takes `--thread` and
`--group`.

Registering a coordinator kind (`--node`, `--run`, `--quota`) prints text, like
every other kind. It used to print a JSON document with no `--json` asked for,
so anything that pipes a registration into `jq` has to pass `--json` now.

## Inspect

```sh
t3-steward wait list [--thread ID] [--host HOST] [--all] [--json]
t3-steward wait list --native [--thread ID] [--host HOST] [--json]
t3-steward wait run-now <id>    # run a shell check immediately and show its output
t3-steward wait cancel <id>
t3-steward wait cancel <nw-id>  # a coordinator-held wait, through the admin transport
```

`wait list` answers what a thread is waiting for from both places a wait lives:
this host's local checks and the node, quota and task-bound waits the
coordinator holds, joined into one row shape with kind, subject, state,
`delivery=`, `host=`, `registered=`, `deadline=` and the coordinator wait a
local check is bound to. It answers for the calling thread by default.
`--thread` names another thread, `--host` keeps only the waits one host would
deliver, and `--all` widens to every thread *and* every state, because settled
and delivered waits are hidden otherwise and counted at the end. `--native`
asks the coordinator for its own inventory instead of the joined answer, scoped
and printed the same way.

Under `--json` both forms print one document — `waits`, `sources`,
`unavailable`, `hidden` — and not an array of checks. Read `unavailable` before
reading an empty `waits`: a source that could not be read is a different zero
from nothing pending, and only the first is a failure.

## Exit codes

Registering exits 0; a refused or failed wait exits 1. Listing exits 0 when
every source answered, and non-zero when one could not be read: the transport
class below when that source's failure carried one, and 1 when it did not. A
shorter list is never returned silently.

Native and task-bound waits reach the coordinator, so they can also exit with a
transport class: 3 client configuration, 4 authentication, 5 unavailable, 6
timeout, 7 protocol, 8 refused by the coordinator. 3, 4 and 8 are permanent
until something changes; 5 and 6 are usually temporary. Branch on the code
rather than on the message. Run `t3-steward coordinator identity --json` to see
which coordinator answers; never reach one with `ssh <coordinator> t3-steward`.
