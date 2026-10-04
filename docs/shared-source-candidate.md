# Pending UpKeeper shared-source candidate

S1a prepares shared/agent-instructions in UpKeeper from this repository at
c6f58c421053690cff9ef1de04bc544cbb1fe720. It is inert and no active release
selects it. agent-instruction-ownership.md remains the supported legacy contract
until independent acceptance and transactional cutover. Keep all legacy sources.

Source publication retains generator install/check defaults, module 31, module 28
distribution and post-update behavior. run.sh and its hook do not select the scratch
command. The instruction suite covers these old paths; homelab-cli independently tests
legacy sync and local installer through disposable homes and stub transport.
Mixing old/new source candidates introduces no activation route in this preparation.
Lead source-order/mixed-version acceptance is still required before publication.

Future SAME-ACTIVATION must fence every destination writer before candidate bytes become
observable, including historical copied generators, delayed writes and rollback binaries.
Unknown writer reachability refuses activation. A marker or sender-side check is not
authority. The destination lock spans validation through final file/import write.
Pending/corrupt/interrupted generation refuses writes. Read-only help/check remains useful.
Activation, interrupted recovery, rollback and racing writers remain blocking tests.

nvim a8c430ac52f0502034f37d68f5b74594290cd624 already removed agent99.
Editor-owner reconciliation is a BLOCKING complete-S1 preservation criterion,
not a passed plugin test. Module 40, theme bridge and dependencies remain untouched.
