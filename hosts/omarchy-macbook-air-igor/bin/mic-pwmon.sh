#!/usr/bin/env bash
# Log PipeWire graph events (params hidden - they were ~107KB/s of Pod spam), timestamped.
#
# The log is a two-file ring: the live log is rotated to .1 every MAX_LINES
# lines and started fresh, so the pair never exceeds roughly 2 * MAX_LINES
# lines on disk. Snapshots only ever read the tail, so nothing older matters.
# Rotating in-process this way also avoids restarting the service to truncate.
STATE="$HOME/.local/state/mic-watch"
LOG="$STATE/pw-mon.log"
MAX_LINES=20000
mkdir -p "$STATE"
[ -f "$LOG" ] && mv -f "$LOG" "$LOG.1"

# Note: the awk variable cannot be called "log" - that is a gawk builtin.
# stdbuf keeps pw-mon line-buffered. Without it pw-mon fills a 4KB pipe
# buffer before anything reaches the log, so the events immediately
# before a teardown - the ones a snapshot exists to capture - can still
# be unwritten when the snapshot runs.
exec stdbuf -oL pw-mon -a -N -p 2>&1 | awk -v logfile="$LOG" -v max="$MAX_LINES" '
{
    printf "%s %s\n", strftime("%F %T"), $0 >> logfile
    fflush(logfile)
    if (++n >= max) {
        close(logfile)
        system("mv -f \"" logfile "\" \"" logfile ".1\"")
        n = 0
    }
}'
