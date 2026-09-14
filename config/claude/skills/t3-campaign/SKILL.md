---
name: t3-campaign
description: >
  Author a multi-step t3-steward job as a campaign directory: a version 2
  workflow with a task DAG, artifacts passed between tasks, and preflight
  evidence, validated offline, checked against the live fleet and submitted with
  `t3-steward campaign`. Use when work needs more than one unattended task, when
  tasks depend on each other or pass files between them, when a plan should be
  reviewed before it is implemented, when a failed run must be started again
  from one task, or when the user asks for a DAG, a pipeline, a multi-stage job
  or a campaign. Triggers: campaign, DAG, workflow, pipeline, multi-step job,
  fan out, parallel tasks, artifact between tasks, declared commit, plan then
  implement, review then implement, campaign check, readiness, rerun,
  accepted_waiting.
---

# t3-campaign

A campaign is a directory you write and submit. It becomes exactly one workflow
and one workflow run; there is no separate campaign record, schedule or state.
Every lifecycle command below is the existing backlog operation with the same
JSON and exit codes.

Use `t3-backlog` for a single unattended task. Use a campaign when there is more
than one task, when tasks depend on each other, or when one task's output is
another's input.

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
so you may end your turn on it, or pass `--notify-thread` to be woken when it
settles.

`check` exits 0 for `ready` and `accepted_waiting`, and 8 for `impossible`; an
impossible campaign is reported as transport class `rejected` with the permanent
reasons only.

Permanent reason codes, which waiting can never fix: `unknown-project`,
`unknown-setup-profile`, `unknown-provider-instance`, `unknown-model`,
`unknown-quota-pool`, `worker-not-eligible`, `capability-missing`,
`cpu-class-impossible`, `resources-impossible`, `directory-impossible`,
`credential-missing`, `repository-syntax-invalid`,
`repository-authentication-failed`, `repository-not-found`, `ref-not-found`,
`no-configured-route`, `timing-window-closed`, `message-limit-exceeded`.

Temporary reason codes, which submission proceeds through: `quota-closed`,
`worker-at-capacity`, `worker-offline`, `worker-stale`, `network-unavailable`,
`dns-failure`, `probe-timeout`, `snapshot-stale`, `lock-held`,
`timing-window-not-open`, `catalog-digest-mismatch`.

Recovery for the common permanent ones:

```sh
t3-steward backlog workers --json                 # unknown-project, no-configured-route
t3-steward worker enroll <host> --catalog-revision <desired>   # catalog-digest-mismatch
```

`t3-steward campaign help readiness` has the full table, including what the
repository and ref probe does.

## submit

```sh
t3-steward campaign submit ./campaign --idempotency-key KEY [--json] \
  [--notify-thread <current|id>]
```

The idempotency key is required and never generated. The same key with the same
bytes returns the same run; the same key with different bytes is refused.
Retrying a submission is therefore safe, and changing a campaign means a new key.

`--allow-unverified --reason TEXT` skips only the client-side check. It is an
operator escape hatch: **agents should not use it.** The coordinator still
refuses a permanently impossible campaign at acceptance, and the principal and
the reason are written into the submission audit record.

## A minimal manifest

```yaml
version: 2
name: review-and-implement
class: surplus           # surplus runs on spare quota (default); required is admitted first

environment:
  project: my-project    # a project configured on the fleet
  type: git              # git, or fresh for an empty scratch directory
  scope: task
  ref: main

routes:
  - instance: claudeAgent
    model: claude-haiku-4-5
    quota_pool: claude-main

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
naming it in `needs` is refused. `outputs` are required: only a declared output
is captured, checksummed and retained, and a task that does not produce one
fails with `missing declared output` naming the file.

A Git commit a later task needs is declared separately, under `commits:`; see
the next section. `t3-steward campaign help dag-semantics` is the full
explanation of these fields.

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

Where it shows up:

- `campaign plan` text: `commits  implementation: Git commit at HEAD, retained
  as its provenance record`, and a `N declared commits` total;
- `campaign plan --json`: `tasks[].commits` and `totals.commits`;
- `campaign plan --dot`: the edge label marks it, `implementation (commit)`;
- `t3-steward campaign help commits`.

`plan` cannot print the ref: it contains the run and task IDs, which are
assigned at ingestion.

Lifetime: the refs of a run are released together once the run has settled, and
a run carrying a commit into a rerun holds its source. Since a rerun may only be
created from a finished run, create one that must carry a declared commit while
the source run's refs are still there.

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

A task that has to wait for something external — CI, a review, a long build —
must not poll and must not finish. It registers a task-bound wait and ends the
turn:

```sh
t3-steward wait add --task current --name "CI on $(git rev-parse HEAD)" \
  --request-id ci-$T3_STEWARD_ATTEMPT_REVISION -- \
  sh -c 'test "$(gh run view --json status --jq .status)" = completed'
```

That parks the attempt: nothing is collected, nothing is verified, no dependent
task is released and the run sink cannot settle until the steward resumes the
same thread with the outcome. **End the turn there.** Read the `t3-wait` skill
before using it; getting this wrong is what makes a run verify against work the
task has not done.

## Being woken when the run settles

```sh
t3-steward campaign submit ./campaign --idempotency-key KEY --notify-thread current
```

`--notify-thread` registers a durable wait on the new run's sink and wakes that
T3 thread with the terminal outcome. `current` is the calling agent's own
canonical thread, resolved before anything is submitted: an unresolvable thread
leaves no run behind. Pass `--notify-thread <id>` when resolution is ambiguous.

The registration ID is derived from the idempotency key, so re-running the same
submit registers the same wait rather than a second one. After a successful
registration, end the turn. If submission succeeded and registration then
failed, the error names the run; register it separately with
`t3-steward wait add --run <run> --thread <id>`.

There is no SSH helper and no polling loop for this. Full explanation:
`t3-steward campaign help notify`.

## Watching a campaign

```sh
t3-steward campaign show <run> [--json]                 # task states
t3-steward campaign graph <run> [--json|--dot]          # the persisted graph
t3-steward campaign explain <run>/<task> [--json]       # why a task is not running
t3-steward campaign list [--project P] [--progress STATES] [--class CLASS] [--json]
t3-steward campaign cancel <run>/<task> --reason TEXT [--command-id ID] [--json]
```

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
