# Display coordination on omarchy-pc

The local display coordinator runs under the existing hyprmoncfgd user service.
It supervises one hyprmoncfgd process and sends layout transactions through its
Unix socket. TV power/input selection and physical scanout recovery share that
coordinator. The daemon remains the display writer; Hyprland owns fullscreen
HDR metadata.

This host requires saved desk, tv-game and tv-recovery profiles. Their layout,
calibration and audio commands stay machine-local. The coordinator must not
rewrite them. The game launcher only executes its command.

## Installation and retirement

The host overlay installs display-controller, its service drop-in, passive
compatibility commands, and the fullscreen HDR configuration. The host-specific
32-display-controller module disables the old tv-output-guard timer and restarts
the existing user service. It does not create another timer or service.

Old calls to ha-display-select enter the coordinator. Old tv-settle and
tv-output-guard calls are read-only diagnostics. Remove the old tv-settle
monitor.added registration from ~/.config/hypr/autostart.lua after installing the
overlay; the passive shim keeps an older hook from changing display modes.

Run only the relevant setup modules when installing this change. Do not run a
whole-machine setup as part of a display fix. A display-service restart can
briefly interrupt monitor management, so install while unlocked and with the
working SDR profile available.

## Readiness and live testing

Before live HDR testing, verify:

- One coordinator and one hyprmoncfgd child are running, without --profile.
- The old watchdog timer is disabled and no hotplug helper writes profiles.
- display-controller --status reports current routing and health.
- display-controller --check agrees with actual DRM scanout.
- Hyprland reports no configuration errors and the shell responds.
- The TV uses the intended 4K119.88 10-bit SDR baseline.

Keep the same HDMI mode and bit depth across fullscreen HDR transitions.
Hyprland's configured color preset can remain srgb during automatic HDR;
inspect actual DRM HDR metadata and the TV's picture mode during live tests.
A compositor report alone does not prove a working HDMI signal.

The simulator tests do not prove that this NVIDIA driver and AVR can repeatedly
transition HDR metadata. Run that physical check separately, with the user
ready to report loss of signal. Stop after a failed transition instead of
repeatedly modesetting a stuck driver.

## Rollback

Stop the display service before restoring the backed-up scripts and its previous
drop-in. Restore the prior autostart file and timer enablement only after the old
writer paths are back. Reload user units, restart the old display service, and
verify compositor state against DRM scanout. Leave HDR disabled if signal
recovery has not been confirmed.
