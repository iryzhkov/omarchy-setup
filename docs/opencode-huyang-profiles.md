# OpenCode Huyang profiles (M7)

Supported host API: **OpenCode 2.0.30 V2 server plugins**, upstream tag v2.0.30,
commit `f16ef9ad8878279ea2be3cfab7baeed97aef61aa`. On another reported version the
plugin withholds only Huyang: no profile connections are added, the recognized legacy
connection is removed, and existing reserved/duplicate Huyang exposure is disabled.
Normal chat and unrelated tools keep working. Fleet's existing OpenCode updater policy
is unchanged; a later release does not require a global version pin. Source implementation
is not evidence of runtime acceptance.

## Ownership and installation

Omarchy owns `config/opencode/plugins/huyang-profiles.js` and
`test/opencode-huyang.test.mjs`. Fleet carries byte-identical reviewed copies at
`roles/agent_config/files/opencode/huyang-profiles.js` and
`tests/opencode-huyang.test.mjs`. Update both sources together; never capture
an installed plugin back into either repository.

Only fleet's `agent_config` role installs this artifact, through
`tasks/opencode-huyang.yml`, at the exact path
`~/.config/opencode/plugins/huyang-profiles.js`. It refuses symlink components,
wrong file types and existing files without the exact managed marker. It changes
no OpenCode JSON, sibling plugins, provider settings, permissions or mise wrapper.
Omarchy's bootstrap and instruction generators do not install the plugin or become
MCP configuration owners. This source task deploys nothing.

## Connections and requests

The V2 default export registers an MCP transform and one request callback on
`context`, `compaction` and `generate`. It replaces only the managed legacy
connection named `huyang` with two direct connections:

- `huyang_lean`: `mcp --profile lean`, `codemode: false`.
- `huyang_full`: `mcp --profile full`, `codemode: false`.

A recognized local legacy entry supplies the executable, environment, cwd, timeouts,
protocol and other arguments. Its profile flag is replaced; explicit disablement is
preserved. Without a legacy entry, the executable policy remains
`$HOME/.local/share/huyang/bin/huyang`, resolved with Node's home-directory API.
No host-specific path, shell execution, credential discovery or environment logging
is added. Remote/wrapped legacy entries, unknown profiles, conflicting reserved names
and normalized namespace collisions withhold only Huyang. The recognized local legacy
entry is removed; other entries in Huyang's reserved/colliding namespaces and local
Huyang aliases are retained with runtime `disabled: true` and `codemode: false`.
Their command/URL, environment and other settings are preserved; no persistent JSON
is changed and somebody else's reserved-name connection is never deleted. Connections
outside this Huyang boundary are untouched. The transform catches validation failures:
throwing would disable V2's whole plugin group and remove its containment policy.

Only exact `event.model.providerID === "ollama"` selects lean; every other resolved
provider selects full. There are no endpoint, model-name or credential guesses.
Switches affect the next request, including continuations, without changing agents or
global MCP state. Concurrent sessions filter independent dictionaries. Transcript
content is not erased.

The filter deletes the wrong profile and preserves surviving definition-object
identity. It adds no permission-filtered tools and never falls back when the selected
connection is unavailable. With supported, valid configuration both connections stay
registered; selection controls the request surface, not process lifetime. Explicitly
disabled connections stay disabled.
A missing selected catalog leaves no Huyang tools on that request.

Registry metadata must prove managed tools are direct and have the expected effective
IDs. An invalid/missing model or managed-tool identity withholds Huyang definitions
without throwing from the request hook. ACP's late named `huyang` entry is handled by
transform replay. Duplicate/conflict containment latches only Huyang until owner
cleanup and plugin reload. Recognized Huyang aliases are disabled in the MCP projection
before catalog construction so they cannot enter shared Code Mode; the shared
`execute` tool is never removed as a shortcut. Unrelated definitions preserve their
identity, and requests with no Huyang tools continue normally. Missing selected catalogs
still never fall back to the other Huyang profile.

## Native names and permissions

The pinned MCP bridge normalizes characters other than letters, digits, underscore
and hyphen to underscores. Native names are the server namespace, one underscore and
the normalized advertised tool name. For advertised `read`, exact names are
**`huyang_lean_read`** and **`huyang_full_read`**. For `workspace_open`, names are
`huyang_lean_workspace_open` and `huyang_full_workspace_open` if advertised by those
profiles. These are not `mcp__huyang__read` names. The complete lean catalog is pending
Huyang's M7 implementation.

Permission actions use the same native IDs. Existing rules are never rewritten or
broadened; old exact `huyang_read` rules may need an owner-reviewed update. M3 canonical
correlation aliases require separate homelab-cli review for both server names; this
task does not edit homelab-cli. Claude/Codex stay explicitly on canonical `full`.
The one-release `edit` compatibility alias belongs to Huyang's core M7 change.

## Deferred checks and acceptance

No tests, builds or generation have run for this source task. Run checks only through
`chaldea exec --host agent-a` after the lead releases compute, using disk-backed
scratch and a disposable HOME.

- Omarchy: `node --test test/opencode-huyang.test.mjs`, also wired into its GitHub
  workflow. Regression coverage includes unsupported versions, tool-free chat,
  unrelated direct/Code Mode definitions, retained reserved-name records, and unavailable
  selections in both provider directions on every tool-bearing hook.
- Fleet: `python3 -m pytest -q tests/test_opencode_huyang.py`, then
  `bash tools/ci.sh` with its required scratch setup. The Python fixture invokes
  the identical Node suite against the role's copy.
- Verify the JSDoc interface against public `@opencode/plugin@2.0.30` and decode both
  connection configs with the actual `@opencode/schema@2.0.30` `Mcp.ServerConfig`
  codec in an isolated job. The synthetic editor is not schema proof.
- Once Huyang M7 exists, compare actual lean/full tool schemas and names through the
  pinned MCP bridge, tool snapshot and request preparation. Test wrong-profile
  execution rejection, unavailable selection, Code Mode exclusion and permissions.
  This real-schema integration is explicitly deferred; fixture catalogs are not a
  substitute.
- Verify global discovery and cleanup in the pinned binary, then interactive switches
  and ACP `session/set_config_option` model changes in both directions. Confirm T3's
  selected provider/model reaches the resolved request. Synthetic ACP fixtures model
  that boundary but do not test T3's transport.
- Every later Go test sets `HUYANG_FRICTION=0` inside its Chaldea job.

Primary references at the pinned commit:
[plugin interface](https://github.com/anomalyco/opencode/blob/f16ef9ad8878279ea2be3cfab7baeed97aef61aa/packages/plugin/src/promise/plugin.ts),
[MCP editor](https://github.com/anomalyco/opencode/blob/f16ef9ad8878279ea2be3cfab7baeed97aef61aa/packages/plugin/src/promise/mcp.ts),
[session hooks](https://github.com/anomalyco/opencode/blob/f16ef9ad8878279ea2be3cfab7baeed97aef61aa/packages/plugin/src/promise/session.ts),
[MCP naming](https://github.com/anomalyco/opencode/blob/f16ef9ad8878279ea2be3cfab7baeed97aef61aa/packages/core/src/tool/mcp.ts),
[definition identity](https://github.com/anomalyco/opencode/blob/f16ef9ad8878279ea2be3cfab7baeed97aef61aa/packages/core/src/session/model-request.ts),
[Code Mode and execution](https://github.com/anomalyco/opencode/blob/f16ef9ad8878279ea2be3cfab7baeed97aef61aa/packages/core/src/tool.ts),
[ACP](https://github.com/anomalyco/opencode/blob/f16ef9ad8878279ea2be3cfab7baeed97aef61aa/packages/cli/src/acp/sessions.ts).
