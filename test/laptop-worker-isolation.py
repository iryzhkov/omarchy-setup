#!/usr/bin/env python3
"""Production refusal and staging decisions; no ARM/kernel/provider proof."""
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import runpy
from unittest import mock
import subprocess
import sys
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / "config/bin/t3-laptop-worker-setup"
GIB = 1024 ** 3

def sandbox_unavailable():
    """Probe prerequisites only; qualification assertions must never become skips."""
    try:
        version = subprocess.run(["/usr/bin/bwrap", "--version"],
                                 capture_output=True, timeout=5, check=False)
        if version.returncode != 0 or version.stdout.strip() != b"bubblewrap 0.12.0":
            return "unsupported-bwrap-version (requires exactly 0.12.0)"
        probe = subprocess.run(
            ["/usr/bin/bwrap", "--unshare-all", "--die-with-parent", "--new-session",
             "--clearenv", "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib",
             "--ro-bind", "/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev",
             "--tmpfs", "/tmp", "--", "/usr/bin/true"],
            capture_output=True, timeout=5, check=False)
        if probe.returncode != 0:
            return "unprivileged-namespace-unavailable"
    except (OSError, subprocess.TimeoutExpired):
        return "bwrap-unavailable-or-timeout"
    return None


def utc(value):
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")

class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir="/tmp")
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
        terminal = self.run_tool("retire-stage", "--output", self.output)
        self.assertEqual(terminal["status"], "retired-disabled")
        self.assertEqual(terminal["expires_at"], self.request["expires_at"])
        self.assertEqual(before, {k: v for k, v in self.snapshot(self.output).items()
                                  if k != "retired.json"})
        retired = self.snapshot(self.output)
        self.assertEqual(terminal, self.run_tool("retire-stage", "--output", self.output))
        self.assertEqual(terminal, self.run_tool("inspect", "--output", self.output))
        self.assertEqual(terminal, self.run_tool("assess", "--output", self.output,
                                              "--gates", "/home/igor/auth-not-opened"))
        self.assertEqual(retired, self.snapshot(self.output))
        self.stage(success=False)
        self.assertEqual(retired, self.snapshot(self.output))

    def test_all_live_actions_refuse_without_opening_inputs(self):
        before = self.snapshot(self.root)
        for action in ("apply", "activate", "inactivate", "rollback", "bridge", "install", "enroll", "qualify-live"):
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

    def test_repair2_held_directory_survives_real_ancestor_replacement(self):
        functions = runpy.run_path(str(TOOL), run_name="held_directory_fixture")
        ancestor = self.root / "ancestor"
        ancestor.mkdir(mode=0o700)
        original_output = ancestor / "stage"
        original_output.mkdir(mode=0o700)
        original_input = ancestor / "request.json"
        self.save(original_input, self.request)
        replacement = self.root / "replacement"
        replacement.mkdir(mode=0o700)
        replacement_output = replacement / "stage"
        replacement_output.mkdir(mode=0o700)
        self.save(replacement / "request.json", {"redirected": True})
        replacement_before = self.snapshot(replacement)
        original_raw = original_input.read_bytes()
        moved = self.root / "held-original"
        with functions["private_dir"](str(original_output)) as output:
            with functions["open_directory"](ancestor) as inputs:
                output_fd, input_fd = output.fd, inputs.fd
                # Real pathname attack after verification, not a mocked helper result.
                ancestor.rename(moved)
                ancestor.symlink_to(replacement, target_is_directory=True)
                self.assertEqual(functions["read_at"](inputs, "request.json"), original_raw)
                first = functions["stage"](self.request, output)
                self.assertEqual(first, functions["stage"](self.request, output))
                self.assertEqual(first, functions["inspect_at"](output)[1])
                self.assertEqual(replacement_before, self.snapshot(replacement))
                self.assertIn("receipt.json", self.snapshot(moved / "stage"))
                with self.assertRaises(OSError):
                    functions["open_directory"](ancestor)
        for fd in (output_fd, input_fd):
            with self.assertRaises(OSError):
                os.fstat(fd)
        self.assertIsNone(output.fd)
        self.assertIsNone(inputs.fd)

    def test_repair2_trusted_ancestor_owner_and_error_descriptor_cleanup(self):
        functions = runpy.run_path(str(TOOL), run_name="ownership_fixture")
        ancestor = self.root / "foreign-policy-fixture"
        ancestor.mkdir(mode=0o755)
        nested = ancestor / "private"
        nested.mkdir(mode=0o700)
        target_inode = ancestor.stat().st_ino
        real_fstat, real_open = os.fstat, os.open
        opened = []

        def foreign_owner(fd):
            info = real_fstat(fd)
            if info.st_ino == target_inode:
                values = list(info)
                values[4] = max(2001, os.geteuid() + 1)
                return os.stat_result(values)
            return info

        def record_open(*args, **kwargs):
            fd = real_open(*args, **kwargs)
            opened.append(fd)
            return fd

        # The host does not grant chown. Only UID policy is simulated; pathname
        # rename/symlink attacks use real filesystem operations in the test above.
        with mock.patch.object(os, "fstat", side_effect=foreign_owner):
            with mock.patch.object(os, "open", side_effect=record_open):
                with self.assertRaisesRegex(functions["Refusal"], "untrusted-ancestor-owner"):
                    functions["private_dir"](str(nested))
        for fd in set(opened):
            with self.assertRaises(OSError):
                real_fstat(fd)
        with functions["open_directory"](self.root) as directory:
            self.input.chmod(0o644)
            opened.clear()
            with mock.patch.object(os, "open", side_effect=record_open):
                with self.assertRaisesRegex(functions["Refusal"], "private-owned-regular-input"):
                    functions["read_at"](directory, self.input.name)
            for fd in opened:
                with self.assertRaises(OSError):
                    real_fstat(fd)
            self.input.chmod(0o600)

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
        for name in sorted(self.snapshot(self.output)):
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

    def test_repair3_expired_inspection_and_retirement_preserve_evidence(self):
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
        def after_expiry(action, output=self.output):
            result = subprocess.run([sys.executable, "-c", program, str(TOOL),
                                     str(output), self.request["expires_at"], action],
                                    env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
                                    capture_output=True, text=True, check=True)
            value = json.loads(result.stdout)
            self.assertFalse(value["live_qualified"])
            self.assertEqual(value["expires_at"], self.request["expires_at"])
            return value

        self.assertEqual(after_expiry("inspect")["status"], "expired-disabled")
        self.assertEqual(before, self.snapshot(self.output))
        first = after_expiry("retire-stage")
        self.assertEqual(first["status"], "retired-disabled")
        retired = self.snapshot(self.output)
        self.assertEqual(first, after_expiry("retire-stage"))
        self.assertEqual(first, after_expiry("inspect"))
        self.assertEqual(retired, self.snapshot(self.output))
        self.assertEqual(before, {k: v for k, v in retired.items() if k != "retired.json"})

        # Retirement before expiry also remains terminal when the clock advances.
        early_output = self.root / "early-retired"
        early_output.mkdir(mode=0o700)
        self.run_tool("stage", "--request", self.input, "--output", early_output)
        original = self.snapshot(early_output)
        early = self.run_tool("retire-stage", "--output", early_output)
        self.assertEqual(early["status"], "retired-disabled")
        early_bytes = self.snapshot(early_output)
        self.assertEqual(early, after_expiry("inspect", early_output))
        self.assertEqual(early, after_expiry("retire-stage", early_output))
        self.assertEqual(early_bytes, self.snapshot(early_output))
        self.assertEqual(original, {k: v for k, v in early_bytes.items() if k != "retired.json"})

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

    def fixture(self):
        functions = runpy.run_path(str(TOOL), run_name="fixture_builder")
        self.request["artifact_sha256"] = hashlib.sha256(
            functions["FIXTURE_RUNTIME"].encode()).hexdigest()
        self.save(self.input, self.request)
        self.stage()
        fixture = self.root / "fixture"
        fixture.mkdir(mode=0o700)
        home = fixture / "home"
        home.mkdir(mode=0o700)
        personal = fixture / "personal"
        personal.mkdir(mode=0o700)
        (personal / "sentinel").write_text("SECRET-SENTINEL-DO-NOT-ECHO")
        self.save(fixture / "fixture.json",
                  {"kind": "disposable-laptop-qualification", "version": 1,
                   "source_commit": self.request["source_commit"],
                   "artifact_sha256": self.request["artifact_sha256"]})
        (home / "fixture-auth.json").write_bytes(
            functions["encode"]({"kind": "disposable-own-auth", "provider": "synthetic"}))
        (home / "fixture-auth.json").chmod(0o600)
        self.save(home / "provider-auth.fixture", {})  # then fixed noncredential marker
        (home / "provider-auth.fixture").write_bytes(b"disposable-own-auth-only\n")
        auth = home / ".config/upkeeper/secrets/f02-protocol/laptop-isolated"
        auth.parent.mkdir(parents=True, mode=0o700)
        auth.write_bytes(b"disposable-qualification-only\n")
        auth.chmod(0o600)
        return fixture, home

    def qualify(self, fixture, success=True):
        return self.run_tool("qualify-fixture", "--output", self.output,
                             "--fixture", fixture, success=success,
                             env={"SSH_ORIGINAL_COMMAND": "exec arbitrary-command",
                                  "SSH_AUTH_SOCK": "/excluded/personal/agent.sock",
                                  "DBUS_SESSION_BUS_ADDRESS": "unix:path=/excluded/personal/bus.sock",
                                  "T3CODE_HOME": str(self.personal),
                                  "HUYANG_SOCKET": str(self.personal / "huyang.sock")})

    def test_repair1_supported_preparation_and_fixed_launch_refusal(self):
        self.stage()
        bootstrap = json.loads((self.output / "worker-bootstrap.json").read_text())
        self.assertEqual(bootstrap["schema_version"], 1)
        self.assertEqual(bootstrap["credential_ref"], "secretref:f02-protocol/laptop-isolated")
        self.assertEqual(bootstrap["capabilities"], ["git", "huyang"])
        preparation = json.loads((self.output / "preparation.json").read_text())
        self.assertEqual(preparation["binding"]["artifact_sha256"], self.request["artifact_sha256"])
        self.assertEqual(preparation["binding"]["source_commit"], self.request["source_commit"])
        self.assertFalse(preparation["enabled"])
        self.assertFalse(preparation["auth_provisioned"])
        self.assertEqual(preparation["directory_modes"]["home"], "0700")
        self.assertEqual(preparation["directory_modes"]["t3"], "0700")
        self.assertEqual(preparation["directory_modes"]["huyang"], "0700")
        unit = (self.output / "disabled.service").read_text()
        self.assertNotIn("/usr/bin/false", unit)
        self.assertNotIn("[Install]", unit)
        for directive in ("CPUQuota=400%", "MemoryMax=12G", "KillMode=control-group"):
            self.assertIn(directive, unit)
        # Exercise generated production wrapper, not just inspect strings.
        before = self.snapshot(self.output)
        for mode in ("serve", "bridge", "worker;sh"):
            result = subprocess.run([sys.executable, str(self.output / "worker-launcher.py"), mode],
                                    env={"PATH": "/usr/bin:/bin", "SSH_ORIGINAL_COMMAND": "x;sh"},
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertFalse(json.loads(result.stdout)["live_qualified"])
        self.assertEqual(before, self.snapshot(self.output))

    def test_repair1_actual_sandbox_own_auth_and_negative_access(self):
        unavailable = sandbox_unavailable()
        if unavailable:
            if os.environ.get("T3_LAPTOP_REQUIRE_SANDBOX") == "1":
                self.fail("required sandbox prerequisite: " + unavailable)
            self.skipTest("optional local real sandbox unavailable: " + unavailable)
        fixture, home = self.fixture()
        # Actual listening local fixture sockets exist outside the mount allowlist.
        import socket
        sockets = []
        for name in ("agent", "bus", "t3", "huyang"):
            listener = socket.socket(socket.AF_UNIX)
            listener.bind(str(fixture / "personal" / (name + ".sock")))
            listener.listen(1)
            sockets.append(listener)
        try:
            before = self.snapshot(self.output)
            result = self.qualify(fixture)
            self.assertEqual(result["status"], "offline-fixture-qualified")
            self.assertEqual(result["roles"], ["serve", "bridge", "verification"])
            self.assertTrue(result["artifact_bound"])
            self.assertEqual(result["own_auth"], "fixture-positive-only")
            self.assertEqual(before, self.snapshot(self.output))
            # Removal of the own provider prerequisite must fail through the same path.
            (home / "provider-auth.fixture").unlink()
            value = self.qualify(fixture, success=False)
            self.assertEqual(value["reason"], "unprivileged-bwrap-fixture-unavailable-or-probe-failed")
            self.assertEqual(before, self.snapshot(self.output))
        finally:
            for listener in sockets:
                listener.close()

    def test_repair1_artifact_and_fixture_identity_refuse(self):
        fixture, home = self.fixture()
        before = self.snapshot(self.output)
        marker = json.loads((fixture / "fixture.json").read_text())
        self.save(fixture / "fixture.json", dict(marker, artifact_sha256="3" * 64))
        value = self.qualify(fixture, success=False)
        self.assertEqual(value["reason"], "fixture-identity")
        self.save(fixture / "fixture.json", marker)
        (home / "fixture-auth.json").chmod(0o644)
        self.qualify(fixture, success=False)
        self.assertEqual(before, self.snapshot(self.output))
        # A tampered exact candidate artifact must refuse before process execution.
        path = self.output / "qualification-runtime.py"
        original = path.read_bytes()
        path.write_bytes(b"print('fake proof')")
        self.qualify(fixture, success=False)
        path.write_bytes(original)
        self.assertEqual(before, self.snapshot(self.output))
        self.run_tool("retire-stage", "--output", self.output)
        retired = self.snapshot(self.output)
        self.qualify(fixture, success=False)
        self.assertEqual(retired, self.snapshot(self.output))

    def test_ci1_workflow_prerequisite_contract(self):
        contract = runpy.run_path(str(TOOL.parents[2] / "test/sandbox-ci-contract.py"))
        text = (TOOL.parents[2] / ".github/workflows/test.yml").read_text()
        self.assertTrue(contract["validate"](text))
        for old, new in (
            ('T3_LAPTOP_REQUIRE_SANDBOX: "1"', 'T3_LAPTOP_REQUIRE_SANDBOX: "0"'),
            ('  sandbox-qualification:', '  optional-qualification:'),
            ('    runs-on: ubuntu-24.04', '    if: false\n    runs-on: ubuntu-24.04'),
            ('sha256sum -c -', 'true'),
            (contract["SHA256"], "0" * 64),
            ('sudo install -m 0755 "$sandbox_build/build/bwrap" /usr/bin/bwrap', 'sudo install -m 0755 "$sandbox_build/build/bwrap" /tmp/bwrap'),
            ('sudo sysctl -w kernel.unprivileged_userns_clone=1', 'true'),
            ('-- /usr/bin/true', '-- /usr/bin/false'),
            ('run: python3 test/laptop-worker-isolation.py', 'run: echo passed'),
        ):
            with self.subTest(missing=old):
                self.assertIn(old, text)
                with self.assertRaises(AssertionError):
                    contract["validate"](text.replace(old, new))

    def test_ci1_missing_and_blocked_sandbox_production_refusals(self):
        fixture, home = self.fixture()
        functions = runpy.run_path(str(TOOL), run_name="blocked_fixture")
        real_run = subprocess.run
        for failure, reason in (
            ("missing", "unprivileged-bwrap-fixture-unavailable-or-timeout"),
            ("blocked", "unprivileged-bwrap-fixture-unavailable-or-probe-failed"),
        ):
            def unavailable(argv, **kwargs):
                if argv[0] != "/usr/bin/bwrap":
                    return real_run(argv, **kwargs)
                if failure == "missing":
                    raise FileNotFoundError("/usr/bin/bwrap")
                if argv[1:] == ["--version"]:
                    return subprocess.CompletedProcess(argv, 0, b"bubblewrap 0.12.0" + bytes([10]), b"")
                return subprocess.CompletedProcess(argv, 1, b"", b"namespace blocked")
            before = self.snapshot(self.output)
            with self.subTest(failure=failure), functions["private_dir"](str(self.output)) as directory:
                with mock.patch.object(subprocess, "run", side_effect=unavailable):
                    with self.assertRaisesRegex(functions["Refusal"], reason):
                        functions["qualify_fixture"](self.request, directory, str(fixture))
            self.assertEqual(before, self.snapshot(self.output))

    def test_repair1_exact_unsupported_fixture_capability(self):
        # No substitute sandbox or declaration can make unavailable bwrap pass.
        fixture, home = self.fixture()
        functions = runpy.run_path(str(TOOL), run_name="unsupported_fixture")
        real_run = subprocess.run
        def unsupported(argv, **kwargs):
            if argv[:2] == ["/usr/bin/bwrap", "--version"]:
                return subprocess.CompletedProcess(argv, 0, b"bubblewrap 0.11.0\n", b"")
            return real_run(argv, **kwargs)
        with functions["private_dir"](str(self.output)) as directory:
            with mock.patch.object(subprocess, "run", side_effect=unsupported):
                with self.assertRaisesRegex(functions["Refusal"], "unsupported-bwrap-version"):
                    functions["qualify_fixture"](self.request, directory, str(fixture))

if __name__ == "__main__":
    unittest.main(verbosity=2)
