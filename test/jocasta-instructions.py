#!/usr/bin/env python3
"""Exercise generated Jocasta guidance without changing real agent settings."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temporary:
    home = Path(temporary)
    imported = home / ".claude/omarchy-setup"
    imported.mkdir(parents=True)
    (imported / "CLAUDE.md").write_bytes((root / "config/claude/CLAUDE.md").read_bytes())
    for name in ("ov-memory", "ov-memory-curation", "t3-backlog", "t3-campaign", "t3-wait"):
        skill = home / ".claude/skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# Fixture\n")
    codex = home / ".codex/AGENTS.md"
    codex.parent.mkdir()
    codex.write_text("# Existing instructions\nKeep this text.\n")
    opencode = home / ".config/opencode/opencode.json"
    opencode.parent.mkdir(parents=True)
    opencode.write_text(json.dumps({"instructions": ["original.md"], "model": "keep"}))
    opencode.chmod(0o600)
    command = ["bash", str(root / "config/bin/agents-instructions-gen")]
    env = dict(os.environ, HOME=str(home))
    subprocess.run(command, env=env, check=True, capture_output=True)
    first = codex.read_bytes()
    subprocess.run(command, env=env, check=True, capture_output=True)
    assert codex.read_bytes() == first
    assert b"Keep this text." in first
    assert first.count(b"<!-- jocasta:start -->") == 1
    guidance = (home / ".config/agents/jocasta.md").read_text()
    assert "30 days without a read or update" in guidance
    assert "Archived documents remain searchable" in guidance
    assert "Reading and editing code" not in guidance
    config = json.loads(opencode.read_text())
    assert config["model"] == "keep"
    assert config["instructions"] == ["original.md", str(home / ".config/agents/jocasta.md")]
    assert opencode.stat().st_mode & 0o777 == 0o600
print("Jocasta instruction generation: preservation and idempotence passed")
