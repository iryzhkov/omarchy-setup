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
# All this module adds on top is turning password auth off, which Omarchy
# deliberately leaves alone.
source "${OMARCHY_SETUP_LIB:?}/common.sh"

# GITHUB_USER comes from config/defaults.conf via common.sh (--github-user).
SSH_PUBKEY=""
HARDEN_PASSWORD_AUTH=1
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

(( HARDEN_PASSWORD_AUTH )) || { info "leaving password authentication enabled"; exit 0; }

# Our own drop-in rather than a managed block: /etc/ssh/sshd_config is
# root-owned and package-managed, and this file is entirely ours.
DROPIN=/etc/ssh/sshd_config.d/50-omarchy-setup.conf
tmp=$(mktemp); register_cleanup "$tmp"
cat >"$tmp" <<'CONF'
# Managed by omarchy-setup. Edits here are overwritten on the next run.
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
CONF

if [[ -f $DROPIN ]] && cmp -s "$tmp" "$DROPIN"; then
  info "sshd hardening drop-in already current"
  exit 0
fi

# Never disable passwords without a working key: that is how you lock yourself
# out of a remote box permanently. The --gh-keys step above should have just
# populated this, so an empty file means that step did not do what we expect.
if [[ ! -s ${HOME}/.ssh/authorized_keys ]]; then
  if (( DRY_RUN )); then
    warn "would refuse to disable password auth: ~/.ssh/authorized_keys is empty"
    exit 0
  fi
  die "refusing to disable password auth: ~/.ssh/authorized_keys is empty after --gh-keys"
fi

run sudo install -D -m 0644 -o root -g root "$tmp" "$DROPIN"
run sudo sshd -t
run sudo systemctl reload sshd
ok "password authentication disabled; key-only access via GitHub keys"
