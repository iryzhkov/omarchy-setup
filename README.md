# omarchy-setup

Post-install setup for a fresh [Omarchy](https://omarchy.org) machine.

## End-to-end run on a fresh machine

See exactly what it would do, changing nothing:

```bash
curl -fsSL https://raw.githubusercontent.com/iryzhkov/omarchy-setup/main/install.sh \
  | bash -s -- --profile client --dry-run
```

Then do it for real:

```bash
curl -fsSL https://raw.githubusercontent.com/iryzhkov/omarchy-setup/main/install.sh \
  | bash -s -- --profile client
```

Use `--profile remote` for a headless box. The `-s --` is required: it is how
arguments reach the script when bash is reading it from a pipe.

`install.sh` only bootstraps -- it verifies this is Omarchy, installs git,
shallow-clones this repo to `~/.local/share/omarchy-setup`, runs it, and then
**removes the clone again**, so a fresh machine is left configured with no build
litter. All real logic lives in the repo, where it is reviewable and testable.

What survives a run:

| Path | Why |
|------|-----|
| `~/.local/state/omarchy-setup/profile` | remembered profile, so re-runs need no flags |
| `~/.local/state/omarchy-setup/last-run.log` | log of the last run |
| `~/.config/nvim` | your live config checkout, deliberately kept as a git repo |

Set `OMARCHY_SETUP_KEEP=1` to keep the clone for iterating. A checkout that was
already at `~/.local/share/omarchy-setup` before the run is treated as yours and
never deleted.

## Configuring / forking

Every personal value lives in one file, `config/defaults.conf`, and each can be
overridden without editing anything:

| Value | Flag | Default |
|-------|------|---------|
| GitHub account | `--github-user` | `iryzhkov` |
| git user.name | `--git-name` | `Igor Ryzhkov` |
| git user.email | `--git-email` | `igor.o.ryzhkov@gmail.com` |
| Bitwarden server | `--bw-server` | `https://vault.ryzhkov.dev` |
| Neovim config repo | `--nvim-repo` | derived from the GitHub account |
| Omarchy theme | `--theme` | `kanagawa` |

Precedence is **flag > environment variable > `config/defaults.conf`**:

```bash
./run.sh --github-user octocat --git-email mona@example.com
GITHUB_USER=octocat ./run.sh
BW_SERVER= ./run.sh          # empty = the official Bitwarden cloud
```

The repo URLs derive from the account name, so a fork changes one value and the
SSH keys, the Neovim repo, and `install.sh`'s own clone URL all follow. For the
bootstrap itself, set `OMARCHY_SETUP_GH_USER` (or `OMARCHY_SETUP_REPO`):

```bash
curl -fsSL https://raw.githubusercontent.com/<you>/omarchy-setup/main/install.sh \
  | OMARCHY_SETUP_GH_USER=<you> bash -s -- --profile client
```

Nothing secret belongs in `defaults.conf` — addresses and usernames only.

## Profiles

| Profile  | For                                          |
|----------|----------------------------------------------|
| `client` | a workstation you sit at — GUI, theming, secrets |
| `remote` | a headless box reached over ssh — sshd, no vault access |

Chosen on first run and remembered in `~/.local/state/omarchy-setup/profile`.

```bash
./run.sh --profile client      # first run
./run.sh                       # subsequent runs
./run.sh --list                # what would run
./run.sh --dry-run             # show every change, apply none
./run.sh --only hypr --dry-run # one module
```

## Layout

```
install.sh              bootstrap (curl | bash target)
run.sh                  orchestrator: profile, ordering, logging
lib/common.sh           logging, dry-run, managed blocks, package helpers
modules/
  common/               runs on every machine
  client/               GUI machines only
  remote/               headless machines only
packages/
  common|client|remote/ one script per package, run by 20-packages-install
config/hypr/*.lua       shared Hyprland config (real .lua, edit directly)
hosts/<hostname>/       per-machine overrides, layered on top of config/
```

Modules from `common/` and the active profile are merged and ordered by their
numeric prefix, so `35-sshd` (remote) slots between the shared `30-` and `40-`.

## Running over ssh

Setting up a workstation from another machine works, and is how this repo is
tested:

```bash
ssh <host> 'curl -fsSL https://raw.githubusercontent.com/iryzhkov/omarchy-setup/main/install.sh | bash -s -- --profile client'
```

Three things differ from running it at the machine, and each is handled:

- **`OMARCHY_PATH` is not set.** `ssh host 'cmd'` runs a non-login,
  non-interactive shell, which sources neither `/etc/profile.d/omarchy.sh` nor
  `~/.bashrc`. Without that variable Omarchy's own commands break in confusing
  ways: `omarchy theme list` looks in `/themes/` and reports every theme as
  nonexistent, so `omarchy theme set kanagawa` answers "Theme 'kanagawa' does
  not exist", and `omarchy plugin` refuses to run at all. `lib/common.sh`
  sources Omarchy's `default/bash/env-bootstrap`, which is its declared single
  source of truth for `OMARCHY_PATH` and for the `PATH` entries that make the
  mise shims findable.
- **Hyprland is running but unaddressable.** There is no
  `HYPRLAND_INSTANCE_SIGNATURE` over ssh, so a plain `hyprctl reload` does
  nothing. `hypr_reload` reads `hyprctl instances` instead and reloads the one
  running session by name, so a remote run takes effect immediately rather than
  at the next login. With no session, or more than one, it does nothing.
- **There is no terminal.** Secrets are skipped automatically (see below), and
  a module failure cannot be confirmed interactively -- so an unattended run
  continues through the remaining modules and names every failure at the end,
  rather than stopping at the first one and hiding the rest.

## Managed blocks

Omarchy's own migrations rewrite files under `~/.config/hypr/` on
`omarchy update`, so this repo never replaces those files. It appends a fenced
block and owns only what is inside the fence:

```lua
-- >>> omarchy-setup:looknfeel >>>
hl.config({ decoration = { rounding = 0 } })
-- <<< omarchy-setup:looknfeel <<<
```

Re-running rewrites only between the fences and skips the write entirely when
nothing changed. The pristine file is backed up once, the first time it is
touched. (The pattern is borrowed from the block Omaland already writes into
`looknfeel.lua`.)

For settings Omarchy declares as a `local` near the top of a file — monitor
scale, GDK scale — a trailing block cannot reassign the variable, so re-call
the setter instead. `hl.monitor()` and `hl.env()` are last-wins.

## Agent CLIs and dev tools

`claude`, `codex`, `agy` (antigravity-cli), `pi`, `opencode`, `crush` are **not
packages** -- they are mise tools under `~/.local/share/mise/installs`. They
live in `config/mise-tools.txt` and are applied by `modules/common/25-mise.sh`
with `mise use --global`, which lets mise edit its own TOML rather than this
repo hand-editing it.

Both profiles get them: a remote is often exactly where you want an agent
running.

## Packages

**Check before adding anything to `packages/`** -- Omarchy's base install is
large, and most of what a setup script reaches for is already there:

```bash
bin/preinstalled neovim git herdr ripgrep
```

Do not just grep the base list: it records some packages by what they
*provide*. The entry is `nvim`, satisfied by the `neovim` package, so a plain
`grep -w neovim` wrongly reports it missing. `bin/preinstalled` resolves
provides.

`nvim`/`neovim`, `git`, `mise-bin`, `herdr`, `ripgrep`, `fd`, `lazygit`, `tmux`
and `obsidian` are all base packages; re-installing them is noise. Modules that
depend on one use `ensure_cmd`, silent when present. What remains is genuinely
absent software (Brave, via Omarchy's own `omarchy install browser brave`, which
picks the right build per platform) or real post-install configuration.

## Neovim

`~/.config/nvim` is a checkout of `NVIM_REPO` (`--nvim-repo`), deliberately left
as a git repo so it stays yours to edit and push.

**x86 and aarch64 start from different places.** On x86 the `omarchy-nvim`
package ships a complete LazyVim config in `/etc/skel/.config/nvim`, so a fresh
user already has `~/.config/nvim` before this repo runs; the aarch64 fork has no
such package and the directory is absent. The module handles both: a seeded
config that is not a git checkout is moved to
`~/.config/nvim.omarchy-setup.bak.<epoch>` once, and the repo is cloned in its
place. `omarchy-nvim-setup` will not re-seed over a directory that exists, so
the move does not fight `omarchy update`.

Delete the backup once you are happy; nothing reads it.

**Plugins are installed with `Lazy! restore`, not `Lazy! sync`.** The config repo
commits a `lazy-lock.json` and that lockfile is the pin. `sync` *updates* it,
which both ignores the pin and leaves the checkout dirty -- and a dirty checkout
is what then blocks the next run's `git pull --ff-only`. `restore` installs
what is missing at the locked commits and leaves the tree clean. A config with
no lockfile falls back to `sync`.

Updating a pin is therefore a deliberate act in the config repo (`:Lazy sync`,
then commit the lockfile), not a side effect of running setup.

A checkout with local changes is left alone entirely, with the `git status`
printed. Omarchy migrations do write into `~/.config/nvim` -- the
remote-clipboard migration installs a file there -- so this is a real state to
land in, and skipping the pull beats failing halfway through it.

## herdr

Installed by Omarchy already. Both profiles keep its server running, by
different means:

- **client** -- `modules/client/55-herdr-autostart.sh` adds
  `o.launch_on_start("herdr server")` to `~/.config/hypr/autostart.lua`, so it
  comes up with the Hyprland session.
- **remote** -- `modules/remote/45-herdr.sh` enables lingering, so the user
  manager and the server outlive an ssh logout. The client then attaches with
  `herdr --remote <ssh-target>`.

## Shell plugins

`config/plugins.txt` lists plugin git URLs, installed on the client profile by
`modules/client/50-plugins.sh` via `omarchy plugin add --yes`. Headless boxes
skip it -- these are bar widgets and desktop UI.

Already-installed plugins are detected by their **git remote**, not their id:
the id is only knowable after installing, but the URL is what the config has up
front.

Installing does not place a widget on the bar. Add `enable:<plugin-id>` after a
URL to also run `omarchy plugin enable`, which writes `shell.json`.

## Unwanted packages

Removal lists are data, not code -- edit `config/remove/*.txt`, one package per
line, `#` starts a comment:

| File | Applies to |
|------|-----------|
| `config/remove/common.txt` | every machine |
| `config/remove/client.txt` | workstations |
| `config/remove/remote.txt` | headless boxes (telegram, signal, discord, ...) |

Packages that aren't installed are skipped silently, and anything another
package depends on is kept with a warning -- so these lists cannot break
`omarchy update`.

## Non-goals

- **The bar *layout* is left alone.** `~/.config/omarchy/shell.json` is yours
  to arrange via `omarchy bar ...`; this repo never writes it. Plugins are
  *installed* (see below) but not placed, unless a `config/plugins.txt` line
  carries an explicit `enable:<id>` marker.
- Themes are selected, not vendored -- custom ones install from a git URL via
  `omarchy theme install`.

## Adding things

- **A package** — drop `packages/<profile>/<name>.sh` in. It can carry its own
  post-install config; see `packages/remote/tmux.sh`.
- **Hyprland config** — edit `config/hypr/<name>.lua`, or
  `hosts/<hostname>/hypr/<name>.lua` for one machine. Both are plain Lua with a
  `.luarc.json` so `lua_ls` knows about `hl`/`o`.
- **A step** — add `modules/<profile>/NN-<name>.sh`, source `lib/common.sh`,
  keep it idempotent.

## SSH access (remote profile)

`modules/remote/35-sshd.sh` delegates to Omarchy's own
`omarchy setup security sshd`, which installs and enables sshd, opens the
firewall (`ufw limit 22/tcp`, rate limited against brute force), and authorizes
keys from `https://github.com/<user>.keys`. The account comes from
`GITHUB_USER` (`--github-user`).

**Prerequisite: a public key published to GitHub.** An account with no keys
returns HTTP 200 with an empty body, so the fetch silently yields nothing. The
module preflights this and fails early rather than aborting mid-setup, after
packages are installed and the firewall is already open.

Publishing one is not just `gh ssh-key add` -- `admin:public_key` is **not** in
`gh`'s default scopes, so a fresh machine gets `HTTP 404` from the API until the
token is refreshed:

```bash
gh auth refresh -h github.com -s admin:public_key
gh ssh-key add ~/.ssh/id_ed25519.pub --title "$(hostnamectl hostname)"
curl -fsSL https://github.com/<user>.keys        # verify: should print a key
```

If you would rather not depend on GitHub, set `SSH_PUBKEY` in `config/ssh.conf`
to a literal public key instead. Both may be set; each is applied in its own
call, because Omarchy's command refuses `--key` and `--gh-keys` together.

Password authentication is disabled afterwards (`HARDEN_PASSWORD_AUTH=1`), which
Omarchy itself leaves enabled. That step refuses to run while
`~/.ssh/authorized_keys` is empty -- disabling passwords without a working key
is how a remote box gets locked away permanently.

## Secrets

Bitwarden is the source of truth. This repo holds only the *manifest* — which
environment variable comes from which vault item — never the material.

```
config/secrets/bitwarden.conf   server URL + output path (non-secret)
config/secrets/common.map       ENV_VAR  vault-item  [field]
config/secrets/client.map
config/secrets/remote.map
```

A run unlocks the vault interactively, reads what the manifest asks for,
renders `~/.config/omarchy-setup/secrets.env` (mode 0600 in a 0700 directory),
and wires a managed block into `.bashrc` to source it. Then it re-locks — or
**logs out entirely if the run was what logged in**, so a machine we touched is
left holding no vault data.

Rotation is just a re-run: change the value in Bitwarden, run setup again.
Nothing hardcodes a key.

This runs on **both profiles** -- a remote needs secrets as much as a
workstation does, so `bitwarden-cli` is installed there too. What a remote does
not get is the desktop app or the bar widget
(`io.github.elevate08.qs-bitwarden-cli`, a shell plugin): both are GUI, and the
bar is a non-goal here. Keep `config/secrets/remote.map` shorter than the
client's regardless -- a remote should hold only what it needs to run.

Skipping:

```bash
./run.sh --skip-secrets
```

Secrets are skipped automatically when there is no terminal to type a master
password into, so unattended runs still succeed rather than hanging.

**The vault step needs a real terminal.** `bw unlock` uses Node's readline and
fails with `ERR_USE_AFTER_CLOSE: readline was closed` anywhere without a tty --
including inside an agent's shell. Run `--only secrets` from a terminal
yourself; everything else works headless.

### What the rendered file reaches

`secrets.env` is sourced from `.bashrc`, so the variables reach **shell-launched
processes only** -- terminals, and anything started from one. An app launched
straight from the Hyprland launcher or a keybind does **not** see them, because
nothing sources `.bashrc` on that path. If a desktop-launched app ever needs
one, put it in `~/.config/environment.d/` instead.

### Client version must match the server

Arch's `bitwarden-cli` was four releases behind the API version Vaultwarden
advertises, and unlocking failed in `bitwarden_crypto::keys::master_key` with
"The provided key is not the expected type" -- which reads like a wrong
password but is not. `bitwarden@<version>` is pinned in
`config/mise-tools.txt`; check the server with:

```bash
curl -fsSL https://<your-vault>/api/config | jq .version
```

and bump the pin to match after upgrading Vaultwarden.

The pinned client also has to be the one that actually runs. Omarchy appends
the mise shims to `PATH` *after* the system directories, so a pacman-installed
`bitwarden-cli` at `/usr/bin/bw` shadows the mise build -- silently reintroducing
the version mismatch above. `bw_resolve` in `lib/secrets.sh` therefore asks mise
for the path (`mise which bw`) and calls that binary directly, falling back to
`PATH` only when mise has no `bw` at all.

Deliberate properties:

- `BW_SESSION` is exported, never passed as `--session`: command-line arguments
  are visible to every process via `ps`.
- Values are never logged, never echoed, and never written to the repo — only
  the variable name is printed.
- `run.sh` completes fully with `--skip-secrets`; nothing else depends on the
  vault.

The tradeoff to be aware of: unlocking on a remote means typing your master
password on that machine. That is fine for hosts you own and trust, and it is
why nothing long-lived is left behind — but if a remote were compromised, a
keylogger would see it. The alternative is rendering secrets on the client and
pushing them over ssh, which keeps vault access on exactly one machine.

## Caveats

- This machine is the **aarch64 (Apple Silicon) fork** of Omarchy. Package
  availability differs from x86 remotes; `omarchy pkg add` skips packages
  missing from the repos with a warning rather than failing.
- `pkg_remove` refuses to remove anything another package depends on, so it
  cannot break `omarchy update`.
- Pin `OMARCHY_SETUP_REF` to a tag before pointing a fresh machine at `main`.
