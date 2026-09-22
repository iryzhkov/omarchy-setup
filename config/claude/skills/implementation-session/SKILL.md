---
name: implementation-session
description: Produce a focused, quota-conscious kickoff prompt from a plan for an interactive implementation session in Claude Code, Codex or OpenCode. Use when the user wants to prepare an implementation session or reduce coordination and context overhead; generating the prompt does not start the work.
---

# Implementation session

Turn a supplied plan into a copyable execution prompt. This is prompt preparation,
not permission to implement, delegate, submit a campaign or publish. If the user
explicitly asks to execute too, finish the brief first and use their existing
authorization. Preserve explicit model choices, scope, checks and release gates.

## Prepare only what changes the brief

Read the plan and applicable repository instructions. Inspect enough source to
pin the baseline and verify the first milestone's paths, symbols and commands;
do not survey the entire repository or solve all later milestones. Reuse current
revision-bound evidence. Fetch references only when needed.

Choose the smallest end-to-end outcome that exercises the uncertain integration
boundary. For example, recovery means a failed task resumes through its original
check and independent review, not merely that a retry helper passes its unit test.
When the seam is unknown, make a bounded investigation the first milestone and
require its output to be an implementation-ready brief.

Use [references/prompt-template.md](references/prompt-template.md) to produce one
copyable prompt, normally under 900 words excluding user-supplied constraints.
Remove irrelevant sections. Include exact references rather than copied logs.
Do not invent repository paths, model IDs, acceptance commands or budgets.
If source is unavailable, mark the map unverified and make verification the
first action before edits. Ask only for missing information that materially
changes the brief; otherwise state a reasonable assumption.

The prompt must carry:
- The authorized overall outcome and first milestone's observable acceptance.
- Verified baseline, code map, prerequisites and evidence/output locations.
- A model and delegation policy adapted to available tools, not harness-specific
  calls. Prefer Sol/Opus for ordinary implementation, investigation and review
  when available; reserve Astra/Fable for bounded consequential decisions.
  Resolve exact IDs at execution time and preserve user selections. Never claim
  to switch the current conversation's model. If routing is unavailable, work
  with the selected model and report the limitation.
- Focused context and evidence handling, diagnostic repair bounds, independent
  review where required, and a durable continuation checkpoint.
- Existing approval boundaries, plus separate source/release/deployment claims.

Default to a direct implementer. Where delegation is authorized and useful,
use one implementer and one independent reviewer at a meaningful milestone;
parallelize only genuinely independent tasks with nonoverlapping ownership.
Do not create a permanent premium-model supervisor for routine mechanics.
A fresh worker gets a focused brief and evidence pointers, not the entire
conversation. Keep a worker for related work when its context remains useful.

A milestone is an efficiency checkpoint, not a new human gate. Continue within
the authorized plan and budget. A quota/time stop leaves exact commits, accepted
versus provisional work, checks, findings and one concrete next action. Use
supported durable waits for external conditions; waiting is pending, not done.

Measure tokens per verified outcome including lead, workers, retries and review
when accounting exists. Separate cached input, uncached input and output; do not
add reasoning twice or count inherited usage again. Report missing accounting.
Token totals are not subscription-quota units; do not infer savings from cache
hits, shorter prompts or weaker checks.

## Steward adaptation

For new campaigns, apply these principles through the maintained t3-campaign
skill and executor briefs: coherent tasks, an early integration proof, bounded
repair, durable evidence, and selective independent review. Preserve autonomous
continuation and supervisor ownership; the companion does not also repair.
Do not impose interactive stage approvals, create a competing scheduler, invent
budget/telemetry manifest fields, or amend a live campaign implicitly. Guidance
is not evidence that the runtime enforces a policy. Runtime gaps require a
separate implementation task and causal verification.
