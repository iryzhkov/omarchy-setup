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

    def ipc_editor(self, source, override, **status):
        daemon = {"ipc_only": True, "running": True,
                  "profile_override": override, **status}
        editor = {"source_profile": source,
                  "profiles": copy.deepcopy(list(self.host.profiles.values()))}
        connection = mock.MagicMock()
        connection.request.side_effect = lambda method: (
            {"daemon": copy.deepcopy(daemon)} if method == "status"
            else copy.deepcopy(editor))
        adapter = vd.Host(Path(self.temp.name))
        factory = mock.MagicMock()
        factory.return_value.__enter__.return_value = connection
        self.host.editor = adapter.editor
        return factory

    def test_live_ephemeral_override_through_real_editor_adapter(self):
        # Live IPC reports no saved source for a temporary committed profile.
        self.host.system.apply("tv-game")
        self.host.mon = self.host.system.mon
        for workspace in self.host.ws:
            workspace["monitor"] = vd.dc.TV_OUTPUT
        factory = self.ipc_editor(None, "tv-game", preview=False, unmanaged=None)
        with mock.patch.object(vd.dc, "IPC", factory):
            self.session.start(self.size)
        self.assertFalse(self.host.running)
        self.assertTrue(all(w["monitor"] == self.session.load()["output"]
                            for w in self.host.ws))
        self.session.stop()
        self.assertTrue(self.host.running)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.profile_hashes(), self.hashes)

    def test_editor_source_precedence_and_missing_or_unknown_override(self):
        factory = self.ipc_editor("desk", "tv-game")
        with mock.patch.object(vd.dc, "IPC", factory):
            self.assertEqual(self.host.editor()["source_profile"], "desk")
        for override in (None, "unknown-profile"):
            with self.subTest(override=override):
                factory = self.ipc_editor(None, override)
                with mock.patch.object(vd.dc, "IPC", factory):
                    with self.assertRaises(ValueError):
                        self.session.start(self.size)
                self.assertEqual(self.host.calls, [])
                self.assertFalse(self.path.exists())

    def test_override_never_bypasses_daemon_ownership_or_capability(self):
        for status in ({"preview": {"id": "human"}},
                       {"unmanaged": True}, {"ipc_only": False},
                       {"running": False}):
            with self.subTest(status=status):
                factory = self.ipc_editor(None, "tv-game", **status)
                with mock.patch.object(vd.dc, "IPC", factory):
                    with self.assertRaises(ValueError):
                        self.session.start(self.size)
                self.assertEqual(self.host.calls, [])
                self.assertFalse(self.path.exists())

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
        self.active_ws = {"DP-1": 1}
        self.focused = "DP-1"
        self.lifecycle = []
        for index, m in enumerate(self.mon):
            m.update(id=index, refreshRate=60.0, scale=1.0, x=0, y=0, transform=0)

    def regulars(self, output):
        return [w for w in self.ws if w["monitor"] == output
                and not w["name"].startswith("special:")]

    def default_workspace(self, output):
        # Monitor::findAvailableDefaultWS and workspace gap filling both choose
        # the lowest free positive ID, in global workspace creation order.
        number = 1
        while any(w["id"] == number for w in self.ws):
            number += 1
        self.ws.append({"id": number, "name": str(number), "monitor": output,
                        **self.refill_metadata})
        self.active_ws[output] = number
        self.lifecycle.append(("create", number, output))
        return number

    def monitor_workspaces(self):
        if not self.refill:
            return
        for m in self.mon:
            name = m["name"]
            if m["disabled"]:
                self.active_ws.pop(name, None)
                self.ws = [w for w in self.ws if w["monitor"] != name
                           or w.get("windows") != 0 or w.get("ispersistent") is not False]
            elif name not in self.active_ws:
                regulars = self.regulars(name)
                if regulars:
                    self.active_ws[name] = regulars[0]["id"]
                else:
                    self.default_workspace(name)
        if self.focused not in self.active_ws:
            self.focused = next(iter(self.active_ws))

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
                if self.refill:
                    self.default_workspace(args[3])
            self.schedule("create", create)
        elif args[:2] == ("output", "remove"):
            own = next(m for m in self.mon if m["name"] == args[2])
            if own["disabled"]:
                raise ValueError("output not found")
            def remove():
                self.mon = [m for m in self.mon if m["name"] != args[2]]
                self.ws = [w for w in self.ws if w["monitor"] != args[2]]
                self.active_ws.pop(args[2], None)
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
                self.monitor_workspaces()
            action = "disable" if "disabled=true" in args[1] else "mode"
            self.schedule(action, rule)
        elif args == ("reload",):
            def reload():
                for m in self.mon:
                    disabled = (m["name"] == vd.dc.TV_OUTPUT
                                or self.disable_on_reload and m["name"].startswith("HEADLESS-"))
                    m.update(disabled=disabled, dpmsStatus=not disabled)
                self.monitor_workspaces()
            self.schedule("reload", reload)
        else:
            raise AssertionError(args)

    def hypr(self, args):
        if args[1] != "eval" or not self.refill:
            return super().hypr(args)
        match = re.search(r'workspace=("[^"]+"),monitor=("[^"]+")', args[2])
        assert match is not None
        selector, target = map(json.loads, match.groups())
        workspace = next((w for w in self.ws if selector == (
            w["name"] if w["name"].startswith("special:") else
            str(w["id"]) if w["id"] > 0 else "name:" + w["name"])), None)
        if workspace is None or workspace["name"].startswith("special:"):
            return super().hypr(args)
        source = workspace["monitor"]
        if source == target:
            return "ok"
        active = self.active_ws.get(source) == workspace["id"]
        focused = self.focused == source
        if active:
            replacements = [w for w in self.regulars(source) if w is not workspace]
            if replacements:
                self.active_ws[source] = replacements[0]["id"]
            else:
                self.default_workspace(source)
        old_target = self.active_ws.get(target)
        result = super().hypr(args)
        if active and focused:
            self.active_ws[target] = workspace["id"]
            self.focused = target
            self.lifecycle.append(("focus", workspace["id"], target))
            # Releasing Monitor's old active workspace weak reference destroys an
            # empty nonpersistent target workspace after the dispatch completes.
            replaced = next((w for w in self.ws if w["id"] == old_target), None)
            if (replaced is not None and replaced.get("windows") == 0
                    and replaced.get("ispersistent") is False
                    and old_target not in self.active_ws.values()):
                self.ws.remove(replaced)
                self.lifecycle.append(("destroy", old_target, target))
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

    @staticmethod
    def two_occupied_workspaces(c):
        c.ws = [{"id": n, "name": str(n), "monitor": "DP-1",
                 "windows": 1, "ispersistent": False} for n in (1, 2)] + [
                     w for w in c.ws if w["name"].startswith("special:")]
        c.active_ws = {"DP-1": 1}
        c.focused = "DP-1"

    def test_lowest_free_id_reuse_during_start(self):
        c = Compositor(refill=True)
        self.two_occupied_workspaces(c)
        session = self.attach(c)
        session.start((1920, 1080, 60, False))
        output = session.load()["output"]
        self.assertEqual(c.lifecycle[:4], [
            ("create", 3, output), ("focus", 1, output),
            ("destroy", 3, output), ("create", 3, "DP-1")])
        self.assertTrue(all(w["monitor"] == output for w in c.ws))
        self.assertEqual({w["id"] for w in c.regulars(output)}, {1, 2})
        session.stop()
        self.assertFalse(self.path.exists())

    def test_lowest_free_id_reuse_during_stop_without_manual_retry(self):
        c = Compositor(refill=True)
        self.two_occupied_workspaces(c)
        session = self.attach(c)
        # Seed the successfully streamed state independently of start, so a
        # start regression cannot prevent exercising the real stop adapter.
        output = "HEADLESS-SUNSHINE-" + "a" * 32
        c.command("output", "create", "headless", output)
        c.ws = [w for w in c.ws if w["id"] != 3]
        for w in c.ws:
            w["monitor"] = output
        c.mon[0].update(disabled=True, dpmsStatus=False)
        c.active_ws = {output: 1}
        c.focused = output
        c.running = False
        c.lifecycle.clear()
        session.save({"version": 1, "service_active": True, "output": output,
                      "profiles": copy.deepcopy(c.profiles),
                      "mutated": True, "restored": False})
        session.stop()
        self.assertEqual(c.lifecycle[:4], [
            ("create", 3, "DP-1"), ("focus", 1, "DP-1"),
            ("destroy", 3, "DP-1"), ("create", 3, output)])
        self.assertEqual({w["id"] for w in c.regulars("DP-1")}, {1, 2})
        self.assertTrue(all(w["monitor"] == "DP-1" for w in c.ws))
        self.assertNotIn(output, [m["name"] for m in c.mon])
        self.assertTrue(c.running)
        self.assertFalse(self.path.exists())

    def test_interim_refuses_misplaced_occupied_persistent_or_unknown(self):
        for metadata in ({"windows": 1, "ispersistent": False},
                         {"windows": 0, "ispersistent": True},
                         {}, {"windows": 0}, {"ispersistent": False},
                         {"windows": False, "ispersistent": False},
                         {"windows": None, "ispersistent": False},
                         {"windows": "0", "ispersistent": False},
                         {"windows": 0, "ispersistent": None}):
            with self.subTest(metadata=metadata):
                c = Compositor()
                c.ws.append({"id": 3, "name": "3", "monitor": "DP-1", **metadata})
                def leave_workspace(args, timeout=5):
                    if args[1] == "eval" and 'workspace="3"' in args[2]:
                        return "ok"
                    return c.run(args, timeout)
                with mock.patch.object(vd.dc, "run", side_effect=leave_workspace):
                    with self.assertRaises(ValueError):
                        vd.dc.migrate_workspaces(vd.dc.TV_OUTPUT, lambda: None)

    def test_interim_keeps_preexisting_required_on_target_even_if_now_empty(self):
        c = Compositor()
        def leave_workspace(args, timeout=5):
            if args[1] == "eval" and 'workspace="1"' in args[2]:
                c.ws[0].update(windows=0, ispersistent=False)
                return "ok"
            return c.run(args, timeout)
        with mock.patch.object(vd.dc, "run", side_effect=leave_workspace):
            with self.assertRaises(ValueError):
                vd.dc.migrate_workspaces(vd.dc.TV_OUTPUT, lambda: None)

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

    def test_special_noop_does_not_verify_concurrent_user_changes(self):
        for change in ("toggle", "destroy", "no_regulars"):
            with self.subTest(change=change):
                c = Compositor()
                queries = []
                def changed(args, timeout=5):
                    queries.append(args[1:])
                    self.assertEqual(args[1:], ["workspaces", "-j"])
                    result = c.run(args, timeout)
                    if change == "toggle":
                        c.shown.clear()
                    elif change == "destroy":
                        c.ws = [w for w in c.ws if not w["name"].startswith("special:")]
                    return result
                if change == "no_regulars":
                    c.ws = [w for w in c.ws if w["name"].startswith("special:")]
                with mock.patch.object(vd.dc, "run", side_effect=changed):
                    guard = mock.Mock()
                    verify = vd.dc.migrate_workspaces("DP-1", guard, special_only=True)
                    verify(final=True)
                    guard.assert_not_called()
                self.assertEqual(queries, [["workspaces", "-j"]])

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


class ReceiverCompositor(Compositor):
    """Recorded TV-off receiver identity; reload first re-enables physical HDMI."""
    def __init__(self):
        super().__init__()
        identities = {
            "DP-1": ("Samsung Electric Company", "Odyssey G95SC", "H1AK500000"),
            vd.dc.TV_OUTPUT: ("Sony", "SONY TV  *30", "0x01010101"),
        }
        for profile in self.profiles.values():
            for output in profile["outputs"]:
                output.update(zip(("make", "model", "serial"), identities[output["name"]]))
        self.mon[0].update(make="Samsung Electric Company", model="Odyssey G95SC",
                           serial="H1AK500000", disabled=True, dpmsStatus=True,
                           width=5120, height=1440, refreshRate=239.99899, scale=1.25,
                           x=0, y=-72)
        self.mon[1].update(make="Sony", model="SONY AVSYSTEM", serial="0x01010101",
                           disabled=False, dpmsStatus=True, width=1280, height=720,
                           refreshRate=60.0, scale=1.6, x=0, y=0)
        for monitor in self.mon:
            monitor.update({
                "currentFormat": "XRGB8888", "colorManagementPreset": "srgb", "vrr": False,
                "sdrBrightness": 1, "sdrSaturation": 1,
                "sdrMinLuminance": 0.2, "sdrMaxLuminance": 80})
        self.initial = copy.deepcopy(self.mon)
        for workspace in self.ws:
            workspace["monitor"] = vd.dc.TV_OUTPUT
        self.physical_ready = False

    def command(self, *args):
        if args == ("reload",):
            self.calls.append(args)
            if "reload" not in self.never:
                self.mon[0]["disabled"] = True
                self.mon[1].update(disabled=False, dpmsStatus=True,
                                   width=3840, height=2160, refreshRate=60.0,
                                   scale=1.0, x=90, colorManagementPreset="hdr",
                                   currentFormat="XRGB2101010", vrr=True,
                                   sdrBrightness=0.9, sdrSaturation=0.8,
                                   sdrMinLuminance=0.1, sdrMaxLuminance=100)
                self.physical_ready = True
            return
        if args[0] == "eval" and 'output="HDMI-A-1"' in args[1] and "disabled=true" not in args[1]:
            # Lua disabled=false alone does not revive a physical output.
            self.calls.append(args)
            if not self.physical_ready or "physical" in self.never:
                return
            monitor = self.mon[1]
            mode = re.search(r'mode="([0-9]+)x([0-9]+)@([0-9.]+)"', args[1])
            if mode:
                width, height, fps = mode.groups()
                monitor.update(width=int(width), height=int(height), refreshRate=float(fps))
            for key in ("scale", "transform"):
                value = re.search(key + r"=([0-9.]+)", args[1])
                if value:
                    monitor[key] = int(value[1]) if key == "transform" else float(value[1])
            position = re.search(r'position="(-?[0-9]+)x(-?[0-9]+)"', args[1])
            if position:
                monitor.update(x=int(position[1]), y=int(position[2]))
            for field, lua in (("sdrBrightness", "sdrbrightness"),
                               ("sdrSaturation", "sdrsaturation"),
                               ("sdrMinLuminance", "sdr_min_luminance"),
                               ("sdrMaxLuminance", "sdr_max_luminance")):
                value = re.search(lua + r"=([0-9.]+)", args[1])
                if value:
                    monitor[field] = float(value[1])
            if "bitdepth=8" in args[1]:
                monitor["currentFormat"] = "XRGB8888"
            if 'cm="srgb"' in args[1]:
                monitor["colorManagementPreset"] = "srgb"
            if "vrr=0" in args[1]:
                monitor["vrr"] = False
            monitor.update(disabled=False, dpmsStatus=True)
            return
        super().command(*args)


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.json"
        self.c = ReceiverCompositor()
        host = vd.Host(Path(self.temp.name))
        connection = mock.MagicMock()
        self.daemon = {"ipc_only": True, "running": True, "profile_override": None,
                       "preview": False, "unmanaged": None}
        self.editor = {"source_profile": None,
                       "profiles": copy.deepcopy(list(self.c.profiles.values()))}
        connection.request.side_effect = lambda method: (
            {"daemon": copy.deepcopy(self.daemon)} if method == "status"
            else copy.deepcopy(self.editor))
        factory = mock.MagicMock()
        factory.return_value.__enter__.return_value = connection
        for patch in (
                mock.patch.object(vd.dc, "IPC", factory),
                mock.patch.object(host, "active", side_effect=self.c.active),
                mock.patch.object(vd.dc, "run", side_effect=self.c.run),
                mock.patch.object(vd, "time", mock.Mock(
                    monotonic=lambda: self.c.now, sleep=self.c.wait))):
            patch.start()
            self.addCleanup(patch.stop)
        self.session = vd.Session(host, self.path)

    def test_null_source_receiver_start_stop_exact_restore(self):
        saved = copy.deepcopy(self.c.profiles)
        self.session.start((2560, 1440, 120, False))
        state = self.session.load()
        self.assertFalse(self.c.running)
        self.assertTrue(all(w["monitor"] == state["output"] for w in self.c.ws))
        self.session.stop()
        self.assertEqual(self.c.mon, self.c.initial)
        self.assertTrue(all(w["monitor"] == vd.dc.TV_OUTPUT for w in self.c.ws))
        self.assertEqual(self.c.shown, {"special:shown"})
        self.assertTrue(self.c.running)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.c.profiles, saved)
        # Exact rule qualified live, including spelling, numeric format and SDR.
        self.assertIn(("eval", 'hl.monitor({output="HDMI-A-1",mode="1280x720@60",'
                       'position="0x0",scale=1.6,transform=0,disabled=false,bitdepth=8,'
                       'cm="srgb",vrr=0,sdrbrightness=1,sdrsaturation=1,'
                       'sdr_min_luminance=0.2,sdr_max_luminance=80})'), self.c.calls)

    def test_receiver_recognized_source_also_uses_snapshot(self):
        self.editor["source_profile"] = "tv-game"
        self.session.start((1920, 1080, 60, False))
        self.assertIn("physical_snapshot", self.session.load())
        self.session.stop()
        self.assertEqual(self.c.mon, self.c.initial)

    def test_receiver_initially_stopped_service_remains_stopped(self):
        self.c.running = False
        self.session.start((1920, 1080, 60, False))
        self.session.stop()
        self.assertFalse(self.c.running)
        self.assertFalse(any(call[0] == "service" for call in self.c.calls))

    def test_receiver_ownership_identity_and_unqualified_states_refuse_before_writes(self):
        initial = copy.deepcopy(self.c.mon)
        for fault in ("preview", "unmanaged", "source", "serial", "model", "desk",
                      "extra", "absent", "all-disabled", "dpms", "hdr", "vrr"):
            with self.subTest(fault=fault):
                self.c.mon = copy.deepcopy(initial)
                self.daemon.update(preview=False, unmanaged=None)
                self.editor["source_profile"] = None
                if fault in ("preview", "unmanaged"):
                    self.daemon[fault] = True
                elif fault == "source":
                    self.editor["source_profile"] = "unknown"
                elif fault in ("serial", "model"):
                    self.c.mon[1][fault] = "Replacement"
                elif fault == "desk":
                    self.c.mon[0]["serial"] = "Replacement"
                elif fault == "extra":
                    self.c.mon.append({"name": "HEADLESS-HUMAN", "disabled": True})
                elif fault == "absent":
                    self.c.mon.pop(0)
                elif fault == "all-disabled":
                    self.c.mon[1]["disabled"] = True
                elif fault == "dpms":
                    self.c.mon[1]["dpmsStatus"] = False
                elif fault == "hdr":
                    self.c.mon[1]["colorManagementPreset"] = "hdr"
                else:
                    self.c.mon[1]["vrr"] = True
                with self.assertRaises(ValueError):
                    self.session.start((1920, 1080, 60, False))
                self.assertEqual(self.c.calls, [])
                self.assertFalse(self.path.exists())

    def test_receiver_cleanup_identity_or_connector_change_is_retryable(self):
        self.session.start((1920, 1080, 60, False))
        physical = copy.deepcopy(self.c.mon)
        for fault in ("identity", "missing", "extra", "service"):
            with self.subTest(fault=fault):
                self.c.mon = copy.deepcopy(physical)
                self.c.running = False
                if fault == "identity":
                    self.c.mon[1]["model"] = "Replacement"
                elif fault == "missing":
                    self.c.mon.pop(0)
                elif fault == "extra":
                    self.c.mon.append({"name": "HEADLESS-HUMAN", "disabled": True})
                else:
                    self.c.running = True
                calls = copy.deepcopy(self.c.calls)
                with self.assertRaises(ValueError):
                    self.session.stop()
                self.assertEqual(self.c.calls, calls)
                self.assertTrue(self.path.exists())
        self.c.mon = physical
        self.c.running = False
        self.session.stop()
        self.assertEqual(self.c.mon, self.c.initial)

    def test_receiver_restore_failures_keep_service_stopped_and_journal_for_retry(self):
        for stage in ("reload", "physical", "remove"):
            with self.subTest(stage=stage):
                self.session.start((1920, 1080, 60, False))
                output = self.session.load()["output"]
                self.c.physical_ready = False
                self.c.never.add(stage)
                with self.assertRaises(TimeoutError):
                    self.session.stop()
                self.assertFalse(self.c.running)
                self.assertTrue(self.path.exists())
                self.assertFalse(self.session.load()["restored"])
                self.assertIn(output, [m["name"] for m in self.c.mon])
                self.c.never.clear()
                self.session.stop()
                self.assertEqual(self.c.mon, self.c.initial)
                self.assertFalse(self.path.exists())
                self.assertTrue(self.c.running)

    def test_receiver_layout_change_during_handoff_does_not_create_headless(self):
        service = self.c.service
        def changed(action):
            service(action)
            if action == "stop":
                self.c.mon[1]["scale"] = 2.0
        self.c.service = changed
        with self.assertRaisesRegex(ValueError, "layout changed"):
            self.session.start((1920, 1080, 60, False))
        self.assertFalse(any(c[0] in ("output", "eval", "reload") for c in self.c.calls))
        self.assertTrue(self.c.running)
        self.assertFalse(self.path.exists())

    def test_receiver_restore_wait_does_not_remove_headless_on_identity_change(self):
        self.session.start((1920, 1080, 60, False))
        output = self.session.load()["output"]
        self.c.never.add("physical")
        def replace():
            self.c.mon[1]["serial"] = "Replacement"
            self.c.on_wait = None
        self.c.on_wait = replace
        with self.assertRaisesRegex(ValueError, "identity changed"):
            self.session.stop()
        self.assertIn(output, [m["name"] for m in self.c.mon])
        self.assertFalse(self.c.running)
        self.assertFalse(self.session.load()["restored"])
        self.c.mon[1]["serial"] = "0x01010101"
        self.c.never.clear()
        self.session.stop()
        self.assertEqual(self.c.mon, self.c.initial)

    def test_receiver_snapshot_rejects_malformed_journal_before_mutation(self):
        self.session.start((1920, 1080, 60, False))
        state = self.session.load()
        good = copy.deepcopy(state["physical_snapshot"])
        for bad in (None, [], [good[0], good[0]],
                    [{**good[0], "scale": float("nan")}, good[1]],
                    [good[0], {**good[1], "serial": "Replacement"}]):
            with self.subTest(snapshot=bad):
                state["physical_snapshot"] = bad
                self.session.save(state)
                calls = copy.deepcopy(self.c.calls)
                with self.assertRaises(ValueError):
                    self.session.stop()
                self.assertEqual(self.c.calls, calls)
                self.assertFalse(self.c.running)
                self.assertTrue(self.path.exists())
        state["physical_snapshot"] = good
        self.session.save(state)
        self.session.stop()


class RediscoveryTests(unittest.TestCase):
    """Production recovery with a compositor simulation and fake child/root I/O."""
    def setUp(self):
        import contextlib
        import struct
        import threading
        self.dc = fixtures.dc
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.runtime = Path(self.temporary.name)
        self.c = Compositor(refill=True)
        self.c.active_ws = {self.dc.TV_OUTPUT: 1}
        self.c.focused = self.dc.TV_OUTPUT
        self.profiles = self.c.profiles
        self.identity = {"make": "Sony", "model": "SONY TV  *30", "serial": "0x01010101"}
        for profile in self.profiles.values():
            for output in profile["outputs"]:
                output.update(self.identity if output["name"] == self.dc.TV_OUTPUT else
                              {"make": "Samsung", "model": "Odyssey", "serial": "desk"})
                output.update(scale=2 if output["name"] == self.dc.TV_OUTPUT else 1,
                              transform=0)
        self.saved = copy.deepcopy(self.profiles)
        self.c.mon = copy.deepcopy(self.profiles["tv-game"]["outputs"])
        for monitor in self.c.mon:
            monitor.update(disabled=not monitor["enabled"], dpmsStatus=True)
        self.c.mon[0].update(width=0, height=0, currentFormat="Invalid")
        self.c.mon[1].update(model="SONY AVSYSTEM", width=1280, height=720)
        for workspace in self.c.ws:
            workspace["monitor"] = self.dc.TV_OUTPUT
        self.c.ws[0].update(windows=1, ispersistent=False)
        self.c.ws[1].update(windows=1, ispersistent=False)
        self.states = fixtures.ha()
        self.states[2]["attributes"] = {"source": "Racing"}
        self.log = []
        self.preview = None
        self.pid = 100
        self.on_phase = lambda phase: None
        test = self

        class Process:
            def __init__(self):
                test.pid += 1
                self.pid = test.pid
                self.exited = False
            def poll(self):
                return 0 if self.exited else None
            def terminate(self):
                test.log.append("child-stop")
                test.on_phase("child-stop")
                self.exited = True
            def wait(self, timeout):
                if not self.exited:
                    raise TimeoutError("child stop failed")
                return 0

        def spawn(args):
            self.log.append("child-start")
            self.on_phase("child-start")
            return Process()
        self.child = self.dc.Child(spawn)
        self.child.start()
        class Connection:
            def __init__(self):
                self.sock = mock.Mock()
                self.sock.getsockopt.return_value = struct.pack("3i", test.child.proc.pid,
                                                                os.getuid(), 0)
            def request(self, method, **params):
                test.on_phase("ipc-" + method)
                if method == "status":
                    return {"daemon": {"ipc_only": True, "running": True,
                                       "preview": test.preview, "unmanaged": False}}
                if method == "editor_state":
                    return {"source_profile": "tv-game",
                            "profiles": copy.deepcopy(list(test.profiles.values()))}
                if method == "preview":
                    if test.preview:
                        raise ValueError("human preview owns daemon")
                    test.preview = {"transaction_id": "owned"}
                    test.log.append("preview")
                    profile = params["profile"]
                    if getattr(test, "disable_backup", False):
                        for monitor in test.c.mon:
                            if monitor["name"].startswith("HEADLESS-REDISCOVER-"):
                                monitor["disabled"] = True
                        test.c.monitor_workspaces()
                    for monitor in test.c.mon:
                        if monitor["name"] == test.dc.TV_OUTPUT:
                            monitor.update(copy.deepcopy(self_tv(profile)),
                                           disabled=False, dpmsStatus=True)
                    for rule in profile["workspaces"]["rules"]:
                        for workspace in test.c.ws:
                            if rule["workspace"] == (str(workspace["id"]) if workspace["id"] > 0
                                                    else "name:" + workspace["name"]):
                                workspace["monitor"] = rule["output_name"]
                    return {"id": "owned"}
                if method in ("commit", "revert"):
                    test.log.append(method)
                    test.preview = None
                    return {}
                raise AssertionError(method)
        def self_tv(profile):
            return next(o for o in profile["outputs"] if o["name"] == test.dc.TV_OUTPUT)
        @contextlib.contextmanager
        def ipc(timeout=25):
            yield Connection()
        def monitors():
            return json.loads(self.c.hypr(["hyprctl", "monitors", "all", "-j"]))
        self.system = self.dc.System(self.runtime, threading.Event())
        self.system.ipc = ipc
        self.system.verify_watcher_claim = lambda: None
        self.addCleanup(lambda: self.system.watcher_holds.close() if self.system.watcher_holds else None)
        self.system.ha = lambda: copy.deepcopy(self.states)
        self.system.tv_edid = lambda: copy.deepcopy(self.identity)
        self.system.monitors = monitors
        self.system.workspace_snapshot = lambda: copy.deepcopy(self.c.ws)
        self.system.workspaces = lambda: self.dc.workspace_placement(self.c.ws)
        self.system.drm = lambda: (3840, 2160)
        self.system.wait = self.c.wait
        def command(*args):
            self.log.append(args[0] + "-" + args[1])
            self.on_phase(args[0] + "-" + args[1])
            self.c.command(*args)
        self.system.command = command
        self.coordinator = self.dc.Coordinator(self.system, clock=lambda: self.c.now)
        self.recovery = self.dc.Rediscovery(self.system, self.child, self.coordinator)
        self.helper = mock.Mock()
        self.helper.detected = False
        self.helper.__enter__ = mock.Mock(return_value=self.helper)
        self.off = False
        def detect():
            self.log.append("detect")
            self.on_phase("detect")
            self.c.mon = [m for m in self.c.mon if m["name"] != self.dc.TV_OUTPUT]
            tv = copy.deepcopy(self.profiles["tv-game"]["outputs"][1])
            tv.update(disabled=False, dpmsStatus=True, width=1280, height=720)
            self.c.mon.append(tv)
            self.helper.detected = True
        def off():
            self.log.append("off")
            self.on_phase("off")
            self.off = True
            self.c.mon = [m for m in self.c.mon if m["name"] != self.dc.TV_OUTPUT]
        def exit_helper(*_):
            if self.off and not self.helper.detected:
                detect()
        self.helper.off.side_effect = off
        self.helper.detect.side_effect = detect
        self.helper.__exit__ = mock.Mock(side_effect=exit_helper)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(self.dc, "run", self.c.hypr))
        self.preflight = self.stack.enter_context(mock.patch.object(
            self.dc, "helper_preflight", return_value=self.identity))
        self.stack.enter_context(mock.patch.object(self.dc, "ConnectorProcess", return_value=self.helper))
        self.stack.enter_context(mock.patch.object(self.dc.Path, "read_bytes", return_value=b"qualified"))
        self.stack.enter_context(mock.patch.object(self.dc, "WATCHER_SHA256S",
                                                  {hashlib.sha256(b"qualified").hexdigest()}))

    def test_complete_handoff_restores_all_workspaces_and_preserves_disabled_dp(self):
        self.recovery.run(self.profiles)
        self.assertFalse(self.recovery.path.exists())
        self.assertEqual([v for v in self.log if v in ("off", "detect")], ["off", "detect"])
        self.assertLess(self.log.index("child-stop"), self.log.index("off"))
        self.assertEqual(self.log.count("child-start"), 2)
        self.assertEqual(self.log[-1], "commit")
        self.assertTrue(all(w["monitor"] == self.dc.TV_OUTPUT for w in self.c.ws))
        self.assertEqual(self.c.shown, {"special:shown"})
        dp = next(m for m in self.c.mon if m["name"] == "DP-1")
        self.assertEqual((dp["disabled"], dp["width"], dp["currentFormat"]), (True, 0, "Invalid"))
        self.assertEqual(self.profiles, self.saved)

    def test_preflight_failures_preview_and_stream_lock_defer_before_takeover(self):
        import contextlib
        for fault in ("helper", "preview", "watcher", "stream"):
            with self.subTest(fault=fault):
                self.setUp()
                with contextlib.ExitStack() as stack:
                    if fault == "helper":
                        self.preflight.side_effect = PermissionError("sudo refused")
                    elif fault == "preview":
                        self.preview = {"transaction_id": "human"}
                    elif fault == "watcher":
                        stack.enter_context(mock.patch.object(self.dc, "WATCHER_SHA256S", {"unqualified"}))
                    else:
                        directory = self.runtime / "sunshine-virtual-display"
                        directory.mkdir(mode=0o700)
                        stack.enter_context(self.dc.coordinator_lock(directory, "lock"))
                    with self.assertRaises((OSError, ValueError)):
                        self.recovery.run(self.profiles)
                self.assertNotIn("child-stop", self.log)
                self.assertFalse(any(v.startswith("output-") for v in self.log))
                self.assertNotIn("off", self.log)

    def test_sunshine_journal_overlap_never_stops_child(self):
        directory = self.runtime / "sunshine-virtual-display"
        directory.mkdir(mode=0o700)
        (directory / "state.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "Sunshine"):
            self.recovery.run(self.profiles)
        self.assertNotIn("child-stop", self.log)

    def test_watcher_locks_held_across_daemon_release_and_reclaim(self):
        def phase(value):
            if value not in ("child-stop", "child-start", "off", "detect"):
                return
            for name in ("omarchy-monitor-clamshell.lock", "omarchy-monitor-modeless.lock"):
                with self.assertRaises(BlockingIOError):
                    with self.dc.coordinator_lock(self.runtime, name):
                        self.fail("watcher could write during handoff")
        self.on_phase = phase
        self.recovery.run(self.profiles)

    def test_cancellation_after_off_compensates_and_retains_backup_journal(self):
        def phase(value):
            if value == "off":
                self.off = True
                self.system.stop.set()
                raise InterruptedError("cancel after uncertain off")
        self.on_phase = phase
        with self.assertRaises(InterruptedError):
            self.recovery.run(self.profiles)
        self.assertIn("detect", self.log)
        self.assertTrue(self.recovery.path.exists())
        self.assertTrue(any(m["name"].startswith("HEADLESS-REDISCOVER-") for m in self.c.mon))

    def test_detect_failure_retains_explicit_compensation_ownership(self):
        self.helper.detect.side_effect = OSError("detect failed")
        def exit_helper(*_):
            pass
        self.helper.__exit__.side_effect = exit_helper
        with self.assertRaisesRegex(OSError, "detect failed"):
            self.recovery.run(self.profiles)
        state = json.loads(self.recovery.path.read_text())
        self.assertEqual(state["stage"], "detect-pending")
        self.assertTrue(any(m["name"] == state["output"] for m in self.c.mon))

    def test_child_stop_failure_never_creates_backup_or_disconnects(self):
        self.child.proc.wait = mock.Mock(side_effect=TimeoutError("stop failed"))
        with self.assertRaisesRegex(TimeoutError, "stop failed"):
            self.recovery.run(self.profiles)
        self.assertTrue(self.recovery.path.exists())
        self.assertNotIn("off", self.log)
        self.assertFalse(any(v.startswith("output-") for v in self.log))

    def test_restart_failure_retains_journal(self):
        def phase(value):
            if value == "child-start":
                raise OSError("restart failed")
        self.on_phase = phase
        with self.assertRaisesRegex(OSError, "restart failed"):
            self.recovery.run(self.profiles)
        self.assertIn("detect", self.log)
        self.assertTrue(self.recovery.path.exists())

    def test_new_human_preview_after_restart_is_preserved(self):
        def phase(value):
            if value == "child-start":
                self.preview = {"transaction_id": "human"}
        self.on_phase = phase
        with self.assertRaisesRegex(ValueError, "human"):
            self.recovery.run(self.profiles)
        self.assertNotIn("preview", self.log)
        self.assertEqual(self.preview, {"transaction_id": "human"})
        self.assertTrue(self.recovery.path.exists())

    def test_incomplete_output_cleanup_retains_journal(self):
        self.c.never.add("remove")
        with self.assertRaises(TimeoutError):
            self.recovery.run(self.profiles)
        self.assertTrue(self.recovery.path.exists())
        self.assertIn("revert", self.log)

    def test_unknown_output_arriving_during_handoff_never_disconnects(self):
        def phase(value):
            if value == "child-stop":
                self.c.mon.append({"name": "DP-9", "disabled": False})
        self.on_phase = phase
        with self.assertRaises(ValueError):
            self.recovery.run(self.profiles)
        self.assertNotIn("off", self.log)

    def test_startup_cleanup_finishes_without_another_off(self):
        self.c.never.add("remove")
        with self.assertRaises(TimeoutError):
            self.recovery.run(self.profiles)
        self.c.never.clear()
        recovery = self.dc.Rediscovery(self.system, self.child, self.coordinator)
        recovery.resume()
        self.assertFalse(recovery.path.exists())
        self.assertEqual(self.log.count("off"), 1)
        self.assertTrue(all(w["monitor"] == self.dc.TV_OUTPUT for w in self.c.ws))

    def test_scanout_or_scale_mismatch_retains_backup_and_journal(self):
        self.system.drm = lambda: (1280, 720)
        with self.assertRaises(TimeoutError):
            self.recovery.run(self.profiles)
        self.assertTrue(self.recovery.path.exists())
        self.assertTrue(any(m["name"].startswith("HEADLESS-REDISCOVER-") for m in self.c.mon))
        self.assertNotIn("commit", self.log)

    def test_corrupt_journal_never_performs_cleanup(self):
        self.recovery.path.write_text("{}")
        with self.assertRaises(ValueError):
            self.recovery.resume()
        self.assertEqual(self.log, ["child-start"])

    def test_disabled_backup_reenable_allows_empty_replacement_until_removal(self):
        self.disable_backup = True
        self.recovery.run(self.profiles)
        self.assertFalse(self.recovery.path.exists())
        self.assertTrue(all(w["monitor"] == self.dc.TV_OUTPUT for w in self.c.ws))

    def test_preoff_failure_restores_workspace_snapshot_without_tv_modeset(self):
        def phase(value):
            if value == "output-create":
                self.c.fail = "move"
        self.on_phase = phase
        with self.assertRaises(OSError):
            self.recovery.run(self.profiles)
        self.assertNotIn("off", self.log)
        self.assertNotIn("preview", self.log)
        self.assertFalse(self.recovery.path.exists())
        self.assertTrue(all(w["monitor"] == self.dc.TV_OUTPUT for w in self.c.ws))
        self.assertFalse(any(m["name"].startswith("HEADLESS-REDISCOVER-") for m in self.c.mon))

    def test_restart_failure_keeps_watcher_locks_until_reclaim(self):
        def phase(value):
            if value == "child-start":
                raise OSError("restart failed")
        self.on_phase = phase
        with self.assertRaises(OSError):
            self.recovery.run(self.profiles)
        self.assertIsNotNone(self.system.watcher_holds)
        for name in ("omarchy-monitor-clamshell.lock", "omarchy-monitor-modeless.lock"):
            with self.assertRaises(BlockingIOError):
                with self.dc.coordinator_lock(self.runtime, name):
                    self.fail("watcher exclusion lost")

    def test_watcher_reclaim_failure_retains_exclusion_and_journal(self):
        self.system.verify_watcher_claim = mock.Mock(side_effect=ValueError("watcher still active"))
        with self.assertRaisesRegex(ValueError, "still active"):
            self.recovery.run(self.profiles)
        self.assertIsNotNone(self.system.watcher_holds)
        self.assertTrue(self.recovery.path.exists())

    def test_natural_real_tv_identity_before_off_compensates_without_modeset(self):
        def phase(value):
            if value == "output-create":
                self.c.mon[1].update(self.identity, width=3840, height=2160, refreshRate=119.88)
        self.on_phase = phase
        with self.assertRaises(ValueError):
            self.recovery.run(self.profiles)
        self.assertNotIn("off", self.log)
        self.assertNotIn("preview", self.log)
        self.assertFalse(self.recovery.path.exists())
        self.assertTrue(all(w["monitor"] == self.dc.TV_OUTPUT for w in self.c.ws))

    def test_explicit_helper_refusal_compensates_without_an_off(self):
        self.helper.off.side_effect = self.dc.ConnectorRefused("refused before write")
        with self.assertRaises(self.dc.ConnectorRefused):
            self.recovery.run(self.profiles)
        self.assertNotIn("off", self.log)
        self.assertFalse(self.recovery.path.exists())
        self.assertTrue(all(w["monitor"] == self.dc.TV_OUTPUT for w in self.c.ws))

    def test_sleep_abort_defers_until_awake_then_backup_resume_compensates(self):
        def phase(value):
            if value == "output-create":
                self.c.mon[1]["dpmsStatus"] = False
        self.on_phase = phase
        with self.assertRaises(ValueError):
            self.recovery.run(self.profiles)
        self.assertEqual(json.loads(self.recovery.path.read_text())["stage"], "backup")
        self.c.mon[1]["dpmsStatus"] = True
        self.dc.Rediscovery(self.system, self.child, self.coordinator).resume()
        self.assertFalse(self.recovery.path.exists())
        self.assertNotIn("off", self.log)
        self.assertTrue(all(w["monitor"] == self.dc.TV_OUTPUT for w in self.c.ws))

    def test_preoff_compensation_and_failed_child_restart_keep_journal(self):
        def phase(value):
            if value == "output-create":
                self.c.fail = "move"
            elif value == "child-start":
                raise OSError("child recreation refused")
        self.on_phase = phase
        with self.assertRaisesRegex(OSError, "recreation refused"):
            self.recovery.run(self.profiles)
        self.assertTrue(self.system.recovery_pending())
        self.assertEqual(json.loads(self.recovery.path.read_text())["stage"], "compensated")
        self.assertIsNotNone(self.system.watcher_holds)
        self.assertTrue(all(w["monitor"] == self.dc.TV_OUTPUT for w in self.c.ws))

    def test_watcher_claim_parser_matches_daemon_scope_contract(self):
        for active in ("active", "activating", "inactive"):
            with mock.patch.object(self.dc, "run", return_value=json.dumps([{
                "description": "omarchy-hyprland-monitor-watch", "active": active,
                "unit": "app-omarchy-watcher.scope"}])):
                if active in ("active", "activating"):
                    with self.assertRaises(ValueError):
                        self.dc.System.verify_watcher_claim(self.system)
                else:
                    self.dc.System.verify_watcher_claim(self.system)

    def test_changed_child_object_is_not_terminated(self):
        expected = self.child.proc
        self.child.proc = mock.Mock()
        with self.assertRaisesRegex(ValueError, "changed"):
            self.child.handoff_stop(expected)
        self.child.proc.terminate.assert_not_called()
        self.assertFalse(expected.exited)

    def test_external_ipc_pid_is_rejected(self):
        with self.system.ipc() as ipc:
            import struct
            ipc.sock.getsockopt.return_value = struct.pack("3i", self.pid + 99, os.getuid(), 0)
            with self.assertRaisesRegex(ValueError, "another daemon"):
                self.recovery.owner(ipc)

    def test_sunshine_start_fails_closed_on_recovery_journal(self):
        self.recovery.path.write_text("{}")
        with mock.patch.object(vd.dc, "IPC") as ipc:
            with self.assertRaisesRegex(ValueError, "recovery journal"):
                vd.Host(self.runtime).editor()
            ipc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
