# Copyable kickoff prompt

Fill the bracketed fields using verified evidence, remove unused clauses, and
adapt the wording to the user's actual authority and available harness. Do not
leave unresolved placeholders in a ready-to-run prompt.

~~~text
Implement [plan reference and revision] toward [authorized overall outcome].
Start with [one end-to-end milestone], accepted when [observable behavior and
causal verification]. Later work remains [reference]; do not expand the current
milestone speculatively. Continue authorized milestones after acceptance unless
the agreed budget or a genuine external gate prevents it.

Source and inputs:
- Repository/worktree: [location]; exact baseline: [commit].
- Code map: [verified paths/symbols and their roles].
- Inputs: [versioned references, required sections, dependency artifacts].
- Setup and checks: [exact commands, prerequisites and expected outcomes].
- Allowed edits, invariants and external-action boundaries: [scope].
If source or prerequisites differ, retain the actual revision and mismatch.
Reconcile safe routine differences within scope and update the brief; stop
dependent edits for consequential contract ambiguity. Never force a stale patch.

Use the user's selected models. Otherwise prefer an available Sol/Opus executor
for ordinary work and an independent reviewer at a meaningful milestone; resolve
exact IDs from the available catalog. Use Astra/Fable only for a bounded difficult
decision or consequential review. If model selection or delegation is unavailable,
say so and use the current harness without inventing capabilities. Delegate only
when authorized. Give workers verified, self-contained briefs, allowed files and
acceptance criteria; do not make them rediscover the repository. Add parallelism
only for independent deliverables. Use a fresh focused context at an unrelated
handoff; retain context when the next work shares it.

Prove the integration boundary early, before broad component work. Run focused
deterministic checks during development, then all required milestone/repository
checks before independent review. Preserve review independence and original
acceptance criteria. Fix findings and rerun affected checks plus required final
gates; do not repeat unchanged full checks without a reason.

Keep reads and outputs bounded. Use the repository's required source tools
(Huyang where configured), symbol/line reads and scoped searches. Reuse workspace
IDs and current evidence; refresh on revision changes. Emit one useful payload,
not duplicate wrappers, full manifests with embedded bundles, or entire passing
logs. Keep full evidence in files/references and summarize only conclusions,
failures and next actions.

Each failed repair must add evidence or change the fix. A repeated identical
deterministic failure triggers diagnosis of the approach or brief, not another
identical attempt or automatic premium-model escalation. Preserve successful
branches. Reconcile uncertain external effects before retrying them.

Budget: [user-supplied limit, or a clearly labeled proposed milestone boundary].
Reserve room for necessary diagnosis and review. At a budget stop, checkpoint
rather than weaken verification. Wait durably for external conditions when
supported; do not spend model turns polling. Stage completion alone does not
require user confirmation.

Maintain one compact checkpoint at [durable location]: exact commits, accepted
and provisional work, check/review receipts, unresolved risks and the next
action. Keep detailed logs by reference. Report usage per verified outcome,
including retries/reviews, when available; otherwise say unavailable. Cached
tokens are not a measured quota saving.

Complete with observable outcomes and evidence. Report implemented, validated,
source-published, release-published and deployed states separately where relevant.
Honor [explicit approvals/protected systems]; do not infer deployment authority
from implementation authority.
~~~
