#!/usr/bin/env bash
# sshd for headless boxes.
#
# The heavy lifting is Omarchy's own `omarchy setup security sshd`, which
# installs and enables sshd, opens the firewall (`ufw limit 22/tcp`, rate
# limited against brute force), and authorizes keys straight from
# https://github.com/<user>.keys -- so a fresh machine trusts your existing
# GitHub keys with nothing to copy by hand. It is idempotent and explicitly
# supports unattended use via --gh-keys.
#
# On top of that this module turns password auth off, which Omarchy
# deliberately leaves alone, and exempts the trusted home subnets from the
# rate limit: ufw's LIMIT refuses a source that opens six connections in 30
# seconds, and the steward's admin transport and parallel agents open SSH
# connections faster than that.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

# GITHUB_USER comes from config/defaults.conf via common.sh (--github-user).
SSH_PUBKEY=""
HARDEN_PASSWORD_AUTH=1
SSH_TRUSTED_SUBNETS=(192.168.70.0/24 192.168.90.0/24)
conf="$OMARCHY_SETUP_ROOT/config/ssh.conf"
[[ -f $conf ]] && source "$conf"

# Where sshd's configuration lives. Overridable only so the tests can point the
# module at a fixture tree.
SSHD_DIR=${OMARCHY_SETUP_SSHD_DIR:-/etc/ssh}
DROPIN="$SSHD_DIR/sshd_config.d/50-omarchy-setup.conf"
# The ufw comment that marks a rule as this module's. Only rules carrying it
# are ever removed; an equivalent rule without it belongs to someone else.
OWNED_COMMENT=omarchy-sshd-trusted
# A shorter prefix would exempt more than a home VLAN.
MIN_PREFIX=16

# ------------------------------------------------------ trusted subnet list --
# Prints the canonical form of an IPv4 network (no leading zeros), or prints
# why it is not one and returns 1.
canonical_subnet() {
  local re='^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})/([0-9]{1,2})$'
  [[ $1 =~ $re ]] || { echo "not an IPv4 network in a.b.c.d/prefix form"; return 1; }
  local o1=$((10#${BASH_REMATCH[1]})) o2=$((10#${BASH_REMATCH[2]}))
  local o3=$((10#${BASH_REMATCH[3]})) o4=$((10#${BASH_REMATCH[4]}))
  local prefix=$((10#${BASH_REMATCH[5]})) octet
  for octet in "$o1" "$o2" "$o3" "$o4"; do
    (( octet <= 255 )) || { echo "octet $octet is above 255"; return 1; }
  done
  if (( prefix < MIN_PREFIX || prefix > 32 )); then
    echo "prefix /$prefix is outside /$MIN_PREFIX to /32"
    return 1
  fi
  local addr=$(( (o1 << 24) | (o2 << 16) | (o3 << 8) | o4 ))
  local mask=$(( (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF ))
  local net=$(( addr & mask ))
  if (( net != addr )); then
    printf 'host bits are set; the network is %d.%d.%d.%d/%d\n' \
      $((net >> 24)) $(((net >> 16) & 255)) $(((net >> 8) & 255)) $((net & 255)) "$prefix"
    return 1
  fi
  printf '%d.%d.%d.%d/%d\n' "$o1" "$o2" "$o3" "$o4" "$prefix"
}

# The whole list is validated before anything on the host is touched.
DESIRED=()
invalid=""
for entry in "${SSH_TRUSTED_SUBNETS[@]}"; do
  if canonical=$(canonical_subnet "$entry"); then
    [[ " ${DESIRED[*]} " == *" $canonical "* ]] || DESIRED+=("$canonical")
  else
    invalid+="  '$entry': $canonical"$'\n'
  fi
done
[[ -z $invalid ]] || die "refusing to run: SSH_TRUSTED_SUBNETS in config/ssh.conf has invalid entries, and nothing was changed:
${invalid%$'\n'}"

# ---------------------------------------------------------- omarchy sshd ----
[[ -n $GITHUB_USER || -n $SSH_PUBKEY ]] ||
  die "set GITHUB_USER or SSH_PUBKEY in config/ssh.conf"

if [[ -n $GITHUB_USER ]]; then
  # Fail early and legibly: an account with no published keys returns 200 with
  # an empty body, and omarchy's command would then abort mid-setup.
  if keys=$(curl -fsSL "https://github.com/$GITHUB_USER.keys" 2>/dev/null) && [[ -n $keys ]]; then
    step "sshd + firewall + GitHub keys for '$GITHUB_USER'"
    run omarchy setup security sshd --gh-keys "$GITHUB_USER"
  elif [[ -n $SSH_PUBKEY ]]; then
    warn "no public keys at https://github.com/$GITHUB_USER.keys; using SSH_PUBKEY instead"
  else
    die "https://github.com/$GITHUB_USER.keys has no keys, and no SSH_PUBKEY is set.
      Publish one with: gh ssh-key add ~/.ssh/id_ed25519.pub
      or set SSH_PUBKEY in config/ssh.conf"
  fi
fi

# Applied separately: omarchy's command refuses --key and --gh-keys together.
if [[ -n $SSH_PUBKEY ]]; then
  step "sshd + firewall + literal public key"
  run omarchy setup security sshd --key="$SSH_PUBKEY"
fi

# ------------------------------------------------------- hardening drop-in --
# Our own drop-in rather than a managed block: /etc/ssh/sshd_config is
# root-owned and package-managed, and this file is entirely ours.
DROPIN_CHANGED=0
DROPIN_PREVIOUS=""   # a copy of the drop-in this run replaced, if there was one
harden_password_auth() {
  local tmp
  tmp=$(mktemp); register_cleanup "$tmp"
  cat >"$tmp" <<'CONF'
# Managed by omarchy-setup. Edits here are overwritten on the next run.
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
CONF

  if [[ -f $DROPIN ]] && cmp -s "$tmp" "$DROPIN"; then
    info "sshd hardening drop-in already current"
    return 0
  fi

  # Never disable passwords without a working key: that is how you lock
  # yourself out of a remote box permanently. The --gh-keys step above should
  # have just populated this, so an empty file means that step did not do what
  # we expect.
  if [[ ! -s ${HOME}/.ssh/authorized_keys ]]; then
    if (( DRY_RUN )); then
      warn "would refuse to disable password auth: ~/.ssh/authorized_keys is empty"
      return 0
    fi
    die "refusing to disable password auth: ~/.ssh/authorized_keys is empty after --gh-keys"
  fi

  if [[ -f $DROPIN ]]; then
    DROPIN_PREVIOUS=$(mktemp); register_cleanup "$DROPIN_PREVIOUS"
    cp "$DROPIN" "$DROPIN_PREVIOUS"
  fi
  run sudo install -D -m 0644 -o root -g root "$tmp" "$DROPIN"
  (( DRY_RUN )) || DROPIN_CHANGED=1
}

restore_dropin() {
  (( DROPIN_CHANGED )) || return 0
  if [[ -n $DROPIN_PREVIOUS ]]; then
    sudo install -m 0644 -o root -g root "$DROPIN_PREVIOUS" "$DROPIN"
    warn "restored the previous $DROPIN"
  else
    sudo rm -f -- "$DROPIN"
    warn "removed the new $DROPIN"
  fi
}

if (( HARDEN_PASSWORD_AUTH )); then
  harden_password_auth
else
  info "leaving password authentication enabled"
fi

# ---------------------------------------------------------- ufw reading -----
# Fills UFW_ACTIVE and, for every IPv4 rule on port 22 (`22/tcp` or `22`),
# RULE_NUM, RULE_ACTION, RULE_FROM and RULE_COMMENT from a fresh
# `ufw status numbered`. IPv6 rows render as `22/tcp (v6)` and are counted in
# V6_LIMITS instead. Every decision reads a fresh snapshot.
ufw_read() {
  local status line
  local re='^\[ *([0-9]+)\] +22(/tcp)? +([A-Z]+)( IN)? +([^ ]+) *(# (.*))?$'
  local re6='^\[ *[0-9]+\] +22(/tcp)? \(v6\) +LIMIT( IN)? +Anywhere \(v6\)'
  status=$(sudo ufw status numbered) || die "ufw status failed"
  UFW_ACTIVE=0; [[ $status == *"Status: active"* ]] && UFW_ACTIVE=1
  RULE_NUM=() RULE_ACTION=() RULE_FROM=() RULE_COMMENT=() V6_LIMITS=0
  while IFS= read -r line; do
    line=${line%"${line##*[![:space:]]}"}
    if [[ $line =~ $re ]]; then
      RULE_NUM+=("${BASH_REMATCH[1]}") RULE_ACTION+=("${BASH_REMATCH[3]}")
      RULE_FROM+=("${BASH_REMATCH[5]}") RULE_COMMENT+=("${BASH_REMATCH[7]}")
    elif [[ $line =~ $re6 ]]; then
      V6_LIMITS=$((V6_LIMITS + 1))
    fi
  done <<<"$status"
}

# Index into RULE_* of the first rule with <action> from <source>, or nothing.
rule_index() {
  local i
  for i in "${!RULE_NUM[@]}"; do
    if [[ ${RULE_ACTION[i]} == "$1" && ${RULE_FROM[i]} == "$2" ]]; then
      echo "$i"
      return 0
    fi
  done
}

limit_count() {
  local i n=0
  for i in "${!RULE_NUM[@]}"; do
    [[ ${RULE_ACTION[i]} == LIMIT && ${RULE_FROM[i]} == Anywhere ]] && n=$((n + 1))
  done
  echo "$n"
}

owned_rule_spec() { printf 'allow proto tcp from %s to any port 22 comment %s' "$1" "$OWNED_COMMENT"; }

# Untagged port-22 ALLOW rules for a specific source exempt that source just as
# well, but they are not ours to remove, so they are reported on every run.
report_unmanaged() {
  local i limit_num="" where
  i=$(rule_index LIMIT Anywhere); [[ -z $i ]] || limit_num=${RULE_NUM[i]}
  for i in "${!RULE_NUM[@]}"; do
    [[ ${RULE_ACTION[i]} == ALLOW && ${RULE_FROM[i]} != Anywhere && ${RULE_COMMENT[i]} != "$OWNED_COMMENT" ]] || continue
    where=""
    if [[ -n $limit_num ]]; then
      if (( RULE_NUM[i] < limit_num )); then where=", ahead of the LIMIT"; else where=", behind the LIMIT so it exempts nothing"; fi
    fi
    warn "unmanaged exemption: ${RULE_FROM[i]} (ufw rule ${RULE_NUM[i]}${RULE_COMMENT[i]:+, comment '${RULE_COMMENT[i]}'}$where); not tagged $OWNED_COMMENT, so this module never removes it"
  done
}

# Removes every rule this module owns for a source not in DESIRED, by full
# rule specification, so a stale number can never delete the wrong rule.
revoke_undesired() {
  local i
  for i in "${!RULE_NUM[@]}"; do
    [[ ${RULE_ACTION[i]} == ALLOW && ${RULE_COMMENT[i]} == "$OWNED_COMMENT" ]] || continue
    [[ " ${DESIRED[*]} " == *" ${RULE_FROM[i]} "* ]] && continue
    # shellcheck disable=SC2046 # the rule specification is words by design
    run sudo ufw delete $(owned_rule_spec "${RULE_FROM[i]}")
    info "${RULE_FROM[i]}: owned exemption revoked"
  done
}

# Grants nothing: removes every owned exemption, reports the rest, and stops.
refuse_exemptions() {
  if (( DRY_RUN )); then
    warn "dry run: $1"
    exit 0
  fi
  ufw_read
  if (( UFW_ACTIVE )); then
    DESIRED=()
    revoke_undesired
    ufw_read
    report_unmanaged
  else
    warn "ufw is not active, so owned exemption rules could not be listed or revoked"
  fi
  die "$1"
}

# ------------------------------------------------ sshd: running and gated --
# Validation and reload happen in this run, even when the drop-in did not
# change, so the exemption rests on what the running daemon loaded rather than
# on what is on disk. A failure restores the drop-in this run replaced.
if (( DROPIN_CHANGED || ${#DESIRED[@]} )); then
  failure=""
  if ! run sudo sshd -t; then
    failure="sshd -t rejected the configuration"
  elif ! run sudo systemctl reload sshd; then
    failure="reload sshd failed"
  fi
  if [[ -n $failure ]]; then
    restore_dropin
    refuse_exemptions "refusing to exempt any subnet from the SSH rate limit: $failure, so the running sshd is not known to be key-only."
  fi
  if (( DROPIN_CHANGED )); then
    ok "password authentication disabled; key-only access via GitHub keys"
  fi
fi

if (( ${#DESIRED[@]} == 0 )); then
  ufw_read
  if (( UFW_ACTIVE )); then
    revoke_undesired
    ufw_read
    report_unmanaged
  fi
  info "no trusted SSH subnets configured; port 22 stays rate limited for every source"
  exit 0
fi

step "SSH rate-limit exemption for ${DESIRED[*]}"

# Every sshd configuration file, following Include lines (relative paths are
# relative to the configuration directory, as sshd resolves them).
sshd_config_files() {
  local -a queue=("$SSHD_DIR/sshd_config") patterns
  local seen=" " file line pattern match
  local re='^[[:space:]]*[Ii][Nn][Cc][Ll][Uu][Dd][Ee][[:space:]]+(.*)$'
  while (( ${#queue[@]} )); do
    file=${queue[0]}; queue=("${queue[@]:1}")
    [[ $seen == *" $file "* ]] && continue
    seen+="$file "
    printf '%s\n' "$file"
    while IFS= read -r line; do
      [[ $line =~ $re ]] || continue
      read -ra patterns <<<"${BASH_REMATCH[1]}"
      for pattern in "${patterns[@]}"; do
        [[ $pattern == /* ]] || pattern="$SSHD_DIR/$pattern"
        while IFS= read -r match; do
          [[ -n $match ]] && queue+=("$match")
        done < <(compgen -G "$pattern" | sort)
      done
    done < <(sudo cat -- "$file" 2>/dev/null)
  done
}

# Prints one line per reason the sshd configuration is unsafe to exempt from
# the rate limit, or nothing. Conservative on purpose: any Match block at all
# refuses, because `sshd -T` shows only the global settings and a Match can
# grant passwords or root login to some sources.
sshd_exemption_blockers() {
  local file effective key got matches
  while IFS= read -r file; do
    if ! sudo test -r "$file"; then
      printf '%s: cannot be read\n' "$file"
      continue
    fi
    matches=$(sudo grep -niE '^[[:space:]]*match[[:space:]]' -- "$file" || true)
    [[ -z $matches ]] || printf '%s:%s\n' "$file" "${matches//$'\n'/$'\n'"$file":}"
  done < <(sshd_config_files)
  if ! effective=$(sudo sshd -T 2>&1); then
    printf 'sshd -T failed: %s\n' "$(head -n 1 <<<"$effective")"
    return 0
  fi
  for key in passwordauthentication kbdinteractiveauthentication permitrootlogin; do
    got=$(awk -v k="$key" '$1 == k { print $2; exit }' <<<"$effective")
    [[ $got == no ]] || printf '%s is %s, not no\n' "$key" "${got:-unset}"
  done
}

blockers=$(sshd_exemption_blockers)
if [[ -n $blockers ]]; then
  refuse_exemptions "refusing to exempt ${DESIRED[*]} from the SSH rate limit. An ALLOW rule removes brute-force limiting for every address on those subnets, so it is granted only while sshd is key-only with no exceptions. Blocking:
$blockers
To grant it: remove every Match block listed above, and make sure 'sshd -T' reports passwordauthentication, kbdinteractiveauthentication and permitrootlogin as no. Or set SSH_TRUSTED_SUBNETS=() in config/ssh.conf to keep every source rate limited. Rules tagged $OWNED_COMMENT are revoked by this refusal."
fi

# ------------------------------------------------- firewall: fail closed ----
ufw_read
(( UFW_ACTIVE )) || die "refusing to exempt any subnet: ufw is not active, so there is no '22/tcp LIMIT Anywhere' rule to place an exemption ahead of"
limits=$(limit_count)
(( limits == 1 )) || die "refusing to exempt any subnet: expected exactly one IPv4 '22/tcp LIMIT Anywhere' rule and found $limits. Make exactly one exist first ('omarchy setup security sshd' creates it with 'ufw limit 22/tcp'); an ALLOW is never added without a single LIMIT behind it."
open=$(rule_index ALLOW Anywhere)
[[ -z $open ]] || die "refusing to exempt any subnet: ufw rule ${RULE_NUM[open]} already allows port 22 from Anywhere, so the rate limit is not what it seems. Remove that rule first."
limit_num=${RULE_NUM[$(rule_index LIMIT Anywhere)]}
for i in "${!RULE_NUM[@]}"; do
  if [[ ${RULE_ACTION[i]} == ALLOW && ${RULE_COMMENT[i]} == "$OWNED_COMMENT" ]] && (( RULE_NUM[i] > limit_num )); then
    die "refusing to change the firewall: owned rule ${RULE_NUM[i]} for ${RULE_FROM[i]} sits behind the LIMIT rule $limit_num, which this module never creates. Inspect 'sudo ufw status numbered' and remove it with: sudo ufw delete $(owned_rule_spec "${RULE_FROM[i]}")"
  fi
done
v6_before=$V6_LIMITS

# --------------------------------------------- firewall: reconcile owned ----
revoke_undesired
for subnet in "${DESIRED[@]}"; do
  ufw_read
  i=$(rule_index ALLOW "$subnet")
  if [[ -n $i ]]; then
    if [[ ${RULE_COMMENT[i]} == "$OWNED_COMMENT" ]]; then
      info "$subnet: owned exemption already ahead of the rate limit"
    fi
    continue   # an untagged equivalent is reported, and checked below
  fi
  limit_num=${RULE_NUM[$(rule_index LIMIT Anywhere)]}
  # shellcheck disable=SC2046 # the rule specification is words by design
  run sudo ufw insert "$limit_num" $(owned_rule_spec "$subnet")
  ok "$subnet: SSH allowed ahead of the rate limit"
done

# ------------------------------------------------ firewall: verify ----------
ufw_read
report_unmanaged
(( DRY_RUN )) && exit 0
problems=""
limits=$(limit_count)
if (( limits != 1 )); then
  problems+="  expected one IPv4 '22/tcp LIMIT Anywhere' rule, found $limits"$'\n'
else
  limit_num=${RULE_NUM[$(rule_index LIMIT Anywhere)]}
  for subnet in "${DESIRED[@]}"; do
    i=$(rule_index ALLOW "$subnet")
    if [[ -z $i ]]; then
      problems+="  $subnet: no ALLOW rule"$'\n'
    elif (( RULE_NUM[i] > limit_num )); then
      problems+="  $subnet: ALLOW rule ${RULE_NUM[i]} is behind the LIMIT rule $limit_num"$'\n'
    fi
  done
fi
for i in "${!RULE_NUM[@]}"; do
  if [[ ${RULE_COMMENT[i]} == "$OWNED_COMMENT" && " ${DESIRED[*]} " != *" ${RULE_FROM[i]} "* ]]; then
    problems+="  ${RULE_FROM[i]}: owned rule ${RULE_NUM[i]} should have been revoked"$'\n'
  fi
done
(( V6_LIMITS == v6_before )) || problems+="  IPv6 LIMIT rows changed from $v6_before to $V6_LIMITS"$'\n'
[[ -z $problems ]] || die "the firewall does not have the expected order after this run; inspect 'sudo ufw status numbered':
${problems%$'\n'}"
ok "verified: ${DESIRED[*]} ahead of the single '22/tcp LIMIT Anywhere' rule"
