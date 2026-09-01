# Terminal bottom status line.
#
# Reserves the last terminal row with DECSTBM (set-scrolling-region) and paints
# a three-zone bar into it: user@host over SSH on the left, language versions
# for the current project in the middle, clock on the right.
#
# The scrolling region is *not* part of the state the alternate screen saves:
# a terminal keeps the margins across the DECSET 1049 switch, and neither nvim
# nor less resets them on entry. So the region has to be released before every
# foreground command, otherwise a full-screen program runs one row short of the
# real screen, its own bottom line lands on the reserved row, and the display
# shifts by a line whenever the terminal scrolls inside the stale margins.
# PS0 does the release (it is emitted after a command line is read, before the
# command runs) and the next prompt re-arms the region.
#
# Content comes from one `starship prompt` call against
# starship-bar.toml next to this file -- that reuses starship's context detection, so a
# language version shows up only inside a matching project. The clock only
# advances when a prompt is drawn; it is a prompt-time bar, not a live one.
#
# Disable for a session with BOTTOM_BAR=0.

[[ $- == *i* ]] || return 0
[[ ${TERM:-dumb} == dumb ]] && return 0

__bottom_bar_config="$HOME/.config/bash/omarchy-setup/starship-bar.toml"

# Strip readline markers and CSI ... m colour sequences, to measure printed width.
__bottom_bar_plain() {
  local s=$1 out=""
  s=${s//$'\001'/}
  s=${s//$'\002'/}
  s=${s//'\['/}
  s=${s//'\]'/}
  while [[ $s == *$'\e['* ]]; do
    out+=${s%%$'\e['*}
    s=${s#*$'\e['}
    s=${s#*m}
  done
  printf '%s' "$out$s"
}

# Drop readline markers but keep colours, for printing outside a prompt.
__bottom_bar_unwrap() {
  local s=$1
  s=${s//$'\001'/}
  s=${s//$'\002'/}
  s=${s//'\['/}
  s=${s//'\]'/}
  printf '%s' "$s"
}

__bottom_bar_compose() {
  local cols=${1:-${COLUMNS:-80}} raw rest left mid right lp mp rp line pad

  raw=$(STARSHIP_CONFIG=$__bottom_bar_config starship prompt --status=0 2>/dev/null) || return 1
  [[ $raw == *§*§* ]] || return 1

  left=$(__bottom_bar_unwrap "${raw%%§*}")
  rest=${raw#*§}
  mid=$(__bottom_bar_unwrap "${rest%%§*}")
  right=$(__bottom_bar_unwrap "${rest#*§}")

  lp=$(__bottom_bar_plain "$left")
  mp=$(__bottom_bar_plain "$mid")
  rp=$(__bottom_bar_plain "$right")

  # Right zone wins when space is tight, then left, then middle.
  if (( ${#lp} + ${#mp} + ${#rp} + 4 > cols )); then
    mid="" mp=""
  fi
  if (( ${#lp} + ${#rp} + 2 > cols )); then
    left="" lp=""
  fi

  local mid_start=$(( (cols - ${#mp}) / 2 ))
  (( mid_start < ${#lp} + 1 )) && mid_start=$(( ${#lp} + 1 ))
  (( mid_start + ${#mp} > cols - ${#rp} - 1 )) && mid_start=$(( cols - ${#rp} - ${#mp} - 1 ))
  (( mid_start < ${#lp} )) && mid_start=${#lp}

  line=$left
  pad=$(( mid_start - ${#lp} ))
  (( pad > 0 )) && printf -v line '%s%*s' "$line" "$pad" ""
  line+=$mid
  pad=$(( cols - ${#rp} - mid_start - ${#mp} ))
  (( pad > 0 )) && printf -v line '%s%*s' "$line" "$pad" ""
  line+=$right

  printf '%s' "$line"
}

__bottom_bar_draw() {
  __bottom_bar_ps0=""
  [[ ${BOTTOM_BAR:-1} == 0 ]] && return 0
  [[ -t 1 ]] || return 0

  local rows=${LINES:-0} cols=${COLUMNS:-0} line
  (( rows < 6 || cols < 30 )) && return 0

  line=$(__bottom_bar_compose "$cols") || return 0

  # Save cursor, reserve rows 1..rows-1, paint the last row, restore cursor.
  printf '\e7\e[1;%dr\e[%d;1H\e[K%s\e8' "$(( rows - 1 ))" "$rows" "$line"

  # Armed only now that a bar is actually on screen: drop the region and wipe
  # the bar row before the next command takes the terminal over. CUP to row 999
  # is clamped to the last row, so this needs no row count of its own.
  __bottom_bar_ps0=$'\e7\e[r\e[999;1H\e[K\e8'
}

__bottom_bar_release() {
  [[ -t 1 ]] || return 0
  printf '\e[r\e[%d;1H\e[K' "${LINES:-24}"
}

# Release sequence for the command that runs next, filled in by a successful
# draw. Expanded out of PS0 rather than written there literally so that a
# session with no bar (BOTTOM_BAR=0, a short window, a starship failure) does
# not clear a last row that holds real output.
__bottom_bar_ps0=""
case $PS0 in
  *'${__bottom_bar_ps0}'*) ;;
  *) PS0="${PS0}\${__bottom_bar_ps0}" ;;
esac

shopt -s checkwinsize
trap '__bottom_bar_draw' WINCH
trap '__bottom_bar_release' EXIT

if [[ ${PROMPT_COMMAND@a} == *a* ]]; then
  PROMPT_COMMAND+=(__bottom_bar_draw)
else
  PROMPT_COMMAND="${PROMPT_COMMAND:+$PROMPT_COMMAND$'\n'}__bottom_bar_draw"
fi
