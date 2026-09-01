#!/usr/bin/env bash
# Coding-agent configuration: Claude Code, its skills, and the ov-mcp server
# that gives every agent the shared OpenViking memory.
#
# Runs on both profiles -- a remote is often exactly where an agent runs. The
# agent binaries themselves come from mise (config/mise-tools.txt, 25-mise).
#
#   config/claude/CLAUDE.md        -> ~/.claude/omarchy-setup/CLAUDE.md (owned),
#                                     imported by one fenced @-line in ~/.claude/CLAUDE.md
#   config/claude/settings.json    -> merged into ~/.claude/settings.json (owned keys)
#   config/claude/skills/<name>/   -> ~/.claude/skills/<name>/ (owned files)
#   config/claude/skills.txt       -> npx skills add ... -g, for published skills
#   OV_MCP_REPO                    -> ~/.local/lib/ov-mcp + venv, registered as
#                                     the user-scope MCP server "ov-memory"
#   OV_BASE_URL                    -> ~/.config/ov-mcp/config.toml (owned)
source "${OMARCHY_SETUP_LIB:?}/common.sh"

CLAUDE_DIR="$HOME/.claude"
SRC="$OMARCHY_SETUP_ROOT/config/claude"

# ---- default agent ---------------------------------------------------------
# `omarchy default agent claude` ends by exec'ing the agent, so write the file
# it would write instead. Omarchy's menu and launchers read this file.
printf 'claude\n' | write_owned_file "$HOME/.config/omarchy/defaults/agent"

# ---- CLAUDE.md -------------------------------------------------------------
# Claude Code expands `@path` lines in CLAUDE.md, so the user file needs only
# one import. Markdown has no line comment; the fence uses an HTML comment.
write_owned_file "$CLAUDE_DIR/omarchy-setup/CLAUDE.md" <"$SRC/CLAUDE.md"
printf '@~/.claude/omarchy-setup/CLAUDE.md\n' |
  write_managed_block "$CLAUDE_DIR/CLAUDE.md" claude '<!--' '-->'

# ---- settings.json ---------------------------------------------------------
# No include mechanism, so the keys in config/claude/settings.json are merged
# in: scalars and objects from the repo win, permissions.allow is the union so
# an allow added on the machine survives. Nothing else in the file is touched.
merge_settings() {
  local file=$1 ours=$2 tmp cur
  cur=$(mktemp); tmp=$(mktemp)
  if [[ -s $file ]]; then cp "$file" "$cur"; else echo '{}' >"$cur"; fi
  jq -n --slurpfile c "$cur" --slurpfile o "$ours" '
    ($c[0] // {}) as $cur | $o[0] as $ours
    | ($cur * $ours)
    | .permissions.allow = ((($cur.permissions.allow // []) + ($ours.permissions.allow // [])) | unique)
  ' >"$tmp" || die "could not merge $file"
  rm -f "$cur"
  if [[ -f $file ]] && cmp -s <(jq -S . "$file") <(jq -S . "$tmp"); then
    rm -f "$tmp"; info "$(basename "$file"): already current"; return 0
  fi
  if (( DRY_RUN )); then
    printf '%s  would merge%s %s\n' "$C_DIM" "$C_RESET" "$file" >&2
    diff -u "$([[ -f $file ]] && printf %s "$file" || printf /dev/null)" "$tmp" | sed 's/^/      /' >&2 || true
    rm -f "$tmp"; return 0
  fi
  mkdir -p "$(dirname "$file")"
  backup_once "$file"
  chmod 0644 "$tmp"; mv "$tmp" "$file"
  ok "$(basename "$file"): merged"
}
merge_settings "$CLAUDE_DIR/settings.json" "$SRC/settings.json"

# ---- skills written here ---------------------------------------------------
for d in "$SRC"/skills/*/; do
  [[ -d $d ]] || continue
  name=$(basename "$d")
  for f in "$d"*; do
    [[ -f $f ]] || continue
    write_owned_file "$CLAUDE_DIR/skills/$name/$(basename "$f")" <"$f"
  done
done

# ---- published skills ------------------------------------------------------
# `npx skills add` is not idempotent-quiet, so each name is checked first. The
# Skills CLI installs globally to ~/.agents/skills and symlinks into
# ~/.claude/skills, which is the layout the check relies on.
if command -v npx >/dev/null 2>&1; then
  while read -r source names; do
    [[ -n $source ]] || continue
    for name in $names; do
      if [[ -e $CLAUDE_DIR/skills/$name ]]; then
        info "skill already installed: $name"
        continue
      fi
      step "installing skill: $name (from $source)"
      run npx -y skills add "$source" -g -y -a claude-code -s "$name" ||
        warn "could not install skill $name"
    done
  done < <(read_list "$SRC/skills.txt")
else
  warn "npx not found; skipping published skills (node comes from mise, see 25-mise)"
fi

# ---- ov-mcp ----------------------------------------------------------------
OV_MCP_DIR="$HOME/.local/lib/ov-mcp"
OV_PY="$OV_MCP_DIR/venv/bin/python"
ensure_cmd git
ensure_cmd python python

if [[ -d $OV_MCP_DIR/.git ]]; then
  if [[ -n $(git -C "$OV_MCP_DIR" status --porcelain 2>/dev/null) ]]; then
    warn "ov-mcp checkout has local changes; not pulling"
  else
    info "updating ov-mcp"
    run git -C "$OV_MCP_DIR" pull --ff-only -q || warn "ov-mcp pull failed; keeping current checkout"
  fi
elif [[ -e $OV_MCP_DIR ]]; then
  warn "$OV_MCP_DIR exists but is not a git checkout; leaving it alone"
else
  step "cloning ov-mcp"
  run git clone -q "$OV_MCP_REPO" "$OV_MCP_DIR"
fi

if [[ -x $OV_PY ]]; then
  info "ov-mcp venv present"
else
  step "creating ov-mcp venv"
  run python -m venv "$OV_MCP_DIR/venv"
fi
# The repo ships no requirements file; these two are its only imports.
if [[ -x $OV_PY ]] && "$OV_PY" -c 'import mcp, httpx' 2>/dev/null; then
  info "ov-mcp dependencies present"
else
  step "installing ov-mcp dependencies"
  run "$OV_MCP_DIR/venv/bin/pip" install -q mcp httpx
fi

# Machine config: address only. The key comes from OV_API_KEY (secrets.env),
# the api_key line here (never written by this repo), or the GNOME keyring.
{
  printf '# Written by omarchy-setup from OV_BASE_URL in config/defaults.conf.\n'
  printf 'base_url = "%s"\nagent = "claude-code"\ntimeout = 120\n' "$OV_BASE_URL"
} | write_owned_file "$HOME/.config/ov-mcp/config.toml"

if command -v claude >/dev/null 2>&1; then
  if claude mcp get ov-memory >/dev/null 2>&1; then
    info "MCP server ov-memory already registered"
  else
    step "registering MCP server ov-memory (user scope)"
    run claude mcp add --scope user ov-memory -- "$OV_PY" "$OV_MCP_DIR/server.py"
  fi
else
  warn "claude not on PATH; MCP server not registered (re-run after 25-mise has installed it)"
fi
