#!/usr/bin/env bash
# Drop Omarchy preinstalls that aren't wanted on this kind of machine.
#
# The lists are data, not code -- edit config/remove/*.txt:
#   common.txt   every machine
#   client.txt   workstations only
#   remote.txt   headless boxes only
#
# pkg_remove skips anything another package depends on, so extending these
# lists cannot break `omarchy update`.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

declare -a wanted=()
for list in "$OMARCHY_SETUP_ROOT/config/remove/common.txt" \
            "$OMARCHY_SETUP_ROOT/config/remove/$SETUP_PROFILE.txt"; do
  while read -r pkg; do
    [[ -n $pkg ]] && wanted+=("$pkg")
  done < <(read_list "$list")
done

(( ${#wanted[@]} )) || { info "nothing listed for removal on profile '$SETUP_PROFILE'"; exit 0; }

info "removal candidates: ${wanted[*]}"
pkg_remove "${wanted[@]}"
