#!/usr/bin/env python3
"""Exercise the generated agent instructions without changing real agent settings.

The generator reads a checkout and never $HOME. Every case below therefore builds a
fixture checkout and a throwaway home, and the home is poisoned with text no output may
contain, because reading the installed copies back is the defect these tests exist to
keep out: it turned one machine's hand-edit into the whole fleet's instructions.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from m15_guidance import assert_m15_guidance
from campaign_example import assert_campaign_example

root = Path(__file__).resolve().parents[1]
generator = str(root / "config/bin/agents-instructions-gen")
skills = ("ov-memory", "ov-memory-curation", "t3-task", "t3-campaign", "t3-wait")
POISON = "# Hand-edited on this host\n"


def make_checkout(base):
    """A checkout holding this repository's CLAUDE.md and fixture skills."""
    claude = base / "checkout/config/claude"
    (claude / "skills").mkdir(parents=True)
    (claude / "CLAUDE.md").write_bytes((root / "config/claude/CLAUDE.md").read_bytes())
    for name in skills:
        skill = claude / "skills" / name
        skill.mkdir()
        (skill / "SKILL.md").write_text("# Fixture\n")
    (claude / "skills/t3-campaign/SKILL.md").write_text(
        "# Campaign fixture\n\nRead [the brief](references/executor-briefs.md).\n"
    )
    campaign_reference = claude / "skills/t3-campaign/references"
    campaign_reference.mkdir()
    (campaign_reference / "executor-briefs.md").write_text("# Executor brief fixture\n")
    huyang = claude / "skills/huyang"
    huyang.mkdir()
    (huyang / "SKILL.md").write_text("---\nname: huyang\n---\n\n# Cheapest correct call\n")
    return base / "checkout"


def make_home(base):
    """A home whose installed copies all say something the checkout never says."""
    home = base / "home"
    for name in skills + ("huyang",):
        skill = home / ".claude/skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(POISON)
    imported = home / ".claude/omarchy-setup"
    imported.mkdir(parents=True)
    (imported / "CLAUDE.md").write_text(POISON)
    codex = home / ".codex/AGENTS.md"
    codex.parent.mkdir(parents=True)
    # A host that still carries the superseded Jocasta block, plus text of the user's own.
    codex.write_text(
        "# Existing instructions\nKeep this text.\n\n"
        "<!-- jocasta:start -->\n## Shared working documents\n<!-- jocasta:end -->\n"
    )
    opencode = home / ".config/opencode/opencode.json"
    opencode.parent.mkdir(parents=True)
    foreign = [
        "original.md", "/elsewhere/rules.md", ".config/agents/user.md",
        str(home / ".config/agents-personal/rules.md"),
        str(home / ".config/agents-custom/user.md"), str(home / ".config/agents.md"),
        str(home / ".config/agents/user.md"),
    ]
    opencode.write_text(json.dumps({
        "instructions": foreign + [
            str(home / ".config/agents/t3-steward.md"),
            str(home / ".config/agents/jocasta.md"),
        ],
        "model": "keep",
        "permission": {"edit": "ask"},
    }))
    opencode.chmod(0o600)
    return home


def generate(home, *arguments, env=None):
    environment = dict(os.environ, HOME=str(home))
    environment.pop("OMARCHY_SETUP_ROOT", None)
    environment.update(env or {})
    return subprocess.run(
        ["bash", generator, *arguments], env=environment, capture_output=True, text=True
    )


with tempfile.TemporaryDirectory() as temporary:
    base = Path(temporary)
    checkout = make_checkout(base)
    home = make_home(base)

    finished = generate(home, "--root", str(checkout))
    assert finished.returncode == 0, finished.stderr
    codex = home / ".codex/AGENTS.md"
    first = codex.read_bytes()
    assert generate(home, "--root", str(checkout)).returncode == 0
    assert codex.read_bytes() == first, "a second run must not change ~/.codex/AGENTS.md"
    assert b"Keep this text." in first
    assert first.count(b"<!-- fleet:start -->") == 1
    assert b"jocasta:start" not in first, "the superseded block must be replaced, not kept"
    assert first.count(b"## OV memory") == 1

    generated = sorted(path.name for path in (home / ".config/agents").glob("*.md"))
    assert generated == [
        "AGENTS.md", "huyang.md", "jocasta.md", "ov-memory.md",
        "t3-campaign-executor-briefs.md", "t3-steward.md",
    ], generated
    for path in (home / ".config/agents").glob("*.md"):
        assert POISON.strip() not in path.read_text(), (
            f"{path.name} carries text that exists only in $HOME; the generator read an "
            "installed copy instead of the checkout"
        )

    shared = (home / ".config/agents/AGENTS.md").read_text()
    assert "## Reading and editing code" in shared
    assert "the `publish-agent-tooling` skill" in shared
    assert shared.strip() in first.decode(), "the Codex block carries the shared pointer"
    # The steward paragraph teaches the command the fleet actually runs, and none of the
    # path the campaign replaced. The text is wrapped, so a phrase is matched against it
    # with its line breaks collapsed.
    flat = " ".join(shared.split())
    assert "t3-steward task run" in flat
    assert "t3-steward task result" in flat
    assert "backlog list" not in flat, "the obsolete intake verification is gone"
    assert "backlog start" not in flat, "the operator override is not advertised here"
    assert "<T3 project>" not in flat, "--project takes a fleet project name"
    steward_reference = (home / ".config/agents/t3-steward.md").read_text()
    assert "](t3-campaign-executor-briefs.md)" in steward_reference
    campaign_briefs = home / ".config/agents/t3-campaign-executor-briefs.md"
    assert campaign_briefs.read_text() == "# Executor brief fixture\n"
    for flag in ("--at", "--for", "--github", "--node", "--quota", "--or-timeout"):
        assert flag in flat, f"the wait kinds must name {flag}"

    guidance = (home / ".config/agents/jocasta.md").read_text()
    assert "30 days without a read or update" in guidance
    assert "Reading and editing code" not in guidance
    assert "~/.config/agents/jocasta.md" not in guidance, "the file must not point at itself"

    huyang_reference = (home / ".config/agents/huyang.md").read_text()
    assert "# Reading and editing code" in huyang_reference
    assert "# Cheapest correct call" in huyang_reference, "the skill body is appended"
    assert "name: huyang" not in huyang_reference, "skill front matter is stripped"

    config = json.loads((home / ".config/opencode/opencode.json").read_text())
    assert config["model"] == "keep"
    foreign = [
        "original.md", "/elsewhere/rules.md", ".config/agents/user.md",
        str(home / ".config/agents-personal/rules.md"),
        str(home / ".config/agents-custom/user.md"), str(home / ".config/agents.md"),
        str(home / ".config/agents/user.md"),
    ]
    assert config["permission"] == {"edit": "ask"}
    assert config["instructions"] == [str(home / ".config/agents/AGENTS.md")] + foreign, (
        "only the shared pointer is loaded into every session; foreign entries are kept"
    )
    assert (home / ".config/opencode/opencode.json").stat().st_mode & 0o777 == 0o600

    # The checkout may be named by the environment as well as by the flag.
    assert generate(home, env={"OMARCHY_SETUP_ROOT": str(checkout)}).returncode == 0

    # And when it is named by neither and the script is not in one, the generator fails
    # and changes nothing rather than falling back to the installed copies.
    stranded = base / "home/.local/bin/agents-instructions-gen"
    stranded.parent.mkdir(parents=True, exist_ok=True)
    stranded.write_bytes(Path(generator).read_bytes())
    before = sorted(
        (path.name, path.read_bytes()) for path in (home / ".config/agents").glob("*.md")
    )
    refused = subprocess.run(
        ["bash", str(stranded)],
        env={k: v for k, v in os.environ.items() if k != "OMARCHY_SETUP_ROOT"} | {"HOME": str(home)},
        capture_output=True,
        text=True,
    )
    assert refused.returncode != 0, "a generator with no checkout must fail"
    assert "config/claude/CLAUDE.md" in refused.stderr, refused.stderr
    assert "never falls" in refused.stderr, refused.stderr
    after = sorted(
        (path.name, path.read_bytes()) for path in (home / ".config/agents").glob("*.md")
    )
    assert before == after, "the refusal must change nothing"

    # A checkout missing the linked campaign reference is refused rather than
    # generating a dangling link.
    source_briefs = checkout / "config/claude/skills/t3-campaign/references/executor-briefs.md"
    source_briefs.unlink()
    missing_reference = generate(home, "--root", str(checkout))
    assert missing_reference.returncode != 0
    assert "t3-campaign/references/executor-briefs.md" in missing_reference.stderr
    source_briefs.write_text("# Executor brief fixture\n")

    # A checkout missing one of the skills it concatenates is named, not silently
    # turned into a reference file with a hole in it.
    (checkout / "config/claude/skills/t3-wait/SKILL.md").unlink()
    incomplete = generate(home, "--root", str(checkout))
    assert incomplete.returncode != 0
    assert "t3-wait/SKILL.md" in incomplete.stderr, incomplete.stderr

with tempfile.TemporaryDirectory() as temporary:
    # --check reports, and repairs nothing. It is the only thing that notices that an
    # installed copy no longer matches the checkout it was derived from.
    base = Path(temporary)
    checkout = make_checkout(base)
    home = make_home(base)
    assert generate(home, "--root", str(checkout)).returncode == 0

    diverged = generate(home, "--root", str(checkout), "--check")
    assert diverged.returncode == 3, diverged.stdout + diverged.stderr
    assert "omarchy-setup/CLAUDE.md" in diverged.stdout
    assert "skills/t3-task/SKILL.md" not in diverged.stdout

    # Converge the imported instruction artifact and the host matches.
    (home / ".claude/omarchy-setup/CLAUDE.md").write_bytes(
        (checkout / "config/claude/CLAUDE.md").read_bytes()
    )
    converged = generate(home, "--root", str(checkout), "--check")
    assert converged.returncode == 0, converged.stdout + converged.stderr

    # One leftover in a directory that is generated whole is a divergence too, and the
    # check says which direction it is in.
    (home / ".config/agents/agent99.md").write_text("leftover\n")
    leftover = generate(home, "--root", str(checkout), "--check")
    assert leftover.returncode == 3
    assert "agent99.md: present on this host and generated by nothing" in leftover.stdout
    assert (home / ".config/agents/agent99.md").exists(), "--check must change nothing"

print("Shared agent instruction generation: source, preservation, idempotence and divergence passed")

# Exercise the real source trees too: fixture skills above deliberately cannot
# catch stale guidance leaking into the reference every harness reads.
with tempfile.TemporaryDirectory() as temporary:
    base = Path(temporary)
    home = make_home(base)
    result = generate(home, "--root", str(root))
    assert result.returncode == 0, result.stdout + result.stderr
    shared = (home / ".config/agents/AGENTS.md").read_text()
    reference = (home / ".config/agents/t3-steward.md").read_text()
    claude = (root / "config/claude/CLAUDE.md").read_text()
    briefs = (home / ".config/agents/t3-campaign-executor-briefs.md").read_text()
    failures = []

    def require(label, condition):
        if not condition:
            failures.append(label)

    for label, text in (("Claude", claude), ("shared", shared)):
        for term in ("interactive", "Igor has agreed", "Jocasta", "run id",
                     "ledger", "operator-level", "estimated cost", "fleet",
                     "high", "medium", "max effort",
                     "generated policy", "reader subagent", "bounded answer",
                     "known file", "t3-steward ask", "ask-answer.json",
                     "t3-steward review"):
            require(f"{label}: missing {term}", term in text)
    require("no-policy guidance remains inert", "assigned by hand" in claude and "assigned by hand" in shared)
    require("no-policy resident source stays unchanged",
            (home / ".claude/omarchy-setup/CLAUDE.md").read_bytes() == POISON.encode())
    require("no-policy API creates no native roles",
            not (home / ".claude/agents").exists() and
            not list((home / ".codex").glob("*.config.toml")))
    for term in ("task run --input", "--dry-run", "task result <run> --wait",
                 "campaign show <run> --wait", "triage", "--independent",
                 "--swarm", "--judge", "summary.json", "review result",
                 "continuation.md", "goal", "checklist", "current step",
                 "blockers", "last verification", "milestone", "handoff"):
        require(f"reference: missing {term}", term in reference)
    require("brief checkpoint is portable", "continuation.md" in briefs)
    require("brief validator path is portable", "$HOME/.codex/skills/" in briefs)
    for obsolete in ("t3-backlog", "or backlog", "backlog_v2",
                     "Legacy file", "BACKLOG STATUS:", "/home/igor/",
                     "claude-haiku-4-5", "t3-primary/opus", "--model opus",
                     "claude-sonnet-5", "codex/gpt-5.6-sol",
                     "claudeAgent/claude-opus-5", "rc.9",
                     "backlog or campaign task", "backlog show", "backlog list",
                     "backlog status"):
        require(f"obsolete guidance: {obsolete}",
                obsolete not in claude + shared + reference + briefs)
    require("subagents cannot replace a declared task or review",
            "never in place of a declared task or review" in reference)
    require("operator commands are labeled", "Operator-only" in reference)
    # Operator guidance must survive generation, separately from agent lifecycle.
    campaign = (root / "config/claude/skills/t3-campaign/SKILL.md").read_text()
    task = (root / "config/claude/skills/t3-task/SKILL.md").read_text()
    assert_m15_guidance((claude, shared), reference)
    assert_campaign_example(campaign)
    deployment_doc = (root / "docs/t3-code-and-steward.md").read_text()
    deployment_work = deployment_doc.split("## Agent work through the steward\n", 1)[1]
    require("deployment doc public submission and cancellation",
            all(term in deployment_work for term in ("task run", "campaign submit",
                                                      "schedules", "campaign cancel")))
    require("deployment doc does not authorize old wrappers",
            "existing scripts can continue" not in deployment_work)
    require("deployment doc permanent retirement and authority",
            all(term in deployment_work for term in (
                "permanently retires", "true enable flags", "rejected", "false",
                "marker-only cleanup", "cannot retry", "immutable",
                "never reenable", "rc109", "do not prove runtime deployment",
                "production diversity waiver", "explicit route and effort pins",
                "Codex medium only", "schedule mutations require explicit operator")))
    for obsolete in ("retired in stages", "Final removal is pending",
                     "temporary compatibility opt-in", "next intake cycle retries"):
        require(f"deployment doc obsolete retirement: {obsolete}",
                obsolete not in deployment_work)
    operator = campaign.partition("## Operator-only administration")[2]
    require("operator section separate from normal lifecycle", bool(operator))
    for term in ("backlog start", "explicit user authority", "manually monitoring quota",
                 "quota forecast", "admission", "freshness", "runway",
                 "automatic quota throttling", "effect-safety",
                 "quarantine release", "creates nothing", "worker enroll",
                 "must run on the coordinator host", "one deliberate exception",
                 "--current-catalog", "catalog-digest-mismatch",
                 "campaign recovery", "backlog --help full", "worker --help full",
                 "resume", "retry", "skip", "pause", "delay", "rewake", "recover",
                 "events", "usage", "diagnose", "task show", "commands",
                 "edge add", "artifact get", "--expected-revision", "--request-id"):
        require(f"operator reference: missing {term}", term in operator)
    for term in ("schedules show <schedule> --json", "schedules --help full",
                 "list", "history", "run", "enable", "disable", "delay-next"):
        require(f"schedule reference: missing {term}", term in reference)
    require("bundled plan declared", "inputs: [inputs/plan.md]" in campaign)
    require("bundled plan mounted path", ".t3/inputs/inputs/plan.md" in reference)
    require("task checkpoint retention explained",
            "--outputs continuation.md,handoff.md" in task)
    require("task catalog is read-only",
            "Read-only catalog lookups" in task and "operator-only catalog" not in task)
    require("task points at shared operator guidance",
            "Operator-only administration" in task)
    require("no-policy check reports imported source drift",
            generate(home, "--root", str(root), "--check").returncode == 3)
    # Link rewriting and source provenance remain correct with real skills.
    require("generated reference link",
            "](t3-campaign-executor-briefs.md)" in reference)
    require("brief source bytes", briefs == (
        root / "config/claude/skills/t3-campaign/references/executor-briefs.md"
    ).read_text())
    assert not failures, "\n".join(failures)

print("Steward instruction contracts: real-source generation passed")

# INERT preparation compatibility: the legacy direct generator and installed
# module path keep writing only legacy source bytes in disposable homes.
with tempfile.TemporaryDirectory() as temporary:
    base = Path(temporary)
    home = make_home(base)
    stale = home / ".config/agents/agent99.md"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("retired reference")
    result = generate(home, "--root", str(root))
    assert result.returncode == 0, result.stderr
    assert not stale.exists(), "legacy retirement cleanup must remain"
    assert not (home / ".config/agents/owner.json").exists()
    assert not (root / "shared/agent-instructions").exists()
    for source in ("run.sh", "modules/common/28-scripts.sh",
                   "modules/common/31-agent-instructions.sh",
                   "config/hooks/post-update.d/omarchy-setup.hook"):
        text = (root / source).read_text()
        assert "upkeeper-shared-prepare" not in text, source
        assert "candidate-inert" not in text, source
    installed = home / ".local/bin/agents-instructions-gen"
    installed.parent.mkdir(parents=True)
    installed.write_bytes(Path(generator).read_bytes())
    invoked = subprocess.run(
        ["bash", str(installed), "--root", str(root)],
        env=dict(os.environ, HOME=str(home)),
        capture_output=True, text=True,
    )
    assert invoked.returncode == 0, invoked.stderr
    assert (home / ".config/agents/AGENTS.md").read_text() == shared

print("Inert candidate: legacy direct/copied writer and retirement preserved")

subprocess.run(["python3", str(root / "test/agent-roles.py")], check=True)
