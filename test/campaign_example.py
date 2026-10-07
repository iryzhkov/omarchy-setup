"""The copyable workflow.yaml example in the t3-campaign skill declares a ledger.

The hand-off instruction tells authors to give every campaign a `ledger:` block,
and the Steward writes nothing durable without one. An author who copies the
example must therefore get the block and be told to replace its placeholder.
"""
import re
import sys
from pathlib import Path


def assert_campaign_example(campaign):
    blocks = re.findall(r"^```yaml\n(.*?)^```", campaign, flags=re.M | re.S)
    examples = [block for block in blocks if block.startswith("version: 2\n")]
    assert len(examples) == 1, ("one copyable workflow example", len(examples))
    example = examples[0]
    ledger = [line for line in example.splitlines() if line.startswith("ledger:")]
    assert ledger == ["ledger: {jocasta_project: JOCASTA_PROJECT}"], (
        "workflow example declares a top-level ledger", ledger)
    preamble = campaign.split("```yaml\n" + example, 1)[0]
    preamble = preamble.rsplit("```", 1)[-1]
    assert "JOCASTA_PROJECT" in preamble, (
        "example instructions name the ledger placeholder", preamble)


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    source = root / "config/claude/skills/t3-campaign/SKILL.md"
    assert_campaign_example(source.read_text())
    print("t3-campaign workflow example declares a ledger: passed")
    sys.exit(0)
