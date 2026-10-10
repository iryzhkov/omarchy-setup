#!/usr/bin/env python3
"""Check the owning CI prerequisite contract without third-party YAML dependencies.

This deliberately accepts only the current two-job, block-scalar workflow shape.
Unknown conditions or alternative structures refuse rather than pass silently.
"""
from pathlib import Path
import re

URL = "https://github.com/containers/bubblewrap/releases/download/v0.12.0/bubblewrap-0.12.0.tar.xz"
SHA256 = "9760d007363e3abba7c747489910f9f82d9fca53ba3bd3282e396fa3c97a3314"

def validate(text):
    jobs = re.findall(r"^  ([a-z][a-z-]*):$", text.split("jobs:\n", 1)[1], re.M)
    assert jobs == ["test", "sandbox-qualification"], "qualification job must be unconditional and present"
    job = text.split("  sandbox-qualification:\n", 1)[1]
    assert not re.search(r"^\s*(if|continue-on-error|needs|strategy):", job, re.M), "conditional/optional qualification"
    assert "runs-on: ubuntu-24.04" in job
    assert 'T3_LAPTOP_REQUIRE_SANDBOX: "1"' in job
    for dependency in ("build-essential", "pkg-config", "libcap-dev", "meson", "ninja-build", "curl", "xz-utils"):
        assert dependency in job, "missing build dependency: " + dependency
    for command in (
        "set -euo pipefail", URL, SHA256, "sha256sum -c -",
        'meson setup "$sandbox_build/build" "$sandbox_build/bubblewrap-0.12.0" -Dman=disabled -Dtests=false -Dselinux=disabled -Dbash_completion=disabled -Dzsh_completion=disabled',
        'meson compile -C "$sandbox_build/build" -j 1',
        'sudo install -m 0755 "$sandbox_build/build/bwrap" /usr/bin/bwrap',
        'test "$(/usr/bin/bwrap --version)" = \'bubblewrap 0.12.0\'',
        "sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0",
        "sudo sysctl -w kernel.unprivileged_userns_clone=1",
        "/usr/bin/bwrap --unshare-all --die-with-parent --new-session --clearenv",
        "-- /usr/bin/true", "run: python3 test/laptop-worker-isolation.py",
        "run: python3 test/sandbox-prerequisites.py",
    ):
        assert command in job, "missing prerequisite: " + command
    assert job.index("sha256sum -c -") < job.index("tar -xJf") < job.index("meson setup")
    assert job.index("sudo install") < job.index("sudo sysctl") < job.index("-- /usr/bin/true") < job.index("run: python3 test/laptop-worker-isolation.py")
    assert not re.search(r"\|\|\s*true|--not-a-security-boundary|unittest.*mock", job)
    assert "run: test/run.sh" in text and "run: python3 test/agents-instructions.py" in text
    return True

if __name__ == "__main__":
    validate((Path(__file__).resolve().parents[1] / ".github/workflows/test.yml").read_text())
    print("CI sandbox prerequisite contract: passed")
