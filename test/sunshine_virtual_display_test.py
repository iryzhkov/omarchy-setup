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
                             "width": 1920, "height": 1080, "refreshRate": 60.0,
                             "scale": 1.0, "x": 0, "y": 0, "transform": 0})
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
                monitor.update(disabled=False, dpmsStatus=True)
                match = re.search(r'mode="([0-9]+)x([0-9]+)@([0-9]+)"', args[1])
                if match is not None:
                    width, height, fps = map(int, match.groups())
                    monitor.update(width=width, height=height, refreshRate=float(fps))
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
            migration = vd.dc.migrate_workspaces(target, guard)
        def verify(final=False):
            with mock.patch.object(vd.dc, "run", self.hypr):
                migration(final=final)
        return verify

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



class Compositor(Host):
    """IPC adapter fixture: rule acceptance and later render application differ."""
    def __init__(self, *, delayed=False, refill=False, disable_on_reload=False):
        super().__init__()
        self.delayed, self.refill = delayed, refill
        self.disable_on_reload = disable_on_reload
        self.now = 0.0
        self.pending = []
        self.never = set()
        self.on_wait: Any = None
        self.refill_metadata = {"windows": 0, "ispersistent": False}
        for index, m in enumerate(self.mon):
            m.update(id=index, refreshRate=60.0, scale=1.0, x=0, y=0, transform=0)

    def wait(self, seconds):
        self.now += seconds
        if self.on_wait:
            self.on_wait()
        ready = [item for item in self.pending if item[0] <= self.now]
        self.pending = [item for item in self.pending if item[0] > self.now]
        for _, apply in ready:
            apply()

    def schedule(self, action, apply):
        if action in self.never:
            return
        if self.delayed:
            self.pending.append((self.now + 0.2, apply))
        else:
            apply()

    def command(self, *args):
        self.calls.append(args)
        if args[:2] == ("output", "create"):
            def create():
                self.mon.append({"name": args[3], "id": 10 + len(self.calls),
                                 "disabled": False, "dpmsStatus": True,
                                 "width": 1920, "height": 1080, "refreshRate": 60.0,
                                 "scale": 1.0, "x": 0, "y": 0, "transform": 0})
            self.schedule("create", create)
        elif args[:2] == ("output", "remove"):
            own = next(m for m in self.mon if m["name"] == args[2])
            if own["disabled"]:
                raise ValueError("output not found")
            def remove():
                self.mon = [m for m in self.mon if m["name"] != args[2]]
                self.ws = [w for w in self.ws if w["monitor"] != args[2]]
            self.schedule("remove", remove)
        elif args[0] == "eval":
            match = re.search(r'output=("[^"]+")', args[1])
            assert match is not None
            name = json.loads(match[1])
            def rule():
                monitor = next(m for m in self.mon if m["name"] == name)
                disabled = "disabled=true" in args[1]
                monitor.update(disabled=disabled, dpmsStatus=not disabled)
                mode = re.search(r'mode="([0-9]+)x([0-9]+)@([0-9]+)"', args[1])
                if mode:
                    width, height, fps = map(int, mode.groups())
                    monitor.update(width=width, height=height, refreshRate=float(fps),
                                   scale=1.0, x=0, y=0)
                if disabled:
                    # Only explicitly empty nonpersistent workspaces may disappear.
                    self.ws = [w for w in self.ws if w["monitor"] != name
                               or w.get("windows") != 0 or w.get("ispersistent") is not False]
            action = "disable" if "disabled=true" in args[1] else "mode"
            self.schedule(action, rule)
        elif args == ("reload",):
            def reload():
                for m in self.mon:
                    disabled = (m["name"] == vd.dc.TV_OUTPUT
                                or self.disable_on_reload and m["name"].startswith("HEADLESS-"))
                    m.update(disabled=disabled, dpmsStatus=not disabled)
            self.schedule("reload", reload)
        else:
            raise AssertionError(args)

    def hypr(self, args):
        if args[1] != "eval":
            return super().hypr(args)
        before = {w["name"]: w["monitor"] for w in self.ws}
        result = super().hypr(args)
        if self.refill:
            for source in set(before.values()):
                enabled = any(m["name"] == source and m["disabled"] is False for m in self.mon)
                regulars = [w for w in self.ws if w["monitor"] == source
                            and not w["name"].startswith("special:")]
                if enabled and not regulars:
                    number = max([w["id"] for w in self.ws if w["id"] > 0] + [0]) + 1
                    self.ws.append({"id": number, "name": str(number), "monitor": source,
                                    **self.refill_metadata})
        return result

    def run(self, args, timeout=5):
        if args[0] == "systemctl":
            self.service(args[2])
            return ""
        if args[1:] == ["monitors", "all", "-j"] or args[1:] == ["workspaces", "-j"]:
            return self.hypr(args)
        if args[1] == "eval" and "workspace.move" in args[2]:
            return self.hypr(args)
        self.command(*args[1:])
        return "ok"


class AdapterTests(unittest.TestCase):
    """Exercise Session through the real Host monitors/command/move adapter."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.json"

    def attach(self, compositor):
        host = vd.Host(Path(self.temp.name))
        patches = [
            mock.patch.object(host, "active", side_effect=compositor.active),
            mock.patch.object(host, "editor", side_effect=compositor.editor),
            mock.patch.object(vd.dc, "run", side_effect=compositor.run),
            mock.patch.object(vd, "time", mock.Mock(
                monotonic=lambda: compositor.now, sleep=compositor.wait), create=True),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        return vd.Session(host, self.path)

    def test_refill_survives_until_disable_then_final_placement_is_verified(self):
        c = Compositor(refill=True)
        session = self.attach(c)
        session.start((1920, 1080, 60, False))
        output = session.load()["output"]
        self.assertTrue(all(w["monitor"] == output for w in c.ws))
        session.stop()
        self.assertTrue(all(w["monitor"] == "DP-1" for w in c.ws))
        self.assertFalse(self.path.exists())

    def test_creation_mode_isolation_and_restore_converge_after_acceptance(self):
        c = Compositor(delayed=True)
        session = self.attach(c)
        session.start((2560, 1440, 120, False))
        self.assertEqual([m["name"] for m in c.mon if not m["disabled"]],
                         [session.load()["output"]])
        session.stop()
        self.assertGreaterEqual(c.now, 0.8)
        self.assertTrue(c.running)
        self.assertFalse(self.path.exists())

    def test_reload_disabled_output_is_reenabled_destroyed_and_absent(self):
        c = Compositor(disable_on_reload=True)
        session = self.attach(c)
        session.start((1920, 1080, 60, False))
        output = session.load()["output"]
        session.stop()
        self.assertNotIn(output, [m["name"] for m in c.mon])
        # The next helper start and controller topology must both be usable.
        self.assertTrue(vd.dc.topology(c.mon, c.profiles, c.profiles["desk"]))
        session.start((1920, 1080, 60, False))
        session.stop()

    def test_restore_waits_for_new_physical_layout_before_removal(self):
        c = Compositor()
        session = self.attach(c)
        session.start((1920, 1080, 60, False))
        c.delayed = True
        session.stop()
        self.assertTrue(c.running)
        self.assertFalse(self.path.exists())
        self.assertEqual([m["name"] for m in c.mon if not m["disabled"]], ["DP-1"])

    def test_delayed_refill_and_disabled_restore_complete_together(self):
        c = Compositor(delayed=True, refill=True, disable_on_reload=True)
        session = self.attach(c)
        session.start((2560, 1440, 120, False))
        self.assertTrue(all(w["monitor"] == session.load()["output"] for w in c.ws))
        session.stop()
        self.assertTrue(all(w["monitor"] == "DP-1" for w in c.ws))
        self.assertFalse(self.path.exists())
        self.assertEqual(c.shown, {"special:shown"})

    def test_special_noop_skips_guard_but_actual_moves_are_guarded(self):
        c = Compositor()
        with mock.patch.object(vd.dc, "run", side_effect=c.run):
            guard = mock.Mock()
            vd.dc.migrate_workspaces("DP-1", guard, special_only=True)
            guard.assert_not_called()
            vd.dc.migrate_workspaces(vd.dc.TV_OUTPUT, guard, special_only=True)
            self.assertEqual(guard.call_count, 2)
            self.assertEqual(c.shown, {"special:shown"})

    def test_each_start_convergence_timeout_compensates(self):
        for stage in ("create", "mode", "disable"):
            with self.subTest(stage=stage):
                c = Compositor(delayed=True)
                c.never.add(stage)
                session = self.attach(c)
                with self.assertRaises(TimeoutError):
                    session.start((2560, 1440, 120, False))
                self.assertTrue(c.running)
                self.assertFalse(self.path.exists())
                self.assertGreaterEqual(c.now, vd.CONVERGENCE_TIMEOUT)
                self.assertLess(c.now, 2 * vd.CONVERGENCE_TIMEOUT)

    def test_restore_and_remove_timeouts_retain_journal_and_retry(self):
        for stage in ("reload", "mode", "remove"):
            with self.subTest(stage=stage):
                c = Compositor(disable_on_reload=True)
                session = self.attach(c)
                session.start((1920, 1080, 60, False))
                c.never.add(stage)
                with self.assertRaises(TimeoutError):
                    session.stop()
                state = session.load()
                self.assertIsNotNone(state)
                self.assertFalse(state["restored"])
                self.assertFalse(c.running)
                self.assertTrue(any(m["name"] == state["output"] for m in c.mon))
                c.never.clear()
                session.stop()
                self.assertTrue(c.running)
                self.assertFalse(self.path.exists())

    def test_wait_rechecks_unknown_hotplug_and_cancellation_before_writes(self):
        for fault in ("hotplug", "cancel", "service"):
            with self.subTest(fault=fault):
                c = Compositor(delayed=True)
                session = self.attach(c)
                cancelled = [False]
                session.stopped = lambda: cancelled[0]
                def interrupt():
                    if fault == "hotplug":
                        c.mon.append({"name": "HEADLESS-HUMAN", "disabled": True})
                    elif fault == "cancel":
                        cancelled[0] = True
                    else:
                        c.running = True
                    c.on_wait = None
                c.on_wait = interrupt
                with self.assertRaises((OSError, ValueError)):
                    session.start((1920, 1080, 60, False))
                self.assertTrue(self.path.exists())
                self.assertFalse(any(call[0] in ("eval", "move", "reload")
                                     for call in c.calls))
                # Resolve the fixture conflict and exercise the documented retry.
                c.mon = [m for m in c.mon if m["name"] != "HEADLESS-HUMAN"]
                cancelled[0] = False
                c.running = False
                session.stop()
                self.assertFalse(self.path.exists())

    def test_final_verification_requires_all_regulars_and_required_survival(self):
        for fault in ("retained_refill", "lost_required", "misplaced_required"):
            with self.subTest(fault=fault):
                c = Compositor(refill=True)
                with mock.patch.object(vd.dc, "run", side_effect=c.run):
                    verify = vd.dc.migrate_workspaces(vd.dc.TV_OUTPUT, lambda: None)
                    if fault == "lost_required":
                        c.ws = [w for w in c.ws if w["id"] != 1]
                    elif fault == "misplaced_required":
                        c.ws[0]["monitor"] = "DP-1"
                    with self.assertRaises(ValueError):
                        verify(final=True)

    def test_mode_checks_refresh_scale_and_position_before_workspace_moves(self):
        for key, wrong in (("refreshRate", 60.0), ("scale", 2.0), ("x", 100)):
            with self.subTest(key=key):
                c = Compositor()
                session = self.attach(c)
                original = c.schedule
                def wrong_mode(action, apply):
                    original(action, apply)
                    if action == "mode":
                        c.mon[-1][key] = wrong
                with mock.patch.object(c, "schedule", side_effect=wrong_mode):
                    with self.assertRaises(TimeoutError):
                        session.start((2560, 1440, 120, False))
                # Compensation moves to DP-1, never to the unverified output.
                self.assertFalse(any(call[0] == "move" and "HEADLESS-SUNSHINE" in call[1]
                                     for call in c.calls))
                self.assertTrue(c.running)
                self.assertFalse(self.path.exists())

    def test_unknown_or_occupied_refill_is_not_tolerated(self):
        for metadata in ({}, {"windows": 1, "ispersistent": False},
                         {"windows": 0, "ispersistent": True}):
            with self.subTest(metadata=metadata):
                c = Compositor(refill=True)
                c.refill_metadata = metadata
                with mock.patch.object(vd.dc, "run", side_effect=c.run):
                    with self.assertRaises(ValueError):
                        vd.dc.migrate_workspaces(vd.dc.TV_OUTPUT, lambda: None)


if __name__ == "__main__":
    unittest.main()
