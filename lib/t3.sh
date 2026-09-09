#!/usr/bin/env bash
# Version arithmetic and upstream lookups for the T3 Code / t3-steward pair.
#
# Kept out of modules/common/26-t3.sh so the part that decides *which* versions
# to run can be tested without a network, an npm registry or a GitHub token:
# everything above the "upstream" banner is pure text handling.
#
# The pair is chosen by asking the steward binary what it was built against.
# `t3-steward version` ends with "tested with T3 <min>..<max>", which is the
# same range its control actions refuse to operate outside of, so a candidate
# steward answers the question "which T3 may I run" itself. Nothing here reads
# a README or a hand-maintained table.

[[ -n "${_OMARCHY_SETUP_T3:-}" ]] && return 0
_OMARCHY_SETUP_T3=1

# ---------------------------------------------------------------- versions --
# Dotted numeric versions, ordered by sort -V. Equal counts as ">=".
t3_ver_ge() {
  [[ $1 == "$2" ]] && return 0
  [[ $(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -1) == "$1" ]]
}

t3_ver_gt() {
  [[ $1 != "$2" ]] && t3_ver_ge "$1" "$2"
}

t3_ver_max() {
  if t3_ver_ge "$1" "$2"; then printf '%s\n' "$1"; else printf '%s\n' "$2"; fi
}

# The T3 range a steward binary declares, as "<min> <max>", from its own
# `version` output on stdin. Prints nothing when the binary is too old to say,
# which the caller must treat as "do not move the T3 pin".
t3_steward_range() {
  sed -n 's/.*tested with T3 \([0-9][0-9.]*\)\.\.\([0-9][0-9.]*\).*/\1 \2/p' | head -1
}

# Highest version on stdin that falls inside [min, max]. Prereleases (any
# version carrying a hyphen) are never picked automatically: a machine that
# upgrades itself should track what upstream considers finished.
t3_pick_version() {
  local min=$1 max=$2 v best=""
  while read -r v; do
    [[ -n $v ]] || continue
    [[ $v == *-* ]] && continue
    t3_ver_ge "$v" "$min" || continue
    t3_ver_ge "$max" "$v" || continue
    if [[ -z $best ]] || t3_ver_gt "$v" "$best"; then best=$v; fi
  done
  [[ -n $best ]] && printf '%s\n' "$best"
  return 0
}

# The T3 server version and the number of running threads, from
# `t3-steward check` output on stdin. Either prints nothing when the line is
# absent, which happens when the server is down or the steward is unconfigured.
t3_server_version() {
  sed -n 's/.*T3 server \([0-9][0-9.]*\) .*/\1/p' | head -1
}

t3_running_threads() {
  sed -n 's/.*shell snapshot: [0-9]* threads, \([0-9]*\) running.*/\1/p' | head -1
}

# ---------------------------------------------------------------- upstream --
# Both lookups reach the network, and both are called under `set -e` with
# `set -o pipefail` in force, so both end in `|| true`: a registry that is
# down, a rate-limited API or an npm that cannot run must leave the caller with
# an empty answer to act on, not take the whole module down with it.

# Every version npm has for the `t3` package, newest last.
t3_npm_versions() {
  {
    npm view t3 versions --json 2>/dev/null |
      jq -r 'if type == "array" then .[] else . end' 2>/dev/null |
      sort -V
  } || true
}

# Release tags of a GitHub repository, newest last, with the leading v removed.
# Drafts never appear; prereleases appear only when asked for, because the
# steward publishes them and this fleet has run them deliberately.
#
#   t3_github_releases <owner/repo> [include_prereleases 0|1]
t3_github_releases() {
  local repo=$1 pre=${2:-0}
  local -a auth=()
  local token=""
  # gh's token lifts the 60/hour anonymous rate limit; its absence is fine.
  token=$(gh auth token 2>/dev/null) || token=""
  [[ -n $token ]] && auth=(-H "Authorization: Bearer $token")

  {
    curl -fsSL --max-time 20 "${auth[@]}" \
      -H 'Accept: application/vnd.github+json' \
      -H 'X-GitHub-Api-Version: 2022-11-28' \
      "https://api.github.com/repos/$repo/releases?per_page=30" 2>/dev/null |
      jq -r --argjson pre "$pre" '
        .[]
        | select(.draft | not)
        | select($pre == 1 or (.prerelease | not))
        | .tag_name
      ' 2>/dev/null |
      sed 's/^v//' |
      sort -V
  } || true
}
