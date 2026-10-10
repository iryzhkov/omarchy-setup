#!/usr/bin/env python3
"""Production refusal and staging decisions; no ARM/kernel/provider proof."""
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / "config/bin/t3-laptop-worker-setup"
GIB = 1024 ** 3

def utc(value):
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")

class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        self.output = self.root / "stage"
        self.output.mkdir(mode=0o700)
        self.personal = self.root / "personal"
        self.personal.mkdir(mode=0o700)
        (self.personal / "service.conf").write_text("personal service untouched")
        (self.personal / "sentinel").write_text("SECRET-SENTINEL-DO-NOT-ECHO")
        now = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=2)
        self.request = {"version": 1, "operation_id": "next-week-one", "host": "laptop",
                        "uid": 2400, "account": "t3-laptop-isolated",
                        "source_commit": "1" * 40, "artifact_sha256": "2" * 64,
                        "created_at": utc(now), "expires_at": utc(now + dt.timedelta(days=7)),
                        "auth_mode": "dedicated-login"}
        self.input = self.root / "request.json"
        self.save(self.input, self.request)
        self.before_personal = self.snapshot(self.personal)

    def tearDown(self):
        self.assertEqual(self.before_personal, self.snapshot(self.personal))
        self.tmp.cleanup()

    def save(self, path, value):
        path.write_text(json.dumps(value))
        path.chmod(0o600)

    def snapshot(self, root):
        return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.rglob("*") if p.is_file()}

    def run_tool(self, *args, success=True, env=None):
        settings = {"PATH": "/usr/bin:/bin", "HOME": str(self.personal),
                    "PYTHONDONTWRITEBYTECODE": "1"}
        settings.update(env or {})
        result = subprocess.run([sys.executable, str(TOOL), *map(str, args)],
                                env=settings, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0 if success else 2, result.stdout + result.stderr)
        self.assertNotIn("SECRET-SENTINEL", result.stdout + result.stderr)
        value = json.loads(result.stdout)
        self.assertIs(value["live_qualified"], False)
        self.assertIs(value.get("enrolled", False), False)
        return value

    def stage(self, success=True):
        return self.run_tool("stage", "--request", self.input, "--output", self.output,
                             success=success)

    def gates(self):
        return {"version": 1, "observed_at": utc(dt.datetime.now(dt.timezone.utc)),
                "host": "laptop", "uid": 2400, "cpu_count": 8,
                "ram_available_bytes": 14 * GIB, "disk_free_bytes": 60 * GIB,
                "conflicting_executors": 0, "account_locked": True, "groups": [],
                "home_mode": "0700", "auth_mode": "dedicated-login",
                "source_commit": "1" * 40, "artifact_sha256": "2" * 64}

    def test_default_plan_has_no_effect(self):
        before = self.snapshot(self.root)
        value = self.run_tool()
        self.assertFalse(value["activation_supported"])
        self.assertEqual(before, self.snapshot(self.root))
        subprocess.run([sys.executable, str(TOOL), "--help"], check=True, capture_output=True)
        self.assertEqual(before, self.snapshot(self.root))

    def test_stage_replay_inspect_and_retirement(self):
        first = self.stage()
        before = self.snapshot(self.output)
        self.assertEqual(first, self.stage())
        self.assertEqual(before, self.snapshot(self.output))
        self.assertEqual(first, self.run_tool("inspect", "--output", self.output))
        self.assertEqual(first["changes"], [])
        for path in self.output.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.run_tool("retire-stage", "--output", self.output)
        self.assertEqual(before, {k: v for k, v in self.snapshot(self.output).items()
                                  if k != "retired.json"})
        retired = self.snapshot(self.output)
        self.run_tool("retire-stage", "--output", self.output)
        self.assertEqual(retired, self.snapshot(self.output))
        self.stage(success=False)

    def test_all_live_actions_refuse_without_opening_inputs(self):
        before = self.snapshot(self.root)
        for action in ("apply", "activate", "inactivate", "rollback", "bridge"):
            value = self.run_tool(action, "--request", "/home/igor/auth",
                                  "--output", self.personal, success=False,
                                  env={"SSH_ORIGINAL_COMMAND": "x; cat /home/igor/auth",
                                       "SSH_AUTH_SOCK": "/run/user/1001/agent",
                                       "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1001/bus"})
            self.assertEqual(value["reason"], "unsupported-live-" + action)
        self.assertEqual(before, self.snapshot(self.root))

    def test_strict_request_invalid_cases_no_writes(self):
        cases = [{"version": 2}, {"uid": 1001}, {"uid": True}, {"account": "igor"},
                 {"host": "laptop;sh"}, {"operation_id": "../escape"},
                 {"artifact_sha256": "wrong"}, {"source_commit": "wrong"},
                 {"auth_mode": "broad-home"}, {"secret": "SECRET-SENTINEL"}]
        for change in cases:
            with self.subTest(change=change):
                request = dict(self.request, **change)
                self.save(self.input, request)
                self.stage(success=False)
                self.assertEqual(list(self.output.iterdir()), [])
        self.input.write_text('{"version":1,"version":1}')
        self.stage(success=False)

    def test_missing_private_hardlink_and_symlink_request(self):
        self.input.chmod(0o644)
        self.stage(success=False)
        self.input.chmod(0o600)
        alias = self.root / "hard"
        os.link(self.input, alias)
        self.stage(success=False)
        alias.unlink()
        self.input.unlink()
        self.input.symlink_to(self.personal / "sentinel")
        self.stage(success=False)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_output_alias_overlap_foreign_and_permissions(self):
        self.output.chmod(0o755)
        self.stage(success=False)
        self.output.chmod(0o700)
        alias = self.root / "alias"
        alias.symlink_to(self.output, target_is_directory=True)
        self.run_tool("stage", "--request", self.input, "--output", alias, success=False)
        inside = self.output / "request.json"
        self.save(inside, self.request)
        self.run_tool("stage", "--request", inside, "--output", self.output, success=False)
        self.assertEqual(set(self.output.iterdir()), {inside})
        inside.unlink()
        self.output.rmdir()
        self.output.symlink_to(self.personal, target_is_directory=True)
        self.stage(success=False)

    def test_personal_home_alias_refuses(self):
        # HOME may have a non-/home canonical spelling; no separate-HOME claim.
        before = self.snapshot(self.output)
        self.run_tool("stage", "--request", self.input, "--output", self.output,
                      success=False, env={"HOME": str(self.root)})
        self.assertEqual(before, self.snapshot(self.output))

    def test_writable_parent_refuses(self):
        self.root.chmod(0o777)
        self.stage(success=False)
        self.root.chmod(0o700)

    def test_operation_conflict_preserves_stage(self):
        self.stage()
        before = self.snapshot(self.output)
        self.request["operation_id"] = "another"
        self.save(self.input, self.request)
        self.stage(success=False)
        self.assertEqual(before, self.snapshot(self.output))

    def test_crash_partial_stage_no_blind_replay(self):
        marker = self.output / "manifest.json"
        self.save(marker, {"partial": True})
        before = self.snapshot(self.output)
        self.stage(success=False)
        self.run_tool("retire-stage", "--output", self.output, success=False)
        self.assertEqual(before, self.snapshot(self.output))

    def test_payload_and_receipt_tamper(self):
        self.stage()
        for name in ("manifest.json", "disabled.service", "parent-gates.json", "receipt.json"):
            path = self.output / name
            original = path.read_bytes()
            path.write_bytes(b"tampered")
            before = self.snapshot(self.output)
            self.run_tool("inspect", "--output", self.output, success=False)
            self.run_tool("retire-stage", "--output", self.output, success=False)
            self.assertEqual(before, self.snapshot(self.output))
            path.write_bytes(original)

    def test_payload_link_and_foreign_file(self):
        self.stage()
        path = self.output / "disabled.service"
        data = path.read_bytes()
        path.unlink()
        path.symlink_to(self.personal / "sentinel")
        self.run_tool("inspect", "--output", self.output, success=False)
        path.unlink()
        path.write_bytes(data)
        path.chmod(0o600)
        os.link(path, self.root / "hard-unit")
        self.run_tool("inspect", "--output", self.output, success=False)
        (self.root / "hard-unit").unlink()
        self.save(self.output / "unmanaged.json", {})
        self.run_tool("retire-stage", "--output", self.output, success=False)

    def test_expiry_and_nonrenewal(self):
        for change in ({"expires_at": utc(dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1))},
                       {"expires_at": utc(dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=8))},
                       {"created_at": utc(dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1))}):
            self.save(self.input, dict(self.request, **change))
            self.stage(success=False)
        self.save(self.input, self.request)
        self.stage()
        before = self.snapshot(self.output)
        self.save(self.input, dict(self.request,
                                  expires_at=utc(dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=6))))
        self.stage(success=False)
        self.assertEqual(before, self.snapshot(self.output))

    def test_capacity_account_and_identity_decisions(self):
        self.stage()
        gatefile = self.root / "gates.json"
        changes = [{"cpu_count": 7}, {"cpu_count": True},
                   {"ram_available_bytes": 14 * GIB - 1},
                   {"disk_free_bytes": 60 * GIB - 1}, {"conflicting_executors": 1},
                   {"account_locked": False}, {"groups": ["wheel"]}, {"groups": ["docker"]},
                   {"home_mode": "0755"}, {"host": "other"}, {"uid": 1001},
                   {"artifact_sha256": "3" * 64}, {"source_commit": "3" * 40},
                   {"auth_mode": "protected-same-host-reference"},
                   {"observed_at": utc(dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=6))},
                   {"observed_at": utc(dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=1))},
                   {"ACCEPT": True}, {"live_qualified": True}, {"provider_auth": "SECRET-SENTINEL"}]
        before = self.snapshot(self.output)
        for change in changes:
            with self.subTest(change=change):
                self.save(gatefile, dict(self.gates(), **change))
                self.run_tool("assess", "--output", self.output, "--gates", gatefile, success=False)
                self.assertEqual(before, self.snapshot(self.output))
        self.save(gatefile, self.gates())
        result = self.run_tool("assess", "--output", self.output, "--gates", gatefile)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["evidence_kind"], "offline-declarations")
        self.assertIn("descendant-cgroup-caps-including-verification", result["blockers"])
        self.assertIn("offline-reboot-expiry-and-bridge-refusal", result["blockers"])
        self.assertEqual(before, self.snapshot(self.output))

    def test_expired_inspection_and_retirement_preserve_evidence(self):
        self.stage()
        before = self.snapshot(self.output)
        # Controlled clock only: this is metadata simulation, never runtime expiry proof.
        program = """
import datetime as dt
import json
import runpy
import sys
tool, output, expiry, action = sys.argv[1:]
module = runpy.run_path(tool, run_name="offline_clock_fixture")
functions = module["main"].__globals__
functions["clock"] = lambda: functions["timestamp"](expiry) + dt.timedelta(days=1)
sys.argv = [tool, action, "--output", output]
print(json.dumps(module["main"]()))
"""
        for action in ("inspect", "retire-stage"):
            result = subprocess.run([sys.executable, "-c", program, str(TOOL),
                                     str(self.output), self.request["expires_at"], action],
                                    env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
                                    capture_output=True, text=True, check=True)
            value = json.loads(result.stdout)
            self.assertFalse(value["live_qualified"])
            self.assertIn(value["status"], ("expired-disabled", "retired-disabled"))
        self.assertEqual(before, {k: v for k, v in self.snapshot(self.output).items()
                                  if k != "retired.json"})

    def test_same_host_reference_is_plan_only(self):
        self.request["auth_mode"] = "protected-same-host-reference"
        self.save(self.input, self.request)
        self.stage()
        value = self.run_tool("inspect", "--output", self.output)
        self.assertEqual(value["status"], "staged-disabled")
        # No auth path/value/digest is accepted or read, including parent binding source.
        self.request["auth_path"] = "/home/igor/.provider/auth"
        self.save(self.input, self.request)
        self.stage(success=False)

if __name__ == "__main__":
    unittest.main(verbosity=2)
