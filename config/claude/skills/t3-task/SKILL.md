---
name: t3-task
description: >
  Start one independent unattended outcome on an eligible t3-steward fleet worker
  when its quota pool has room. Use t3-campaign for an agreed plan with dependent
  tasks, artifacts, declared reviews or recurring schedules. Triggers: queued task,
  single unattended task, queue it, later, tonight, overnight, off-peak, async task,
  defer.
---

# t3-task

Use this for one bounded outcome that can run without the user now. Stay interactive
for exploration, design and contract decisions; an agreed multi-step plan goes to
`t3-campaign`. Quick same-provider reading or sub-work can use a subagent, but it
cannot replace a declared task or independent review. The resident instructions
own model roles; select a currently advertised route with `t3-steward models`.

## Start from the checkout

Choose `ROUTE` from `t3-steward models` for the required role and effort. Do not
guess provider instance names or model aliases.

```sh
t3-steward models
t3-steward task run --model "$ROUTE" --input plan.md --prompt-file prompt.md --dry-run
t3-steward task run --model "$ROUTE" --input plan.md --prompt-file prompt.md --json
```

`task run --input FILE` pins repeatable file inputs under
`.t3/inputs/<basename>` (1 MiB per file, 3 MiB total, 100 files; no final symlinks
or `..`). The prompt is exactly one of text after `--`, `--prompt-file FILE`,
`--prompt-file -`, or stdin. `--fan-out GLOB` creates one run with one independent
task per prompt file; dependencies need a campaign.

The CLI derives the project from the checkout's origin, the ref from its pushed
upstream branch, the route, idempotency key and notify thread. A detached HEAD or
an unpushed branch needs `--ref REF`; dirty changes are not sent. `--project NAME`
takes the fleet catalog name, never a T3 project title. `--dry-run` derives and
validates locally, may query the catalog read-only, and submits nothing.

Use `--fresh` for a single repository-free outcome, and declare its files:

```sh
t3-steward task run --fresh --model "$ROUTE" --outputs findings.md -- "Write bounded findings."
```

Other flags: `--outputs a.md,b.md`, repeatable `--verify "CMD"`,
`--class surplus|required` (default surplus), `--max-turns N` (default 3),
`--name TEXT`, `--worker WORKER`, `--idempotency-key KEY`,
`--notify-thread current|THREAD-ID` (default current), `--no-notify`, `--json`.
Normally leave placement to the fleet. A repeat key replays the same run; the same
key with different bytes is refused. The derived key excludes `--worker` and
`--name`; give distinct keys when changing only those should create another run.

Submission is synchronous. Read the first line `run <id>` or JSON `.run`, never
the closing result command. Follow the record's closing instruction: end the turn
only when a wait exists that will fire; if the run already ended, collect it.
Unresolvable notify threads are refused before submission. A script intentionally
wanting no wake passes `--no-notify`.

## Write a self-contained contract

Give the task the goal, pinned source, verified paths, input locations, allowed
scope, exact checks, retained outputs and completion criteria. Resolve known
contract decisions before starting; ordinary implementation choices belong to the
executor. Keep independent review distinct. For a reusable brief, see the
`t3-campaign` skill and its executor reference.

Inside a steward task, the one way to get a decision from Igor is:

```sh
t3-steward ask "Which contract should apply?" --option "Keep current behavior" \
  --option "Change the contract" --deadline 4h --default "Keep current behavior"
```

End the turn after the task is parked. Read `ask-answer.json` on resume and act
on the answer. An approver-required ask uses `--requires approver` with no default
and fails unanswered. Outside a task, use the session's own question tool.

Ending a task turn with no task-bound wait completes the task: declared outputs
are collected and verification runs. Run long checks in the foreground and wait
for them; background shell processes are not waited for. For an external condition,
use `t3-steward wait add --task current` and end the turn immediately; see
`t3-wait`. Keep `continuation.md` current before a park or handoff. Parking
holds the local checkpoint in the workspace. For retention after completion or
handoff, declare `--outputs continuation.md,handoff.md` at task submission.

## Collect and diagnose

```sh
t3-steward campaign list --project PROJECT --state open --json
t3-steward campaign show <run>
t3-steward campaign explain <run>/<task>
t3-steward task result <run>
t3-steward task result <run> --wait --timeout 30m
t3-steward triage
```

Results default to `<state>/results/<run>/<task>/`, outside the checkout.
`--output DIR` changes that destination; `--json` inlines the final message.
Exit 0 means succeeded or skipped, 2 means failed or cancelled, 1 means pending
or a client wait timeout. `--wait` blocks in a plain CLI; interruption exits 130
and never cancels work. Inside an agent task, park instead of blocking on external
work. Reattach with the same selector. Diagnose before retrying; use
`campaign cancel <run> --reason TEXT` for an authorized cancellation.

Read-only catalog lookups without a replacement are
`t3-steward backlog projects` (fleet names and types for `--project` / `--fresh`)
and `t3-steward backlog workers --json` (worker capabilities and enrollment).
For retained controls and safeguards, see **Operator-only administration** in
`t3-campaign`; use `triage` for attention and prepared recovery commands.
