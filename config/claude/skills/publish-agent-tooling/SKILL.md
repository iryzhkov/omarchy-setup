---
name: publish-agent-tooling
description: >
  The publication path for a validated change to agent tooling: run the checks,
  push the source, confirm its GitHub CI, capture an UpKeeper release from a
  validated host, and let the fleet converge. Use whenever the work touches
  Huyang, t3-steward, UpKeeper, agent99, shared AGENTS.md or CLAUDE.md files,
  skills, or MCP configuration, and before reporting such a fix as distributed.
  Triggers: upkeeper push, release manifest, capture, converge, publish the fix,
  agent tooling change, instruction change, skill change, MCP registration.
---

# Publishing a validated agent-tooling change

A validated fix to agent tooling is published through UpKeeper without waiting for a
separate request to push. The always-on summary is in CLAUDE.md; this is the whole
procedure.

1. Run the applicable checks for the repository that owns the change.
2. Commit and push the source to its configured remotes, and confirm that the exact
   source commit's required GitHub CI succeeds.
3. Publish any required release artifact and validate the intended controller
   installation.
4. For an instruction change, edit the owning sources and regenerate the derived files
   rather than editing a generated or deployed copy.
5. Run `upkeeper push` from the fleet host where the intended tooling and agent
   environment have been validated, using a clean, current UpKeeper checkout with push
   access to the configured remotes. Normandy is not required.
6. Confirm GitHub CI for the published UpKeeper release commit before convergence.

## What capture actually publishes

Capture publishes the observed pins and agent environment of the host it runs on, so
review the whole candidate release rather than the file you changed, and preserve
unrelated pins before publication. A Git push alone does not update the UpKeeper release
manifest.

Verify that the manifest diff contains only intended changes. Preserve unrelated work,
worker configuration and secret references. Do not capture unvalidated local builds or
unrelated newer component versions.

## Deployment and reporting

Use UpKeeper for deployment; the laptop converges through its local `upkeeper pull --self`
timer. Report the release commit, the validation performed, and any pending or blocked
publication or convergence honestly. If capture or a gate is blocked, record the precise
blocker and preserve the safeguards rather than declaring the fix distributed.

An explicit user instruction to keep the work local takes precedence over all of this.
