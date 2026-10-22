#!/usr/bin/env python3
"""Focused coordinator tests. All services, processes and display queries are fake."""
import contextlib
import copy
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import threading
import unittest
from unittest import mock
from typing import Any

SOURCE = Path(__file__).resolve().parents[1] / "hosts/omarchy-pc/bin/display-controller"
loader = importlib.machinery.SourceFileLoader("display_controller", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
dc = importlib.util.module_from_spec(spec)
loader.exec_module(dc)


def setUpModule():
    # Refuse to create even test scratch under a real operator HOME.
    expected = os.environ.get("DISPLAY_TEST_SCRATCH_HOME", "")
    scratch = Path(expected)
    if (not expected or not scratch.is_absolute() or os.environ.get("HOME") != expected
            or scratch.resolve() in (Path("/home/igor"), Path("/root"), Path("/home/job"))):
        raise RuntimeError("set DISPLAY_TEST_SCRATCH_HOME to an absolute private disposable HOME")
    if not scratch.is_dir() or scratch.stat().st_mode & 0o077:
        raise RuntimeError("scratch HOME must exist and be private")
    temporary = Path(os.environ.get("TMPDIR", ""))
    if not temporary.is_absolute() or scratch.parent.resolve() not in temporary.resolve().parents:
        raise RuntimeError("TMPDIR must be inside the task scratch directory")


def ha(source="HDMI 3", screen="on", avr="on"):
    return [
        {"entity_id": dc.TV, "state": "on", "attributes": {"source": source}},
        {"entity_id": dc.SCREEN, "state": screen},
        {"entity_id": dc.AVR, "state": avr},
        {"entity_id": dc.BRAVIA, "state": "idle", "attributes": {}},
        {"entity_id": dc.CAST, "state": "idle", "attributes": {}},
    ]


def profile(name, output, width, height):
    return {"name": name, "outputs": [
        {"name": "DP-1", "enabled": output == "DP-1", "width": 5120, "height": 1440},
        {"name": dc.TV_OUTPUT, "enabled": output == dc.TV_OUTPUT, "width": width, "height": height},
    ], "workspaces": {"enabled": True, "strategy": "manual",
                       "rules": [{"workspace": "1", "output_key": ""}]}}



class FakeAudio:
    """pactl JSON fixture with actual device identity and arbitrary object IDs."""
    def __init__(self):
        self.card = "alsa_card.pci-0000_01_00.1"
        self.tv_name = "alsa_output.pci-0000_01_00.1.hdmi-stereo-extra1"
        self.profile = "output:hdmi-stereo-extra1"
        self.cards = [{"index": 19, "name": self.card,
                       "active_profile": self.profile,
                       "profiles": {p: {"available": True} for p in (
                           self.profile, "output:hdmi-surround-extra1", "output:hdmi-surround71-extra1")},
                       "ports": {
                           "hdmi-output-0": {"availability": "unavailable",
                                             "properties": {"device.product.name": "SAMSUNG"},
                                             "profiles": ["output:hdmi-surround"]},
                           "hdmi-output-1": {"availability": "available",
                                             "properties": {"device.product.name": "SONY TV  *30"},
                                             "profiles": [self.profile, "output:hdmi-surround-extra1",
                                                          "output:hdmi-surround71-extra1"]}}}]
        self.sony = {"index": 73, "name": self.tv_name, "active_port": "hdmi-output-1",
                     "properties": {"alsa.name": "SONY TV  *30", "device.name": self.card,
                                    "device.bus": "pci", "device.bus_path": "pci-0000:01:00.1"}}
        self.desk = {"index": 12, "name": dc.DESK_SINK, "properties": {"device.bus": "usb"}}
        self.sinks = [self.desk, self.sony]
        self.streams = [{"index": 808, "sink": 12}, {"index": 909, "sink": 73}]
        self.default = dc.DESK_SINK
        self.calls = []
        self.error: Any = None
        self.publish_after: Any = None
        self.sink_queries = 0

    def run(self, args, timeout=5):
        if args[0] != "pactl":
            raise AssertionError("unexpected real command " + repr(args))
        if timeout != 5:
            raise AssertionError("audio subprocess must be bounded")
        return self.pactl(*args[1:])

    def pactl(self, *args):
        self.calls.append(args)
        if self.error:
            raise self.error
        if args[:3] == ("-f", "json", "list"):
            if args[3] == "sinks":
                self.sink_queries += 1
                if self.publish_after is not None and self.sink_queries >= self.publish_after:
                    self.sinks = [self.desk, self.sony]
            return json.dumps({"sinks": self.sinks, "cards": self.cards,
                               "sink-inputs": self.streams}[args[3]])
        if args == ("get-default-sink",):
            return self.default + "\n"
        if args[0] == "set-card-profile":
            self.cards[0]["active_profile"] = args[2]
        elif args[0] == "set-default-sink":
            self.default = args[1]
        elif args[0] == "move-sink-input":
            target = next(s for s in self.sinks if s["name"] == args[2])
            next(s for s in self.streams if str(s["index"]) == args[1])["sink"] = target["index"]
        else:
            raise AssertionError("unexpected pactl write " + repr(args))
        return ""

    def writes(self):
        return [call for call in self.calls if call[0] in (
            "set-card-profile", "set-default-sink", "move-sink-input")]


class FakeSystem:
    def __init__(self):
        self.audio = FakeAudio()
        self.states: Any = ha()
        self.profiles = {"desk": profile("desk", "DP-1", 3840, 2160),
                         "tv-game": profile("tv-game", dc.TV_OUTPUT, 3840, 2160),
                         "tv-recovery": profile("tv-recovery", dc.TV_OUTPUT, 1920, 1080)}
        self.saved = copy.deepcopy(self.profiles)
        self.mon = []
        self.ws = [{"id": n, "name": str(n), "monitor": "DP-1"} for n in (1, 2)]
        self.workspace_fault: Any = None
        self.workspace_error: Any = None
        self.apply("desk")
        self.override = "desk"
        self.editor_name: Any = None
        self.preview: Any = None
        self.unmanaged = False
        self.ipc_only: Any = True
        self.calls = []
        self.connect_error: Any = None
        self.fail = {}
        self.faults: dict[str, Any] = {}
        self.actual: Any = "follow"
        self.now = 0
        self.stop = threading.Event()
        self.stop.wait = mock.Mock(side_effect=self.advance)
        self.connections = 0
        self.inflight: Any = None
        self.wait_hook: Any = None
        self.wake = mock.Mock(side_effect=lambda: next(m for m in self.mon if not m["disabled"]).update(dpmsStatus=True))

    def advance(self, seconds):
        self.now += seconds
        return self.stop.is_set()

    def apply(self, name):
        self.mon = [{"name": o["name"], "disabled": not o["enabled"],
                     "dpmsStatus": o["enabled"], "width": o["width"], "height": o["height"]}
                    for o in self.profiles[name]["outputs"]]
        self.live = name

    def ha(self):
        if isinstance(self.states, Exception):
            raise self.states
        return copy.deepcopy(self.states)

    def pactl(self, *args):
        return self.audio.pactl(*args)

    def audio_lock(self):
        return contextlib.nullcontext()

    def monitors(self):
        return copy.deepcopy(self.mon)

    def workspaces(self):
        if self.workspace_error:
            raise self.workspace_error
        return dc.workspace_placement(copy.deepcopy(self.ws))

    def drm(self):
        value = self.faults.get(self.live, self.actual)
        if isinstance(value, Exception):
            raise value
        if value == "follow":
            tv = next(m for m in self.mon if m["name"] == dc.TV_OUTPUT)
            return tv["width"], tv["height"]
        return value

    def wait(self, seconds):
        self.advance(seconds)
        if self.wait_hook:
            self.wait_hook()

    @contextlib.contextmanager
    def ipc(self, timeout=25):
        if self.connect_error:
            raise self.connect_error
        self.connections += 1
        connection = self.connections
        system = self

        class Connection:
            def request(self, method, **params):
                system.calls.append((connection, method, params))
                if method in system.fail:
                    raise system.fail[method]
                if method == "status":
                    return {"daemon": {"running": True, "preview": system.preview, "profile_override": system.override,
                                       "unmanaged": system.unmanaged,
                                       **({"ipc_only": system.ipc_only} if system.ipc_only is not None else {})}}
                if method == "editor_state":
                    return {"profiles": copy.deepcopy(list(system.profiles.values())),
                            "source_profile": system.live if system.editor_name is None else system.editor_name}
                if method == "preview":
                    if system.preview:
                        raise ValueError("another preview active")
                    system.inflight = (copy.deepcopy(system.mon), system.live, system.override,
                                       copy.deepcopy(system.ws))
                    target = params["profile"] if "profile" in params else system.profiles[params["profile_name"]]
                    system.apply(target["name"])
                    settings = target.get("workspaces", {})
                    if settings.get("enabled"):
                        for rule in settings.get("rules", []):
                            if not (rule.get("output_key") or rule.get("output_name")):
                                continue  # Same unbound manual-rule behavior as the daemon.
                            for workspace in system.ws:
                                selector = str(workspace["id"]) if workspace["id"] > 0 else "name:" + workspace["name"]
                                if selector == rule["workspace"] and selector != system.workspace_fault:
                                    workspace["monitor"] = rule.get("output_name")

                    system.preview = {"transaction_id": "owned"}
                    return {"id": "owned"}
                if params.get("transaction_id") != "owned":
                    raise AssertionError("wrong transaction")
                if method == "commit":
                    system.override = system.live
                elif method == "revert":
                    system.mon, system.live, system.override, system.ws = system.inflight
                else:
                    raise AssertionError("unexpected method " + method)
                system.preview = None

        yield Connection()

    def mutations(self):
        return [(method, params) for _, method, params in self.calls if method not in ("status", "editor_state")]


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.system = FakeSystem()
        self.coordinator = dc.Coordinator(self.system, clock=lambda: self.system.now)

    def tick(self, n=1):
        for _ in range(n):
            self.coordinator.step()
            self.system.advance(dc.POLL)

    def route_tv(self):
        self.tick(2)
        self.assertEqual(self.coordinator.selected, "tv-game")

    def test_route_debounce_and_source_precedence(self):
        for source in ("HDMI 3", " hdmi 3 (earc/arc) ", "STR-AZ5000ES"):
            self.assertEqual(dc.choose(ha(source)), "tv-game")
        self.assertEqual(dc.choose(ha("HDMI 2")), "desk")
        self.assertEqual(dc.choose(ha(screen="off")), "desk")
        self.assertEqual(dc.choose(ha(avr="off")), "desk")
        states = ha("")
        states[0]["state"] = "off"
        states[3]["attributes"]["source"] = "HDMI 3"
        self.assertEqual(dc.choose(states), "tv-game")
        states[3]["attributes"].clear()
        states[4].update(state="playing", attributes={"app_name": "TV", "media_title": "HDMI 3"})
        self.assertEqual(dc.choose(states), "tv-game")
        self.tick()
        self.assertEqual(self.system.mutations(), [])
        self.tick()
        self.assertEqual(self.coordinator.selected, "tv-game")
        self.system.states = ha("HDMI 1")
        self.tick()
        self.assertEqual(self.coordinator.selected, "tv-game")
        self.tick()
        self.assertEqual(self.coordinator.selected, "desk")

    def test_workspace_placement_both_directions_without_saving(self):
        self.system.ws.append({"id": -1337, "name": "browser", "monitor": "DP-1"})
        for states, output in ((ha(), dc.TV_OUTPUT), (ha("HDMI 2"), "DP-1")):
            with self.subTest(output=output):
                self.system.states = states
                self.tick(2)
                self.assertTrue(all(w["monitor"] == output for w in self.system.ws))
                self.assertEqual(self.coordinator.last_action,
                                 "committed " + ("desk" if output == "DP-1" else "tv-game"))
                self.assertEqual(self.system.profiles, self.system.saved)
        previews = [p for m, p in self.system.mutations() if m == "preview"]
        self.assertTrue(all("profile_name" not in p and p["save_on_commit"] is False for p in previews))
        self.assertTrue(all(p["save"] is False for m, p in self.system.mutations() if m == "commit"))

    def test_stranded_workspace_reverts_both_directions(self):
        for initial, states in (("desk", ha()), ("tv-game", ha("HDMI 2"))):
            with self.subTest(initial=initial):
                self.setUp()
                self.system.apply(initial)
                self.system.override = initial
                self.coordinator.selected = initial
                output = dc.targets(self.system.profiles[initial])[0]["name"]
                for workspace in self.system.ws:
                    workspace["monitor"] = output
                before = copy.deepcopy(self.system.ws)
                self.system.workspace_fault = "2"
                self.system.states = states
                self.tick(2)
                self.assertEqual(self.system.live, initial)
                self.assertEqual(self.system.ws, before)
                self.assertEqual([m for m, _ in self.system.mutations()], ["preview", "revert"])
                self.assertIn("workspace placement", self.coordinator.error)
                mutations = self.system.mutations()
                self.tick(5)
                self.assertEqual(self.system.mutations(), mutations)

    def test_workspace_query_failure_prevents_preview(self):
        self.system.workspace_error = TimeoutError("workspace query")
        self.tick(3)
        self.assertEqual(self.system.mutations(), [])

    def test_unknown_ha_retains_route_and_restarts_debounce(self):
        self.route_tv()
        count = len(self.system.mutations())
        for states in ([], ha(""), ha(screen="unknown"), ha(avr="unavailable"), TimeoutError("HA timeout")):
            self.system.states = states
            self.tick(3)
            self.assertEqual(self.coordinator.selected, "tv-game")
            self.assertEqual(len(self.system.mutations()), count)
        self.system.states = ha("HDMI 1")
        self.tick()
        self.assertEqual(self.coordinator.selected, "tv-game")
        self.tick()
        self.assertEqual(self.coordinator.selected, "desk")

    def test_sleep_preview_absent_target_and_ambiguity_defer(self):
        for kind in ("sleep", "preview", "absent", "extra", "two-enabled", "unmanaged", "identity"):
            with self.subTest(kind=kind):
                self.setUp()
                if kind == "sleep":
                    self.system.mon[0]["dpmsStatus"] = False
                elif kind == "preview":
                    self.system.preview = {"transaction_id": "human", "reclaimable": True}
                elif kind == "absent":
                    self.system.mon.pop()
                elif kind == "extra":
                    self.system.mon.append({"name": "DP-9", "disabled": True})
                elif kind == "two-enabled":
                    self.system.mon[1].update(disabled=False, dpmsStatus=True)
                elif kind == "unmanaged":
                    self.system.unmanaged = True
                else:
                    self.system.profiles["tv-game"]["outputs"][1]["serial"] = "expected"
                    self.system.mon[1]["serial"] = "replacement"
                self.tick(4)
                self.assertEqual(self.system.mutations(), [])

    def test_confirmed_sleep_wake_rearms_failed_route_once(self):
        self.system.fail["preview"] = TimeoutError("transient HDMI switch")
        self.tick(3)
        before = len(self.system.mutations())
        self.tick(3)
        self.assertEqual(len(self.system.mutations()), before)
        self.system.mon[0]["dpmsStatus"] = False
        self.tick(2)
        self.system.mon[0]["dpmsStatus"] = True
        self.system.fail.clear()
        self.tick(3)
        self.assertEqual(self.coordinator.selected, "tv-game")
        after = len(self.system.mutations())
        self.tick(4)
        self.assertEqual(len(self.system.mutations()), after)

    def test_fresh_tv_selection_wakes_once_but_unchanged_intent_does_not(self):
        self.system.wake = mock.Mock(side_effect=lambda: self.system.mon[0].update(dpmsStatus=True))
        self.system.states = ha("HDMI 1")
        self.tick(2)
        self.system.mon[0]["dpmsStatus"] = False
        self.tick(2)
        self.system.wake.assert_not_called()
        self.system.states = ha()
        self.tick(3)
        self.system.wake.assert_called_once_with()
        self.assertEqual(self.coordinator.selected, "tv-game")
        for m in self.system.mon:
            m["dpmsStatus"] = False
        self.tick(4)
        self.system.wake.assert_called_once_with()

    def test_stale_wake_intent_is_discarded_after_query_failure(self):
        self.system.states = ha("HDMI 1")
        self.tick(2)
        self.system.states = ha()
        self.system.connect_error = TimeoutError("IPC unavailable")
        self.tick(4)
        self.system.connect_error = None
        self.system.mon[0]["dpmsStatus"] = False
        self.tick(3)
        self.system.wake.assert_not_called()

    def test_pending_wake_expires_while_debounce_is_delayed(self):
        self.system.states = ha("HDMI 1")
        self.tick(2)
        self.system.states = ha()
        self.system.mon[0]["dpmsStatus"] = False
        self.tick()
        self.system.advance(4 * dc.POLL)
        self.tick(3)
        self.system.wake.assert_not_called()

    def test_fresh_tv_selection_tolerates_unknown_ha_between_known_routes(self):
        self.system.states = ha("HDMI 1")
        self.tick(2)
        self.system.states = ha(screen="unknown")
        self.tick(2)
        self.system.states = ha()
        self.system.mon[0]["dpmsStatus"] = False
        self.tick(3)
        self.system.wake.assert_called_once_with()
        self.assertEqual(self.coordinator.selected, "tv-game")

    def test_fresh_selection_does_not_wake_unsafe_layouts(self):
        for kind in ("preview", "unmanaged", "identity", "two-enabled", "wrong-target", "no-target"):
            with self.subTest(kind=kind):
                self.setUp()
                self.system.states = ha("HDMI 1")
                self.tick(2)
                self.system.mon[0]["dpmsStatus"] = False
                self.system.states = ha()
                if kind == "preview":
                    self.system.preview = {"transaction_id": "human"}
                elif kind == "unmanaged":
                    self.system.unmanaged = True
                elif kind == "identity":
                    self.system.profiles["tv-game"]["outputs"][1]["serial"] = "expected"
                    self.system.mon[1]["serial"] = "other"
                elif kind == "two-enabled":
                    self.system.mon[1]["disabled"] = False
                elif kind == "wrong-target":
                    self.system.profiles["tv-game"] = profile("tv-game", "DP-1", 3840, 2160)
                else:
                    for output in self.system.profiles["tv-game"]["outputs"]:
                        output["enabled"] = False
                self.tick(3)
                self.system.wake.assert_not_called()
                self.assertEqual(self.system.mutations(), [])

    def test_repeated_failed_sleep_wake_cycles_have_one_retry_budget(self):
        self.system.fail["preview"] = TimeoutError("switch failed")
        self.tick(3)
        for _ in range(3):
            self.system.mon[0]["dpmsStatus"] = False
            self.tick(2)
            self.system.mon[0]["dpmsStatus"] = True
            self.tick(3)
        self.assertEqual(sum(method == "preview" for method, _ in self.system.mutations()), 2)

    def test_startup_sleep_does_not_wake_from_existing_tv_intent(self):
        self.system.wake = mock.Mock()
        self.system.mon[0]["dpmsStatus"] = False
        self.tick(4)
        self.system.wake.assert_not_called()
        self.assertEqual(self.system.mutations(), [])

    def test_mismatch_requires_two_stable_observations(self):
        self.route_tv()
        self.system.actual = (1280, 720)
        self.tick()
        self.assertEqual(self.coordinator.health, "mismatch")
        self.assertEqual(len(self.system.mutations()), 2)
        self.system.actual = (1920, 1080)
        self.tick()
        self.assertEqual(len(self.system.mutations()), 2)
        self.system.actual = None
        self.tick(3)
        self.assertEqual(len(self.system.mutations()), 2)

    def test_bounded_recovery_restores_preferred_once(self):
        self.route_tv()
        self.system.actual = (1280, 720)
        self.tick()
        self.system.faults = {"tv-recovery": "follow"}
        self.system.wait_hook = lambda: setattr(self.system, "actual", "follow")
        self.tick()
        names = [p["profile"]["name"] for m, p in self.system.mutations() if m == "preview"]
        self.assertEqual(names, ["tv-game", "tv-recovery", "tv-game"])
        self.assertEqual(self.system.live, "tv-game")
        self.assertEqual(self.coordinator.health, "recovered")
        self.system.faults["tv-game"] = (1280, 720)
        self.tick(10)
        self.assertEqual(len([1 for m, _ in self.system.mutations() if m == "preview"]), 3)
        self.assertEqual(self.system.profiles, self.system.saved)

    def test_failed_preferred_returns_to_verified_recovery(self):
        self.route_tv()
        self.system.faults = {"tv-game": (1280, 720), "tv-recovery": "follow"}
        self.tick(2)
        self.assertEqual(self.system.live, "tv-recovery")
        self.assertEqual(self.system.override, "tv-recovery")
        self.assertEqual(self.coordinator.last_action, "committed tv-recovery")
        mutations = self.system.mutations()
        self.assertEqual(mutations[-1][0], "revert")
        self.tick(10)
        self.assertEqual(self.system.mutations(), mutations)
        self.assertEqual(self.system.profiles, self.system.saved)
        commits = [p for m, p in mutations if m == "commit"]
        self.assertTrue(commits)
        self.assertTrue(all(p["save"] is False for p in commits))
        for connection in {c for c, m, _ in self.system.calls if m == "preview"}:
            calls = [(m, p) for c, m, p in self.system.calls if c == connection]
            self.assertIn("commit", [m for m, _ in calls])
        self.system.states = ha("HDMI 2")
        self.tick(2)
        self.system.states = ha()
        self.tick(2)
        self.assertEqual(self.system.live, "tv-game")

    def test_unknown_or_bad_recovery_never_committed_or_retried(self):
        for fault in (None, (800, 600), TimeoutError("driver query")):
            with self.subTest(fault=fault):
                self.setUp()
                self.route_tv()
                self.system.faults = {"tv-game": (1280, 720), "tv-recovery": fault}
                self.tick(2)
                self.assertEqual(self.system.live, "tv-game")
                mutations = self.system.mutations()
                self.tick(12)
                self.assertEqual(self.system.mutations(), mutations)
                self.assertEqual([p for m, p in mutations if m == "commit"],
                                 [{"transaction_id": "owned", "save": False}])

    def test_query_and_ipc_errors_do_not_retry_modesets(self):
        self.system.connect_error = TimeoutError("connect")
        self.tick(4)
        self.assertEqual(self.system.mutations(), [])
        self.system.connect_error = None
        self.tick(2)
        self.assertEqual(self.coordinator.selected, "tv-game")
        self.system.actual = TimeoutError("DRM")
        self.tick(5)
        self.assertEqual(len(self.system.mutations()), 2)
        # A preview timeout has an uncertain outcome. No new preview follows it.
        self.system.actual = "follow"
        self.system.states = ha("HDMI 1")
        self.system.fail["preview"] = TimeoutError("IPC preview")
        self.tick(4)
        mutations = self.system.mutations()
        self.tick(10)
        self.assertEqual(self.system.mutations(), mutations)
        self.assertEqual(self.coordinator.selected, "tv-game")

    def test_sleep_or_route_change_during_verification_reverts(self):
        for change in ("sleep", "route"):
            with self.subTest(change=change):
                self.setUp()
                self.route_tv()
                self.system.faults = {"tv-game": (1280, 720), "tv-recovery": "follow"}

                def interrupt():
                    if change == "sleep":
                        self.system.mon[1]["dpmsStatus"] = False
                    else:
                        self.system.states = ha("HDMI 2")

                self.system.wait_hook = interrupt
                self.tick(2)
                self.assertEqual(self.system.live, "tv-game")
                self.assertEqual(self.system.mutations()[-1][0], "revert")

    def test_unknown_startup_keeps_daemon_and_adopts_desk_read_only(self):
        self.system.states = ha("")
        self.system.override = ""
        process = mock.Mock(pid=77)
        process.poll.return_value = None
        child = dc.Child(mock.Mock(return_value=process))
        statuses = []

        def publish(state):
            statuses.append(state)
            if len(statuses) == 3:
                self.system.stop.set()

        dc.supervise(self.system, self.coordinator, child, publish)
        child.spawn.assert_called_once_with([str(Path.home() / ".local/libexec/display-controller/hyprmoncfgd"), "--ipc-only"])
        self.assertTrue(all(s["selected_route"] == "desk" for s in statuses))
        self.assertTrue(all(s["ha_route"] is None for s in statuses))
        self.assertTrue(statuses[0]["daemon_ready"])
        self.assertEqual(statuses[0]["observed_profile"], "desk")
        self.assertEqual(self.system.mutations(), [])

    def test_unknown_input_adopts_only_verified_tv_layout(self):
        self.system.apply("tv-game")
        self.system.states = ha("")
        self.tick(3)
        self.assertEqual(self.coordinator.selected, "tv-game")
        self.assertIsNone(self.coordinator.ha_route)
        self.assertEqual(self.coordinator.observed_profile, "tv-game")
        self.assertEqual(self.system.override, "desk")
        self.assertTrue(all(m in ("status", "editor_state") for _, m, _ in self.system.calls))
        self.assertEqual(self.system.mutations(), [])
        self.coordinator.selected = None
        self.system.actual = (1280, 720)
        self.tick()
        self.assertIsNone(self.coordinator.selected)
        self.assertIsNone(self.coordinator.observed_profile)
        self.system.actual = "follow"
        self.system.editor_name = ""
        self.tick()
        self.assertIsNone(self.coordinator.selected)
        self.system.editor_name = "tv-game"
        self.system.mon[1]["width"] = 1920
        self.tick()
        self.assertIsNone(self.coordinator.selected)
        self.assertEqual(self.system.mutations(), [])

    def test_optional_missing_fallback_does_not_gate_primary_source(self):
        states = ha()[:3]
        self.assertEqual(dc.choose(states), "tv-game")
        states[0]["attributes"]["source"] = "HDMI 2"
        self.assertEqual(dc.choose(states), "desk")
        states[0]["attributes"].clear()
        self.assertIsNone(dc.choose(states))
        states[2]["state"] = "unavailable"
        states[0]["attributes"]["source"] = "HDMI 3"
        self.assertIsNone(dc.choose(states))
        self.system.states = ha()[:3]
        self.route_tv()

    def test_observed_hotplug_rearms_but_query_error_does_not(self):
        self.route_tv()
        self.system.faults = {"tv-game": (1280, 720), "tv-recovery": None}
        self.tick(2)
        self.assertTrue(self.coordinator.recovery_attempted)
        self.tick(2)  # finish HA debounce after failed verification
        saved_tv = self.system.mon.pop()
        self.tick()
        self.system.mon.append(saved_tv)
        self.tick()
        self.assertFalse(self.coordinator.recovery_attempted)

    def test_one_child_across_route_changes_and_shutdown(self):
        process = mock.Mock(pid=77)
        process.poll.return_value = None
        spawn = mock.Mock(return_value=process)
        child = dc.Child(spawn)
        statuses = []

        def publish(state):
            statuses.append(state)
            if len(statuses) == 3:
                self.system.states = ha("HDMI 1")
            elif len(statuses) == 6:
                self.system.stop.set()

        dc.supervise(self.system, self.coordinator, child, publish)
        spawn.assert_called_once_with([str(Path.home() / ".local/libexec/display-controller/hyprmoncfgd"), "--ipc-only"])
        self.assertIn("tv-game", [s["selected_route"] for s in statuses])
        self.assertIn("desk", [s["selected_route"] for s in statuses])
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=8)

    def test_startup_handshake_timeout_stops_child_within_deadline(self):
        self.system.connect_error = ConnectionRefusedError("not ready")
        process = mock.Mock(pid=77)
        process.poll.return_value = None
        child = dc.Child(mock.Mock(return_value=process))
        statuses = []
        with self.assertRaises(TimeoutError):
            dc.supervise(self.system, self.coordinator, child, statuses.append)
        self.assertEqual(self.system.now, 15)
        process.terminate.assert_called_once()
        self.assertIn("startup", statuses[-1]["error"])
        self.assertEqual(self.system.mutations(), [])

    def test_startup_tv_mismatch_reaches_bounded_recovery(self):
        self.system.apply("tv-game")
        self.system.override = ""
        for workspace in self.system.ws:
            workspace["monitor"] = dc.TV_OUTPUT
        self.system.faults = {"tv-game": (1280, 720), "tv-recovery": "follow"}
        dc.startup(self.system, self.coordinator)
        self.assertEqual(self.system.override, "")
        self.assertIsNone(self.coordinator.selected)
        self.assertTrue(self.coordinator.status()["policy_deferred"])
        self.assertEqual(self.system.calls, [(1, "status", {})])
        self.tick(3)
        self.assertEqual(self.system.live, "tv-recovery")
        self.assertEqual([p["profile"]["name"] for m, p in self.system.mutations() if m == "preview"],
                         ["tv-recovery", "tv-game"])
        self.assertEqual(self.system.mutations()[-1][0], "revert")

    def test_startup_sleep_keeps_daemon_and_defers_modesets(self):
        self.system.apply("tv-game")
        self.system.override = ""
        self.system.mon[1]["dpmsStatus"] = False
        self.system.actual = TimeoutError("sleeping DRM must not be queried")
        process = mock.Mock(pid=77)
        process.poll.return_value = None
        child = dc.Child(mock.Mock(return_value=process))
        statuses = []

        def publish(state):
            statuses.append(state)
            if len(statuses) == 3:
                self.system.stop.set()

        dc.supervise(self.system, self.coordinator, child, publish)
        self.assertEqual(self.system.override, "")
        self.assertTrue(statuses[0]["daemon_ready"])
        self.assertTrue(all(s["policy_deferred"] for s in statuses[:-1]))
        self.assertIn("topology unavailable or asleep", [s["health"] for s in statuses])
        self.assertEqual(self.system.mutations(), [])
        process.terminate.assert_called_once()  # Only normal requested shutdown.

    def test_unmatched_startup_keeps_daemon_without_forcing_a_route(self):
        self.system.editor_name = ""
        self.system.states = ha("")
        self.system.mon[0]["width"] = 4000
        process = mock.Mock(pid=77)
        process.poll.return_value = None
        child = dc.Child(mock.Mock(return_value=process))
        statuses = []

        def publish(state):
            statuses.append(state)
            if len(statuses) == 4:
                self.system.stop.set()

        dc.supervise(self.system, self.coordinator, child, publish)
        self.assertTrue(all(s["daemon_ready"] and s["policy_deferred"] for s in statuses[:-1]))
        self.assertTrue(all(s["selected_route"] is None for s in statuses))
        self.assertEqual(self.system.mon[0]["width"], 4000)
        self.assertEqual(self.system.mutations(), [])
        process.terminate.assert_called_once()

    def test_unmatched_startup_leaves_known_route_to_regular_loop(self):
        self.system.editor_name = ""
        self.system.override = ""
        self.system.mon[0]["width"] = 4000
        dc.startup(self.system, self.coordinator)
        self.assertTrue(self.coordinator.daemon_ready)
        self.assertIsNone(self.coordinator.selected)
        self.assertEqual(self.system.calls, [(1, "status", {})])
        self.tick()
        self.assertEqual(self.system.mutations(), [])
        self.assertTrue(self.coordinator.status()["policy_deferred"])
        self.tick()
        self.assertEqual([p["profile"]["name"] for m, p in self.system.mutations() if m == "preview"],
                         ["tv-game"])

    def test_startup_human_preview_is_untouched(self):
        self.system.preview = {"transaction_id": "human"}
        dc.startup(self.system, self.coordinator)
        self.assertEqual(self.system.calls, [(1, "status", {})])
        self.assertEqual(self.coordinator.health, "ready; policy deferred")

    def test_startup_rejects_missing_or_incompatible_ipc_only(self):
        for capability in (None, False, 1, "true"):
            with self.subTest(capability=capability):
                self.setUp()
                self.system.ipc_only = capability
                process = mock.Mock(pid=77)
                process.poll.return_value = None
                child = dc.Child(mock.Mock(return_value=process))
                with self.assertRaisesRegex(ValueError, "ipc_only=true"):
                    dc.supervise(self.system, self.coordinator, child, lambda _: None)
                process.terminate.assert_called_once()
                self.assertEqual(self.system.calls, [(1, "status", {})])
                self.assertFalse(self.coordinator.daemon_ready)
                self.assertEqual(self.system.mutations(), [])

    def test_capability_loss_blocks_regular_loop_and_transaction(self):
        self.tick()
        self.system.ipc_only = False
        self.tick(3)
        self.assertFalse(self.coordinator.daemon_ready)
        self.assertIn("ipc_only=true", self.coordinator.error)
        with self.system.ipc() as ipc, self.assertRaisesRegex(ValueError, "ipc_only=true"):
            self.coordinator.transaction(ipc, "tv-game", self.system.profiles)
        self.assertEqual(self.system.mutations(), [])

    def test_startup_only_checks_capability_without_policy_queries(self):
        with (mock.patch.object(self.system, "ha", side_effect=AssertionError("HA queried")),
              mock.patch.object(self.system, "monitors", side_effect=AssertionError("monitors queried")),
              mock.patch.object(self.system, "drm", side_effect=AssertionError("DRM queried"))):
            dc.startup(self.system, self.coordinator)
        self.assertEqual(self.system.calls, [(1, "status", {})])
        self.assertTrue(self.coordinator.status()["daemon_ready"])
        self.assertTrue(self.coordinator.status()["policy_deferred"])

    def test_private_binary_missing_has_no_system_fallback(self):
        spawn = mock.Mock(side_effect=FileNotFoundError("private daemon missing"))
        child = dc.Child(spawn)
        with self.assertRaises(FileNotFoundError):
            child.start()
        spawn.assert_called_once_with(
            [str(Path.home() / ".local/libexec/display-controller/hyprmoncfgd"), "--ipc-only"])
        self.assertIsNone(child.proc)

    def test_unknown_ha_mismatch_keeps_daemon_without_modesets(self):
        self.system.apply("tv-game")
        self.system.override = ""
        self.system.actual = (1280, 720)
        self.system.states = ha("")
        dc.startup(self.system, self.coordinator)
        self.tick(10)
        self.assertTrue(self.coordinator.status()["daemon_ready"])
        self.assertTrue(self.coordinator.status()["policy_deferred"])
        self.assertIsNone(self.coordinator.selected)
        self.assertEqual(self.system.override, "")
        self.assertEqual(self.system.mutations(), [])

    def test_child_exit_stops_instead_of_restart_storm(self):
        process = mock.Mock(pid=77)
        process.poll.return_value = 1
        child = dc.Child(mock.Mock(return_value=process))
        statuses = []
        with self.assertRaisesRegex(ChildProcessError, "hyprmoncfgd exited"):
            dc.supervise(self.system, self.coordinator, child, statuses.append)
        child.spawn.assert_called_once()
        self.assertEqual(statuses[0]["error"], "hyprmoncfgd exited")

    def test_child_crash_propagates_failure_exit_status(self):
        process = mock.Mock(pid=77)
        process.poll.return_value = 1
        child = dc.Child(mock.Mock(return_value=process))
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            with (mock.patch.object(dc, "runtime_dir", return_value=runtime),
                  mock.patch.object(dc, "System", return_value=self.system),
                  mock.patch.object(dc, "Child", return_value=child),
                  contextlib.redirect_stdout(io.StringIO()) as output):
                self.assertEqual(dc.main([]), 2)
            self.assertIn("hyprmoncfgd exited", output.getvalue())



class AudioTests(unittest.TestCase):
    def setUp(self):
        self.system = FakeSystem()
        self.coordinator = dc.Coordinator(self.system, clock=lambda: self.system.now)
        # Exercise System's real bounded pactl adapter, with only run() mocked.
        self.system.pactl = dc.System(None, self.system.stop).pactl
        self.helper = mock.patch.object(dc, "run", side_effect=self.system.audio.run)
        self.helper.start()
        self.addCleanup(self.helper.stop)

    def tick(self, n=1):
        for _ in range(n):
            self.coordinator.step()
            self.system.advance(dc.POLL)

    def tv(self):
        self.system.apply("tv-game")

    def test_startup_adopts_tv_and_routes_default_and_running_game_without_modeset(self):
        self.tv()
        self.tick()
        self.assertEqual(self.system.audio.default, self.system.audio.tv_name)
        self.assertEqual(self.system.audio.writes(), [
            ("set-default-sink", self.system.audio.tv_name),
            ("move-sink-input", "808", self.system.audio.tv_name)])
        self.assertEqual(self.system.mutations(), [])
        self.assertEqual(self.coordinator.status()["audio_health"], "healthy")

    def test_tv_audio_idempotence(self):
        self.tv()
        self.tick()
        self.system.audio.calls.clear()
        self.tick(4)
        self.assertEqual(self.system.audio.writes(), [])

    def test_pending_ha_tv_intent_keeps_desk_audio_until_layout_changes(self):
        self.system.audio.default = self.system.audio.tv_name
        self.tick()
        self.assertEqual(self.system.audio.default, dc.DESK_SINK)
        self.assertEqual(self.system.mutations(), [])
        self.tick()  # Display transaction changes the verified current layout.
        self.assertEqual(self.system.live, "tv-game")
        self.tick()
        self.assertEqual(self.system.audio.default, self.system.audio.tv_name)

    def test_unknown_ha_still_routes_verified_current_tv(self):
        self.tv()
        self.system.states = ha(source="")
        self.tick()
        self.assertEqual(self.system.audio.default, self.system.audio.tv_name)
        self.assertEqual(self.system.mutations(), [])
        self.assertEqual(self.coordinator.health, "HA uncertain; live route verified")

    def test_current_surround_profile_is_preserved(self):
        self.tv()
        self.system.audio.cards[0]["active_profile"] = "output:hdmi-surround71-extra1"
        self.system.audio.sony["name"] = "alsa_output.pci-0000_01_00.1.hdmi-surround71-extra1"
        self.tick()
        self.assertEqual(self.system.audio.default, self.system.audio.sony["name"])
        self.assertFalse(any(c[0] == "set-card-profile" for c in self.system.audio.writes()))

    def test_unavailable_wrong_or_ambiguous_sony_defers_without_writes(self):
        for fault in ("unavailable", "samsung", "ambiguous", "usb"):
            with self.subTest(fault=fault):
                self.system.audio = FakeAudio()
                card = self.system.audio.cards[0]
                if fault == "unavailable":
                    card["ports"]["hdmi-output-1"]["availability"] = "unavailable"
                elif fault == "samsung":
                    card["ports"]["hdmi-output-1"]["properties"]["device.product.name"] = "SAMSUNG"
                elif fault == "usb":
                    card["name"] = "alsa_card.usb-unrelated"
                else:
                    other = copy.deepcopy(card)
                    other["name"] = "alsa_card.pci-0000_02_00.1"
                    self.system.audio.cards.append(other)
                with mock.patch.object(dc, "run", side_effect=self.system.audio.run):
                    self.tv()
                    self.tick()
                self.assertEqual(self.system.audio.writes(), [])
                self.assertEqual(self.coordinator.audio_health, "unavailable")

    def test_existing_sink_on_wrong_hdmi_output_is_never_selected(self):
        self.tv()
        self.system.audio.sony["active_port"] = "hdmi-output-0"
        self.tick()
        self.assertEqual(self.system.audio.writes(), [])
        self.assertEqual(self.system.audio.default, dc.DESK_SINK)
        self.assertEqual(self.coordinator.audio_health, "unavailable")

    def test_contradictory_sink_product_is_never_selected(self):
        self.tv()
        self.system.audio.sony["properties"]["alsa.name"] = "SAMSUNG"
        self.tick()
        self.assertEqual(self.system.audio.writes(), [])
        self.assertEqual(self.coordinator.audio_health, "unavailable")

    def test_preview_or_sleep_during_publication_wait_prevents_routing(self):
        for fault in ("preview", "sleep", "desk"):
            with self.subTest(fault=fault):
                system = FakeSystem()
                system.apply("tv-game")
                system.audio.sinks = [system.audio.desk]
                system.audio.publish_after = 3
                coordinator = dc.Coordinator(system, clock=lambda: system.now)

                def interrupt():
                    if fault == "preview":
                        system.preview = {"transaction_id": "human"}
                    elif fault == "sleep":
                        next(m for m in system.mon if not m["disabled"])["dpmsStatus"] = False
                    else:
                        system.apply("desk")

                system.wait_hook = interrupt
                coordinator.step()
                self.assertEqual(system.audio.writes(), [])
                self.assertEqual(coordinator.audio_health, "unavailable")

    def test_malformed_nested_audio_data_does_not_escape_into_display_policy(self):
        self.tv()
        self.system.audio.sinks = [self.system.audio.desk]
        self.system.audio.cards[0]["ports"]["hdmi-output-1"]["profiles"] = [None]
        self.tick(2)
        self.assertEqual(self.coordinator.health, "healthy")
        self.assertEqual(self.coordinator.count, 2)
        self.assertEqual(self.coordinator.audio_health, "unavailable")

    def test_ambiguous_sinks_defer(self):
        self.tv()
        self.system.audio.sinks.append(dict(self.system.audio.sony, index=74, name="duplicate"))
        self.tick()
        self.assertEqual(self.system.audio.writes(), [])
        self.assertIn("ambiguous", self.coordinator.audio_error)

    def test_available_sony_profile_discovery_and_late_publication(self):
        self.tv()
        audio = self.system.audio
        audio.sinks = [audio.desk]
        audio.cards[0]["active_profile"] = "output:hdmi-surround"
        audio.cards[0]["profiles"]["output:hdmi-surround"] = {"available": False}
        audio.publish_after = 4
        self.tick()
        self.assertEqual(audio.writes()[0], ("set-card-profile", audio.card, audio.profile))
        self.assertEqual(audio.default, audio.tv_name)
        self.assertEqual(audio.cards[0]["active_profile"], audio.profile)
        self.assertEqual(audio.sink_queries, 4)

    def test_profile_already_active_waits_without_rewriting(self):
        self.tv()
        audio = self.system.audio
        audio.sinks = [audio.desk]
        audio.publish_after = 3
        self.tick()
        self.assertEqual(audio.default, audio.tv_name)
        self.assertFalse(any(c[0] == "set-card-profile" for c in audio.writes()))

    def test_sink_publication_wait_is_bounded_and_no_profile_storm(self):
        self.tv()
        audio = self.system.audio
        audio.sinks = [audio.desk]
        audio.cards[0]["active_profile"] = "off"
        self.tick()
        self.assertEqual(audio.sink_queries, 5)  # initial list plus four wait attempts
        self.assertIn("timed out", self.coordinator.audio_error)
        self.tick(4)
        self.assertEqual([c for c in audio.writes() if c[0] == "set-card-profile"],
                         [("set-card-profile", audio.card, audio.profile)])
        self.assertFalse(any(c[0] == "set-default-sink" for c in audio.writes()))

    def test_failed_profile_write_is_cooled_down(self):
        self.tv()
        audio = self.system.audio
        audio.sinks = [audio.desk]
        audio.cards[0]["active_profile"] = "off"
        original = audio.pactl

        def fail_profile(*args):
            if args[0] == "set-card-profile":
                audio.calls.append(args)
                raise subprocess.TimeoutExpired("pactl", 5)
            return original(*args)

        with mock.patch.object(dc, "run", side_effect=lambda args, timeout=5: fail_profile(*args[1:])):
            self.tick(4)
        self.assertEqual(len([c for c in audio.writes() if c[0] == "set-card-profile"]), 1)
        self.assertEqual(self.coordinator.audio_health, "unavailable")

    def test_unavailable_profiles_never_enabled(self):
        self.tv()
        audio = self.system.audio
        audio.sinks = [audio.desk]
        for settings in audio.cards[0]["profiles"].values():
            settings["available"] = False
        self.tick()
        self.assertEqual(audio.writes(), [])
        self.assertIn("no available", self.coordinator.audio_error)

    def test_desk_return_moves_playback_without_card_or_capture_changes(self):
        self.tv()
        self.tick()
        self.system.apply("desk")
        self.system.states = ha(screen="off")
        self.system.audio.calls.clear()
        self.tick()
        self.assertEqual(self.system.audio.default, dc.DESK_SINK)
        self.assertEqual(self.system.audio.writes(), [
            ("set-default-sink", dc.DESK_SINK),
            ("move-sink-input", "808", dc.DESK_SINK),
            ("move-sink-input", "909", dc.DESK_SINK)])
        self.assertEqual(self.system.mutations(), [])

    def test_missing_focusrite_does_not_choose_other_usb_sink(self):
        self.system.audio.desk["name"] = "alsa_output.usb-unrelated"
        self.tick()
        self.assertEqual(self.system.audio.writes(), [])
        self.assertIn("Focusrite", self.coordinator.audio_error)

    def test_sleep_preview_unmanaged_and_unsupported_topology_yield(self):
        for fault in ("sleep", "preview", "unmanaged", "unknown", "dual", "mismatch"):
            with self.subTest(fault=fault):
                self.system = FakeSystem()
                self.tv()
                self.coordinator = dc.Coordinator(self.system, clock=lambda: self.system.now)
                if fault == "sleep":
                    next(m for m in self.system.mon if not m["disabled"])["dpmsStatus"] = False
                elif fault == "preview":
                    self.system.preview = {"transaction_id": "human"}
                elif fault == "unmanaged":
                    self.system.unmanaged = True
                elif fault == "unknown":
                    self.system.mon.append({"name": "unknown"})
                elif fault == "dual":
                    self.system.mon[0].update(disabled=False, dpmsStatus=True)
                else:
                    self.system.actual = (1280, 720)
                self.tick()
                self.assertEqual(self.system.audio.calls, [])
                self.assertEqual(self.coordinator.audio_health, "deferred")

    def test_audio_errors_preserve_display_debounce_and_recovery(self):
        self.tv()
        self.system.audio.error = subprocess.TimeoutExpired("pactl", 5)
        self.tick(2)
        self.assertEqual(self.coordinator.health, "healthy")
        self.assertEqual(self.coordinator.candidate, "tv-game")
        self.assertEqual(self.coordinator.count, 2)
        self.assertIn("timed out", self.coordinator.status()["audio_error"])
        self.system.actual = (1920, 1080)
        self.tick(2)
        self.assertTrue(self.coordinator.recovery_attempted)
        self.assertTrue(any(method == "preview" for method, _ in self.system.mutations()))
        self.assertEqual(self.coordinator.audio_health, "deferred")

    def test_audio_failure_does_not_prevent_display_route_change(self):
        self.system.audio.error = ValueError("invalid pactl JSON")
        self.tick(2)
        self.assertEqual(self.system.live, "tv-game")
        self.assertEqual(self.coordinator.health, "route applied")
        self.assertEqual(self.coordinator.audio_health, "unavailable")
        self.system.audio.error = None
        self.tick()
        self.assertEqual(self.coordinator.audio_health, "healthy")
        self.assertIsNone(self.coordinator.audio_error)

    def test_rollback_reconciles_restored_route_on_next_iteration(self):
        self.system.workspace_fault = "2"
        self.tick(2)
        self.assertEqual(self.system.live, "desk")
        # Simulate a legacy post-apply audio helper having changed playback.
        self.system.audio.default = self.system.audio.tv_name
        self.system.audio.streams[0]["sink"] = 73
        self.tick()
        self.assertEqual(self.system.audio.default, dc.DESK_SINK)
        self.assertEqual(self.system.audio.streams[0]["sink"], 12)
        self.assertEqual(self.system.live, "desk")

    def test_busy_audio_lock_does_not_reset_display_policy(self):
        self.tv()
        self.system.audio_lock = mock.Mock(side_effect=BlockingIOError("audio busy"))
        self.tick(2)
        self.assertEqual(self.coordinator.health, "healthy")
        self.assertEqual(self.coordinator.count, 2)
        self.assertEqual(self.coordinator.audio_health, "unavailable")

    def test_audio_cli_modes_are_early_and_verify_live_route(self):
        for mode, live, preview, expected in (
                ("--audio-tv", "tv-game", None, 0),
                ("--audio-desk", "desk", None, 0),
                ("--audio-tv", "desk", None, 2),
                ("--audio-desk", "tv-game", None, 2),
                ("--audio-tv", "tv-game", {"transaction_id": "human"}, 2)):
            with self.subTest(mode=mode, live=live, preview=preview):
                system = FakeSystem()
                system.apply(live)
                system.preview = preview
                with mock.patch.object(dc, "runtime_dir", return_value=Path("/unused")), \
                        mock.patch.object(dc, "System", return_value=system), \
                        mock.patch.object(dc, "Child", side_effect=AssertionError("must not start daemon")), \
                        mock.patch.object(system, "ha", side_effect=AssertionError("must not read HA")), \
                        contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(dc.main([mode]), expected)
                self.assertEqual(system.mutations(), [])
                if expected:
                    self.assertEqual(system.audio.calls, [])

    def test_three_line_shims_forward_to_controller_audio_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            binary = home / ".local/bin/display-controller"
            binary.parent.mkdir(parents=True)
            binary.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            binary.chmod(0o700)
            for route in ("tv", "desk"):
                shim = SOURCE.with_name("hyprmoncfg-audio-" + route)
                self.assertEqual(len(shim.read_text().splitlines()), 3)
                result = subprocess.run(["sh", str(shim), "extra"], env=dict(os.environ, HOME=directory),
                                        text=True, capture_output=True, check=True, timeout=3)
                self.assertEqual(result.stdout.splitlines(), ["--audio-" + route, "extra"])


class BoundaryTests(unittest.TestCase):
    def test_scratch_guard_rejects_unset_real_home_and_escaping_tmpdir(self):
        for updates in ({"DISPLAY_TEST_SCRATCH_HOME": ""},
                        {"DISPLAY_TEST_SCRATCH_HOME": "/home/igor", "HOME": "/home/igor"},
                        {"TMPDIR": "/tmp"}):
            with self.subTest(updates=updates), mock.patch.dict(os.environ, updates):
                with self.assertRaises(RuntimeError):
                    setUpModule()

    def test_drm_connector_encoder_crtc_chain(self):
        report = """Encoders:
11 22 TMDS 0x1 0x0
12 23 TMDS 0x2 0x0
Connectors:
31 11 connected DP-1 600x340 1 11
32 12 connected HDMI-A-1 1600x900 1 12
CRTCs:
22 44 (0,0) (5120x1440)
23 45 (4096,0) (1920x1080)
"""
        self.assertEqual(dc.drm_size(report), (1920, 1080))
        self.assertIsNone(dc.drm_size(report.replace("12 23 TMDS", "12 0 TMDS")))
        self.assertIsNone(dc.drm_size(report.replace("connected HDMI", "disconnected HDMI")))

    def test_check_health_and_cli_exit_codes_are_read_only(self):
        system = FakeSystem()
        system.apply("tv-game")
        for actual, code in (("follow", 0), ((1280, 720), 1), (None, 2)):
            system.actual = actual
            with mock.patch.object(dc, "System", return_value=system), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(dc.main(["--check"]), code)
        self.assertEqual(system.calls, [])

    def test_ha_reader_does_not_query_unused_fallbacks(self):
        responses = [json.dumps(s) for s in ha()[:3]]
        with mock.patch.object(dc, "run", side_effect=responses) as helper:
            states = dc.System(None, threading.Event()).ha()
        self.assertEqual(dc.choose(states), "tv-game")
        self.assertEqual(helper.call_count, 3)
        self.assertEqual([call.args[0][-1] for call in helper.call_args_list],
                         ["/api/states/" + e for e in (dc.TV, dc.SCREEN, dc.AVR)])

    def test_helper_timeout_kills_group_and_reaps(self):
        process = mock.Mock(pid=4242)
        process.communicate.side_effect = [subprocess.TimeoutExpired("ha", 12), ("", "")]
        with mock.patch.object(dc.subprocess, "Popen", return_value=process) as spawn, mock.patch.object(dc.os, "killpg") as kill:
            with self.assertRaises(subprocess.TimeoutExpired):
                dc.run(["fake-ha"], timeout=12)
        self.assertTrue(spawn.call_args.kwargs["start_new_session"])
        kill.assert_called_once_with(4242, signal.SIGKILL)
        self.assertEqual(process.communicate.call_count, 2)

    def test_child_shutdown_escalates_with_bounded_waits(self):
        process = mock.Mock(pid=42)
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("daemon", 8), 0]
        child = dc.Child(mock.Mock(return_value=process))
        child.start()
        child.stop()
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_args_list, [mock.call(timeout=8), mock.call(timeout=2)])

    def test_private_runtime_duplicate_guard_and_atomic_status(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            with mock.patch.dict(os.environ, XDG_RUNTIME_DIR=directory):
                self.assertEqual(dc.runtime_dir(), runtime)
                with dc.coordinator_lock(runtime):
                    with self.assertRaises(BlockingIOError):
                        with dc.coordinator_lock(runtime):
                            self.fail("duplicate lock acquired")
                state = {"selected_route": "tv-game", "health": "healthy", "daemon_pid": 42}
                path = runtime / "display-controller-status.json"
                dc.atomic_write(path, json.dumps(state))
                dc.atomic_write(path, json.dumps(dict(state, health="mismatch")))
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(dc.main(["--status"]), 0)
                self.assertEqual(json.loads(output.getvalue())["health"], "mismatch")
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertFalse((runtime / "ha-display-profile").exists())
                runtime.chmod(0o755)
                with self.assertRaises(ValueError):
                    dc.runtime_dir()
                runtime.chmod(0o700)


class FakeSocket:
    def __init__(self, *_):
        self.closed = False
        self.sent = []
        self.messages = []
        self.timeout = None
        self.connect_error: Any = None
        self.recv_error: Any = None

    def settimeout(self, timeout):
        self.timeout = timeout

    def connect(self, path):
        if self.connect_error:
            raise self.connect_error

    def sendall(self, message):
        request = json.loads(message)
        self.sent.append(request)
        self.messages = [json.dumps({"protocol_version": 1, "type": "event", "event": "status"}) + "\n",
                         json.dumps({"protocol_version": 1, "type": "response", "id": request["id"], "result": {"id": "tx"}}) + "\n"]

    def recv(self, size):
        if self.recv_error:
            raise self.recv_error
        return self.messages.pop(0).encode()

    def close(self):
        self.closed = True



class LauncherTests(unittest.TestCase):
    def test_hdr_override_is_inside_gamescope_and_preserves_command(self):
        launcher = SOURCE.with_name("hdr-game-launch")
        with tempfile.TemporaryDirectory() as directory:
            gamescope = Path(directory) / "gamescope"
            gamescope.write_text("#!/bin/bash\nwhile [[ $1 != -- ]]; do shift; done\n"
                                 "shift\nexport DXVK_HDR=0\nexec \"$@\"\n")
            gamescope.chmod(0o700)
            command = ["/usr/bin/python3", "-c",
                       "import json,os,sys; print(json.dumps([os.getenv('DXVK_HDR'),sys.argv[1:]])); sys.exit(7)",
                       "argument with spaces", "literal $argument"]
            env = dict(os.environ, DXVK_HDR="0")
            nested = subprocess.run([str(launcher), str(gamescope), "-f", "--", *command],
                                    text=True, capture_output=True, env=env)
            self.assertEqual(nested.returncode, 7, nested.stderr)
            self.assertEqual(json.loads(nested.stdout), ["1", command[3:]])
            direct = subprocess.run([str(launcher), *command],
                                    text=True, capture_output=True, env=env)
            self.assertEqual(direct.returncode, 7, direct.stderr)
            self.assertEqual(json.loads(direct.stdout), ["0", command[3:]])


class IPCTests(unittest.TestCase):
    def test_exact_envelopes_interleaved_events_and_same_connection(self):
        sock = FakeSocket()
        with dc.IPC("fake", connect=lambda *_: sock) as ipc:
            transaction = ipc.request("preview", profile_name="tv-recovery", save_on_commit=False)
            ipc.request("commit", transaction_id=transaction["id"], save=False)
            ipc.request("revert", transaction_id="other-owned")
        self.assertTrue(sock.closed)
        for i, request in enumerate(sock.sent, 1):
            self.assertEqual(request["protocol_version"], 1)
            self.assertEqual(request["type"], "request")
            self.assertEqual(request["id"], str(i))
        self.assertEqual(sock.sent[1]["params"], {"transaction_id": "tx", "save": False})

    def test_connect_and_response_timeouts_close_socket(self):
        for phase in ("connect", "recv"):
            with self.subTest(phase=phase):
                sock = FakeSocket()
                if phase == "connect":
                    sock.connect_error = socket.timeout("connect")
                else:
                    sock.recv_error = socket.timeout("response")
                with self.assertRaises(TimeoutError):
                    with dc.IPC("fake", connect=lambda *_: sock) as ipc:
                        ipc.request("status")
                self.assertTrue(sock.closed)

    def test_event_flood_cannot_extend_deadline(self):
        sock = FakeSocket()
        clock = mock.Mock(side_effect=range(100))
        with self.assertRaises(TimeoutError):
            with dc.IPC("fake", timeout=3, clock=clock, connect=lambda *_: sock) as ipc:
                ipc.request("status")
        self.assertTrue(sock.closed)


if __name__ == "__main__":
    unittest.main()
