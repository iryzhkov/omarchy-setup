---
name: t3-campaign
description: >
  Author an autonomous multi-step t3-steward job with minimal human interruption
  as a campaign directory: a version 2
  workflow with a task DAG, artifacts passed between tasks, and preflight
  evidence, validated offline, checked against the live fleet and submitted with
  `t3-steward campaign`. Use when work needs more than one unattended task, when
  tasks depend on each other or pass files between them, when a plan should be
  reviewed before it is implemented, when a failed run must be started again
  from one task, for a recurring scheduled job, or when the user asks for a
  DAG, pipeline, multi-stage job or campaign. Triggers: campaign, DAG, workflow,
  pipeline, multi-step job, recurring job, schedule, cron, fan out, parallel
  tasks, artifact between tasks, declared commit, plan then implement, review
  then implement, campaign check, readiness, rerun, accepted_waiting, research
  or spike campaign without a repository, fresh workspace.
---

# t3-campaign

A campaign carries an authorized project through execution, verification and
completion with as little human interruption as possible. Agents own routine
implementation decisions and recoverable failures. A stage boundary, failed
check or completed review is not by itself a reason to ask the user to continue.

You author it as a directory and submit it. Submission creates exactly one
workflow and one workflow run; there is no separate campaign runtime record.
A recurring schedule is a separate coordinator definition that points at the
immutable workflow. Every lifecycle command below is the existing backlog
operation with the same JSON and exit codes.

Use `t3-steward task run` for a single unattended task: it derives the project,
the ref, the route, the idempotency key and the wake from the checkout and
needs no directory at all (`t3-backlog` remains a compatibility wrapper; the
`t3-task` skill has the contract). Use a campaign when there is more than one
task, when tasks depend on each other, when one task's output is another's
input, or when the workflow will recur on a schedule. `task run --fan-out GLOB`
is the exception that stays a single start: one run with one independent task
per prompt file, no edges to declare.

## Work that needs no repository

Research, spike and review campaigns that produce findings rather than commits
do not need a Git project. Give them a new, empty directory per task:

```yaml
environment:
  project: scratch       # a catalog project of type fresh
  type: fresh            # no ref, no repository; scope stays task
```

`t3-steward backlog projects` shows each project's TYPE. Declare every file a
successor or the owner needs in `outputs`, because outputs are all that is
collected; a successor reads its `inputs_from` files under
`.t3/dependencies/<producer task id>/`, an id assigned at submission, so have
the prompt list `.t3/dependencies/` rather than hard-code it. A single repository-free task is
`t3-steward task run --fresh --model MODEL -- "..."` from any directory.
`check` refuses a Git project with `workspace-type-mismatch` and names the fresh
projects that exist; when there is none, an operator adds one with
`upkeeper project add NAME --type fresh --workers a,b`. The full contract is
`t3-steward campaign help fresh`.

## Frame the work for autonomous completion

Before submission, turn the user's intent into a bounded completion contract:

- State the final outcome, evidence that proves it, source/input versions and
  authorized scope. Include enough context for workers to act without the
  initiating conversation. Resolve material ambiguities together up front;
  delegate routine implementation choices to the executing agents.
- Make tasks meaningful units of work with explicit dependencies and retained
  outputs. Include implementation, verification and required agent review.
  Continue automatically after successful checks and reviews. Do not insert
  human approval at every stage or end prompts with "ask whether to proceed."
- Identify genuine human boundaries from the user's instructions: a missing
  permission, consequential unresolved design choice or explicitly gated
  release. Put each gate at the action it protects, prepare the reviewable
  result first, and let independent authorized work continue.
- Make setup reproducible on an eligible worker. Runner verification must
  establish its prerequisites in a fresh shell; an agent's temporary exports
  are not a verification environment. Declare durable inputs and commits.
- Assign recovery ownership and a bounded attempt/time budget. Prompts should
  require diagnosis, preservation of useful work, repair within scope, the
  original checks and required independent review, then continuation. Retry
  transient failures with backoff; change the cause of deterministic failures
  before retrying. Preserve failure evidence and link replacement runs.
- Define escalation and completion reporting. Ask the user only for missing
  authority or decisions, external blockers the agents cannot resolve, or
  exhausted recovery. Include attempted fixes and the smallest needed action.
  Routine recovery should be visible without requiring a user response.

For example, an implementation brief can say:

> Complete the approved plan through implementation, passing verification and
> independent review. Diagnose and repair ordinary failures within the stated
> scope and recovery budget; continue between stages without asking for routine
> confirmation. Preserve useful work and failure evidence. Escalate when missing
> authority, an unresolved contract decision, an external blocker or exhausted
> recovery prevents further progress. Keep the explicitly required release
> approval at the release action.

These are authoring requirements, not proof that the runtime implements every
recovery path. Check installed help for supported supervision, recovery and
amendment operations; do not invent manifest fields. A success-review gate does
not establish failure recovery. A terminal sink wait does not cover a stalled,
nonterminal run, and a registered or settled wait is not proof of delivery.
Establish the supported recovery/wake path before describing a campaign as
unattended; report any uncovered failure path. If a stall is observed, the
responsible agent diagnoses and performs already-authorized recovery rather
than waiting for the user to notice it or approve routine repair.

Autonomy preserves the original scope and checks: recovery cannot grant itself
new access, weaken verification, approve its own independent review or consume
an explicit human release approval.

## Write the executor brief before the manifest

A task prompt is a self-contained execution contract, not a reminder to inspect
the repository and guess. Verify its source revision, paths, symbols, commands
and referenced artifacts before submission. Give the worker:

- the concrete behavior to produce, including a small before/after example;
- the repository and exact starting revision, plus verified paths and symbols
  and why each matters;
- required references and dependency artifact locations, with provenance and
  the outputs it must retain;
- a suggested approach, allowed scope, invariants, approval boundaries and the
  reason for any constraint that would otherwise look arbitrary;
- setup and exact verification commands, expected results, known worker resource
  bounds, failure evidence to retain, completion criteria and when to escalate;
- the independent reviewer task or channel, route and declared review artifact,
  including its acceptance fields and what remains pending if no reviewer runs;
- instructions to stop and report a missing or stale prerequisite instead of
  forcing an implementation against different source.

Keep shared background in submitted input files and name the exact sections the
task needs. Prompts should point to retained evidence by reference rather than
repeat logs and inventories. Run deterministic checks before independent model
review, and place review at meaningful milestones instead of after every small
edit. Group work that shares repository context into a meaningful task.

Use an explicit route the fleet currently advertises. For ordinary
implementation, investigation, repair and review, prefer `codex/gpt-5.6-sol` or
`claudeAgent/claude-opus-5` when `t3-steward models` and `campaign check` confirm
them. Preserve a user's explicit route and an existing campaign's route
contract. Do not silently escalate to a premium model after a failure; improve
an underspecified brief or change the repair strategy first.

Read [references/executor-briefs.md](references/executor-briefs.md) when
authoring implementation or repair prompts. It contains a reusable template and
a concrete, source-bound example.

### Recovery clauses belong in the brief

Describe recovery behavior even when the installed runtime has no manifest
field for it:

- On restart or worker replacement, resume from verified commits, retained
  artifacts and a compact continuation note. Mark provisional work separately
  from accepted checkpoints and retain the checks and provenance behind reuse.
- Give ordinary execution a budget and leave bounded capacity for diagnosis,
  repair and required review. If recovery is waiting on quota or capacity, say
  what condition resumes it. When the budget is exhausted, preserve evidence
  and escalate rather than weakening checks or inventing capacity.
- Give consequential external actions a stable operation identity and require a
  durable receipt where the external system supports one. After a disconnect
  between effect and acknowledgement, reconcile the uncertain outcome before
  retrying. Escalate unresolved consequential ambiguity; do not promise
  exactly-once behavior across systems that cannot provide it.
- Each diagnostic attempt must add evidence or change the proposed fix.
  Repeated identical failures trigger a different strategy or bounded
  escalation. Keep successful branches and rerun only affected work.
- State how token use, retries, reviews, latency and failures will be recorded.
  If token accounting is unavailable, report that gap instead of estimating
  savings or weakening verification.

These clauses guide agents; they do not create recovery budgets, checkpoints,
operation receipts, restart reconciliation or amendments in the runtime. Use
only fields shown by the installed `campaign help`, and record any necessary
manual recovery path as a limitation.

## The shortest correct path

```sh
t3-steward campaign validate ./campaign            # offline: parses and checks
t3-steward campaign plan     ./campaign            # offline: the graph it will create
t3-steward campaign check    ./campaign --json     # live, read-only: can the fleet run it
t3-steward campaign submit   ./campaign --idempotency-key my-campaign-1 --json
t3-steward campaign show <run>
```

`validate` and `plan` reach no coordinator at all. `check` asks the coordinator
and creates nothing. `submit` is the only mutating verb, and it runs the same
check itself before it packs anything, so the explicit `check` above is for you,
not a precondition.

## The directory

```text
campaign/
├── workflow.yaml
├── inputs/          # optional files submitted with the bundle
│   └── plan.md
└── prompts/
    ├── review.md
    └── implement.md
```

The positional argument of every authoring verb is the directory or the
`workflow.yaml` inside it.

## check: three outcomes, three decisions

`campaign check <dir> [--json] [--task NAME]` sends the projected plan's
requirements, never the bundle, and gets back a per-task, per-worker matrix.
`--task NAME` narrows it to one manifest task.

| Outcome | What it means | What you do |
| --- | --- | --- |
| `ready` | at least one worker can take every task now | submit |
| `accepted_waiting` | nobody can now, and waiting is what fixes it | submit; the run exists and stays queued |
| `impossible` | no worker can ever run it as written | fix the manifest or the fleet; submit is refused |

`accepted_waiting` is a success, not a warning. The run is created and queued,
and the calling thread is notified when it settles, because `submit` notifies
by default. End your turn when the record says to; it is the record, not this
page, that knows whether a wait was actually attached.

`check` exits 0 for `ready` and `accepted_waiting`, and 8 for `impossible`; an
impossible campaign is reported as transport class `rejected` with the permanent
reasons only.

Permanent reason codes, which waiting can never fix: `unknown-project`,
`workspace-type-mismatch`, `unknown-setup-profile`,
`unknown-provider-instance`, `unknown-model`, `unknown-quota-pool`,
`worker-not-eligible`, `capability-missing`, `cpu-class-impossible`,
`resources-impossible`, `directory-impossible`, `credential-missing`,
`repository-syntax-invalid`, `repository-authentication-failed`,
`repository-not-found`, `ref-not-found`, `no-route`, `no-configured-route`,
`supervisor-client-missing`, `timing-window-closed`, `message-limit-exceeded`.

`no-route` means a task declares no `routes` at all. The coordinator never
chooses one, so declare `routes: [{instance, model}]` in `workflow.yaml`; the
refusal lists the instance/model pairs the project's eligible workers advertise,
and `t3-steward models` shows them with their quota state.

Temporary reason codes, which submission proceeds through: `quota-closed`,
`worker-at-capacity`, `worker-offline`, `worker-stale`, `network-unavailable`,
`dns-failure`, `probe-timeout`, `snapshot-stale`, `lock-held`,
`timing-window-not-open`, `catalog-digest-mismatch`.

Recovery for the common permanent ones:

```sh
t3-steward backlog projects                       # unknown-project, workspace-type-mismatch (TYPE column)
t3-steward backlog workers --json                 # no-configured-route
t3-steward worker enroll <host> --current-catalog   # catalog-digest-mismatch; on the coordinator host
```

`t3-steward campaign help readiness` has the full table, including what the
repository and ref probe does.

## submit

```sh
t3-steward campaign submit ./campaign --idempotency-key KEY [--json] \
  [--notify-thread <current|id>] [--no-notify]
```

`--notify-thread` defaults to `current`: a submission notifies the calling
thread unless you say otherwise. A caller with no thread to be woken — a plain
shell, an ssh session, cron, CI — has to pass `--no-notify`, or name a thread
with `--notify-thread <id>`; otherwise the submission is refused and nothing is
submitted.

The idempotency key is required and never generated. The same key with the same
bytes returns the same run; the same key with different bytes is refused.
Retrying a submission is therefore safe, and changing a campaign means a new key.

`--allow-unverified --reason TEXT` skips only the client-side check. It is an
operator escape hatch: **agents should not use it.** The coordinator still
refuses a permanently impossible campaign at acceptance, and the principal and
the reason are written into the submission audit record.

## Recurring schedules

A recurring job is an immutable campaign workflow plus a separate coordinator
schedule. Validate and check the campaign normally, then submit it under a new
idempotency key. Submission creates the workflow and its first run. If the
submission exists only to register a future schedule, cancel that initial run
explicitly with `t3-steward campaign cancel <run> --reason "schedule-only
submission"`; do not mistake registration for a run-free operation.

Read the current definition before replacing it, then use its revision as the
fence:

```sh
t3-steward schedules show <schedule> --json
t3-steward schedules put <schedule> --name "<title>" \
  --workflow <workflow-id> --cron "<expression>" \
  --timezone America/Los_Angeles --expected-revision <revision> \
  --reason "<why>" --request-id <stable-id> --json
```

Choose `--after-failure next-cycle|hold` deliberately. The coordinator creates
one run per firing and will not overlap it with an unfinished prior run. Use
`schedules list`, `show` and `history` for evidence; use the revision-fenced
`run`, `enable`, `disable` and `delay-next` controls for operator changes.
Changing campaign bytes requires a new submission key and workflow ID, then a
revision-fenced schedule update. Do not implement recurring jobs with local
user timers, compatibility task files or repeated `task run` calls.

## A minimal manifest

```yaml
version: 2
name: review-and-implement
class: surplus           # surplus runs on spare quota (default); required is admitted first

environment:
  project: my-project    # a project configured on the fleet
  type: git              # git, or fresh for an empty directory (see "Work that needs no repository")
  scope: task
  ref: main

routes:
  - instance: claudeAgent
    model: claude-haiku-4-5
    quota_pool: claude-main  # optional; must be the pool the instance is bound to
    options: {effort: medium} # optional; passed to T3's model selection as written

tasks:
  review:
    prompt_file: prompts/review.md
    outputs: [review.md]
    resources:
      preset: light

  implement:
    needs: [review]
    inputs_from:
      review: [review.md]
    prompt_file: prompts/implement.md
    outputs: [verification.txt, handoff.md]
    verify:
      - go test ./...
    resources:
      preset: build
    max_turns: 12
```

`needs` builds the DAG. `inputs_from` mounts a named output of a finished
dependency into this task's workspace, read-only, at
`.t3/dependencies/<producer>/<artifact>`; naming a task there without also
naming it in `needs` is refused. `outputs` is optional: the task's final
message is always collected as `final-message.md`, and a task whose only result
is that message is a legitimate task. Declare an output when a later task or a
reader needs a file: only a declared output is captured, checksummed and
retained, and a task that does not produce a declared output fails with
`missing declared output` naming the file.

A Git commit a later task needs is declared separately, under `commits:`; see
the next section. `t3-steward campaign help dag-semantics` is the full
explanation of these fields, and `t3-steward campaign help routes` covers
`routes`, including `options` (`effort` is the option T3 honours for Claude and
Codex). A task `context:` block is accepted by the schema but has not been
qualified in the field; pass the same material as input files instead.

## Handing a Git commit to a later task

Declare the commit, and consume it by name through `inputs_from` like any other
artifact. Both halves:

```yaml
tasks:
  implement:
    prompt_file: prompts/implement.md
    outputs: [handoff.md]
    commits:
      - name: implementation
        revision: HEAD        # optional; HEAD is the default

  review:
    prompt_file: prompts/review.md
    needs: [implement]
    inputs_from:
      implement: [implementation, handoff.md]
```

`name` is one safe path component and must be valid inside a Git ref. It shares
the namespace of `outputs`, so one task cannot declare a commit and an output of
the same name. `revision` is resolved in the producing task's own workspace when
that task finishes; a task that declares a commit it did not produce fails with
`declared commit <name>: <cause>`, exactly as a missing declared output fails.
`revision` must be a ref name or a commit id, preferably the full 40-character
one (`HEAD`, a branch, a tag,
`refs/...`); expressions such as `HEAD~1` or `main^` are refused by `validate`
as "not a safe Git ref". To hand over several commits, commit each to its own
branch and declare one entry per branch.

The consumer receives two things:

- the **provenance record** as the retained artifact of that name, arriving at
  `.t3/dependencies/<producer>/<name>` like every dependency artifact. It is a
  `campaign-commit/v1` JSON document naming the producing task, the repository,
  the base the workspace was pinned to, the commit and its campaign ref;
- the **commit itself**, already fetched into its own checkout under the same
  ref, so `git rev-parse refs/campaigns/<run>/<task>/<name>` resolves there.

The successor therefore resolves the commit from a durable ref and never scans a
repository cache for it. The pin the workspace started from is at
`.t3/base-commit`.

**Why this exists.** An implementation task once pushed its branch only into the
worker's shared repository cache. A later task refreshed that cache with
`remote update --prune`, which deletes any ref the origin does not have, and the
commit survived only by luck. The campaign ref store is a separate store beside
the cache, is never pruned, and holds the declared commit for the campaign's
lifetime.

**Publishing a branch to the project remote.** In a Git task workspace `origin`
fetches from the worker's local repository cache, but its push URL is the
project's own repository, so `git push origin <branch>` publishes the branch
where the owner can see it (t3-steward 0.11.0-rc.91 and later; before that the
push landed in the cache and could be pruned, and a workspace an older worker
prepared, including a reused workflow-scoped one, still behaves that way). It
needs the worker's own write access to that repository, and for a contained task
network and credential access inside the sandbox. Push only the task's own
branch: never force, `--mirror` or `--prune`, because `origin` is now the real
repository. Check publication with `git ls-remote <project repository>`, not
`git fetch origin`, which reads the cache and will not show the branch until the
cache is next refreshed. A declared `commits` entry is still how a successor
receives a commit; a push is how the owner does.

Where it shows up:

- `campaign plan` text: `commits  implementation: Git commit at HEAD, retained
  as its provenance record`, and a `N declared commits` total;
- `campaign plan --json`: `tasks[].commits` and `totals.commits`;
- `campaign plan --dot`: the edge label marks it, `implementation (commit)`;
- `t3-steward campaign help commits`.

`plan` cannot print the ref: it contains the run and task IDs, which are
assigned at ingestion.

Lifetime: a declared commit stays reachable for as long as its provenance record
is retained, not until the run settles. A rerun that carries the commit pins the
source run's artifact, so the ref survives for as long as the new run needs it
and there is no timing for you to get right. A rerun authored after the record
has been pruned is refused by the rerun itself, before it creates anything.

One honest limitation, worth knowing if the campaign is long-lived: nothing in
production prunes coordinator artifacts yet. There is no scheduled retention
pass and no configured retention window, so campaign refs persist for as long as
their provenance records do, which today is indefinitely. The bound arrives when
a retention pass is configured, and needs no change on the campaign side.

For the simple case, declaring a plain text file that contains a SHA is still a
legitimate pattern, and it is what the shipped examples do: `single-lead`
declares `commit.txt` as an output and verifies it with
`git rev-parse --verify "$(cat commit.txt)^{commit}"`. Reach for `commits:` when
a later task in the same campaign has to get at the commit itself.

## Things that will bite you

**Declare a route the fleet actually offers.** A task whose model no enrolled
worker provides is never placed. `t3-steward worker list --json` shows what each
worker offers, and `campaign check` says so before you submit. If a task sits
`ready unassigned` after submission, ask
`t3-steward campaign explain <run>/<task>`, which names the routes it tried.

**Do not name a dependency path in `verify`.** Dependencies are mounted in a
directory named for the *producing task's ID*, which is assigned at ingestion.
You cannot know it when you write the manifest. Tell the prompt to list that
directory; verify your own outputs instead.

**Do not restate an output as a verification command.** `outputs: [x.md]`
already requires the file and reports `missing declared output: x.md`. A
duplicate `test -s x.md` runs first and fails with only an exit code, hiding the
better message.

**Tell the agent to use relative paths.** An agent that constructs an absolute
workspace path can write outside the workspace, where nothing is collected and
the task fails with its output apparently missing. Say: work in your current
directory, write with relative paths.

**`resources.preset` decides where it runs.** `light` means a low CPU class is
enough and prefers a smaller host; `build` means minimum medium and prefers
high. Do not pin a host unless the work genuinely needs that machine.

## Preflight

Preflight runs before the agent session and puts its result in the prompt, so
the agent does not spend a turn rediscovering the baseline.

```yaml
preflight:
  steps:
    - id: source
      kind: context            # collects a fact; does not pass or fail
      probe: git_head
      include: summary
    - id: tests
      kind: check              # establishes a pass/fail baseline
      command: [go, test, ./...]
      failure_policy: record   # record: launch anyway with the failure visible
      include: summary         # require-pass: do not start a session at all
      timeout: 5m
```

Declare it at workflow level to apply to every task; a task that declares its
own replaces the inherited list entirely.

## Waiting inside a campaign task

A task gets one turn: ending it with no task-bound wait registered completes
the task, and a closing `BACKLOG STATUS: continue` is a failure, not a request
for another turn. The Steward then collects the declared outputs and verifies
them at once. Native subagents T3 tracks are waited for; processes the task
started in the background (shell jobs, background commands) are not. A prompt
that has the task start its checks in the background and end its turn gets it
collected with no outputs and failed, with "missing declared output ... the
turn ended before it was written". Tell the task to run long checks in the
foreground, or to park as below. From t3-steward
0.11.0-rc.92 the worker appends a short "How this task ends" section saying so
to every task prompt.

A task that has to wait for something external — CI, a review, a long build,
another campaign, a quota window — must not poll and must not finish. It
registers a task-bound wait of the matching kind and ends the turn:

```sh
t3-steward wait add --task current --github run "$(gh run list --branch "$(git branch --show-current)" --limit 1 --json databaseId --jq '.[0].databaseId')" --timeout 2h
t3-steward wait add --task current --node <other-run>/<task> --state succeeded   # campaign B waits for campaign A
t3-steward wait add --task current --quota claude-main --phase normal
t3-steward wait add --task current --for 20m --or-timeout
```

The wake begins with `t3-steward-wait kind=... outcome=... wait=...`; branch on
`outcome` (`met`, `failed`, `gave-up`, `cancelled`, `timed-out`) and read the
kind's pairs. A task cannot wait for its own run's sink.

`--request-id` defaults to `park-<attempt>-<revision>` from the task's identity;
a custom one may use `$(t3-steward task env --get revision)`. The
`T3_STEWARD_*` variables are not in the shell environment unless
`t3.send_thread_environment` is on (off by default).

That parks the attempt: nothing is collected, nothing is verified, no dependent
task is released and the run sink cannot settle until the steward resumes the
same thread with the outcome. **End the turn there.** Read the `t3-wait` skill
before using it; getting this wrong is what makes a run verify against work the
task has not done.

## Being woken when the run settles

```sh
t3-steward campaign submit ./campaign --idempotency-key KEY   # notifies by default
t3-steward campaign submit ./campaign --idempotency-key KEY --no-notify
```

Notification is the default, not an opt-in. Every submission registers a
durable node wait (`--state terminal`) on the new run's sink and wakes the
calling agent's own canonical thread when the run ends. `--no-notify` is the
only opt-out. `--notify-thread <id>` names a thread other than the caller's,
which is what a script on another host wants.

The thread is resolved before anything is submitted, so a submission for which
no thread resolves is **refused with nothing submitted** rather than left
running with nobody listening. Pass `--notify-thread <id>` when resolution is
ambiguous, or `--no-notify` when nobody is meant to be woken.

The wake's first line is the node trailer, for example
`t3-steward-wait kind=node outcome=met wait=nw-campaign-KEY progress=failed
failed=implement result="t3-steward task result <run>" run=<run> ...`: `outcome=met`
means the run ended, `progress=` says how, `failed=` lists the failed tasks,
and `result=` is the command that fetches the run's result. A cancelled run
wakes `outcome=cancelled`.

The registration ID is derived from the idempotency key, so re-running the same
submit asks for the same wait rather than a second one. That is where the ID
comes from and not a promise that one wait is all you ever get: when the
coordinator answers that the derived wait is spent — already delivered,
cancelled, or held for another thread — both `campaign submit` and `task run`
register a fresh one under a new ID rather than report a wake that will not
arrive. The same rule applies when the key replays onto a run that has already
ended: nothing is registered, because there is nothing left to wait for.

So do what the record's closing line says rather than ending the turn by habit.
It says `End this turn now` only when a wait exists that will fire for this
thread. Otherwise it says plainly that no wake is attached, or that the run has
already ended and the result is there to collect, and names the command to run
instead. If submission succeeded and registration then failed, the error names
the run; register it separately with
`t3-steward wait add --node <run> --thread <id>`.

There is no SSH helper and no polling loop for this. Full explanation:
`t3-steward campaign help notify`.

## Watching a campaign

```sh
t3-steward campaign show <run> [--json]                 # task states
t3-steward campaign graph <run> [--json|--dot]          # the persisted graph
t3-steward campaign explain <run>/<task> [--json]       # why a task is not running
t3-steward campaign list [--project P] [--progress STATES] [--class CLASS] [--json]
t3-steward campaign cancel <run>/<task> --reason TEXT [--command-id ID] [--json]
t3-steward campaign cancel <run> --reason TEXT [--command-id ID] [--json]
```

Naming no task cancels every non-terminal task of the run with one command,
one revision fence per attempt, which is what a fan-out run needs: cancelling
one of its tasks cascades to nothing, because they need each other for nothing.

`plan` is static and says what the manifest means; `explain` is dynamic and says
what the coordinator decided. `check` is dynamic too, before there is a run.
When a task is not starting, `explain` is the one to ask: it names missing
capabilities, a CPU class below the floor, exhausted capacity, a stale worker or
an unavailable route.

## Starting a failed run again

```sh
t3-steward campaign rerun <run> --from <task> --idempotency-key KEY \
  [--reason TEXT] [--json]
```

Both `--from` and `--idempotency-key` are required. The named task and
everything downstream of it are rerun; every other task is reused, with its
outputs carried over by reference into the same place in the workspace. The
source run is never changed: it stays failed and stays readable, which is why
`t3-steward campaign show <source run>` is always the safe next step when a
rerun refuses.

A rerun is refused when the source run has not finished, when a task that would
be reused did not succeed, when an ancestor artifact is no longer retrievable,
or when the source run changed between being read and being reran from. A
refused rerun creates nothing. Full explanation:
`t3-steward campaign help rerun`.

## Talking to the coordinator from another host

`validate` and `plan` need no coordinator. Every other verb reaches one: through
its owner-only socket on the coordinator host, and on any other host through an
SSH session to the coordinator's restricted `coordinator-exchange` command,
selected by a coordinator client in `backlog_v2.coordinator_client` or in the
UpKeeper-owned `~/.config/t3-steward/coordinator-client.json` (mode 0600), whose
credential is a `secretref:f03-admin/<client>` reference resolved at use.

**Never run `ssh <coordinator> t3-steward ...`.** The client transport is the
authority boundary; opening a shell on the coordinator host goes around it.

The one exception is worker enrollment. `t3-steward worker enroll` binds a
worker to the coordinator's identity and epoch, so it is an operator action on
the coordinator itself and is refused to the remote-admin role by design. Run
it on the coordinator host, at its console or through a plain `ssh <coordinator>`
shell, never through the client transport:

```sh
t3-steward worker enroll <worker> --current-catalog --reason "why"   # one worker
t3-steward worker enroll --all --current-catalog --reason "why"      # every stale worker
```

`--current-catalog` reads the required catalog digest and the worker's current
enrollment revision from the coordinator itself, so nothing has to be copied out
of `backlog workers --json`. A project published through UpKeeper without a
local `backlog_v2.projects` binding loads with default local bindings and shows
as `project-binding-defaulted` in `check` and `explain`; its eligible workers
still need this re-enrollment before they are offered the project.

Prove which coordinator will answer before you submit anything:

```sh
t3-steward coordinator identity --json
```

Branch on the exit code, not on the message:

| Exit | Class | Permanent? |
| --- | --- | --- |
| 0 | the coordinator answered | — |
| 3 | client configuration: this host cannot form a request | yes, until configuration changes |
| 4 | authentication: the principal or signature was refused | yes, until credentials are rotated |
| 5 | unavailable: no coordinator answered | usually temporary |
| 6 | timeout: the deadline expired | usually temporary |
| 7 | protocol: version, limit or frame mismatch | yes |
| 8 | rejected: the coordinator answered and refused | yes, on the merits |
| 1 | anything else | — |

With `--json`, a failure that reached the transport also prints
`{"version":"backlog.admin/v1","kind":"error","class":"...","operation":"...","message":"..."}`
on standard output. Re-running with the same `--idempotency-key` is always safe:
it returns the first answer rather than doing the work twice.

## Help topics

```sh
t3-steward campaign help <topic>
```

Topics: `plan`, `graph`, `dag-semantics`, `commits`, `static-versus-dynamic`,
`readiness`, `rerun`, `notify`. Recovery, graph amendment and artifact commands stay under
`t3-steward backlog`.

## Worked examples

Two checked-in campaigns in the t3-steward repository, both covered by tests:

- `docs/examples/campaign/single-lead/` — one lead task that fixes a defect,
  runs the suite and returns a commit, a test receipt and a handoff.
- `docs/examples/campaign/three-node/` — two independent analysis tasks and a
  join that declares both through `inputs_from` and emits a combined result.

Both mark every value that is operator configuration — the project, the provider
instance, the model and the quota pool — with a trailing comment. Replace all
four before submitting either directory.
