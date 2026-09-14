---
name: t3-wait
description: >
  Park a thread until something external happens, instead of polling in a loop:
  register a check with the t3-steward, end the turn, and the steward wakes the
  thread with the outcome when the check succeeds, gives up or times out. Inside
  a backlog or campaign task, `--task current` parks the task attempt itself, so
  the turn must end there. Use whenever you would otherwise sleep and re-check:
  waiting for PR reviews or comments, CI or a deploy to finish, a long job or
  build, a file or service to appear, a human on another channel. Triggers: wait
  for, poll, check back later, until CI passes, when the PR is reviewed, once
  the job finishes, sleep and retry, park the task, waiting-external.
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

## Task-bound wait: registering it parks the task

```sh
t3-steward wait add --task current \
  --name "CI on $(git rev-parse --short HEAD)" \
  --every 60s --max-every 10m --timeout 2h \
  --request-id ci-$T3_STEWARD_ATTEMPT_REVISION -- \
  sh -c 'test "$(gh run view --json status --jq .status)" = completed'
```

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

The worker injects the execution identity, and the command reads it from the
process environment first and from `.t3-steward/task.env` (mode 0600, searched
upward from the working directory) second:

```text
T3_STEWARD_WORKFLOW_RUN_ID  T3_STEWARD_TASK_ID     T3_STEWARD_ATTEMPT_ID
T3_STEWARD_ATTEMPT_REVISION T3_STEWARD_ASSIGNMENT_ID T3_STEWARD_THREAD_ID
```

The registration is fenced on `T3_STEWARD_ATTEMPT_REVISION`. Two refusals are
ordinary command errors: report them, do not retry blindly.

- `attempt is terminal (<progress>); task-bound waits are refused` — the turn
  already completed. The task is over; do not keep working.
- a stale attempt revision — the attempt moved on since this process started.

### `--request-id` names one park, not a standing permission

Repeating a request ID while that wait is still live and holding this attempt
returns the same wait, which is what makes a retried registration safe.
Repeating it after that wait settled is **refused**: the ID names one park.
Include `$T3_STEWARD_ATTEMPT_REVISION` in it so every park of the same task gets
its own ID. A repeated ID with different contents is also refused.

### What happens on wake

The same thread and the same attempt resume, with the wait result in the initial
context. Placement, capacity and locks are reacquired through the normal paths;
it is a new turn on the existing attempt, not a new attempt. Outputs written
after waking are the outputs that are collected, and verification runs once, at
the end of the turn that ends with no live wait.

A failed or timed-out wait still wakes the task, with structured evidence: which
wait, which condition, which exit status, how long it ran. Silence is not an
outcome. A timeout releases the attempt to finish or fail honestly; it never
leaves the task parked. Handle the failure or produce an honest final failure —
do not treat a wake as proof the condition was met.

Re-read the current state before continuing; other things may have moved while
the thread was parked.

## Interactive wait

For an ordinary session, unchanged: it wakes the selected thread and creates or
alters nothing else.

```sh
t3-steward wait add --name "PR 123 reviewed" --every 5m --timeout 24h -- \
  gh pr view 123 --json reviewDecision --jq 'select(.reviewDecision != "") | .reviewDecision'
```

Then finish the turn with a short note of what is parked and what you will do
when woken. The thread is resolved from the caller's provider session
(`CLAUDE_CODE_SESSION_ID`, `CODEX_THREAD_ID` or `OPENCODE_SESSION_ID`). A
provider session ID is an input to that resolution and never a thread ID; if it
is ambiguous the candidates are named and `--thread <T3 thread id>` is required.

Two more interactive forms wait on workflow nodes rather than on a shell check,
and take no command:

```sh
t3-steward wait add --run <run> [--thread ID] [--name TEXT] [--timeout 24h] [--request-id ID]
t3-steward wait add --task <run>/<task> [--thread ID] [--name TEXT] [--timeout 24h]
```

## `each` versus `all`

`--wake each` (the default) wakes on the first settlement. `--wake all` waits
until every member has settled.

- Interactive: `--wake all` requires `--group NAME`, and the group is the set.
- Task-bound: there is no `--group`; `all` is scoped to the attempt. Mixing the
  two on one attempt is defined — any `each` that settles wakes the attempt.

```sh
t3-steward wait add --group deploy --wake all --name "CI green"   -- ./scripts/ci-passed.sh
t3-steward wait add --group deploy --wake all --name "image built" -- ./scripts/image-ready.sh
```

## The check protocol

- `0`: condition met. The steward wakes the thread.
- `2`: give up. The steward wakes the thread with the failure.
- anything else: not yet, keep polling.
- `--timeout` elapsed: the steward wakes the thread with "timed out".

The check is run once at registration and refused if it cannot run, already
exits 0 (nothing to park for) or exits 2. Write it so a "not yet" is a non-zero,
non-2 exit; `test`, `grep -q`, `jq -e` and `gh ... --jq 'select(...)'` all do
that naturally. Put anything longer in a script under the project and call it.

Flags on `add`: `--name`, `--every` (default 30s, minimum 30s; doubles after
each "not yet"), `--max-every` (default 10m), `--timeout` (default 24h; for
`--task current` it is the maximum duration the coordinator enforces),
`--run-timeout` (default 1m, bounds one run), `--dir`, `--wake each|all`,
`--request-id`, and `--json` for `--task current`. Interactive `add` also takes
`--thread` and `--group`.

## Inspect

```sh
t3-steward wait list            # this thread's waits
t3-steward wait list --all      # every thread
t3-steward wait list --native [--json]   # coordinator-side waits and delivery state
t3-steward wait run-now <id>    # run a check immediately and show its output
t3-steward wait cancel <id>
t3-steward wait cancel <nw-id>  # a native wait, through the admin transport
```

## Exit codes

Registering or listing exits 0; a refused or failed wait exits 1.

Native and task-bound waits reach the coordinator, so they can also exit with a
transport class: 3 client configuration, 4 authentication, 5 unavailable, 6
timeout, 7 protocol, 8 refused by the coordinator. 3, 4 and 8 are permanent
until something changes; 5 and 6 are usually temporary. Branch on the code
rather than on the message. Run `t3-steward coordinator identity --json` to see
which coordinator answers; never reach one with `ssh <coordinator> t3-steward`.
