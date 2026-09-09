#!/usr/bin/env bash
# Watch the j413 mic filter chain; snapshot on change, repair only if it stays broken.
#
# Failure mode: the chain is built in two halves --
#   audio_effect.j413-mic  [Stream/Input/Audio]  reads the HPAI hardware
#   effect_output.j413-mic [Audio/Source]        the source apps see
# libpipewire-module-filter-chain destroys itself when either stream goes
# UNCONNECTED (one failed link activation is enough), and WirePlumber's stock
# software-dsp script never rebuilds it while the parent ALSA node survives.
#
# The primary fix now lives inside WirePlumber:
# ~/.local/share/wireplumber/scripts/node/software-dsp-rebuild.lua reloads the
# filter in place within ~1.5s. This watchdog is the fallback for the case
# where that does not work, and a recorder of what happened.
#
# Lessons that shaped it:
#  1. Repair must be driven by current state, not by a transition. A skipped
#     transition used to strand the chain forever.
#  2. A wireplumber restart destroys the whole PipeWire graph, which crashes
#     quickshell (use-after-free in its PwNode bindings). Every runtime restart
#     this script performed took the shell down with it. So restarting is a
#     last resort: only after the chain has been missing for MISS_REQUIRED
#     consecutive polls, and never during WirePlumber's own startup.
#  3. At boot this service used to start 20-40ms before wireplumber, see an
#     empty graph on its first poll, and restart wireplumber 0.5s into its
#     life -- every boot. Those were not mic failures. Hence STARTUP_GRACE,
#     and a fresh grace period whenever wireplumber is seen to have restarted.

STATE="$HOME/.local/state/mic-watch"
LOG="$STATE/events.log"
PWLOG="$STATE/pw-mon.log"
BASE_COOLDOWN=60     # seconds; multiplied by the failure streak
MAX_MULT=4
SETTLE_OK=3          # consecutive healthy checks required after a repair
AUTO_REPAIR=1        # 0 = observe only
MAX_SNAPSHOTS=30     # older snapshot files are pruned after each new one
POLL=5               # seconds between health checks
STARTUP_GRACE=20     # seconds after wireplumber becomes active before judging it
MISS_REQUIRED=4      # consecutive "gone" polls before a restart (4 x 5s = 20s;
                     # the in-WirePlumber rebuild needs ~2s, so this only fires
                     # when that has genuinely failed)
mkdir -p "$STATE"

status()    { wpctl status 2>/dev/null; }
present()   { status | grep -qE 'effect_output\.j413-mic.*Audio/Source'; }
halfbuilt() { status | grep -q 'audio_effect\.j413-mic' && ! present; }
now()       { date +%s; }
wp_started() { systemctl --user show -p ActiveEnterTimestampMonotonic --value wireplumber.service 2>/dev/null; }

snapshot() { # $1=from $2=to
    local ts snap hb
    ts=$(date '+%F %T'); hb=no; halfbuilt && hb=yes
    snap="$STATE/snapshot-$(date +%Y%m%d-%H%M%S)-$2.txt"
    {
        echo "=== $ts  transition: $1 -> $2  (half-built: $hb) ==="
        echo "wireplumber pid: $(pgrep -x wireplumber | tr '\n' ' ')"
        echo "quickshell pid:  $(pgrep -x quickshell | tr '\n' ' ')"
        echo; echo "--- wpctl status ---";    status
        echo; echo "--- arecord -l ---";      arecord -l 2>&1
        echo; echo "--- card profiles ---"
        pactl list cards 2>&1 | grep -E "^Card|Name:|Active Profile:|Active Port:"
        echo; echo "--- default-nodes ---";   cat "$HOME/.local/state/wireplumber/default-nodes" 2>&1
        echo; echo "--- default-profile ---"; cat "$HOME/.local/state/wireplumber/default-profile" 2>&1
        echo; echo "--- fuser /dev/snd ---";  fuser -v /dev/snd/* 2>&1
        echo; echo "--- journal last 5 min ---"
        journalctl --user -u wireplumber -u pipewire -u pipewire-pulse \
                   --since "5 min ago" --no-pager 2>&1 | grep -v 'pipewire.peak' | tail -120
        echo; echo "--- pw-mon.log tail (500) ---"
        cat "$PWLOG.1" "$PWLOG" 2>/dev/null | tail -500
    } > "$snap"
    echo "$ts  $1 -> $2  half-built=$hb  $snap" >> "$LOG"

    ls -1t "$STATE"/snapshot-*.txt 2>/dev/null | tail -n +$(( MAX_SNAPSHOTS + 1 )) |
        while IFS= read -r old_snap; do rm -f "$old_snap"; done
}

# Block until wireplumber is active, then give it STARTUP_GRACE seconds to
# build the graph. Returns the ActiveEnterTimestamp it waited on.
wait_for_wireplumber() {
    until systemctl --user is-active --quiet wireplumber.service; do sleep 2; done
    local started elapsed
    started=$(wp_started)
    elapsed=$(( ( $(cut -d' ' -f1 /proc/uptime | cut -d. -f1) * 1000000 - started ) / 1000000 ))
    if [ "$elapsed" -lt "$STARTUP_GRACE" ]; then
        echo "$(date '+%F %T')  wireplumber is ${elapsed}s old; waiting $(( STARTUP_GRACE - elapsed ))s before judging it" >> "$LOG"
        sleep $(( STARTUP_GRACE - elapsed ))
    fi
    echo "$started"
}

last=unknown
last_repair=0
fail_streak=0
misses=0
wp_epoch=$(wait_for_wireplumber)

while :; do
    # WirePlumber restarted underneath us (crash, update, manual restart):
    # start over with a grace period instead of judging a half-built graph.
    cur_epoch=$(wp_started)
    if [ -n "$cur_epoch" ] && [ "$cur_epoch" != "$wp_epoch" ]; then
        echo "$(date '+%F %T')  wireplumber restarted externally; re-arming grace" >> "$LOG"
        wp_epoch=$(wait_for_wireplumber)
        misses=0; last=unknown
    fi

    if present; then cur=present; misses=0; else cur=gone; misses=$(( misses + 1 )); fi

    if [ "$cur" != "$last" ]; then
        if [ "$last" = unknown ]; then from=startup; else from="$last"; fi
        if [ "$last" != unknown ] || [ "$cur" = gone ]; then
            snapshot "$from" "$cur"
        fi
        last=$cur
    fi

    # Last resort. The in-WirePlumber rebuild should have brought the chain
    # back within one or two polls; only act when it clearly has not.
    if [ "$cur" = gone ] && [ "$AUTO_REPAIR" = 1 ] && [ "$misses" -ge "$MISS_REQUIRED" ]; then
        mult=$(( fail_streak + 1 )); [ "$mult" -gt "$MAX_MULT" ] && mult=$MAX_MULT
        cooldown=$(( BASE_COOLDOWN * mult ))
        if [ $(( $(now) - last_repair )) -ge "$cooldown" ]; then
            last_repair=$(now)
            echo "$(date '+%F %T')  chain missing for $(( misses * POLL ))s and not rebuilt in place; restarting wireplumber (streak=$fail_streak, cooldown was ${cooldown}s)" >> "$LOG"
            systemctl --user restart wireplumber
            wp_epoch=$(wp_started)
            ok=0
            for _ in $(seq 1 15); do
                sleep 1
                if present; then ok=$(( ok + 1 )); else ok=0; fi
                [ "$ok" -ge "$SETTLE_OK" ] && break
            done
            if [ "$ok" -ge "$SETTLE_OK" ]; then
                echo "$(date '+%F %T')  REPAIRED and stable for ${SETTLE_OK}s" >> "$LOG"
                fail_streak=0; misses=0; last=present
                command -v notify-send >/dev/null 2>&1 && \
                    notify-send "j413 mic recovered" "chain rebuilt by wireplumber restart"
            else
                fail_streak=$(( fail_streak + 1 ))
                echo "$(date '+%F %T')  REPAIR DID NOT HOLD (streak=$fail_streak)" >> "$LOG"
                last=gone
                command -v notify-send >/dev/null 2>&1 && \
                    notify-send -u critical "j413 mic still down" "repair attempt $fail_streak did not hold"
            fi
        fi
    fi

    sleep "$POLL"
done
