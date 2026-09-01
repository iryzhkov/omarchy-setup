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
#
# Opt-in: this is the only step that takes something away, and a package on
# the list may have been installed on purpose since. It runs only with
# --remove-packages (REMOVE_PACKAGES=1); by default it just reports what it
# would remove, so a routine or unattended re-run never uninstalls anything.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

declare -a wanted=()
for list in "$OMARCHY_SETUP_ROOT/config/remove/common.txt" \
            "$OMARCHY_SETUP_ROOT/config/remove/$SETUP_PROFILE.txt"; do
  while read -r pkg; do
    [[ -n $pkg ]] && wanted+=("$pkg")
  done < <(read_list "$list")
done

(( ${#wanted[@]} )) || { info "nothing listed for removal on profile '$SETUP_PROFILE'"; exit 0; }

declare -a present=()
for pkg in "${wanted[@]}"; do
  pacman -Qq "$pkg" &>/dev/null && present+=("$pkg")
done
(( ${#present[@]} )) || { info "none of the listed packages are installed"; exit 0; }

if [[ ${REMOVE_PACKAGES:-0} != 1 ]]; then
  warn "installed and listed for removal, kept (pass --remove-packages to remove): ${present[*]}"
  exit 0
fi

info "removal candidates: ${present[*]}"
pkg_remove "${present[@]}"
