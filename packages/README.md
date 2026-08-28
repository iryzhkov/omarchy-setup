# packages/

One script per package, run by `modules/common/20-packages-install.sh`, split
by profile (`common/`, `client/`, `remote/`).

**Only put things here that Omarchy does not already ship.** Check with:

```bash
bin/preinstalled <pkg>...
```

Do not just grep the base list for the package name. It records some packages
by what they *provide*: the entry is `nvim`, satisfied by the `neovim` package,
so `grep -w neovim` reports "not in base" and is wrong. `bin/preinstalled`
resolves provides on both installed and repo packages.

Already covered by Omarchy's base install, among much else:

    nvim (neovim)  git  mise-bin  herdr  ripgrep  fd  lazygit  tmux  obsidian

Modules that merely *depend* on one of these use `ensure_cmd`, which is silent
when the tool is present and installs only if something removed it -- rather
than printing "already installed" on every run.

Genuinely absent, and so worth a script here: Brave (installed through
`omarchy install browser brave`, which picks the right build per platform).

Agent CLIs are not packages at all -- they are mise tools, in
`config/mise-tools.txt`.

## A wrinkle: omarchy-nvim

The base list also carries `omarchy-nvim`, Omarchy's default Neovim config. It
resolves to no package in the aarch64 repos, so it is absent on Apple Silicon,
but on x86 it installs and may seed `~/.config/nvim`.
`modules/common/40-nvim.sh` handles that -- a non-git `~/.config/nvim` is moved
aside before the clone -- but expect a `.bak` directory there on a fresh x86
machine.
