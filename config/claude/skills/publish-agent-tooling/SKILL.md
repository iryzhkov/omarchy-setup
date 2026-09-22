---
name: publish-agent-tooling
description: >
  The publication path for a validated change to agent tooling: run checks,
  publish source and CI, prepare or verify an UpKeeper release, review the full
  release, and gate fleet convergence. Use whenever work touches Huyang,
  t3-steward, UpKeeper, agent99, shared AGENTS.md or CLAUDE.md files, skills, or
  MCP configuration. Triggers: upkeeper push, release manifest, capture,
  authored release, converge, publish the fix, instruction change, skill change,
  MCP registration.
---

# Publishing a validated agent-tooling change

A validated fix to agent tooling is published through UpKeeper without waiting for a
separate request to push, unless the user explicitly keeps it local. Source publication,
release publication and runtime convergence are separate outcomes.

1. Run the owning repository's checks. Commit and push the source, then confirm required
   GitHub CI for that exact commit.
2. Publish any required build artifact and validate the intended controller installation.
3. For instructions, edit the owning source and regenerate derived files; never promote a
   hand-edited installed copy.
4. Choose capture or authored publication deliberately, review the whole release, publish
   it, and confirm CI for the exact release commit.
5. Preview convergence on every intended target and apply it only when the runtime gate is
   safe.

## Prepare the release

Use ordinary upkeeper push when the release should capture the validated host's observed
component pins and agent environment. Capture is intentionally broad: inspect the complete
candidate manifest and referenced assets before committing it. Preserve unrelated pins,
worker configuration, secret references, operational holds and work owned by another
session. Do not capture unvalidated local builds.

Use authored mode when the release manifest and referenced assets were prepared and
reviewed directly and must be published without recapturing the host:

~~~bash
expected_head=$(git rev-parse HEAD)
expected_release_sha256=$(upkeeper fleet-plan --json | jq -er '.release_sha256')
upkeeper push --authored \
  --expect-head "$expected_head" \
  --expect-release-sha256 "$expected_release_sha256" \
  --json
~~~

Run those commands in the clean, current UpKeeper checkout whose branch will be published.
The HEAD fence identifies the reviewed parent; release_sha256 is the canonical release
digest reported by the read-only fleet plan. Do not substitute a guessed file hash.
Authored mode validates the whole manifest, inventory and referenced assets, preserves the
reviewed bytes and timestamp, and refuses --components; it does not recapture local state.
Both fences are mandatory.

Before either form of publication, inspect the full manifest diff, every referenced asset,
the selected remotes and the expected source pins. A Git source push alone does not update
the release manifest. Treat a partial remote failure as incomplete publication: retain the
JSON receipt showing pushed, failed and unattempted remotes, reconcile remote state, and
retry only the missing safe effect.

## Release CI and runtime gate

Confirm required CI for the exact UpKeeper release commit before convergence. Record the
source commit and CI, release commit and CI, manifest digest, asset evidence, and remote
receipts separately.

Preview the complete convergence against intended hosts. Check holds and actual drift, and
identify whether any component would reload, restart, replace or drain a coordinator,
worker or T3 service. Unchanged desired pins do not prove a drifted host is unaffected. If
an active campaign cannot be shown to continue uninterrupted, retain the validated release
and defer convergence until a safe window. Do not weaken campaign prompts, routes, gates,
approvals, artifacts or checks to make deployment convenient.

Use UpKeeper for approved convergence; the laptop normally converges through its local
upkeeper pull --self timer. Report source-published, release-published, actually deployed
and runtime-verified states separately. A successful build, push, wait or release CI run
is not proof of fleet convergence.
