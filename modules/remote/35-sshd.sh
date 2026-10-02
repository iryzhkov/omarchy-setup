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
# connections far faster than that.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

# GITHUB_USER comes from config/defaults.conf via common.sh (--github-user).
SSH_PUBKEY=""
HARDEN_PASSWORD_AUTH=1
SSH_TRUSTED_SUBNETS=(192.168.70.0/24 192.168.90.0/24)
conf="$OMARCHY_SETUP_ROOT/config/ssh.conf"
[[ -f $conf ]] && source "$conf"

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

# Our own drop-in rather than a managed block: /etc/ssh/sshd_config is
# root-owned and package-managed, and this file is entirely ours.
harden_password_auth() {
  local dropin=/etc/ssh/sshd_config.d/50-omarchy-setup.conf tmp
  tmp=$(mktemp); register_cleanup "$tmp"
  cat >"$tmp" <<'CONF'
# Managed by omarchy-setup. Edits here are overwritten on the next run.
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
CONF

  if [[ -f $dropin ]] && cmp -s "$tmp" "$dropin"; then
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

  run sudo install -D -m 0644 -o root -g root "$tmp" "$dropin"
  run sudo sshd -t
  run sudo systemctl reload sshd
  ok "password authentication disabled; key-only access via GitHub keys"
}

if (( HARDEN_PASSWORD_AUTH )); then
  harden_password_auth
else
  info "leaving password authentication enabled"
fi

# ------------------------------------------------- trusted-subnet exemption --
# An ALLOW rule for a subnet, inserted ahead of Omarchy's
# `22/tcp LIMIT Anywhere`, lets that subnet reach sshd without the rate limit;
# ufw stops at the first matching rule, so LIMIT still applies to every other
# source. Exempting a subnet removes brute-force rate limiting for every
# address on it, which is acceptable only while sshd accepts keys alone, so
# the exemption is applied only when the effective configuration for a
# connection from that subnet has password, keyboard-interactive and root
# login all disabled.
TRUSTED_RULE_COMMENT="omarchy-setup: ssh from trusted subnet"

# Prints one line per reason the effective sshd configuration for a connection
# from <subnet> is unsafe to exempt from the rate limit; prints nothing when
# it is safe. `sshd -T -C` evaluates Match blocks for that source, so a Match
# that turns passwords back on for the subnet is caught too.
sshd_exemption_blockers() {
  local subnet=$1 addr=${1%/*} user effective key got
  user=$(id -un)
  if ! effective=$(sudo sshd -T -C "user=$user,host=$addr,addr=$addr" 2>&1); then
    printf '%s: sshd -T failed: %s\n' "$subnet" "$(head -n 1 <<<"$effective")"
    return 0
  fi
  for key in passwordauthentication kbdinteractiveauthentication permitrootlogin; do
    got=$(awk -v k="$key" '$1 == k { print $2; exit }' <<<"$effective")
    [[ $got == no ]] || printf '%s: %s is %s, not no\n' "$subnet" "$key" "${got:-unset}"
  done
  return 0
}

# Number of the first IPv4 port-22 rule with <action> and source <from> in the
# `ufw status numbered` output on stdin, or nothing. IPv6 rules render their
# port as `22/tcp (v6)` and never match, and a rule without a protocol (`22`)
# covers TCP, so it counts.
ufw_ssh_rule() {
  local action=$1 from=$2 line
  local re='^\[ *([0-9]+)\] +22(/tcp)? +([A-Z]+)( IN)? +([^ ]+)'
  while IFS= read -r line; do
    if [[ $line =~ $re && ${BASH_REMATCH[3]} == "$action" && ${BASH_REMATCH[5]} == "$from" ]]; then
      printf '%s\n' "${BASH_REMATCH[1]}"
      return 0
    fi
  done
  return 0
}

# Idempotent: a subnet already allowed ahead of the LIMIT rule is left exactly
# where it is, an ALLOW that sits behind the LIMIT (where it never matches) is
# moved ahead of it, and a missing one is inserted directly before it.
ensure_trusted_allow() {
  local subnet=$1 status limit allow
  status=$(sudo ufw status numbered) || die "ufw status failed"
  limit=$(ufw_ssh_rule LIMIT Anywhere <<<"$status")
  allow=$(ufw_ssh_rule ALLOW "$subnet" <<<"$status")

  if [[ -z $limit ]]; then
    if [[ -n $allow ]]; then
      info "$subnet: already allowed; no LIMIT rule for 22/tcp"
      return 0
    fi
    warn "no '22/tcp LIMIT Anywhere' rule found; appending the ALLOW for $subnet"
    run sudo ufw allow proto tcp from "$subnet" to any port 22 comment "$TRUSTED_RULE_COMMENT"
    return 0
  fi

  if [[ -n $allow ]] && (( allow < limit )); then
    info "$subnet: already allowed ahead of the rate limit"
    return 0
  fi
  if [[ -n $allow ]]; then
    # Behind the LIMIT rule, so deleting it leaves the LIMIT's number alone.
    warn "$subnet: ALLOW rule $allow sits behind the LIMIT rule $limit; moving it ahead"
    run sudo ufw --force delete "$allow"
  fi
  run sudo ufw insert "$limit" allow proto tcp from "$subnet" to any port 22 comment "$TRUSTED_RULE_COMMENT"
  ok "$subnet: SSH allowed ahead of the rate limit"
}

allow_trusted_subnets() {
  if (( ${#SSH_TRUSTED_SUBNETS[@]} == 0 )); then
    info "no trusted SSH subnets configured; port 22 stays rate limited for every source"
    return 0
  fi
  local subnet out reasons=""
  for subnet in "${SSH_TRUSTED_SUBNETS[@]}"; do
    [[ $subnet =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$ ]] ||
      die "SSH_TRUSTED_SUBNETS entry is not an IPv4 CIDR: '$subnet'"
  done

  step "SSH rate-limit exemption for ${SSH_TRUSTED_SUBNETS[*]}"
  for subnet in "${SSH_TRUSTED_SUBNETS[@]}"; do
    out=$(sshd_exemption_blockers "$subnet")
    [[ -z $out ]] || reasons+="$out"$'\n'
  done
  if [[ -n $reasons ]]; then
    local msg="refusing to exempt ${SSH_TRUSTED_SUBNETS[*]} from the SSH rate limit: an ALLOW rule removes brute-force limiting for every address on those subnets, so it needs password, keyboard-interactive and root login disabled in the effective sshd configuration.
${reasons%$'\n'}
Fix the sshd configuration, or set SSH_TRUSTED_SUBNETS=() in config/ssh.conf to keep every source rate limited."
    if (( DRY_RUN )); then
      warn "dry run: $msg"
      return 0
    fi
    die "$msg"
  fi

  local status
  status=$(sudo ufw status numbered) || die "ufw status failed"
  if [[ $status != *"Status: active"* ]]; then
    warn "ufw is not active; no rate limit to exempt from"
    return 0
  fi
  for subnet in "${SSH_TRUSTED_SUBNETS[@]}"; do
    ensure_trusted_allow "$subnet"
  done
}

allow_trusted_subnets
