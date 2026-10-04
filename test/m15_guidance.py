"""Section-scoped M15 guidance contracts shared by legacy and policy generation."""
import re


def section(text, heading):
    """Read one Markdown section without borrowing evidence from later sections."""
    marker = heading + "\n"
    assert text.count(marker) == 1, heading
    body = text.split(marker, 1)[1]
    level = len(heading) - len(heading.lstrip("#"))
    return re.split(r"^#{1," + str(level) + r"} ", body, maxsplit=1, flags=re.M)[0]


def assert_m15_guidance(residents, reference):
    for text in residents:
        interactive = section(text, "## Interactive work and the T3 steward") if (
            "## Interactive work and the T3 steward\n" in text
        ) else section(text, "# Interactive work and the T3 steward")
        for term in ("task run", "campaign submit", "schedules",
                     "campaign cancel <run>[/<task>]", "retired in stages",
                     "fenced operator controls"):
            assert term in interactive, ("resident lifecycle", term)

    campaign = section(reference, "# t3-campaign")
    operator = section(campaign, "## Operator-only administration")
    lifecycle = campaign.split("## Operator-only administration\n", 1)[0]
    retirement = section(campaign, "## Staged legacy intake retirement")
    schedules = section(campaign, "## Recurring schedules and operator boundaries")
    task = section(reference, "# t3-task")
    collection = section(task, "## Collect and diagnose")
    wait = section(reference, "# t3-wait")

    for term in ("disabled by default", "separate intake", "does not prove",
                 "rollout lead", "previous reviewed", "Final removal remains pending",
                 "no active legacy consumers", "no automatic", "quarantine"):
        assert term in retirement, ("retirement", term)
    for family in ("backlog", "worker", "campaign", "campaign supervision",
                   "campaign recovery retry", "coordinator", "install-service", "schedules"):
        assert f"t3-steward {family} --help full" in operator, ("help family", family)
    assert "administrative mutations require\noperator authority" in operator
    assert "record/activation scope" in operator and "reassess" in operator
    assert "campaign cancel <run>[/<task>] --reason TEXT" in operator
    controls = next(line for line in operator.splitlines()
                    if line.startswith("| `backlog start`"))
    assert all(f"`{verb}`" in controls for verb in ("resume", "retry", "skip"))
    assert "`cancel`" not in controls, controls
    for verb in ("pause", "delay", "rewake", "recover", "edge add",
                 "artifact get", "quarantine release"):
        assert verb in operator, ("retained control", verb)
    for fence in ("--expected-revision", "--command-id", "--request-id",
                  "explicit user authority", "manually monitoring quota",
                  "worker health", "effect-safety"):
        assert fence in operator, ("operator fence", fence)
    assert "clearing quarantine does not enable or restart intake" in operator

    # Test the schedule section itself, not occurrences in operator help or prose.
    assert "Schedule reads (`list`, `show`, `history`) are available to agents" in schedules
    assert "Schedule mutations (`put`, `run`, `enable`, `disable`, `delay-next`)" in schedules
    assert "explicit operator authority" in schedules
    assert "Keep disabled schedules disabled" in schedules
    assert "--expected-revision" in schedules and "--command-id" in schedules
    assert "campaign cancel <run> --reason TEXT" in collection
    assert "Read-only catalog lookups" in collection
    assert "backlog projects" in collection and "backlog workers --json" in collection
    assert "cancelling a wait\nonly settles that wait" in wait
    assert "backlog rewake" in wait and "operator\nauthority" in wait
    for obsolete in ("t3-backlog", "t3-job", "backlog new", "backlog receive",
                     "backlog path", "backlog check", "backlog cancel", "BACKLOG STATUS:"):
        assert obsolete not in lifecycle + task + wait, ("obsolete recipe", obsolete)
