# Display coordination on omarchy-pc

The local display coordinator runs under the existing hyprmoncfgd user service.
It supervises one hyprmoncfgd process in explicit IPC-only mode and sends layout
transactions through its Unix socket. Automatic daemon matching is disabled so
hotplug cannot override coordinator policy. TV power/input selection and physical scanout recovery share that
coordinator. The daemon remains the display writer; Hyprland owns fullscreen
HDR metadata.

This host requires saved desk, tv-game and tv-recovery profiles. Their layout,
calibration and profile command settings stay machine-local. The coordinator
must not rewrite them. The game launcher reports HDR availability inside
Gamescope without changing monitor profiles.

Audio follows the verified current display route in the same controller. TV mode
selects the available Sony HDMI device; desk mode selects the Focusrite output.
The controller updates the default and moves existing application streams,
including a running game. Existing hyprmoncfg-audio-tv and -desk profile commands
delegate to that same policy. An existing HDMI channel profile, mute and volume
are preserved. Missing or ambiguous audio is reported separately and does not
block display recovery. Sleep and human previews defer automatic audio changes.

## Installation and retirement

The daemon executable is private to this controller at
~/.local/libexec/display-controller/hyprmoncfgd. The system package stays intact.
The patch under patches/ adds --ipc-only and a capability in daemon status.
The controller refuses an incompatible daemon. Build the pinned 1.25.1 source
and run its daemon/IPC tests in Chaldea:

```sh
chaldea exec --host agent-a --artifact build/display-controller/hyprmoncfgd -- \
  env DISPLAY_BUILD_SCRATCH=/home/job/.cache/display-daemon-build \
  bash test/build-display-daemon.sh
```

Install the returned, reviewed artifact at the private path before applying
host files. The host-file module checks this dependency before replacing the
working helpers. The build job never installs on the gaming PC. CI also builds
and tests the pinned patch. Keep the artifact hash with the deployed revision.

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

- One coordinator and one private hyprmoncfgd child are running with --ipc-only.
- The daemon reports ipc_only=true, with no forced profile.
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

## Workspace and Big Picture placement

Route verification allows an empty, nonpersistent workspace to disappear when
its old monitor is disabled. Occupied, persistent and unknown workspaces must
survive, and every remaining regular workspace must be on the selected output.
Rollback applies the same distinction. This avoids rejecting a good route just
because Hyprland removed an unused workspace.

The host overlay opens Steam Big Picture fullscreen on its workspace's current
monitor. It does not pin Steam or games to a connector or a numbered workspace.
The rule applies when the Big Picture window is created; an already-running
off-screen window needs a one-time focus/fullscreen correction.

## Receiver handshake recovery

The controller can power-cycle the existing STR-AZ5000ES once when the HDMI
connector reports Sony SONY AVSYSTEM instead of the saved TV, with no DRM
scanout. Recovery requires two observations at least five seconds apart, the
known connector topology, an awake HDMI output, the TV on HDMI3, receiver on
Racing, and a complete checksummed kernel EDID matching the saved TV identity.
The same evidence and IPC-only ownership are checked again before the action.
Unknown replacement displays and manual previews still defer all recovery.

After requesting off, the controller waits three seconds and always requests
on, even if off timed out or cancellation interrupted the pause. It reselects
Racing only if that is still the current source, TV intent remains, and no
manual preview owns the display. It never applies a profile under the receiver
alias. Normal profile transactions resume only after the real TV identity
returns. A requested reset is not proof that the physical picture recovered.

A reset consumes its attempt before sending the off request. Query errors,
mode changes and continuous awake polls never rearm it. A confirmed desk
selection or known-output sleep cycle permits another attempt, subject to a
five-minute cooldown. Budgets are in memory for the service lifetime; an
explicit service restart resets them. No additional timer or watchdog is used.
The status includes receiver_recovery_attempted and reports pending, inhibited
or requested handshake recovery separately from verified scanout health.

## Rollback

Stop the display service before restoring the backed-up scripts and its previous
drop-in. Restore the prior autostart file and timer enablement only after the old
writer paths are back. Reload user units, restart the old display service, and
verify compositor state against DRM scanout. Leave HDR disabled if signal
recovery has not been confirmed.
