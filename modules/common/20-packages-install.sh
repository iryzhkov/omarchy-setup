#!/usr/bin/env bash
# Runs one script per package from packages/{common,<profile>}/.
# Each package owns its own install *and* any post-install config, and stays
# runnable on its own:  bash packages/common/ripgrep.sh
source "${OMARCHY_SETUP_LIB:?}/common.sh"

declare -a scripts=()
while IFS=$'\t' read -r _ path; do scripts+=("$path"); done < <(
  for d in "$OMARCHY_SETUP_ROOT/packages/common" "$OMARCHY_SETUP_ROOT/packages/$SETUP_PROFILE"; do
    [[ -d $d ]] || continue
    for f in "$d"/*.sh; do
      [[ -f $f ]] && printf '%s\t%s\n' "$(basename "$f")" "$f"
    done
  done | sort -t$'\t' -k1,1
)

(( ${#scripts[@]} )) || { info "no package scripts for profile '$SETUP_PROFILE'"; exit 0; }

failed=0
for s in "${scripts[@]}"; do
  name=$(basename "$s" .sh)
  if bash "$s"; then :; else fail "package script failed: $name"; failed=1; fi
done
exit "$failed"
