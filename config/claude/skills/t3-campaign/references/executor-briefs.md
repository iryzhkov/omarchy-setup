# Executor brief template and example

Use this reference for campaign tasks that implement, investigate, review or
repair repository work. Delete headings that do not apply; do not leave
placeholders for the executor to infer.

## Template

### Objective and observable behavior

State one outcome and how a reviewer observes it. Include a small before/after
or input/output example. Say what is outside the task.

### Pinned source and verified code map

- Repository: `<canonical repository URL or fleet project>`
- Working directory: current task workspace; use relative paths
- Starting revision: `<full immutable commit>`
- Relevant paths and symbols:
  - `<path>` — `<symbol or section>`: `<role>`
- If HEAD, a named path, symbol, generated file, dependency artifact or
  documented command differs from this map, stop before editing. Record
  `git rev-parse HEAD`, the missing/stale item and the nearest verified
  replacement in `mismatch.md`; do not force the proposed patch.

Verify this map against the pinned revision while authoring. Do not ask the
executor to rediscover the repository unless discovery is the assigned outcome.

### Inputs and provenance

Name each submitted input and dependency artifact, its producer or source
revision, its mounted location, and the section required for this task. Name
the artifact or commit that later tasks consume. Treat undeclared notes as
untrusted context.

### Suggested approach and invariants

Describe the smallest supported implementation seam and an existing pattern to
follow. Explain non-obvious constraints. State allowed files, forbidden live
systems or external effects, approval boundaries, and checks that recovery must
preserve. Suggestions yield to verified source: a mismatch produces evidence,
not a forced edit.

### Setup and deterministic verification

Give commands exactly as they run in a fresh task shell, including known CPU,
memory, disk or concurrency bounds. State expected exit codes or observable
results. A worker may add a resource wrapper such as `GOMAXPROCS=2` or `-p 1`
when it does not reduce coverage, skip checks or change the expected result;
record the wrapper and why it was needed. Run deterministic format, build, lint
and tests before requesting independent review. Keep commands scoped until a
meaningful milestone; run the repository-required full gate before completion.

### Outputs and checkpoint

List every declared output and its required contents. For a code-producing task,
declare a campaign commit when a later task needs the Git object. Put independent
review in a distinct dependent task or an established independent channel. Name
its reviewer task/identity and route, declare its review artifact, and require at
least the reviewed commit, `accept|changes-requested` verdict, findings and
verification evidence. If no review channel is available, implementation may
checkpoint successfully but remains pending review and cannot claim completion.
A useful checkpoint names the exact commit, source base, checks that passed,
artifact hashes or references, known risks and the next action. Label incomplete
or unverified work provisional.

### Recovery, effects and budget

- Budget: `<attempt count/time/turns>`, including room for diagnosis and the
  required review. When capacity or quota is unavailable, register a durable
  wait if supported and report the resume condition.
- Every repair must add evidence or change the fix. After the same deterministic
  failure repeats, change strategy. Escalate when the budget is exhausted.
- Preserve successful branches and rerun only affected checks before the final
  full gate.
- For an external action, assign `operation_id=<stable identity>` and retain
  the remote receipt. If acknowledgement is lost, query the remote system using
  that identity before retrying. Escalate consequential ambiguity when the
  remote system cannot establish the outcome.
- Resume after replacement from the last accepted checkpoint. Distinguish a
  deliberate task-bound wait from abandoned work.
- Record token usage supplied by the runtime alongside latency, attempts and
  outcomes. Write `unavailable` when the runtime supplies no token count.

These are prompt requirements. Do not add manifest keys for them unless the
installed `t3-steward campaign help` documents those keys.

### Completion and escalation

Completion requires the named outputs, deterministic checks and an `accept`
verdict in the declared independent review artifact. Self-review does not satisfy
that gate. State who may approve any release or consequential external action.
Escalate only for missing authority, a source-contract decision, an external
blocker agents cannot resolve, an uncertain consequential effect, or exhausted
recovery. Retain the smallest evidence bundle needed to continue.

## Concrete example: improve campaign guidance

This example is tied to the verified omarchy-setup source at
`51324f838ac14db22fec80d3d48a8fe1c5ea1c29`. Re-verify it before reuse.

### Objective and observable behavior

Update the campaign authoring skill so an executor receives a focused,
self-contained brief. Before: a prompt such as “fix the issue and run tests”
requires repository discovery and has no mismatch rule. After: the skill
requires the pinned source, verified paths, exact checks, retained evidence and
a bounded repair policy, and links a reusable template. Keep existing campaign
purpose, submission, DAG, wait, rerun and notification contracts intact.

### Pinned source and verified code map

- Fleet project/repository: the omarchy-setup checkout supplied to the task.
- Starting revision:
  `51324f838ac14db22fec80d3d48a8fe1c5ea1c29`.
- `config/claude/skills/t3-campaign/SKILL.md` — the maintained campaign skill;
  its “Frame the work for autonomous completion” section owns the current
  purpose and recovery guidance.
- `config/bin/agents-instructions-gen` — generates installed agent references
  from the maintained checkout; it must never be run against the real home in
  this task.
- `test/agents-instructions.py` — isolated generator/reference verification.
- `test/run.sh` — repository integration test, including generated instruction
  checks in a temporary home.

If the revision differs or any path/section is absent, do not transplant this
example. Write `mismatch.md` with the observed full HEAD and path/section
difference, leave the tree unchanged, and finish with a blocked handoff.

### Inputs and provenance

- `inputs/requirements.md`: accepted authoring requirements from the campaign
  plan, submitted with the campaign bundle. Read only “Executor prompt quality”
  and “Recovery capacity and budgets”.
- No live coordinator data is required. Route availability is checked by the
  campaign author before submission.
- Produce `guidance-handoff.md` and a declared commit named `guidance`.
  The independent reviewer consumes both by `inputs_from`.

### Suggested approach and invariants

Add concise decision-changing guidance to the skill and put the detailed
template/example in `config/claude/skills/t3-campaign/references/`. Link the
reference from the skill so it is discoverable only when writing briefs.
Preserve the existing frontmatter and autonomy text. Do not edit installed
copies under `~/.claude` or `~/.config/agents`, run a generator against the
real home, submit a campaign, publish, deploy, or modify other skills.

The separation exists because every campaign user needs the brief principles,
while only authors preparing an implementation or repair prompt need the full
template.

### Setup and deterministic verification

From the isolated repository root:

```sh
test "$(git rev-parse HEAD)" = 51324f838ac14db22fec80d3d48a8fe1c5ea1c29
git diff --check
test/run.sh
python3 test/agents-instructions.py
find . -type f -not -path './.git/*' -exec sh -c '
  for file do
    IFS= read -r first <"$file" || true
    case "$first" in
      "#!"*"sh"*) shellcheck "$file" ;;
    esac
  done
' sh {} +
python3 /home/igor/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  config/claude/skills/t3-campaign
```

Expected: the source revision assertion passes before edits; after edits,
`git diff --check` and every validation command exits 0. The shellcheck loop
examines only files whose first line is a shell shebang. Run tests with their
own isolated homes; do not export the real home as a test target.

### Outputs, recovery and completion

`guidance-handoff.md` records the resulting commit, changed paths, commands
and exit codes, and any missing token accounting. The declared `guidance`
commit contains only the maintained skill and its linked reference plus a
meaningful generation test if behavior needs one. A distinct dependent review
task uses the fleet-confirmed `codex/gpt-5.6-sol` route, consumes `guidance` and
`guidance-handoff.md`, and declares `review.md`. That artifact names the reviewed
commit and reviewer task/route, gives an `accept|changes-requested` verdict,
lists findings and cites deterministic evidence. If that task cannot run, retain
the implementation checkpoint as pending review rather than claiming completion.

Budget: two implementation attempts and one focused diagnostic attempt, with
one independent review after deterministic checks. A repeated deterministic
failure must produce new evidence or a changed fix. Preserve a passing branch.
Do not weaken generator or repository tests. No external effects are authorized,
so an effect receipt is not applicable.

Complete only when all checks pass and the commit is ready for independent
review. Escalate a stale source/path mismatch, a required change outside the
allowed files, or exhausted recovery with `mismatch.md` or the failing log.
Do not claim the representative Sol evaluation; a separate agent performs it
from the retained brief and references.
