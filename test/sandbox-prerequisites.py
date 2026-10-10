#!/usr/bin/env python3
"""Actual missing/wrong/blocked prerequisite replay in disposable user namespaces.

Only synthetic fixture binaries are overlaid. Host /usr/bin/bwrap is untouched.
Every mandatory failure is expected and checked; restored real qualification must pass.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
POSITIVE = "repair1_actual_sandbox_own_auth_and_negative_access"

def main():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", T3_LAPTOP_REQUIRE_SANDBOX="1")
    # Restore/available proof is real production qualification, not a mock.
    restored = subprocess.run([sys.executable, str(ROOT / "test/laptop-worker-isolation.py"),
                               "-k", POSITIVE], env=env, capture_output=True, text=True)
    assert restored.returncode == 0 and "skipped" not in restored.stderr, restored.stderr
    print("available: real mandatory positive passed, zero skips")
    with tempfile.TemporaryDirectory(prefix="sandbox-prerequisites-", dir="/tmp") as tmp:
        fixture = Path(tmp)
        for kind, reason in (
            ("missing", "bwrap-unavailable-or-timeout"),
            ("wrong-version", "unsupported-bwrap-version"),
            ("blocked-namespace", "unprivileged-namespace-unavailable"),
        ):
            binary = fixture / "bwrap"
            version = "0.11.0" if kind == "wrong-version" else "0.12.0"
            binary.write_text("#!/bin/sh\n"
                              'if [ "$1" = --version ]; then\n'
                              f"  printf 'bubblewrap {version}\\n'\n"
                              "  exit 0\nfi\n"
                              "printf 'controlled namespace refusal\\n' >&2\nexit 1\n")
            binary.chmod(0o700)
            # Retain Python and public runtime while omitting bwrap altogether
            # for the missing case. /bin -> usr/bin is recreated in the namespace.
            base = ["/usr/bin/bwrap", "--unshare-all", "--die-with-parent", "--new-session",
                    "--clearenv", "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib",
                    "--ro-bind", "/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev",
                    "--tmpfs", "/tmp", "--ro-bind", str(ROOT), str(ROOT),
                    "--symlink", "usr/bin", "/bin",
                    "--setenv", "PATH", "/usr/bin:/bin",
                    "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
                    "--chdir", str(ROOT)]
            if kind == "missing":
                base += ["--tmpfs", "/usr/bin", "--ro-bind", "/usr/bin/python3", "/usr/bin/python3",
                         "--ro-bind", "/usr/bin/true", "/usr/bin/true"]
            else:
                base += ["--ro-bind", str(binary), "/usr/bin/bwrap"]
            for required in (False, True):
                command = base + ["--setenv", "T3_LAPTOP_REQUIRE_SANDBOX", "1" if required else "0",
                                  "--", "/usr/bin/python3", "test/laptop-worker-isolation.py",
                                  "-k", POSITIVE]
                result = subprocess.run(command, capture_output=True, text=True, timeout=60)
                expected = 1 if required else 0
                assert result.returncode == expected, result.stdout + result.stderr
                assert reason in result.stderr, result.stderr
                if required:
                    assert "FAILED (failures=1)" in result.stderr and "skipped=" not in result.stderr
                else:
                    assert "OK (skipped=1)" in result.stderr
                print(f"{kind}: {'mandatory FAIL exit1, zero skips' if required else 'optional unavailable, one named skip'}")
    restored = subprocess.run([sys.executable, str(ROOT / "test/laptop-worker-isolation.py"),
                               "-k", POSITIVE], env=env, capture_output=True, text=True)
    assert restored.returncode == 0 and "skipped" not in restored.stderr, restored.stderr
    print("restored: real mandatory positive passed, zero skips")

if __name__ == "__main__":
    main()
