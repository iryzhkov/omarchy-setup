# hosts/

Per-machine overrides, keyed by hostname (`hostnamectl hostname`, or
`run.sh --host <name>`).

    hosts/<hostname>/hypr/<name>.lua        appended after config/hypr/<name>.lua (30-hypr)
    hosts/<hostname>/bin/<name>             -> ~/.local/bin/<name>              (29-host-files)
    hosts/<hostname>/config/<path>          -> ~/.config/<path>
    hosts/<hostname>/share/<path>           -> ~/.local/share/<path>
    hosts/<hostname>/systemd/user/<unit>    -> ~/.config/systemd/user/<unit>, enabled
    hosts/<hostname>/root/<path>            -> /<path>, installed with sudo as root:root
    hosts/<hostname>/<file>                 anything a module asks for via host_file

Keep behaviour here, not appearance: monitor scale, theme and bar layout are
tuned by hand on each machine and are deliberately not managed by this repo
(see the README's Non-goals).

## omarchy-macbook-air-igor

The Asahi Linux MacBook Air (M2, J413). Everything here works around that
hardware and is meaningless elsewhere:

- `config/asahi-audio/` and `share/wireplumber/scripts/node/`: a user-override
  DSP graph for the speakers (woofer limiter retuned into a brickwall, see
  `j413-speakers.README`), a mono copy of the mic graph so the panel level
  meter works, and the WirePlumber Lua hook that rebuilds the software DSP
  when the filter chain tears itself down. Wired in by the two `9x-*.conf`
  drop-ins under `config/wireplumber/`.
- `bin/mic-*`, `bin/j413-mic-mono-gen`, `systemd/user/mic-*.service`: the
  watchdog and diagnostics for the mic filter chain, kept as a fallback to
  the Lua hook.
- `bin/voxtype-update` and `systemd/user/voxtype.service`: voxtype is built
  from the AUR PKGBUILD (cloned into `~/Work/pkgbuilds/voxtype` on first
  run) with the Vulkan variant stripped, because the GPU build does not work
  on Asahi; the package is in pacman's IgnorePkg for that reason.
- `root/usr/local/share/omarchy-patches/` and
  `root/etc/pacman.d/hooks/90-omarchy-local-patches.hook`: patches against
  `/usr/share/omarchy` (bar workspaces, speedtest, audio device selection,
  notch height) re-applied by `omarchy-apply-local-patches` after every
  omarchy package transaction. Add a patch there rather than editing in place.
- `root/etc/pacman.d/hooks/91-asahi-audio-overrides.hook`: after an
  asahi-audio upgrade, `asahi-audio-check-overrides` diffs the packaged graph
  against the user override and says when it needs re-basing.
- `root/usr/local/bin/brcmfmac-wedge-watchdog` and its system unit: watches
  the journal for the Broadcom firmware wedge and runs the wifi resume fix.
- `root/usr/local/bin/omarchy-mac-setup`: the guided Omarchy-on-Mac install
  script, kept here so a reinstall has it.
