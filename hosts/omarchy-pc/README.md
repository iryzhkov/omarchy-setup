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

## Sunshine application hooks

The host-bin overlay installs sunshine-virtual-display over the legacy local
helper through the existing 29-host-files module. It depends on the adjacent
display-controller source and the reviewed IPC-only daemon. It does not edit
Sunshine's apps.json, sunshine.conf or service hooks. Keep the installed global
prep do/undo commands as sunshine-virtual-display start/stop. Any existing
ExecStopPost safety call uses the same idempotent stop.

Keep stock Sunshine and restore the physical display when the user quits the
Sunshine application session. These prep commands follow that application
lifetime. Disconnecting the last Moonlight client may leave the application
session and virtual output alive; use Moonlight's Quit Session action to run
the stop hook and restore routing. This is the adopted lifecycle. It needs no
private Sunshine build, log waiter, connection counter or independent service.

Start validates integer client width 320..7680, height 200..4320 and FPS 1..240
before touching runtime state or display management. Defaults remain 1920x1080
at 60 Hz. HDR accepts 0/1/false/true; a rejected HDR rule retries an explicit
SDR rule. This is a command-error fallback only. An accepted rule does not prove
10-bit/HDR application, capture capability or client HDR delivery.
It requires the existing IPC-only capability handshake, no human preview or
unmanaged layout, and an awake known single-output topology. Missing IPC fails
before mutation, including when the user has stopped display management.

A private 0700 directory under the validated XDG_RUNTIME_DIR holds a 0600 journal
and flock. Overlapping calls fail without mutation and can be retried. The
journal records whether hyprmoncfgd.service was active and the unique headless
output name before creation. Start stops that service only if it was active,
waits for output creation and the requested size, refresh rate, scale and position,
then moves regular workspaces before specials and verifies special visibility.
Hyprland creates a replacement workspace when the last regular leaves an enabled
monitor. Only a newly created, explicitly empty nonpersistent replacement may
remain on the source until disable; all remaining regulars must reach the target
after disable converges. Each convergence wait has a five-second deadline and
rechecks cancellation, service ownership and monitor identities. Start writes
no saved profile, TV cooldown, recommended-profile selection or legacy recovery
state.

Stop reloads the existing generated include, waits for a known awake physical
layout at its saved size, and moves regular and special workspaces to its
enabled output. If reload disabled this session's headless output, stop first
re-enables it because Hyprland's remove command resolves enabled monitors.
It removes only the journaled output, waits for its absence from monitors all,
and verifies final workspace placement. It restores the service only if
it was previously active; it never enables a unit. The existing controller then
debounces current HA intent and restores its current route, including receiver
and audio policy. After the final route is healthy, the controller reconciles
special workspaces there too. This handles HA intent that differs from the
initial generated include. The qualified Hyprland v0.56.2 workspace move API
preserves visible and hidden specials without toggling them.

Failures retain the journal whenever recovery is incomplete. Failed physical
restoration deliberately leaves display management stopped so it cannot compete
with recovery. From a local terminal, resolve the reported output identity,
ownership or layout conflict, restore a known physical include if needed, then
run sunshine-virtual-display stop again. Do not start the controller over a
pending restore or delete the journal to force progress. A completed display
restoration is journaled before service restart, so a retry cannot reload over a
resumed controller. Unknown outputs, changed identities and an independently
resumed service inhibit destructive cleanup; resolve ownership before retrying.
A missing journal makes stop a no-op.
The helper does not remove someone else's headless output or infer ownership
from a generic name prefix. Multiple visible specials cannot all remain visible
on one output, so that migration is refused.

Only the service state observed at start can be restored. Systemctl actions
outside this hook do not share its lock; a concurrent operator action requires
resolving ownership before cleanup. Deterministic tests inject failures and
check migration, visibility, safety gates and profile hashes. They do not qualify
live NVIDIA/headless behavior or physical HDMI recovery. Perform that acceptance
separately, after review, with no active game.

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
mode changes and continuous awake polls never rearm it. Two observations of an
explicit TV input away from HDMI3, or a known-output sleep cycle, permit another
attempt, subject to a five-minute cooldown. Receiver-off and TV-power reports
alone cannot rearm a reset. After our own reset, receiver-off echoes cannot
select the desk layout until on is confirmed in two polls or independent TV
intent changes. An unknown TV source retains the layout. If the on request
fails to restore power, this wait remains pending; changing the TV input,
turning the TV off, or restoring receiver power permits routing again.
Budgets are in memory for the process lifetime; both automatic and explicit
service restarts reset them. No additional timer or watchdog is used.
The status includes receiver_recovery_attempted and receiver_restore_pending,
and reports pending, inhibited or requested handshake recovery separately from
verified scanout health.

## Rollback

Stop the display service before restoring the backed-up scripts and its previous
drop-in. Restore the prior autostart file and timer enablement only after the old
writer paths are back. Reload user units, restart the old display service, and
verify compositor state against DRM scanout. Leave HDR disabled if signal
recovery has not been confirmed.
