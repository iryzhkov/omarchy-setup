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
