---
name: t3-wait
description: >
  Park this T3 thread until something external happens, instead of polling
  in a loop: register a check with the t3-steward, end the turn, and the
  steward wakes the thread with the outcome when the check succeeds, gives up
  or times out. Use whenever you would otherwise sleep and re-check: waiting
  for PR reviews or comments, CI or a deploy to finish, a long job or build,
  a file or service to appear, a human on another channel. Triggers: wait
  for, poll, check back later, until CI passes, when the PR is reviewed, once
  the job finishes, sleep and retry.
---

# t3-wait

Polling from inside a thread burns quota for nothing and gets the thread
interrupted by the steward when the window runs low. Register the poll with
the steward instead and end the turn; the thread costs nothing while parked
and comes back with the result.

## Register a check and end the turn

```sh
t3-steward wait add --name "PR 123 reviewed" --every 5m --timeout 24h -- \
  gh pr view 123 --json reviewDecision --jq 'select(.reviewDecision != "") | .reviewDecision'
```

Then finish the turn with a short note of what is parked and what you will
do when woken. The thread is resolved from `CLAUDE_CODE_SESSION_ID`; pass
`--thread <T3 thread id>` from other agents.

The check's exit code is the protocol:

- `0`: condition met. The steward wakes the thread.
- `2`: give up. The steward wakes the thread with the failure.
- anything else: not yet, keep polling.
- `--timeout` elapsed: the steward wakes the thread with "timed out".

The check is run once at registration and rejected if it cannot run, already
exits 0 (nothing to wait for) or exits 2. Write it so a "not yet" is a
non-zero, non-2 exit; `test`, `grep -q`, `jq -e` and `gh ... --jq 'select(...)'`
all do that naturally. Put anything longer in a script under the project and
call it. `--every` is at least 30s; `--run-timeout` (1m) bounds one run.

## Several conditions

Each wait wakes the thread on its own. To wake once when all of a set are
settled, put them in a group:

```sh
t3-steward wait add --group deploy --wake all --name "CI green"   -- ./scripts/ci-passed.sh
t3-steward wait add --group deploy --wake all --name "image built" -- ./scripts/image-ready.sh
```

## What the wake looks like

A new turn starts with a message from the steward: the name, outcome
(condition met, failed, timed out), the command, how many runs, and the
check's last output. Re-read the current state before continuing; other
things may have moved while the thread was parked. If the provider quota is
unhealthy at that moment the wake is held until it recovers.

## Inspect

```sh
t3-steward wait list            # this thread's waits
t3-steward wait list --all      # every thread
t3-steward wait run-now <id>    # run a check immediately and show its output
t3-steward wait cancel <id>
```
