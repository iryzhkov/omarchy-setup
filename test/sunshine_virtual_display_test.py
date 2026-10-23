#!/usr/bin/env python3
"""Deterministic Sunshine prep tests. No desktop, service or HA commands run."""
import copy
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
from typing import Any

import display_controller_test as fixtures

SOURCE = Path(__file__).resolve().parents[1] / "hosts/omarchy-pc/bin/sunshine-virtual-display"
loader = importlib.machinery.SourceFileLoader("sunshine_virtual_display", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
vd = importlib.util.module_from_spec(spec)
loader.exec_module(vd)


def setUpModule():
    fixtures.setUpModule()


class Host:
    def __init__(self):
        self.running = True
        self.system = fixtures.FakeSystem()
        self.profiles = self.system.profiles
        self.mon = self.system.mon
        self.ws = [{"id": 1, "name": "1", "monitor": "DP-1", "windows": 1},
                   {"id": -1337, "name": "notes", "monitor": "DP-1", "windows": 1},
                   {"id": -98, "name": "special:shown", "monitor": "DP-1"},
                   {"id": -99, "name": "special:hidden", "monitor": "DP-1"}]
        self.shown = {"special:shown"}
        self.calls = []
        self.fail: Any = None
        self.preview = False
        self.unmanaged = False
        self.move_hook: Any = None

    def active(self):
        return self.running

    def service(self, action):
        self.calls.append(("service", action))
        self.running = action == "start"
        self.failure("service-" + action)

    def failure(self, action):
        if self.fail == action:
            self.fail = None
            raise OSError("injected " + action)

    def editor(self):
        if self.preview or self.unmanaged:
            raise ValueError("human ownership")
        return {"source_profile": "desk", "profiles": copy.deepcopy(list(self.profiles.values()))}

    def monitors(self):
        return copy.deepcopy(self.mon)

    def command(self, *args):
        self.calls.append(args)
        if args[:2] == ("output", "create"):
            self.mon.append({"name": args[3], "disabled": False, "dpmsStatus": True,
                             "width": 1920, "height": 1080})
        elif args[:2] == ("output", "remove"):
            self.mon = [m for m in self.mon if m["name"] != args[2]]
        elif args[0] == "eval":
            match = re.search(r"output=(\"[^\"]+\")", args[1])
            assert match is not None
            name = json.loads(match[1])
            monitor = next(m for m in self.mon if m["name"] == name)
            if "disabled=true" in args[1]:
                monitor["disabled"] = True
            else:
                match = re.search(r'mode="([0-9]+)x([0-9]+)@', args[1])
                assert match is not None
                width, height = match.groups()
                monitor.update(width=int(width), height=int(height))
        elif args == ("reload",):
            for m in self.mon:
                m["disabled"] = m["name"] == vd.dc.TV_OUTPUT
                m["dpmsStatus"] = not m["disabled"]
        else:
            raise AssertionError(args)
        self.failure(args[0])

    def move(self, target, guard):
        if self.move_hook:
            self.move_hook()
        with mock.patch.object(vd.dc, "run", self.hypr):
            vd.dc.migrate_workspaces(target, guard)

    def hypr(self, args):
        if args[1:] == ["workspaces", "-j"]:
            return json.dumps(self.ws)
        if args[1:] == ["monitors", "all", "-j"]:
            monitors = self.monitors()
            for m in monitors:
                names = [w["name"] for w in self.ws
                         if w["name"] in self.shown and w["monitor"] == m["name"]]
                m["specialWorkspace"] = {"name": names[0] if names else ""}
            return json.dumps(monitors)
        if args[1] == "eval":
            self.calls.append(("move", args[2]))
            match = re.search(r'workspace=("[^"]+"),monitor=("[^"]+")', args[2])
            assert match is not None
            selector, target = match.groups()
            selector, target = json.loads(selector), json.loads(target)
            for w in self.ws:
                current = (w["name"] if w["name"].startswith("special:") else
                           str(w["id"]) if w["id"] > 0 else "name:" + w["name"])
                if current == selector:
                    w["monitor"] = target
            self.failure("move")
            return "ok"
        raise AssertionError(args)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.json"
        self.host = Host()
        self.session = vd.Session(self.host, self.path)
        self.size = vd.dimensions({})
        self.profile_files = []
        for name, profile in self.host.profiles.items():
            path = Path(self.temp.name) / (name + ".json")
            path.write_text(json.dumps(profile))
            self.profile_files.append(path)
        self.hashes = self.profile_hashes()

    def profile_hashes(self):
        return [hashlib.sha256(p.read_bytes()).hexdigest() for p in self.profile_files]

    def test_both_directions_order_visibility_and_profile_hashes(self):
        self.session.start((2560, 1440, 120, False))
        state = self.session.load()
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertFalse(self.host.running)
        self.assertTrue(all(w["monitor"] == state["output"] for w in self.host.ws))
        moves = [call[1] for call in self.host.calls if call[0] == "move"]
        self.assertIn('workspace="1"', moves[0])
        self.assertIn('workspace="name:notes"', moves[1])
        self.assertIn('workspace="special:shown"', moves[2])
        self.assertIn('workspace="special:hidden"', moves[3])
        self.session.stop()
        self.assertTrue(self.host.running)
        self.assertFalse(self.path.exists())
        self.assertTrue(all(w["monitor"] == "DP-1" for w in self.host.ws))
        self.assertEqual(self.host.shown, {"special:shown"})
        self.assertNotIn(state["output"], [m["name"] for m in self.host.mon])
        self.assertEqual(self.profile_hashes(), self.hashes)
        calls = copy.deepcopy(self.host.calls)
        self.session.stop()
        self.assertEqual(self.host.calls, calls)

    def test_initially_stopped_service_is_not_started(self):
        self.host.running = False
        self.session.start(self.size)
        self.session.stop()
        self.assertFalse(self.host.running)
        self.assertFalse(any(c[0] == "service" for c in self.host.calls))

    def test_preview_unmanaged_unknown_and_asleep_refuse_before_mutation(self):
        for fault in ("preview", "unmanaged", "unknown", "asleep"):
            with self.subTest(fault=fault):
                self.host = Host()
                self.session = vd.Session(self.host, self.path)
                if fault in ("preview", "unmanaged"):
                    setattr(self.host, fault, True)
                elif fault == "unknown":
                    self.host.mon.append({"name": "HEADLESS-HUMAN", "disabled": False})
                else:
                    self.host.mon[0]["dpmsStatus"] = False
                with self.assertRaises(ValueError):
                    self.session.start(self.size)
                self.assertEqual(self.host.calls, [])
                self.assertFalse(self.path.exists())

    def test_repeated_start_does_not_change_active_session(self):
        self.session.start(self.size)
        calls = copy.deepcopy(self.host.calls)
        with self.assertRaises(ValueError):
            self.session.start(self.size)
        self.assertEqual(self.host.calls, calls)

    def test_partial_start_failures_restore_or_retain_recoverable_journal(self):
        for fault in ("service-stop", "output", "eval", "move"):
            with self.subTest(fault=fault):
                self.host = Host()
                self.session = vd.Session(self.host, self.path)
                self.host.fail = fault
                with self.assertRaises(OSError):
                    self.session.start(self.size)
                self.session.stop()
                self.assertTrue(self.host.running)
                self.assertFalse(self.path.exists())
                self.assertEqual(self.profile_hashes(), self.hashes)

    def test_remove_timeout_cleanup_retry(self):
        self.session.start(self.size)
        self.host.fail = "output"  # removal took effect but reply was lost
        with self.assertRaises(OSError):
            self.session.stop()
        self.assertTrue(self.path.exists())
        self.assertFalse(self.host.running)
        self.session.stop()
        self.assertTrue(self.host.running)
        self.assertFalse(self.path.exists())

    def test_service_resume_timeout_retry_never_reloads_again(self):
        self.session.start(self.size)
        self.host.fail = "service-start"
        with self.assertRaises(OSError):
            self.session.stop()
        reloads = self.host.calls.count(("reload",))
        self.assertTrue(self.session.load()["restored"])
        self.session.stop()
        self.assertEqual(self.host.calls.count(("reload",)), reloads)

    def test_unknown_hotplug_cleanup_leaves_other_output_and_journal(self):
        self.session.start(self.size)
        self.host.mon.append({"name": "HEADLESS-HUMAN", "disabled": False})
        calls = copy.deepcopy(self.host.calls)
        with self.assertRaises(ValueError):
            self.session.stop()
        self.assertEqual(self.host.calls, calls)
        self.assertTrue(self.path.exists())
        self.host.mon.pop()
        self.session.stop()

    def test_independent_service_resume_refuses_cleanup(self):
        self.session.start(self.size)
        self.host.running = True
        calls = copy.deepcopy(self.host.calls)
        with self.assertRaises(ValueError):
            self.session.stop()
        self.assertEqual(self.host.calls, calls)
        self.assertTrue(self.path.exists())

    def test_identity_change_refuses_before_disable(self):
        self.host.profiles["desk"]["outputs"][0].update(make="Known")
        self.host.mon[0]["make"] = "Known"
        def hotplug():
            self.host.mon[0]["make"] = "Replacement"
        self.host.move_hook = hotplug
        with self.assertRaises(ValueError):
            self.session.start(self.size)
        self.assertFalse(any("disabled=true" in str(c) for c in self.host.calls))
        self.assertTrue(self.path.exists())

    def test_reload_failure_keeps_journal_and_retry_finishes(self):
        self.session.start(self.size)
        self.host.fail = "reload"
        with self.assertRaises(OSError):
            self.session.stop()
        self.assertTrue(self.path.exists())
        self.assertFalse(self.host.running)
        self.session.stop()
        self.assertTrue(self.host.running)

    def test_no_state_stop_does_not_start_stopped_service(self):
        self.host.running = False
        self.session.stop()
        self.assertEqual(self.host.calls, [])

    def test_hdr_rejection_falls_back_and_cleans_up(self):
        # First eval changed the mode but its reply was lost.
        self.host.fail = "eval"
        self.session.start((1920, 1080, 60, True))
        evals = [c[1] for c in self.host.calls if c[0] == "eval"]
        self.assertIn('cm="hdr"', evals[0])
        self.assertNotIn('cm="hdr"', evals[1])
        self.session.stop()
        self.assertTrue(self.host.running)

    def test_workspace_visibility_change_is_detected(self):
        before = self.host.hypr
        def lose_visibility(args):
            result = before(args)
            if args[1] == "eval":
                self.host.shown.clear()
            return result
        with mock.patch.object(vd.dc, "run", lose_visibility):
            with self.assertRaisesRegex(ValueError, "visibility"):
                vd.dc.migrate_workspaces("HDMI-A-1", lambda: None)

    def test_two_visible_specials_refuse_without_moving(self):
        self.host.mon[1]["disabled"] = False
        self.host.ws[-1]["monitor"] = vd.dc.TV_OUTPUT
        self.host.shown.add("special:hidden")
        with self.assertRaisesRegex(ValueError, "multiple visible"):
            self.host.move("new-output", lambda: None)
        self.assertEqual(self.host.calls, [])

    def test_missing_ipc_refuses_without_stopping_service(self):
        with mock.patch.object(self.host, "editor", side_effect=FileNotFoundError("no IPC")):
            with self.assertRaises(FileNotFoundError):
                self.session.start(self.size)
        self.assertEqual(self.host.calls, [])
        self.assertFalse(self.path.exists())

    def test_dimensions_refuse_before_runtime_or_commands(self):
        for key, value in (("WIDTH", "0"), ("WIDTH", "99999"), ("HEIGHT", "-1"),
                           ("FPS", "60;evil"), ("HDR", "yes"), ("WIDTH", "1920.0")):
            with self.subTest(key=key, value=value), mock.patch.dict(
                    os.environ, {"SUNSHINE_CLIENT_" + key: value}), mock.patch.object(
                        vd.dc, "runtime_dir") as runtime:
                self.assertEqual(vd.main(["start"]), 1)
                runtime.assert_not_called()


class LockTests(unittest.TestCase):
    def test_private_lock_and_overlap_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            with vd.locked_state(runtime) as path:
                self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
                self.assertEqual((path.parent / "lock").stat().st_mode & 0o777, 0o600)
                with self.assertRaises(BlockingIOError):
                    with vd.locked_state(runtime):
                        self.fail("overlapping handoff")

    def test_unsafe_state_directory_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            (runtime / "sunshine-virtual-display").symlink_to(runtime, target_is_directory=True)
            with self.assertRaises(ValueError):
                with vd.locked_state(runtime):
                    self.fail("symlink accepted")


class FinalRouteTests(unittest.TestCase):
    def test_controller_moves_specials_after_final_ha_route_both_directions(self):
        dc = fixtures.dc
        system = fixtures.FakeSystem()
        system.ws.extend([{"id": -98, "name": "special:shown", "monitor": "DP-1"},
                          {"id": -99, "name": "special:hidden", "monitor": "DP-1"}])
        coordinator = dc.Coordinator(system, lambda: system.now)
        coordinator.step()
        system.advance(dc.POLL)
        coordinator.step()  # regular transaction changes from restored desk to HA TV
        coordinator.step()  # healthy TV route reconciles special placement
        self.assertTrue(all(w["monitor"] == dc.TV_OUTPUT for w in system.ws))
        self.assertEqual(system.saved, system.profiles)
        system.states = fixtures.ha(source="Other")
        coordinator.step()
        system.advance(dc.POLL)
        coordinator.step()
        coordinator.step()
        self.assertTrue(all(w["monitor"] == "DP-1" for w in system.ws))
        self.assertEqual(system.saved, system.profiles)

    def test_controller_specials_defer_on_existing_safety_boundaries(self):
        dc = fixtures.dc
        for fault in ("preview", "unmanaged", "unknown", "asleep", "uncertain"):
            with self.subTest(fault=fault):
                system = fixtures.FakeSystem()
                system.states = fixtures.ha(source="Other")
                move = mock.Mock()
                system.move_special_workspaces = move
                if fault in ("preview", "unmanaged"):
                    setattr(system, fault, True)
                elif fault == "unknown":
                    system.mon.append({"name": "HEADLESS-HUMAN", "disabled": False})
                elif fault == "asleep":
                    system.mon[0]["dpmsStatus"] = False
                else:
                    system.states = []
                coordinator = dc.Coordinator(system, lambda: system.now)
                coordinator.step()
                system.advance(dc.POLL)
                coordinator.step()
                move.assert_not_called()


if __name__ == "__main__":
    unittest.main()
