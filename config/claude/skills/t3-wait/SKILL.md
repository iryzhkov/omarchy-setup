---
name: t3-wait
description: >
  Park a thread until an external condition settles instead of polling in an agent
  loop. Inside a steward task, --task current parks the attempt itself and requires
  ending the turn. Use for CI, reviews, another run, a time, quota or a service.
  Triggers: wait for, poll, check back later, until CI passes, when the PR is
  reviewed, once the job finishes, wait until, park the task, quota reset.
---

# t3-wait

In a steward task, register `wait add --task current` and end the turn
immediately. It parks the attempt in `waiting-external`: no outputs are collected,
no verification runs and no dependent task is released until the same thread and
attempt resume. Capacity is released; workspace, artifacts and ownership are held.
Ending with no task-bound wait completes the task. Run long local checks in the
foreground; background shell jobs are not waited for.

Outside a task, `wait add` wakes a thread without changing workflow state.
A plain CLI may use `task result <run> --wait` or
`campaign show <run> --wait` instead. Never poll in an agent loop.
For a decision from Igor inside a task, use `t3-steward ask`, not a shell check
or native question tool; see `t3-task`. Outside a task use the session's question tool.

Policy-backed roles do not change wait semantics or implement quota failover.
After deployment, use the resident role policy for work resumed after a wait;
operator/session provider and effort restrictions still require explicit pins.
No nested review orchestration or M16/M17 compiler is implied.

Waiting does not submit legacy files, enable intake, or authorize schedule mutations.
For routine authorized work cancellation use `campaign cancel`; cancelling a wait
only settles that wait. Retained `backlog rewake` recovery requires operator
authority and is refused while the attempt still has a live wait.

## Choose the condition

| Kind | Arguments | Outcome |
| --- | --- | --- |
| Time | `--at RFC3339` or `--for 30m` | met when the instant passes |
| GitHub | `--github run ID` or `--github pr N --state merged\|reviewed\|checks-passed` | success met, unsuccessful run/checks or closed unmerged PR failed |
| Node | `--node RUN[/TASK] --state terminal\|succeeded\|paused\|waiting-external\|active` | terminal may include failure; succeeded fails on failure |
| Quota | `--quota POOL --below N`, `--phase normal`, or `--reset` | met from coordinator bucket observations |
| Shell | `-- COMMAND` | exit 0 met, 2 gave up, anything else not yet |

GitHub targets also accept `owner/name#N` or a PR/run URL, or `--repo owner/name`.
PR state defaults to merged; run state defaults to completed; node state defaults
to terminal and a run alone names its sink. A task cannot wait for its own sink.
Node and quota conditions are settled by the coordinator; time, GitHub and shell
conditions are checked on this host.

```sh
t3-steward wait add --task current --github pr owner/name#123 --state checks-passed --timeout 2h
t3-steward wait add --task current --node OTHER-RUN/TASK --state succeeded
t3-steward wait add --task current --for 30m --or-timeout
t3-steward wait add --task current --quota POOL --phase normal
t3-steward wait add --task current --name "Service ready" -- ./scripts/service-ready.sh
```

After successful registration, end the turn. `--task current` outside a task is
refused. Already-met, failed or unreadable conditions are refused at registration;
nothing is parked. A shell check must exit nonzero and non-2 for "not yet";
prefer a native condition when it exists.

`--timeout` bounds a wait (default 24h; time waits cover their instant).
`--or-timeout` treats the deadline as an acceptable outcome, still named
`timed-out`. `--run-timeout` bounds a shell probe (default 1m).
`--every` starts shell/GitHub checks at 30s minimum, doubling to
`--max-every` (default 10m). Longer checks belong in a project script.

## Identity and registration

The task identity is injected into `.t3-steward/task.env`; it is not necessarily
exported to the shell. Use `t3-steward task env --get revision` or
`eval "$(t3-steward task env)"` rather than assuming `T3_STEWARD_*` is set.
The default request id is `park-<attempt>-<revision>`. Retry the same live
registration with the same id; a settled id cannot park again, and changed
contents under the same id are refused. Terminal or stale attempt refusals
require diagnosis, not a blind retry.

For an interactive wait, omit `--task current`. The current canonical T3 thread
is resolved from provider session metadata. If ambiguous, pass `--thread ID`
from the T3 app; a provider session id is not a T3 thread id. End the turn after
registration. `--wake each` is default; `--wake all` waits for every member
and requires an interactive `--group NAME`. Task-bound all is scoped to the
attempt. An all set cannot mix local and coordinator kinds.

## Resume and inspect

Every wake begins with:

```text
t3-steward-wait kind=<kind> outcome=<outcome> wait=<id> <key>=<value> ...
```

Branch on `met`, `failed`, `gave-up`, `cancelled` or `timed-out`.
A node terminal wake means the run ended, not that it succeeded: inspect
`progress=`, `failed=` and the printed result command. Ignore unknown keys;
key order is not promised. Failed and timed-out waits still resume the task with
evidence; re-read state before continuing. Cancellation resumes with cancelled.

```sh
t3-steward wait list --json
t3-steward wait list --all
t3-steward wait list --native --json
t3-steward wait cancel <id>
t3-steward wait run-now <id>
t3-steward triage
```

Joined list JSON contains `waits`, `sources`, `unavailable` and `hidden`.
Read `unavailable` before treating an empty list as nothing pending.
`--thread ID` and `--host HOST` narrow the list; `--all` includes every
thread and settled waits. Registration exits 0 on success, 1 on refusal/failure.
Listing fails if a source cannot be read. Coordinator calls can also return
3 configuration, 4 authentication, 5 unavailable, 6 timeout, 7 protocol or
8 rejected; never bypass the client transport with a coordinator shell.
