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
That is why the two versions only ever move together, and why the automatic
update described below asks a candidate steward binary what it supports before
it touches T3.

## What was added

| File | Role |
|------|------|
| `config/t3.conf` | the declared pair: `T3_VERSION`, `T3_STEWARD_VERSION`, the steward repo, the auto-update switches, and the bind address used only when seeding a new `t3code.service` |
| `lib/t3.sh` | version comparison, the tested-range parser, the npm and GitHub lookups, and the parsers for `t3-steward check` output. Kept separate so `test/run.sh` can exercise the decision logic with no network |
| `modules/common/26-t3.sh` | resolves the newest compatible pair, installs T3 with npm and the steward from its GitHub release, handles the two user units, and restarts T3 when it is idle |

The module is idempotent and runs on both profiles. It sits at 26 so that
mise (25) has installed node before npm is needed.

What it does on each run:

0. Resolves the pair, unless `T3_AUTO_UPDATE=0`. See "Following upstream"
   below; the result raises `T3_VERSION` and `T3_STEWARD_VERSION` for the rest
   of the run and is recorded in
   `~/.local/state/omarchy-setup/t3-versions.conf`.
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
5. Restarts `t3code.service` only when it is safe to. The server keeps every
   running agent thread in its own process, so a restart kills work in
   progress — possibly the thread of the agent that started the update. The
   module asks `t3-steward check` for the version the server is actually
   serving and for the number of running threads, and restarts only when the
   served version is behind *and* that number is zero. Otherwise it says which
   version is pending and defers to the next run, which is why nothing is lost
   by the host being busy every time. `T3_RESTART_WHEN_IDLE=0` turns the
   restart back into a message.

`omarchy update` reaches all of this through the existing post-update hook
(`config/hooks/post-update.d/omarchy-setup.hook`), which pulls this repo and
re-runs `run.sh --yes --skip-secrets`. So an update re-asserts the pinned pair
instead of drifting, which is the behaviour that was missing.

## Following upstream

The original version of this module kept the pair *pinned*: correct, but it
meant the fleet stayed on whatever versions were last typed into
`config/t3.conf`, which is the same problem in slower motion. `T3_AUTO_UPDATE`
(on by default) makes the module resolve the pair itself, on every run and so
on every `omarchy update` — one step before `omarchy-update-mise` updates the
tools mise does own.

The resolution never consults a table a human maintains:

1. `t3_github_releases` lists the steward's release tags. Prereleases are
   included while `T3_STEWARD_PRERELEASES=1`, because this fleet runs them
   deliberately — the steward is ours and its fixes land there first.
2. If the newest tag is above the current version, the archive is downloaded
   and checksum-verified exactly as an install would, and the extracted binary
   is asked what it supports: `t3-steward version` ends with
   `tested with T3 <min>..<max>`. That is the same range its control actions
   refuse to act outside of, so the candidate answers for itself. A steward too
   old to print a range yields nothing, and nothing then moves.
3. The newest npm `t3` inside that range is the candidate T3. Prereleases on
   npm are never picked.
4. The pair is taken only if it moves *forward*. A steward whose range would
   step T3 back, or for which npm has no version at all, is refused and both
   versions stay where they are — losing the watchdog is worse than running a
   version behind.

Today, on gaming-pc, that produces:

```
info   t3 0.0.38 with t3-steward 0.10.1 is the newest compatible pair
```

npm has `t3` 0.0.40, but steward 0.10.1 is tested with `0.0.38..0.0.38`, so the
module holds. That is the whole point of the gate: the version that looks
newest is not the version this fleet can run.

### Where the resolved versions live

Not in `config/t3.conf`. The post-update hook does `git pull --ff-only` before
re-running `run.sh`, so the checkout has to stay clean, and four hosts
committing to the same file would collide. Each host writes what it installed
to `~/.local/state/omarchy-setup/t3-versions.conf`:

```
T3_BASE_VERSION=0.0.38
T3_BASE_STEWARD_VERSION=0.10.1
T3_LOCAL_VERSION=0.0.38
T3_LOCAL_STEWARD_VERSION=0.10.1
```

`T3_BASE_*` records the `config/t3.conf` values the resolution started from.
On the next run, the effective version is the higher of the repo value and the
local one — but only while the bases still match. Editing `config/t3.conf`
therefore wins in both directions: raise it for a fleet-wide bump, lower it to
roll a host back, and the local record is discarded rather than fighting it.

## Replicating it on the other hosts

The other three hosts (laptop, normandy, homelab) already run T3 and the
steward, so this is an adoption, not an install. On each host:

```bash
cd ~/.local/share/omarchy-setup
git pull --ff-only
OMARCHY_SETUP_LIB=$PWD/lib DRY_RUN=1 bash modules/common/26-t3.sh
```

Read the dry run before the real one. On a host that is already on the newest
compatible pair it changes nothing:

```
info   t3 0.0.38 with t3-steward 0.10.1 is the newest compatible pair
info   t3 0.0.38 already installed
info   t3-steward 0.10.1 already installed
info   t3-steward.service present
info   t3code.service present, left alone
info   t3code is serving 0.0.38
ok     T3 Code and steward ready
```

The dry run resolves versions for real — it queries GitHub and npm and may
download a steward archive to a temporary directory — so what it reports is the
pair the real run would install. It writes nothing.

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

## homelab, which has no Omarchy

homelab is Debian 12. `run.sh` refuses to start there — it requires Omarchy for
`omarchy pkg`, the hook directories and the theme commands — and there is no
`omarchy update`, so the post-update hook that carries the module on every
other host can never fire. The module itself needs none of that: `npm`, `curl`,
`jq` and the steward binary are its whole dependency list.

`bin/t3-update` is the entry point for that case. It pulls the checkout (a
failed pull is a note, not a stop: a host that cannot reach the remote should
still run the module it has) and execs `modules/common/26-t3.sh` directly. It
works on any host, and is the convenient way to ask for the check by hand.

The trigger is homelab's own convention — a user timer, like
`homelab-drift-check.timer` and the backup units next to it. Both units are
tracked here, under `hosts/homelab/systemd/user/`, and installed by hand
because the module that would install them (`29-host-files`) rides on the same
`run.sh` that cannot run there:

```bash
ssh homelab
cd ~/.local/share/omarchy-setup && git pull --ff-only
install -Dm644 hosts/homelab/systemd/user/t3-update.service \
  ~/.config/systemd/user/t3-update.service
install -Dm644 hosts/homelab/systemd/user/t3-update.timer \
  ~/.config/systemd/user/t3-update.timer
systemctl --user daemon-reload
systemctl --user enable --now t3-update.timer
systemctl --user start t3-update.service   # once, to see it work
journalctl --user -u t3-update -n 20 --no-pager
```

It runs daily at 09:15 with a 20-minute jitter, after the overnight backups and
the 08:30 drift check. `Persistent=true` so a reboot does not skip a day. The
units are `%h`-relative, so nothing in them is specific to that host beyond the
choice of hour — a second non-Omarchy host can take the same pair.

Editing either unit later means copying it across again; there is no installer
on that host to do it.

## Upgrading the pair

Normally nobody does: the module resolves the newest compatible pair on every
`omarchy update` and installs it, and restarts T3 the first time it finds the
host idle. `t3-steward check` is how you confirm it — the T3 server line must
say `supported`.

Three cases still need a person:

- **Forcing a specific pair across the fleet.** Set both `T3_VERSION` and
  `T3_STEWARD_VERSION` in `config/t3.conf`, commit, push. Every host takes the
  new values on its next run and drops whatever it had resolved locally. This
  is also how a **rollback** works: a lower value in `config/t3.conf` wins, and
  the auto-update will not climb back past it until upstream offers a pair that
  is genuinely newer than the values recorded there.
- **A host that must not move.** `T3_AUTO_UPDATE=0`, and it stays on the
  declared pair.
- **A restart that keeps being deferred.** A host with a thread running around
  the clock never hits the idle window; the module says which version is
  pending on every run. Restart it yourself when convenient:
  `systemctl --user restart t3code`.

If no steward release supports the T3 version you want, the answer is to wait
for one, not to upgrade T3 and lose the watchdog — which is exactly what the
module does on its own.

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
