---
name: t3-campaign
description: >
  Turn an agreed plan into an unattended version 2 workflow directory with declared
  tasks, dependencies, artifacts and verification. Validate offline, check fleet
  readiness, then submit with the session as notify thread. Use for dependent work,
  plan-review-implementation pipelines, milestone handoffs, recurring schedules,
  reruns, or repository-free research with an agreed scope. Triggers: campaign,
  DAG, workflow, pipeline, multi-step job, recurring job, schedule, cron, fan out,
  artifact handoff, declared commit, plan then implement, review then implement,
  campaign check, readiness, rerun, accepted_waiting, fresh workspace.
---

# t3-campaign

## Hand off an agreed plan

Stay interactive for exploration, design, contract questions and decisions turn
by turn. Once Igor has agreed a plan in the session, write the plan to Jocasta,
author a campaign directory with a `ledger:` block, and submit with `--notify-thread current`. Agents
may do this without another approval: announce the run id and Jocasta ledger
reference. Ask first when estimated cost is large, operator-level access is
needed, or the campaign releases to the fleet. Never submit exploration that is
not yet a plan. Keep only the run id and ledger reference in the session's working
set after handoff. A successor session resumes from the ledger and run ids, not
from a transcript.

A single independent outcome uses `t3-steward task run` (`t3-task` skill).
Use a campaign for dependencies, artifact handoffs, declared reviews or recurring
schedules. Quick same-provider subagents are allowed for reading and sub-work,
but never in place of a declared task or review. Each declared task has its own
admission, placement, verification, artifacts and retry boundary.

The resident instructions own policy-backed roles after explicit deployment,
and manual fallback assignments otherwise. Use `t3-steward models` and
`campaign check` to verify real routes. Keep explicit provider/effort pins for
operator or session restrictions; never silently escalate after failure.

## Keep the orchestrator's context small

A coordinating session reads states, verdicts and finding titles, never raw
diffs, logs or full reviews. Anything longer goes to an economy `read`-role
reader subagent with a focused question; it returns at most about ten lines:
verdict, blocking findings with paths, next action. Keep durable state in the
Steward-written ledger (below), not in the session's context. When the installed
release offers compact views or a progress mirror (check `campaign help`), read
those first.

## Policy-backed roles (Phase A)

After explicit policy-backed deployment, use `read`, `execute`, `review`,
`critical-review` and `plan` for the required role. The native
reader/executor/reviewer/critical-reviewer/planner definitions are for bounded
same-provider work; they cannot replace a declared task or independent review.
Steward retains exact catalog authorization and production review diversity.
Family aliases in native Claude definitions are frontend projection only.

For one task, `t3-steward task run --role execute --dry-run -- "Bounded outcome"`
selects from the deployed policy. Before deployment, continue using an explicit
advertised route. Operator/session restrictions take precedence: pin
`--model "$ROUTE" --effort medium` when restricted to one provider and medium
effort, and verify that the route belongs to that provider. Never silently
raise effort or switch providers after failure. Review roles select one reviewer
in Phase A; explicit independent/judge/swarm routes still express the production
review contract. Nested review orchestration, quota failover and M16/M17
compilation are not implemented by these generated files.

## Write the executor brief before the manifest

A task prompt is a self-contained execution contract. Pin the source revision;
verify paths, commands and input provenance. State outcome, scope, invariants,
verification, retained outputs, independent review, recovery budget and genuine
approval boundaries. Stop on stale prerequisites rather than forcing a patch.
Read [references/executor-briefs.md](references/executor-briefs.md) when authoring
implementation or repair tasks.

Put shared background in bundled input files; name the exact sections each task
needs. Diagnose and repair ordinary failures within scope, then repeat the checks
and independent review. Stage boundaries do not require routine confirmation.
Recovery cannot grant access, weaken verification, approve its own review or
consume explicit release approval. Preserve evidence, change strategy after
repeated deterministic failure, and escalate exhausted recovery or uncertain
external effects.

Every campaign task must keep `continuation.md` current at each step and before
parking or handoff: goal, checklist, current step, blockers, last verification.
Record verified commits and evidence references; label provisional work. This is
a resume checkpoint, not proof of acceptance or a runtime recovery guarantee.

Inside a steward task, use `t3-steward ask` for a decision from Igor: options,
deadline, safe default, end the turn after parking, read `ask-answer.json` on
resume. Approver-required asks have no default and fail unanswered. Outside a
task use the session's own question tool.

## Milestone ledger and handoff

Declare `ledger: {jocasta_project: NAME}` in `workflow.yaml` (optional `plan`,
`risk` and `acceptance`; see `campaign help ledger`). The coordinator then creates
`<project>/handoffs/<run id>.md` at submission and appends one record per ended
attempt, quoting the task's `handoff.md`, plus a closing record. Without the block
nothing is written.

The lead adds the human layer to that document with Jocasta's revision fence:
the agreed plan's exact document/revision reference, scope, budget, model routes,
approval boundaries and, at milestone boundaries, this compact record:

```text
Milestone:
Goal and acceptance:
Inputs and source revisions:
Decisions and why:
Verification and reviewed commit:
Review verdict and blocking findings:
Blockers, risks and next action:
```

Executors retain a `handoff.md` with goal, resulting commit, decisions and why,
checks and evidence, review outcome, open risks, next action and artifact links.
Declare it and `continuation.md` as outputs.

## Review and digest

Use `t3-steward review` for cross-provider plan or diff review with snapshotted
file inputs. Select independent reviewers from the other provider; the caller
cannot review its own work. Critical plan review uses the critical-review role
at medium effort. An optional economy swarm adds lenses; its executor judge
synthesizes findings and does not replace the independent reviewer.

```sh
t3-steward models
t3-steward review --plan plan.md --criteria acceptance.md --independent "$REVIEW_ROUTE" --wait
t3-steward review --diff-file changes.diff --independent "$REVIEW_ROUTE" --swarm default --swarm-model "$READER_ROUTE" --judge "$EXECUTOR_ROUTE" --wait
t3-steward review result <round> --wait
```

Use `--wait` outside T3. Inside T3 notification is default; collect with
`review result <round>` on wake. An executor inside a steward task must use a
task-bound wait for external work and end the turn; notification alone does not
park the task. This release does not support in-task review orchestration: declare
review as a dependent campaign task or run the standalone round from the lead
session. Do not invent nested review gates.

Read only the verdict and finding titles yourself. The reader subagent is the
only path by which full review files, diffs and logs reach the orchestrator: give
it the round's `summary.json` and review files with a focused question and a
bounded answer of at most about ten lines, a deduplicated action list with
severity, affected paths and unresolved contract questions. Fix within
scope or ask Igor, run checks, then review again on the new inputs. Keep the
reviewed commit and acceptance in the ledger. Exit 0 means valid review results,
whatever the verdict; `--gate` requires `--wait` on submission and rejects
anything other than accept. See `review --help full` for collection failures.

## Validate, check and submit

```sh
t3-steward campaign validate ./campaign
t3-steward campaign plan ./campaign
t3-steward campaign check ./campaign --json
t3-steward campaign submit ./campaign --idempotency-key agreed-plan-1 --notify-thread current --json
```

`validate` and `plan` are offline. `check` is live and read-only:
`ready` and `accepted_waiting` both exit 0; `impossible` exits 8 and requires
a changed manifest or fleet configuration. Waiting cannot fix an unknown project,
model, route, credential or impossible resources. Use
`campaign help readiness` for reasons, not an agent polling loop.

Submission creates one workflow run and checks readiness itself. A repeated key
with identical bytes replays; changed bytes need a new key. Notify defaults to
the current canonical T3 thread. An unresolved thread is refused before submission;
use an explicit T3 thread id when ambiguous. Use `--no-notify` only when no wake
is intended. If submission succeeds but notification registration fails, retain
the run id and register `wait add --node <run> --thread <id>`.

Follow the receipt's closing instruction; end the turn only when a wake will fire.
A replay of a terminal run needs collection instead. Do not use
`--allow-unverified`: it is an operator escape hatch.

## Directory and manifest

```text
campaign/
  workflow.yaml
  inputs/plan.md
  prompts/implement.md
  prompts/review.md
```

Replace the project and route placeholders below with fleet-advertised values,
replace `JOCASTA_PROJECT` with the Jocasta project that holds the agreed plan,
then run validation. Choose the execution and review roles deliberately.

```yaml
version: 2
name: implement-and-review
class: surplus
inputs: [inputs/plan.md]
ledger: {jocasta_project: JOCASTA_PROJECT}
environment:
  project: PROJECT
  type: git
  scope: task
  ref: main
routes:
  - instance: EXECUTOR_INSTANCE
    model: EXECUTOR_MODEL
    options: {effort: high}
tasks:
  implement:
    prompt_file: prompts/implement.md
    outputs: [continuation.md, handoff.md]
    commits: [{name: implementation, revision: HEAD}]
    verify: [go test ./...]
    resources: {preset: build}
    max_turns: 12
  review:
    needs: [implement]
    inputs_from:
      implement: [implementation, handoff.md]
    routes:
      - instance: REVIEW_INSTANCE
        model: REVIEW_MODEL
        options: {effort: medium}
    prompt_file: prompts/review.md
    outputs: [continuation.md, review.md]
    resources: {preset: light}
```

Top-level `inputs` ships the plan read-only at `.t3/inputs/inputs/plan.md`;
files merely present in the directory are not bundled.
`prompt_file` is required; inline prompts are unsupported. `needs` builds the
DAG; `inputs_from` names outputs or commits from a task also named in `needs`.
Dependency files are read-only at `.t3/dependencies/<producer task id>/`;
tell the prompt to list that directory, because the id is assigned at submission.
Do not guess dependency paths in `verify`; verify the task's own outputs.

Only declared outputs are retained (plus `final-message.md`). A missing output
fails the task; duplicating existence checks hides that useful error. Write
relative to the current workspace. `resources.preset` chooses placement:
`light` prefers smaller hosts, `build` prefers stronger hosts; do not pin a
host unless its state is required.

Declare a Git commit under `commits` when a successor needs the object.
Names share the output namespace. Revision is a safe ref or full SHA; `HEAD`
is default, expressions such as `HEAD~1` are refused. A consumer gets
`campaign-commit/v1` provenance and the fetched commit under
`refs/campaigns/<run>/<task>/<name>`; the pinned base is `.t3/base-commit`.
Do not depend on refs in the worker cache. Before publishing the task's own branch,
verify `git remote get-url --push origin` points at the project repository;
older prepared workspaces may still push into the cache. Never force, mirror or
prune. Verify publication with `git ls-remote <project repository>`.

For repository-free findings, use a catalog fresh project and
`environment: {project: PROJECT, type: fresh, scope: task}` with no ref or
commits. Declare all retained files. See `campaign help fresh`.

Preflight runs before the agent and records the baseline. For example:

```yaml
preflight:
  steps:
    - id: source
      kind: context
      probe: git_head
      include: summary
    - id: tests
      kind: check
      command: [go, test, ./...]
      failure_policy: record
      include: summary
      timeout: 5m
```

A task's preflight replaces the workflow's; `require-pass` instead of `record`
prevents launch on failure. Verification must establish prerequisites in a fresh
shell. See `campaign help dag-semantics`, `commits`, `routes` and
`supervision` for detailed contracts; do not invent manifest fields.

## Watch, collect, recover

```sh
t3-steward campaign list --state open --project PROJECT
t3-steward campaign show <run>
t3-steward campaign show <run> --wait --timeout 30m
t3-steward campaign graph <run> --dot
t3-steward campaign explain <run>/<task>
t3-steward task result <run> --wait --timeout 30m
t3-steward triage
t3-steward campaign rerun <run> --from <task> --idempotency-key repaired-1 --reason "Fixed prerequisite"
```

Blocking reads belong in a plain CLI; inside a steward task use `t3-wait` to
park and end the turn. Ending with no task-bound wait completes the task, collects
outputs and runs verification. Long checks run in the foreground; background shell
jobs are not waited for. A task cannot wait for its own run's sink.

`show --wait` reports terminal state, not success. `task result` exits 0 for
succeeded/skipped, 2 for failed/cancelled, 1 for pending or wait timeout; inspect
the verdict. Interruption never cancels work. Rerun creates a new run from the
named task and its descendants, reusing successful ancestors' retained artifacts.
It refuses a nonterminal source or unavailable reused evidence. Preserve the
source run and diagnose before rerunning. Authorized cancellation uses
`campaign cancel <run>[/<task>] --reason TEXT`.

## Recurring schedules and operator boundaries

Register a validated workflow without an initial run using
`campaign submit ./campaign --register-only --idempotency-key scheduled-1`.
Then use `schedules put` with the returned workflow id, cron, timezone and an
explicit `--after-failure next-cycle|hold` choice. Fetch the current definition
with `t3-steward schedules show <schedule> --json` and use its revision for
`--expected-revision` when replacing it, plus a stable `--request-id`.
Read commands are `schedules list`, `show` and `history`; revision-fenced controls
are `schedules run`, `enable`, `disable` and `delay-next` (requires `--until`).
Controls require `--reason`; use a stable `--command-id` when retrying.
Schedule reads (`list`, `show`, `history`) are available to agents.
Schedule mutations (`put`, `run`, `enable`, `disable`, `delay-next`) require
explicit operator authority. An agreed workflow alone does not authorize enabling
a recurring schedule. Keep disabled schedules disabled until the operator authorizes
their recreation or enablement.
See `t3-steward schedules --help full` for the complete syntax, including the
required schedule id, `--name`, `--workflow`, `--cron`, `--timezone` and `--reason`
on `put`.
Registration requires an upgraded coordinator and refuses supervision/gates;
do not silently fall back to starting work. Schedules own timing, history and
overlap prevention; never recreate them with local timers or repeated task starts.

## Permanent legacy intake retirement

Submit new work through `task run` or `campaign submit`; use `schedules` for
recurring timing. Legacy Markdown file intake and wrapper submission are obsolete
entry points, not replacements for public submission. Do not write task files
or recreate local wrapper/timer submission recipes.

The new M15 source permanently retires executable Markdown intake: the local
runner, coordinator intake and file forwarding cannot execute file work. Old true
enable flags are rejected; false values are parsed for compatibility. Historical
rc109 phase 1 staged behavior is prior-release evidence, not the new contract.
Source publication and this guidance do not prove runtime deployment. The rollout
lead verifies exact source, release and runtime state; the current fleet remains
on rc109 until a separately reviewed coordinated release is deployed.

Preserve existing files and quarantine evidence under rollout lead custody.
The lead retains previous reviewed immutable rollback bundles; rollback must
never reenable the retired scanner. Historic quarantine read/release remains
authenticated marker-only cleanup, with no automatic retry or submission effect.
Public submission, persisted tasks, artifacts, worker planning, schedules and
retained operator controls remain in scope for normal operation. Retiring file
intake does not retire the `backlog` administration namespace. Keep disabled
schedules disabled; there is no schedule resurrection or production diversity
waiver. Provider/session restrictions require explicit route and effort pins;
this checkpoint is Codex medium only. Ordered policy roles, candidates and tiers
remain unchanged.

## Operator-only administration

Use campaign/task verbs for normal lifecycle work. Routine authorized cancellation
uses `campaign cancel <run>[/<task>] --reason TEXT`, including a single task.
The selected commands below retain low-level administration where public lifecycle
verbs do not replace controls on an existing attempt. This is a selected inventory,
not a complete command list.

Consult the matching help family before administration:
- `t3-steward backlog --help full`: persisted graph, attempt controls, receipts,
  artifacts, historic quarantine and stopped-coordinator backups. Retained help
  does not authorize executable Markdown intake.
- `t3-steward worker --help full`: enrollment, daemon and containment operations.
- `t3-steward campaign --help full`: public lifecycle and recovery;
  `t3-steward campaign supervision --help full`: structured supervision controls;
  `t3-steward campaign recovery retry --help full`: fenced recovery syntax.
- `t3-steward coordinator --help full`: answering identity and local reload.
- `t3-steward install-service --help full`: local service installation.
- `t3-steward schedules --help full`: definitions, history and schedule controls.

Read-only diagnostics are available to agents; administrative mutations require
operator authority. Supervision mutations require the authorized principal and
record/activation scope; `reassess` is operator-only. Help is not authorization.
Coordinator reload, service installation, enrollment, containment, backup restore,
graph amendments and low-level attempt controls require operator authority.
`t3-steward triage` prints recovery commands with ids, revisions and idempotency
keys filled in. Inspect the reason and authority before executing a proposed control.

| Namespace / verbs | Purpose |
| --- | --- |
| `backlog projects`, `workers` | Read-only project catalog and worker enrollment/capabilities. |
| `backlog diagnose`, `task show`, `events`, `usage` | Read-only run diagnosis, task detail, event history and bounded usage. |
| `backlog commands`, `command show` | Read-only control receipts and their application. |
| `backlog artifacts`, `artifact show`, `artifact get` | Inspect retained evidence or retrieve it locally. |
| `backlog task add`, `task set`, `edge add`, `edge remove`, `run clone` | Amend or clone the persisted graph; require `--expected-revision N --request-id ID --reason TEXT`. |
| `backlog start`, `resume`, `retry`, `skip` | Revision-fenced controls on an existing task, rather than creating a campaign rerun; routine cancellation uses `campaign cancel`. |
| `backlog pause`, `delay`, `rewake` | Pause an attempt, defer eligibility, or wake waiting-external after its wait is no longer live. |
| `backlog recover` | Resolve an assignment using coordinator/assignment epochs, attempt revision and evidence id/hash; consult full help for the exact fences. |
| `backlog quarantine`, `quarantine release` | Read historic intake refusals, or perform authenticated marker-only cleanup. |
| `campaign recovery` | Retry a failed supervised operation using fenced evidence; see `campaign recovery retry --help full`. |

`backlog start` is an explicit operator override: it bypasses quota forecast,
admission, freshness, runway and automatic quota throttling through worker delivery.
Use it only under explicit user authority while the user is manually monitoring quota.
Automatic queued work must remain fenced; worker health, dependency, lock, revision
and effect-safety checks still apply. Other controls do not grant this override.
Preserve `--expected-revision` and use a stable `--command-id` for retries.
`campaign rerun` creates a new run; it and supervised `campaign recovery`
are not replacements for these controls on an existing attempt.

Selected syntax (replace placeholders with inspected ids and revisions):

```sh
t3-steward backlog start <run>/<task> --reason "Explicitly authorized quota override" --expected-revision N --command-id ID --json
t3-steward backlog edge add <run>/<task> --from <dependency> --expected-revision N --request-id ID --reason "Add required dependency"
t3-steward backlog artifacts <run>/<task> --json
t3-steward backlog artifact get <artifact> --output evidence.md
t3-steward backlog quarantine --json
t3-steward backlog quarantine release <key> --reason "Authorized historic marker cleanup"
```

Historic quarantine applies to retired file intake, not synchronous task/campaign
submission. Quarantine reads use the authenticated client transport; release
requires operator authority and `--reason`. Release is marker-only cleanup and
creates nothing: clearing quarantine does not enable or restart intake. It cannot
submit work, forward files or trigger a next-cycle retry. Content edits, digest
changes and key aliases cannot reactivate retired intake. Preserve the files and
quarantine evidence under rollout lead custody.

All ordinary remote commands use the configured client transport; never bypass
it with `ssh <coordinator> t3-steward`. Worker enrollment is the one deliberate exception:
`worker enroll` must run on the coordinator host, at its console or through a
plain SSH shell there. The remote-admin role is refused even over an authenticated
client because enrollment binds coordinator identity, epoch and credentials.

```sh
t3-steward worker enroll <worker> --current-catalog --reason "Re-enroll after catalog change"
t3-steward worker enroll --all --current-catalog --reason "Re-enroll stale workers"
```

`--current-catalog` reads the required digest and current enrollment revision
from the coordinator. `--all` skips workers already current. For
`catalog-digest-mismatch`, this is the operator recovery; a
`project-binding-defaulted` warning also requires checking the project binding
and eligible worker enrollment. See `campaign help readiness` and
`worker enroll --help full`; do not enroll as routine task recovery.

Transport exits: 3 configuration, 4 authentication, 5 unavailable, 6 timeout,
7 protocol, 8 rejected. Prove the answering identity with
`t3-steward coordinator identity --json` before submission.
