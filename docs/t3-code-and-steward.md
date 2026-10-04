# T3 Code and steward deployment

UpKeeper in [dev-fleet](https://github.com/iryzhkov/UpKeeper) owns the pair and the
agent environment. desired/release.json records exact versions and the steward's
T3 compatibility range. Capture and publish with upkeeper push; converge selected
inventory hosts with upkeeper pull.

Citadel U1 removes modules/common/26-t3.sh, modules/common/45-agents.sh and
bin/t3-update. UpKeeper pull disables and deletes t3-update.timer and
t3-update.service before deployment; an active updater defers deployment until it
finishes. Rollback never recreates these units.

UpKeeper's T3 component seeds an absent t3code.service with loopback binding, the
mise shim PATH and optional ~/.config/claude/oauth.env. Existing units and their
host-local bind addresses, environment and credentials are preserved. Missing
oauth.env produces a warning; secret provisioning remains a host responsibility.

Use upkeeper rollback --to <release-commit> --hosts <host> --components t3-steward
for a deliberate historical steward deployment. New manifests select the T3 pair
together. UpKeeper verifies the pinned artifact and compatibility rather than
discovering a newest release. The dev-fleet push/pull guide describes limitations
and recovery evidence.

omarchy-setup keeps OS packages, desktop, toolchains, secrets and sshd. Its
UpKeeper bootstrap handoff and pull --self are Citadel U2, not part of U1.

## Agent work through the steward

Stay interactive for exploration, design and contract decisions. Once Igor agrees
a plan, write it to Jocasta and hand it off with the `t3-campaign` skill using
the session as notify thread; retain the run id and ledger reference. Quick
same-provider subagents can read or do sub-work, never replace declared tasks or
reviews. The resident instructions own manual model roles and bulk-reader rules.

Use `task run --input FILE` and `--dry-run` for one independent task;
`campaign validate/plan/check/submit` for dependent work; `review` for
cross-provider plan or diff review; `ask` for owner decisions inside a steward
task; and `triage` for operator attention. Outside a task, use the session's
question tool. A plain CLI can block with `task result --wait` or
`campaign show --wait`; an agent task registers a task-bound wait and ends its
turn. Campaign executors keep `continuation.md` current for resume and handoff.

The `t3-backlog` compatibility wrapper is obsolete for new agent guidance;
existing scripts can continue using it during the rollback window. Use
`t3-steward task run` for new submissions. Retained operator controls and their
authority safeguards live in the `t3-campaign` skill's operator section; full
`backlog` and `worker` help hold the complete low-level command inventories.

Commands and flags were checked against 0.11.0-rc.105. Role assignment,
milestone ledgers and reader digestion are agent conventions until generated
policy and runtime orchestration replace them. Older clients or coordinators may
lack file inputs, blocking collection, review or run-free schedule registration;
check installed full help and report unsupported behavior rather than guessing.
Older prepared workspaces may have cache push URLs: inspect the push URL before
publishing a task branch. No installed instructions or fleet deployment are changed
by a source-only PR. See [instruction ownership](agent-instruction-ownership.md)
for sources, isolated generation checks and the authorized release path.
