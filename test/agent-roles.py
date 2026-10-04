#!/usr/bin/env python3
"""Static M14 frontend contracts, isolated homes and pinned consumer envelope."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib

root = Path(__file__).resolve().parents[1]
generator = root / "config/bin/agents-instructions-gen"
fixtures = root / "test/fixtures/m14"
raw = (fixtures / "initial-policy.yaml").read_bytes()
response = json.loads((fixtures / "consumer-show.json").read_text())
assert response["digest"] == hashlib.sha256(raw).hexdigest()
roles = ("reader", "executor", "reviewer", "critical-reviewer", "planner")


def snapshot(home):
    return {str(p.relative_to(home)): p.read_bytes()
            for p in home.rglob("*") if p.is_file() and not p.is_symlink()}


with tempfile.TemporaryDirectory() as temporary:
    base = Path(temporary)
    home = base / "home"
    home.mkdir()
    policy = base / "policy.yaml"
    policy.write_bytes(raw)
    binaries = base / "bin"
    binaries.mkdir()
    fake = binaries / "t3-steward"
    fake.write_text("""#!/usr/bin/env python3
import hashlib, json, os, pathlib, sys
assert sys.argv[1:4] == ['policy', 'show', '--file']
assert sys.argv[4] == os.environ['EXPECTED_POLICY']
assert sys.argv[5:] == ['--json']
if os.environ.get('FAIL'):
    sys.exit(9)
if os.environ.get('RACE'):
    pathlib.Path(sys.argv[4]).write_text('changed')
print(os.environ['RESPONSE'])
""")
    fake.chmod(0o755)
    environment = dict(os.environ, HOME=str(home), PATH=str(binaries) + os.pathsep + os.environ["PATH"],
                       EXPECTED_POLICY=str(policy), RESPONSE=json.dumps(response))
    environment.pop("OMARCHY_SETUP_ROOT", None)

    def generate(*args, extra=None):
        return subprocess.run(["bash", str(generator), "--root", str(root), "--policy", str(policy), *args],
                              env=environment | (extra or {}), capture_output=True, text=True)

    def refused(extra=None):
        before = snapshot(home)
        result = generate(extra=extra)
        assert result.returncode == 1, result.stdout + result.stderr
        assert snapshot(home) == before, "refusal partially mutated HOME"
        return result

    # Unrelated profiles, agents, settings and instructions coexist.
    (home / ".claude/agents").mkdir(parents=True)
    (home / ".claude/agents/user.md").write_text("user agent")
    (home / ".codex").mkdir()
    (home / ".codex/user.config.toml").write_text('model = "user"\n')
    (home / ".codex/config.toml").write_text('approval_policy = "never"\n')
    (home / ".codex/AGENTS.md").write_text("Keep user instructions.\n")
    (home / ".config/opencode").mkdir(parents=True)
    (home / ".config/opencode/opencode.json").write_text('{"model":"keep","instructions":["user.md"]}')
    first = generate()
    assert first.returncode == 0, first.stderr
    before = snapshot(home)
    assert generate().returncode == 0
    assert snapshot(home) == before
    assert generate("--check").returncode == 0
    for name in roles:
        profile = home / f".codex/{name}.config.toml"
        value = tomllib.loads(profile.read_text())
        assert set(value) == {"model", "model_reasoning_effort"}
        assert value["model_reasoning_effort"] == ("high" if name == "planner" else "medium")
        agent = (home / f".claude/agents/{name}.md").read_text()
        assert agent.startswith("---\nname: " + name + "\ndescription: ")
        front = agent.split("---\n", 2)[1]
        parsed = dict(line.split(": ", 1) for line in front.strip().splitlines())
        assert set(parsed) == {"name", "description", "model", "effort"}
        assert parsed["model"] in ("opus", "sonnet", "haiku", "fable")
        assert response["digest"] in agent and response["digest"] in profile.read_text()
    assert not (home / ".claude/agents/3d.md").exists()
    assert not (home / ".codex/3d.config.toml").exists()
    shared = (home / ".config/agents/AGENTS.md").read_text()
    imported = (home / ".claude/omarchy-setup/CLAUDE.md").read_text()
    assert "## Model roles (codex)" in shared and "## Model roles (claude)" in imported
    assert "- 3d:" in shared and "- 3d:" not in imported
    assert "assigned by hand" not in shared + imported
    assert "tier" in shared and "provider" in imported
    for label in ("plan", "execute", "review", "critical-review", "read", "3d"):
        assert shared.index("- " + label + ":") >= 0
    assert [line.split(":")[0] for line in shared.splitlines() if line.startswith("- ")][:6] == [
        "- plan", "- execute", "- review", "- critical-review", "- read", "- 3d"]
    assert (home / ".claude/agents/user.md").read_text() == "user agent"
    assert (home / ".codex/user.config.toml").read_text() == 'model = "user"\n'
    assert (home / ".codex/config.toml").read_text() == 'approval_policy = "never"\n'
    assert "Keep user instructions." in (home / ".codex/AGENTS.md").read_text()
    assert json.loads((home / ".config/opencode/opencode.json").read_text())["model"] == "keep"

    drift = home / ".codex/reader.config.toml"
    drift.write_text(drift.read_text() + "# drift\n")
    before = snapshot(home)
    checked = generate("--check")
    assert checked.returncode == 3 and ".codex/reader.config.toml" in checked.stdout
    assert snapshot(home) == before
    assert generate().returncode == 0

    # Policy changes causally alter selected model, effort, digest and preserve order.
    changed = copy.deepcopy(response)
    changed["roles"][0]["candidates"][1]["effort"] = "low"
    changed["roles"][0]["candidates"][1]["route"] = "codex/gpt-6-luna"
    changed_raw = json.dumps({k: v for k, v in changed.items() if k != "digest"}).encode()
    policy.write_bytes(changed_raw)
    changed["digest"] = hashlib.sha256(changed_raw).hexdigest()
    result = generate(extra={"RESPONSE": json.dumps(changed)})
    assert result.returncode == 0, result.stderr
    planner = (home / ".codex/planner.config.toml").read_text()
    assert 'model = "gpt-6-luna"' in planner and 'model_reasoning_effort = "low"' in planner
    assert changed["digest"] in planner
    policy.write_bytes(raw)
    assert generate().returncode == 0

    # Adversarial envelopes test projection rather than duplicate the YAML parser.
    refused({"FAIL": "1"})
    refused({"RESPONSE": "not json"})
    refused({"RESPONSE": '{"schema":"route-policy/v1","schema":"route-policy/v1"}'})
    refused({"RESPONSE": json.dumps(response | {"digest": "0" * 64})})
    for mutation in ("missing", "provider", "alias", "effort", "constraint", "unknown", "exclude", "3d"):
        bad = copy.deepcopy(response)
        if mutation == "missing":
            del bad["roles"][0]["candidates"][0]["effort"]
        elif mutation == "provider":
            bad["roles"][0]["candidates"][0]["route"] = "other/claude-opus-5-5"
        elif mutation == "alias":
            bad["roles"][0]["candidates"][0]["route"] = "claudeAgent/claude-unknown-5"
        elif mutation == "effort":
            bad["roles"][0]["candidates"][0]["effort"] = "max"
        elif mutation == "constraint":
            bad["roles"][0]["constraints"] = {"providerFamilies": ["claude"]}
        elif mutation == "unknown":
            bad["roles"][0]["constraints"] = {"providerFamilies": ["other"]}
        elif mutation == "exclude":
            bad["roles"][0]["constraints"] = {"excludeProviderFamilies": ["codex"]}
        else:
            bad["roles"][-1]["candidates"].append(copy.deepcopy(bad["roles"][0]["candidates"][0]))
        refused({"RESPONSE": json.dumps(bad)})
    refused({"RACE": "1"})
    policy.write_bytes(raw)
    policy.unlink()
    refused()
    policy.write_bytes(raw)
    link = base / "original.yaml"
    link.write_bytes(raw)
    policy.unlink()
    policy.symlink_to(link)
    refused()
    policy.unlink()
    policy.write_bytes(raw)
    destination = home / ".claude/agents/reader.md"
    saved = destination.read_bytes()
    destination.write_text("unmanaged native role")
    refused()
    destination.write_bytes(saved)
    destination.unlink()
    destination.symlink_to(home / ".claude/agents/user.md")
    refused()
    destination.unlink()
    destination.write_bytes(saved)
    settings = home / ".config/opencode/opencode.json"
    settings.write_text('{"instructions":"invalid"}')
    refused()
    settings.write_text('{"instructions":[]}')
    instructions = home / ".codex/AGENTS.md"
    instructions.write_text("<!-- fleet:start -->\nmalformed")
    refused()

# CI is offline and needs no Steward installation; this opt-in proof uses the exact
# reviewed rc108 binary built by the implementation task, without model invocation.
consumer = os.environ.get("M14_POLICY_CONSUMER", "")
if consumer:
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "policy.yaml"
        path.write_bytes(raw)
        def show():
            return subprocess.run([consumer, "policy", "show", "--file", str(path), "--json"],
                                  capture_output=True, text=True)
        actual = show()
        assert actual.returncode == 0, actual.stderr
        assert json.loads(actual.stdout) == response, "pinned consumer schema parity"
        for invalid in (b"schema: route-policy/v1\nroles: []\n", raw + b"unknown: true\n",
                        raw.replace(b"effort: high", b"effort: max")):
            path.write_bytes(invalid)
            assert show().returncode != 0, "real parser accepted malformed fixture"
    print("M14 real rc108 consumer schema parity: passed")
else:
    print("M14 real consumer schema parity: not requested (offline CI)")
print("M14 static native formats, policy projection, ownership and refusal contracts: passed")
