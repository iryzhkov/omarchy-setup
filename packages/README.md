# packages/

One script per package, run by `modules/common/20-packages-install.sh`, split
by profile (`common/`, `client/`, `remote/`).

**Only put things here that Omarchy does not already ship.** Check first:

```bash
grep -qxw <pkg> /usr/share/omarchy/install/omarchy-base.packages && echo preinstalled
```

Most of what a setup like this reaches for -- ripgrep, fd, lazygit, tmux,
herdr, mise-bin, git, neovim, obsidian -- is already in Omarchy's base list, so
installing it again is noise. A script here should either install something
genuinely absent, or do real post-install configuration.

Agent CLIs are not packages at all: they are mise tools, in
`config/mise-tools.txt`.
