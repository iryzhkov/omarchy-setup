#!/usr/bin/env python3
"""Exercise the generated agent instructions without changing real agent settings."""
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
    skills = ("ov-memory", "ov-memory-curation", "t3-backlog", "t3-campaign", "t3-wait")
    for name in skills:
        skill = home / ".claude/skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# Fixture\n")
    huyang = home / ".claude/skills/huyang"
    huyang.mkdir(parents=True)
    (huyang / "SKILL.md").write_text("---\nname: huyang\n---\n\n# Cheapest correct call\n")
    codex = home / ".codex/AGENTS.md"
    codex.parent.mkdir()
    # A host that still carries the superseded Jocasta block, plus text of the user's own.
    codex.write_text(
        "# Existing instructions\nKeep this text.\n\n"
        "<!-- jocasta:start -->\n## Shared working documents\n<!-- jocasta:end -->\n"
    )
    opencode = home / ".config/opencode/opencode.json"
    opencode.parent.mkdir(parents=True)
    opencode.write_text(json.dumps({
        "instructions": [
            "original.md",
            str(home / ".config/agents/t3-steward.md"),
            str(home / ".config/agents/jocasta.md"),
        ],
        "model": "keep",
    }))
    opencode.chmod(0o600)
    command = ["bash", str(root / "config/bin/agents-instructions-gen")]
    env = dict(os.environ, HOME=str(home))
    subprocess.run(command, env=env, check=True, capture_output=True)
    first = codex.read_bytes()
    subprocess.run(command, env=env, check=True, capture_output=True)
    assert codex.read_bytes() == first, "a second run must not change ~/.codex/AGENTS.md"
    assert b"Keep this text." in first
    assert first.count(b"<!-- fleet:start -->") == 1
    assert b"jocasta:start" not in first, "the superseded block must be replaced, not kept"
    assert first.count(b"## OV memory") == 1

    shared = (home / ".config/agents/AGENTS.md").read_text()
    assert "## Reading and editing code" in shared
    assert "the `publish-agent-tooling` skill" in shared
    assert shared.strip() in first.decode(), "the Codex block carries the shared pointer"

    guidance = (home / ".config/agents/jocasta.md").read_text()
    assert "30 days without a read or update" in guidance
    assert "Reading and editing code" not in guidance
    assert "~/.config/agents/jocasta.md" not in guidance, "the file must not point at itself"

    huyang_reference = (home / ".config/agents/huyang.md").read_text()
    assert "# Reading and editing code" in huyang_reference
    assert "# Cheapest correct call" in huyang_reference, "the skill body is appended"
    assert "name: huyang" not in huyang_reference, "skill front matter is stripped"

    config = json.loads(opencode.read_text())
    assert config["model"] == "keep"
    assert config["instructions"] == [str(home / ".config/agents/AGENTS.md"), "original.md"], (
        "only the shared pointer is loaded into every session; foreign entries are kept"
    )
    assert opencode.stat().st_mode & 0o777 == 0o600
print("Shared agent instruction generation: preservation and idempotence passed")
