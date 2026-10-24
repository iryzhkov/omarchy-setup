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
delegate to that same policy. Sony identity comes from the unique available HDMI
card port. Its playback sink must match that exact card and active port; the
sink's product label can name the GPU audio controller. Missing or conflicting
bindings and multiple matches defer audio routing. An existing HDMI channel
profile, mute and volume are preserved. Missing or ambiguous audio is reported
separately and does not block display recovery. Sleep and human previews defer
automatic audio changes.

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
unmanaged layout, and an awake known single-output topology. A narrowly
qualified TV-off fallback also accepts the Sony SONY AVSYSTEM receiver identity
on HDMI-A-1, serial 0x01010101, with HDMI enabled and the identified saved DP-1
display present but disabled. Both must have DPMS on, transform zero and the
qualified 8-bit SDR color/VRR state. This works when IPC reports both
source_profile and profile_override as null, or a recognized source profile.
An unknown source profile still fails. The fallback captures physical identity,
mode, scale, position, disabled state and color settings in the private journal.
Missing connectors, all-disabled layouts and DPMS-off outputs are not supported
by this fallback. Missing IPC fails before mutation, including when the user
has stopped display management.

A private 0700 directory under the validated XDG_RUNTIME_DIR holds a 0600 journal
and flock. Overlapping calls fail without mutation and can be retried. The
journal records whether hyprmoncfgd.service was active and the unique headless
output name before creation. Start stops that service only if it was active,
waits for output creation and the requested size, refresh rate, scale and position,
then moves regular workspaces before specials and verifies special visibility.
Hyprland creates a replacement workspace when the last regular leaves an enabled
monitor and may reuse the ID of a destroyed empty target workspace. Only
explicitly empty nonpersistent workspaces may remain on the source until disable.
Workspaces that were occupied, persistent or unknown before migration must
survive and reach the target; all remaining regulars must reach it after disable
converges. Each convergence wait has a five-second deadline and
rechecks cancellation, service ownership and monitor identities. Start writes
no saved profile, TV cooldown, recommended-profile selection or legacy recovery
state.

Stop reloads the existing generated include, waits for a known awake physical
layout at its saved size, and moves regular and special workspaces to its
enabled output. For the receiver fallback, reload first re-enables HDMI, then
the helper replays its captured mode, scale and position with the qualified SDR
rule. It requires both physical outputs to match the captured state, including
DP staying disabled, before moving workspaces or removing headless. It does not
write the include or a saved profile, power the TV, or re-enable DP. Exact
connector membership and identities must remain unchanged through recovery.
If reload disabled this session's headless output, stop first
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

## HDMI stale identity recovery

The controller replaces its receiver power cycle with one bounded logical
connector disconnect and detect. The automatic trigger remains the exact Sony
SONY AVSYSTEM identity, serial 0x01010101, on the awake HDMI-A-1 output. A
checksummed kernel EDID must identify the saved Sony SONY TV  *30, serial
0x01010101. HA must confirm screen on, HDMI3 intent through the existing source
precedence, and the receiver on Racing. A stale primary TV entity reporting off
does not override an on screen sensor and a playing CAST TV/HDMI3 source.

Two fault observations at least five seconds apart are required. One attempt
consumes the fault budget before takeover. Continuous polls, failed queries,
receiver power reports, input changes and mode jitter cannot rearm it. Two
verified healthy TV observations end the fault; a subsequent fault can attempt
again after the five-minute cooldown. Budgets last for the controller process.
A refused helper, sudo, watcher or stream-lock preflight also consumes that edge;
this conservative inhibition needs a verified healthy edge or an explicit service
restart after the prerequisite is repaired. It does not retry a persistent fault.
A pending recovery journal inhibits ordinary routing, audio and another off.

The root overlay installs /usr/local/libexec/display-hdmi-rediscover, mode 0755,
root:root. The controller checks protected root ownership and runs sudo -n
--check before any display takeover. No grant is installed. The helper uses
isolated Python, standard-library code and fixed sysfs paths only. It requires
one NVIDIA GPU, one HDMI-A-1 connector on it, connected status, and the complete
qualified TV EDID. It rechecks immediately before off. There are no caller paths,
environment settings or external commands in its privileged operation.

A pipe handshake waits for the controller to observe the physical output absent
before detect. Failure, EOF, timeout and SIGTERM/INT/HUP after an attempted off
all execute compensated detect. Signal handlers record cancellation without
raising across the cleanup boundary, and compensation masks repeated signals.
A detect-only command exists for compensation. The ready handshake waits sixty
seconds, matching the controller operation bound and starting later. The
controller checks its deadline again after the last HA query before sending off.
A buffered refusal is still read if sending or flushing off hits a broken pipe;
bare EOF remains uncertain. Closing the pipe drains refusal/detect messages and
reaps the helper even if stdin close fails. Child and watcher restoration runs
in a separate finally path even when helper cleanup raises.
SIGKILL, machine loss or an unwritable kernel status file cannot be compensated
by a process; the private journal retains detect ownership in that case.

Recovery holds the existing Sunshine lock, checks for its application journal,
and refuses every unowned headless or unknown output. Sunshine start also
refuses a pending HDMI recovery journal. Lock overlap defers acquisition; it
never stops an active stream. Stock Sunshine Quit Session semantics remain.

The controller stays alive. After a fresh IPC-only capability, peer PID,
management and preview check, it journals recovery, closes its old IPC connection
and stops/recreates only its exact owned child. It requires old child exit and
socket disappearance before creating a unique temporary headless backup.
It captures regular and special workspaces before off and moves them to that
backup. DP-1 stays disabled, including an uninitialized 0x0/Invalid DP state.

Daemon shutdown can restart Omarchy's monitor watcher. Recovery holds both
omarchy-monitor-clamshell.lock and omarchy-monitor-modeless.lock from before
child shutdown through child startup and cleanup. It accepts only watcher
script SHA-256 values
5b7415c8b25dcccc695c808163b9ff4602cdbacecabf23398a166bfe85623b48 and
124c14fbc0285cf195e529d7cdee6f90baeec2c9a1421f9b9a3cec933024eced.
The latter was qualified from the root read-only installed-monitor-watcher
receipt on 2026-10-23, including both installed paths, complete source, uid 0
and mode 0755. In both versions, clamshell dispatch runs after flock -n and
modeless probes/reloads run after flock -w 1, on the two held lock files.
Different installed
bytes fail closed before takeover and need explicit contract qualification.
The new child reclaims the watcher through the daemon's existing ownership
lifecycle. The controller confirms no active watcher scope before releasing
exclusion. A failed child restart retains both locks in the living supervisor
until a later owned-child startup confirms reclamation. An unverified helper exit
independently retains both locks and its exact process handle, even after the child
is ready. A later cleanup can release them only after that handle confirms exit
and child/watcher reclamation succeeds. Shutdown also retains unresolved exclusion
while the controller process lives. Process death necessarily releases locks.
A journal recording an unverified helper exit then requires operator resolution:
the next controller cannot prove exit using a lost process handle.
No watcher service is disabled or independently restarted here.
A direct user hyprctl write, or a preview arriving in the narrow interval between
the final query and child termination, has no atomic reservation API. Fresh
IPC peer/preview checks and topology checks defer restoration on an observed
conflict; this path does not claim an atomic human-input reservation.

After detect, the new child serves fresh IPC. The controller applies tv-game
once without saving a profile, checks identity, dimensions, scale, transform,
position, refresh and actual DRM scanout, restores regular/special placement and
special visibility, removes only its backup, verifies again, then commits.
Saved profiles and calibration are unchanged. Audio follows the verified live
route on the next normal poll.

The private runtime file display-hdmi-recovery.json owns the backup name,
original workspace snapshot, saved-profile snapshot and recovery stage.
A failure before off compensates only the workspace moves and backup creation.
Either known Sony identity is accepted on the enabled, awake HDMI output, with
DP disabled and no unknown outputs. Cleanup does not apply a display mode or
wake a sleeping display. A sleeping or unknown display retains the backup
journal; after waking or resolving that conflict, a controller start retries
cleanup without off. An explicit root-helper refusal before any write selects
this same compensation path. A fresh ten-second cleanup budget is independent
of the failed operation deadline. The journal records completed compensation
until owned-child readiness and watcher reclamation also succeed. A prepared
journal with no display mutation clears during the same run after helper cleanup,
owned-child readiness, watcher reclamation and backup absence are verified.
Helper ownership is journaled before its ready handshake. A child still stopping
or a helper that cannot be reaped retains the journal and both watcher locks in
the living controller, even when no off was sent. Incomplete cleanup leaves the journal and any remaining backup
in place. Ordinary polls defer.
On a later controller start, one bounded cleanup attempt can compensate detect
and finish restoration; it never repeats off. A changed profile, preview,
identity, sleep state or competing owner leaves recovery pending for the
operator. Do not delete the journal to force routing or start Sunshine over it.
If stop/start, socket cleanup or watcher qualification fails, status reports
the concrete error and retains cleanup ownership.

The kernel off/detect primitive was qualified on the healthy TV under a temporary
backup without restarting Hyprland or applications. Full recovery of a naturally
stale receiver incident still needs live acceptance. A real-TV identity with
stale modes is not an automatic trigger until separately qualified. The existing
Sunshine TV-off receiver snapshot still requires previously initialized DP
geometry and SDR fields; a disabled DP at 0x0 with currentFormat Invalid remains
outside that fallback. This change does not qualify every TV-off state.


Stop the display service before restoring the backed-up scripts and its previous
drop-in. Restore the prior autostart file and timer enablement only after the old
writer paths are back. Reload user units, restart the old display service, and
verify compositor state against DRM scanout. Leave HDR disabled if signal
recovery has not been confirmed.
