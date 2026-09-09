# T3 Code and t3-steward

How T3 Code and its quota steward are installed on these machines, why the two
versions are pinned together, and what to do on each host to bring it under
`omarchy-setup`.

## What was there before

On gaming-pc, and by extension on the other three hosts, T3 was installed by
hand and tracked by nothing:

- `t3` was a global npm package inside mise's node
  (`~/.local/share/mise/installs/node/26.7.0/lib/node_modules/t3`), installed
  with `npm install -g t3`. Because the package lives inside a specific node
  install, bumping the pinned node version would have lost it.
- `t3-steward` was a release binary copied to `~/.local/bin/t3-steward`, with
  `t3-backlog` symlinked out of the `homelab-cli` checkout.
- Both services (`t3code.service`, `t3-steward.service`) were user units
  written by hand or by `t3-steward install-service`.

Nothing updated any of it. Neither `mup` nor `omarchy update` touched T3:
`mup` is `MISE_MINIMUM_RELEASE_AGE=0 mise up`, `omarchy update` runs the same
command through `omarchy-update-mise`, and both only act on tools declared in
`~/.config/mise/config.toml`. T3 was not declared there, so it sat at 0.0.38
while npm offered 0.0.40.

## Why it is not a mise tool

The obvious fix was to declare `npm:t3` in `config/mise-tools.txt` and let
mise's npm backend own it. mise refuses to install it:

```
trust downgrade for @pierre/theme@1.1.0 (trustPolicy=no-downgrade):
earlier published version 0.0.20 had provenance attestation but this
version has no trust evidence
```

That is a real finding, not a quirk of the backend. `@pierre/theme` published
SLSA provenance through 1.0.3 and stopped: 1.1.0 and 2.0.0 carry none. The
publisher of 1.1.0, `amadeusdemarzi`, is a listed maintainer of the package,
and two consecutive releases losing provenance looks like a publishing workflow
that stopped attesting rather than a hijacked release. It is worth knowing that
version 1.1.0 is *already* installed on every host in this fleet: it arrived
with `npm install -g t3`, and npm performs no such check.

Getting past it would mean recording, in mise's config, a
`trust_policy_excludes` entry naming the package whose provenance disappeared.
That is a supply-chain exception, and burying one in a config file that
`omarchy update` re-applies on four machines is worse than leaving the install
where it already was. So T3 stays an npm global, and `modules/common/26-t3.sh`
owns it instead.

## Why both versions are pinned

`t3-steward` is written against T3's control protocol and log formats, which
are internal and undocumented. Its README says so plainly, and the binary
enforces it: outside the T3 version range it was built against, the steward
**refuses to warn, stop or resume**. It reports the range itself:

```
$ t3-steward version
t3-steward 0.10.1 (commit 81f1965..., tested with T3 0.0.38..0.0.38)

$ t3-steward check
ok    T3 server 0.0.38 (omarchy-pc, linux/x64): supported
```

So letting `mise up` float T3 to 0.0.40 — the change this work originally set
out to make — would have quietly disabled the quota watchdog on every host.
That is why `config/t3.conf` pins both versions and why they move together.

## What was added

| File | Role |
|------|------|
| `config/t3.conf` | the pinned pair: `T3_VERSION`, `T3_STEWARD_VERSION`, the steward repo, and the bind address used only when seeding a new `t3code.service` |
| `modules/common/26-t3.sh` | installs the pinned T3 with npm, installs the pinned steward from its GitHub release, and handles the two user units |

The module is idempotent and runs on both profiles. It sits at 26 so that
mise (25) has installed node before npm is needed.

What it does on each run:

1. Compares `npm ls -g t3` against `T3_VERSION`; on a mismatch runs
   `npm install -g t3@<version>` and then `mise reshim`, because
   `t3code.service` starts T3 through the mise shim.
2. Compares `t3-steward version` against `T3_STEWARD_VERSION`; on a mismatch
   downloads `t3-steward_<version>_linux_<arch>.tar.gz` and `checksums.txt`
   from the GitHub release, confirms the archive is listed in `checksums.txt`,
   verifies its SHA-256, extracts it and installs it 0755 into
   `~/.local/bin`. A checksum failure aborts without installing anything.
   Verified against the running binary: the 0.10.1 release archive extracts to
   a file byte-identical to the one already deployed.
3. Restarts `t3-steward.service` if the steward changed, or runs
   `t3-steward install-service` if the unit does not exist yet.
4. Seeds `t3code.service` **only if it is absent**, then enables and starts it.
   An existing unit is never rewritten: a host may have tuned its bind address,
   its `PATH`, or the credential files it reads, and none of that is
   recoverable from this repo.
5. Never restarts `t3code.service` on its own. The server keeps every running
   agent thread in its own process, so a restart kills work in progress. When
   T3 was upgraded the module says a restart is due and leaves the moment to
   you.

`omarchy update` reaches all of this through the existing post-update hook
(`config/hooks/post-update.d/omarchy-setup.hook`), which pulls this repo and
re-runs `run.sh --yes --skip-secrets`. So an update re-asserts the pinned pair
instead of drifting, which is the behaviour that was missing.

## Replicating it on the other hosts

The other three hosts (laptop, normandy, homelab) already run T3 and the
steward, so this is an adoption, not an install. On each host:

```bash
cd ~/.local/share/omarchy-setup
git pull --ff-only
OMARCHY_SETUP_LIB=$PWD/lib DRY_RUN=1 bash modules/common/26-t3.sh
```

Read the dry run before the real one. On a host that already matches the pinned
pair it prints four `info` lines and changes nothing:

```
info   t3 0.0.38 already installed
info   t3-steward 0.10.1 already installed
info   t3-steward.service present
info   t3code.service present, left alone
ok     T3 Code and steward ready
```

If a host reports a different T3 version, decide before running for real. The
module will install the pinned version, which may be a *downgrade* on that
host, and the running server keeps serving the old code until someone restarts
it. Check what the steward there supports first with `t3-steward check`.

Then run it for real, either directly or through the orchestrator:

```bash
./run.sh --yes --skip-secrets --only 26-t3
```

Nothing else is needed: `run.sh` picks the module up automatically from
`modules/common/`, and the post-update hook already runs `run.sh` on every
`omarchy update`.

A host that has never run T3 gets the full path instead — npm install, steward
download, a seeded `t3code.service`, and `t3-steward install-service`. It will
also need `~/.config/claude/oauth.env` (provider credentials, per-host, never
in this repo) and `~/.config/t3-steward/config.yaml`, which
`t3-steward init` writes as a commented template. The module warns if the
credential file is missing rather than failing.

## Upgrading the pair

Order matters, because the steward is the constraint:

1. Look at the [t3-steward releases](https://github.com/iryzhkov/t3-steward/releases)
   and find one whose compatibility table lists the T3 version you want.
   `t3-steward version` prints the range a given binary was built against.
2. Set both `T3_VERSION` and `T3_STEWARD_VERSION` in `config/t3.conf`, commit,
   push.
3. On each host: `git pull` and run the module. It installs both and restarts
   the steward.
4. Restart `t3code.service` on each host at a moment when no agent thread is
   running — check with `t3-steward status` or the T3 UI. This is the only
   disruptive step, and it is deliberately manual.
5. Confirm with `t3-steward check`: the T3 server line must say `supported`.

If no steward release supports the T3 version you want, the answer is to wait
for one, not to upgrade T3 and lose the watchdog.

## Loose end worth a look

`t3code.service` on gaming-pc carries a comment saying the server is bound to
the machine's Nebula address "and nowhere else", and that "the host firewall
allows the mesh interface". Neither is what the machine does. `ExecStart` uses
`--host 0.0.0.0`, which binds every interface, and the ufw rule that keeps the
port reachable is

```
7391/tcp   ALLOW   192.168.20.0/24   # t3code from Traefik VLAN 20
```

so access is scoped by a VLAN allow-list, not by the bind address and not by
Nebula. The behaviour is defensible; the comment describing it is wrong, which
is the kind of thing that misleads exactly when someone is debugging. The
seeded unit
this module writes takes its bind address from `T3_BIND` in `config/t3.conf`,
currently `0.0.0.0` to match what the hosts really run; narrowing it to the
mesh address is a separate decision, and the existing units are not touched
either way.
