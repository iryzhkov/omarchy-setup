# Isolated laptop worker: disabled operator package v1

This opt-in tool stages a nonsecret, inert qualification package. It does **not**
install or activate a worker. Source acceptance approves this limited package;
it cannot establish live qualification, enrollment or a usable active worker.
Ordinary setup may copy the standalone helper through 28-scripts, but never runs
it. There are no automatic module changes or host/root assets.

Use Python 3 on the reviewed checkout:
```sh
python3 config/bin/t3-laptop-worker-setup
python3 config/bin/t3-laptop-worker-setup --help
```
Both are read-only. Installed copies also work without adjoining assets.

## Staging and integrity

Prepare a nonsecret request from config/t3-laptop-isolation/request.example.json.
Replace the example source commit and runtime artifact SHA with the independently
reviewed source and separately accepted nonsecret binary identity. These are
**declared identities**, not a verified ACCEPT or artifact signature. Choose a
unique operation ID, exact laptop host, unused dedicated UID >=2000, and absolute
UTC creation/expiry timestamps. The creation time must be in the past and expiry
in the future, no more than seven days after creation. Expiry is immutable on
replay. Do not put keys, credential values, secret-file hashes or auth paths in
this JSON. The account name is fixed; the worker ID is laptop-isolated.

The strict v1 field set is in request.schema.json and independently enforced by
the tool, including duplicate-key refusal. It has no arbitrary command, mount,
path, endpoint or environment fields. auth_mode selects a parent qualification
lane only: dedicated-login or protected-same-host-reference. It neither opens nor
provisions authentication. The same-host lane requires a proved narrow protected
private leaf/reference and safe refresh/write behavior; broad Igor home access
and copying auth to another host remain disallowed.

Only explicit existing directories owned by the invoking operator, mode0700, are
accepted. Requests must be owned regular mode0600 files with one link. Absolute
canonical paths are required; symlink ancestors, world/group-writable nonsticky
parents, input/output overlap and home/runtime/system directories are refused.
For example, after parent approval to stage files (these are offline operations):
```sh
umask 077
mkdir -m 700 /var/tmp/laptop-isolation-review-OPID
# Write reviewed request to /var/tmp/laptop-isolation-request-OPID.json; chmod 600.
python3 config/bin/t3-laptop-worker-setup stage \
  --request /var/tmp/laptop-isolation-request-OPID.json \
  --output /var/tmp/laptop-isolation-review-OPID
python3 config/bin/t3-laptop-worker-setup inspect \
  --output /var/tmp/laptop-isolation-review-OPID
```

Stage writes only manifest.json, disabled.service, parent-gates.json and
receipt.json in that directory, all0600. The receipt is the durable commit marker;
files and directory are fsynced. It records exact nonsecret payload hashes and
tool hash, immutable operation/expiry, and zero live changes. Identical replay
returns the same receipt without writes. Different identity, modified bytes,
permissions, hardlinks, foreign files or missing receipt refuse without overwrite.
Directory advisory locking serializes cooperating tool calls. This is an offline
operator-owned package, not a privileged installer secure against the invoking
UID replacing its own paths concurrently.

Crash before receipt: preserve that directory unchanged as incomplete evidence,
inspect the failure, and use a separately reviewed new operation/directory.
Never delete or retry partial output blindly. Lost stdout after receipt: inspect
and replay the same request; do not renew its expiry. Tool upgrades invalidate
the tool-hash receipt; preserve the old accepted tool with its package.

Inspect checks exact bytes and receipt schema, even after expiry; an expired
stage reports expired-disabled. This is a metadata deadline, **not a working
runtime expiry mechanism**. A live expiry implementation is an explicit blocker.

## Offline prerequisite assessment

Use gates.example.json with fresh declarations, matching request identities and
auth lane. The exact field set is enforced. observed_at must be UTC, at most five
minutes old and not future. Minimums: 8 logical CPUs, available RAM14GiB, free disk
60GiB, zero conflicting heavy executors, locked dedicated account, no supplementary
groups, HOME0700. In an eventual live implementation the parent must independently
measure these immediately before **every mutation** and again before activation;
stale audit data and this JSON are not proof.
```sh
python3 config/bin/t3-laptop-worker-setup assess \
  --output /var/tmp/laptop-isolation-review-OPID \
  --gates /var/tmp/laptop-isolation-gates-OPID.json
```
Valid declarations yield blocked/offline-declarations, never qualified.
Malformed, stale, unsafe or mismatched declarations refuse, with fixed diagnostic
codes and no input echo. Arbitrary ACCEPT, auth or live-qualified fields refuse.

The manifest fixes intended caps: one executor, CPUQuota400%, MemoryHigh10GiB,
MemoryMax12GiB, TasksMax256, tmp2GiB, workspace20GiB, disk reserve60GiB.
disabled.service demonstrates cgroup hardening directives but executes only
/usr/bin/false, has no Install section, no supported worker command and no auth
or mount bindings. It must never be installed as an active worker. Its directives
are not kernel proof, tmp/workspace quotas, admission control or bridge isolation.

## Unsupported live stages and parent qualification

apply, activate, inactivate, rollback and bridge unconditionally return exit2
with unsupported-live-STAGE before opening inputs. SSH_ORIGINAL_COMMAND is never
evaluated; no forwarding, socket, runner or arbitrary shell interface exists.
No credential contents, probes or environment values are emitted. This tool
does not supply a live backend or accept one from JSON.

The verified mechanism map points to Steward's private schema1 bootstrap,
f02-protocol credential reference, persistent-worker.yaml, fixed worker bridge
and contained provider execution. It is not proof that a separately accepted
ARM binary supports a daemon/bridge sandbox, all assignment paths, narrow auth
refresh, single-executor guard, offline reboot-safe expiry or drain/stop
acknowledgement. No guessed CLI or fabricated CredentialGrant API is supplied.

Parent operations, in order, before any live mutation:
1. Independently ACCEPT the exact source commit; verify accepted tool/payload
   hashes and separately accepted runtime binary/version/hash and actual command
   help. Resolve the blocked command compatibility seam.
2. Measure fresh capacity, account/UID/group availability, platform/cgroup support,
   no conflicting operation and no existing second heavy executor. Keep Igor's
   personal services, masked worker, state, results and workspaces untouched.
3. Prepare a separately reviewed exact runtime installer and rollback manifest.
   Runtime roots must be dedicated under /var/lib/t3-laptop-isolated/OPID, root
   control assets outside worker-writable paths, private account HOME0700, own
   T3/Huyang endpoints, own f02 credential0600 (never f03), private bootstrap and
   config0600. Do not symlink/bind Igor-installed tools or inherit agents/user bus.
4. Parent provisions independent dedicated provider/repository authorization OR
   proves a least-privilege protected same-laptop private auth reference/leaf,
   including refresh/write behavior. If login actually needs Igor interactively,
   record that precise blocker and keep disabled. Do not invent a grant service.
5. Prove daemon, fixed bridge and actual provider child cannot list/read/write a
   controlled sentinel under Igor's root or reach personal agent, bus, T3/Huyang.
   Prove no whole /home, host /tmp or /run bind and selected off-allowlist access
   fails. Use sentinels only, not Igor data.
6. Prove capped cgroup membership/effective cpu.max/memory.max for wrappers,
   agents AND verification/build/test descendants; bound pids/tmp/workspace;
   prove catalog admission and failclosed runtime single-executor guard.
7. Before activation arm <=7day absolute expiry with stable op ID. Prove bridge
   refusal and worker stop across reboot/network outage without deadline renewal;
   collect actual assignment/drain/stop acknowledgements. No journal deletion.
8. Only after all preceding gates, parent performs separately reviewed
   coordinator-local fenced enrollment and a narrow declared real assignment
   smoke; collect real receipt. This tool has no enrollment operation.

These are required operations, not executable commands: an exact live command
sequence cannot honestly be provided until the accepted runtime's unsupported
interfaces are resolved and independently reviewed. No live installer is shipped
or promised by this v1 source package. The parent must not improvise broad mounts
or enable disabled.service to clear blockers. Kernel/ARM/network/provider/bridge,
expiry/drain and assignment qualification remain unperformed.

## Retirement and rollback boundary

```sh
python3 config/bin/t3-laptop-worker-setup retire-stage \
  --output /var/tmp/laptop-isolation-review-OPID
```
This writes only retired.json; it preserves every payload/receipt and performs
zero live reversal. Repetition is idempotent; retired stages cannot be assessed
or restaged. No recursive delete exists. The manifest has managed_live_paths=[]
because no live changes were made. It cannot authorize removal of an account,
HOME, source, evidence, services or any unrelated files.

Eventual parent live rollback must first stop new assignment and close bridge
access, collect drain/stop acknowledgement, then reverse only recorded managed
isolated-account/unit/config changes after checking before/after identities.
Preserve account HOME, journals and evidence; never recursively remove roots.
Unknown stop/de-enrollment semantics remain blockers, not a stopped claim.

## Verification

test/laptop-worker-isolation.py tests production staging, integrity, replay,
crash refusal, lifecycle metadata, private paths, strict identities, capacity and
account decisions, refusal of live modes/forged gates, and personal-fixture
preservation. test/run.sh integrates the suite; the owning shellcheck and
instruction-generation checks remain intact. Fixture success does not prove
actual kernel, ARM, provider, socket, expiry or bridge behavior.
