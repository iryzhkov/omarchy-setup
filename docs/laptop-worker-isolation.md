# Isolated laptop worker: disabled preparation and offline qualification

The opt-in helper stages private schema1 bootstrap and persistent-worker configuration,
a fixed bridge, a disabled service, an artifact-bound launcher and a disposable sandbox
qualifier. Ordinary setup only copies the helper; it never runs or activates it. There
are no autoloaded host/root assets. Source review, source publication, operator
installation, live qualification and enrollment remain separate decisions.

No-argument, help and plan are read-only. Use Python3 on the reviewed checkout:

```sh
python3 config/bin/t3-laptop-worker-setup
python3 config/bin/t3-laptop-worker-setup --help
```

The installed helper is self-contained. It needs no adjoining repository files.

## Private staging and reconciliation

Choose a unique operation ID, laptop identity and unused dedicated UID>=2000 from
request.example.json. Set the exact reviewed source commit and separately accepted
runtime artifact SHA256. Neither declaration establishes ACCEPT. The account is fixed
to t3-laptop-isolated; worker ID laptop-isolated. No credential values, auth paths,
secret hashes, arbitrary commands, mounts, endpoints or environment fields are accepted.
auth_mode chooses dedicated-login or protected-same-host-reference as a later parent
gate. Provisioning and real credential opening are outside this helper.

Creation and expiry are strict absolute UTC, no more than seven days apart, with
creation in the past and expiry in the future for staging. Replay cannot renew expiry.

Outputs must already exist, be owner0700 and outside home/runtime/system directories.
Inputs must be owner0600 regular files with one link, at most64KiB. Every directory
component is opened with no-follow and verified through its descriptor. Ancestor
owners must be root or the invoking UID; writable ancestors refuse except root-owned
sticky directories such as /tmp and /var/tmp. A foreign-owned0755 ancestor refuses.
Held descriptors anchor input reads, output inspection, locking, writes and fsync;
ancestor rename/symlink replacement cannot redirect operations to a new pathname.
Descriptors are CLOEXEC and closed on successful and failed operations. This does
not claim security against the invoking UID modifying its own file bytes concurrently.

```sh
python3 config/bin/t3-laptop-worker-setup stage \
  --request /var/tmp/laptop-request-OPID.json \
  --output /var/tmp/laptop-stage-OPID
python3 config/bin/t3-laptop-worker-setup inspect \
  --output /var/tmp/laptop-stage-OPID
```

Staging writes only the payload files and receipt.json, all0600. Files and the held
directory are fsynced; the receipt is the final durable commit marker. It binds all
nonsecret payload bytes, helper hash, stable operation ID and expiry. Identical replay
returns the same receipt without writes. Changed identities/bytes/modes, symlinks,
hardlinks, unknown files, incomplete crash output or a missing receipt refuse without
overwrite. Preserve partial evidence and use a separately reviewed new directory;
never blindly retry or delete. Advisory flock serializes cooperating invocations.

Lost stdout after receipt: inspect and replay the identical operation. A helper upgrade
invalidates its old tool-hash receipt, so retain the exact reviewed helper with its stage.
Retirement writes only retired.json and preserves all payload/receipt evidence:

```sh
python3 config/bin/t3-laptop-worker-setup retire-stage \
  --output /var/tmp/laptop-stage-OPID
```

retired-disabled is terminal: first/replayed retirement, inspection and assessment
retain it before and after expiry. A stage that expires without retirement reports
expired-disabled on inspection. Staging, assessment and fixture qualification cannot
revive an expired stage. Retirement changes no live runtime and claims no stopped
worker. There is no recursive deletion or live rollback.

## Concrete supported preparation

The generated files include:

- worker-bootstrap.json: strict schema1, sorted Git/Huyang capabilities, SSH
  transport and secretref:f02-protocol/laptop-isolated. The dedicated coordinator
  identity is laptop-coordinator and provider routes are empty until separately
  reviewed parent binding. No f03/admin credential is permitted.
- persistent-worker.yaml: supported policy.dry_run=true, backlog_v2.mode=disabled,
  private /worker/t3 data/token file and private /opt/runtime/t3 CLI. This prevents
  fallback to personal T3 discovery. It provisions neither token nor provider auth.
- preparation.json: exact source/artifact/operation/expiry binding, destination
  mapping under /var/lib/t3-laptop-isolated/OPID, separate0700 home/state/tools/T3/
  Huyang/control directories, private0600 files and parent root-owned control policy.
- worker-launcher.py and fixed-bridge: fixed worker serve --config and worker bridge
  commands, immutable disabled refusal and the actual Bubblewrap policy used by the
  qualifier. They never evaluate SSH_ORIGINAL_COMMAND or arbitrary command arguments.
- coordinator-worker.fragment.yaml: supported disabled coordinator worker fragment,
  accept_backlog=false, persistent-ssh and executors slots1/cpu_units4/memory_mb12288/
  scratch_mb20480. This is a parent merge fragment, not a complete config or enrollment.
- disabled.service: concrete launcher command, no Install section, Restart=no,
  ProtectHome/ProtectSystem/PrivateTmp/NoNewPrivileges, KillMode=control-group,
  CPUQuota400%, MemoryHigh10G/MemoryMax12G and TasksMax256.
- qualification-runtime.py: exact disposable local artifact exercising serve, bridge
  and a verification child, synthetic own-auth prerequisites and namespace denial.
- manifest.json, parent-gates.json and receipt.json: immutable redacted boundaries,
  remaining real gates and durable reconciliation evidence.

The supported command/schema map was inspected at Steward source
04ad0aa85ac63fcf51bf38d8f9aace5d2b15a19a: docs/worker-operations.md,
packaging/systemd/t3-steward-worker.service, internal/workerruntime/bootstrap.go,
internal/config/config.go (T3, V2Worker, V2Executors) and
internal/workerruntime/binding.go. This is source evidence, not proof of an accepted
ARM binary/version. No invented runtime concurrency, Huyang config or grant API exists.

The service always refuses live launch. Parent installation must separately prove
root-owned worker-unwritable controls, account/groups, tool ownership, supported
runtime/version and precise live isolation. Merely enabling this service cannot
clear any gate. Caps apply to the intended complete execution cgroup, including agents
AND verification/build/test descendants. Effective kernel limits and membership are
unproved; tmp2GiB is enforced in the qualifier's Bubblewrap tmpfs, while live
workspace/disk quotas and cgroup descendants remain explicit parent gates.

## Disposable production-path qualifier

qualify-fixture is the only subprocess-running mode. It uses an explicit private
disposable fixture and the exact shipped synthetic artifact SHA256 in the request,
rechecks the opened artifact and uses the generated launcher's policy. It does not
run any supplied provider, live runtime or credential command.

The fixture layout is documented by PackageTests.fixture in test/laptop-worker-isolation.py:
fixture.json binds kind/version/source/artifact; home/fixture-auth.json is fixed
nonsecret metadata; home/provider-auth.fixture and the private f02-protocol fixture
leaf contain fixed disposable markers. personal/ holds controlled sentinels/sockets.
These are test objects only. No real credentials, home, service or endpoint is allowed.
A request binding a real runtime artifact refuses this fixture lane; it cannot produce
a live receipt from that artifact.

```sh
python3 config/bin/t3-laptop-worker-setup qualify-fixture \
  --output /var/tmp/laptop-fixture-stage-OPID \
  --fixture /var/tmp/laptop-disposable-fixture-OPID
```

The policy uses Bubblewrap0.12.0, unshare-all (including network), clearenv,
die-with-parent/new-session, explicit held-FD mounts of private HOME and exact fixture
artifact, read-only public /usr,/lib,/lib64, isolated proc/dev and private tmp/state/
T3/Huyang. It never mounts host home/tmp/run wholesale. All supplied descriptors are
closed before the contained artifact runs; only the explicitly listed environment
survives. Own fixture socket bind/connect succeeds. Excluded personal sentinel
listing/read/write, agent/bus/T3/Huyang socket connection and inherited FD access fail.
The serve fixture holds a one-executor flock across its verification child and proves
a competing process refuses. This local guard test does not establish live runtime
catalog admission or coordinator stop behavior.

Exact artifact, mode, source binding, own fixture auth and capability failures refuse.
Missing bwrap/timeouts, unsupported version and a failed namespace probe have fixed
refusal codes. No fallback sandbox or declaration can yield success. Successful output
is offline-fixture-qualified with live_qualified=false and enrolled=false. The helper
writes no qualifier evidence into the stage; the caller retains redacted stdout.
Actual provider auth/refresh, ARM/kernel live behavior, endpoint network policy,
real assignment and effective live cgroup caps remain unqualified.

## Fresh capacity assessment and later parent gates

assess accepts gates.example.json only: matching host/UID/source/artifact/auth lane,
UTC observed_at within five minutes, CPU>=8, RAM available>=14GiB, free disk>=60GiB,
zero conflicting heavy executors, locked account, no supplementary groups, HOME0700.
Valid declarations return blocked/offline-declarations. They never authorize mutation
or prove capacity. Fake ACCEPT/auth/live-qualified fields refuse. A retired stage
returns its terminal receipt without opening gate input.

apply, activate, install, enroll, qualify-live, inactivate, rollback and bridge refuse
before opening any inputs. The parent later owns these separately reviewed operations:

1. Independently ACCEPT exact repaired source; bind the reviewed helper/payload and
   separately accepted ARM binary/version/hash with actual supported help.
2. Measure fresh capacity/platform/cgroup support and UID/account/group availability
   before every live mutation and again before activation. Keep the personal worker
   masked and personal services/state/results/workspaces untouched.
3. Use a manifest-scoped reversible installer; enforce root controls, locked dedicated
   UID/HOME, private tools/state/T3/Huyang and own f02 credential. No personal tools,
   forwarded agents/bus/sockets or f03/admin authorization.
4. Provision independent provider/repository authorization or prove a narrow protected
   same-laptop auth leaf/reference with least privilege and safe refresh/write behavior.
   No broad home mount, credential copying to another host, secret output or invented
   CredentialGrant lifecycle. Unavoidable interactive login stays an exact blocker.
5. Prove real daemon/bridge/provider-child sentinel denials and own-auth positive
   behavior; qualify network and own endpoints with controlled probes only.
6. Prove one executor through the accepted catalog AND fail-closed runtime guard;
   inspect actual cpu.max/memory.max and membership for agents AND verification,
   bounded pids/tmp/workspace and disk reserve.
7. Arm immutable<=7day absolute expiry and prove refusal/stop across boot, outage,
   bridge and retry without renewal. Collect real assignment/drain/stop acknowledgement.
8. Only then perform separately fenced coordinator-local enrollment and a narrow
   declared assignment smoke with real receipts. No fleet capture/publication here.

Source acceptance cannot substitute for any live gate. Unknown live drain/de-enrollment,
network, contained real provider preparation/verification/output custody and confirmed
stop integration remain precise blockers in the mapped runtime source. Rollback must
close new assignment/bridge, obtain stop acknowledgement, reverse only recorded managed
changes after identity checks and preserve HOME/journals/evidence.

## Verification

The isolation suite preserves existing checks and adds real descriptor/ancestor attacks,
exact terminal lifecycle assertions, generated-wrapper execution, artifact-bound local
Bubblewrap serve/bridge/verification, own fixture auth positive/missing cases, socket/
sentinel denials, competing executor guard and unsupported capability refusal.
test/run.sh integrates it. Owning full ShellCheck/module/instruction-generation checks
remain required. Offline tests never report live qualification or enrollment readiness.
