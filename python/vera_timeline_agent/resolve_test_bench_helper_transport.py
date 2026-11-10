"""Production-only signed Aqua helper transport for the original #473 M4 host.

Never spawns a helper, shell, System Events, Hammerspoon or Resolve. The
installed LaunchAgent owns the private spool; a reply never proves a Roll.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from . import resolve_gui_helper_protocol as protocol
from . import resolve_gui_roll as gui
from . import resolve_test_bench_carrier as carrier
from . import resolve_test_queue as queue

SPOOL = Path.home() / "Library/Application Support/VERA/GUI Helper/spool"
FOCUS_SCHEMA = "vera.gui-helper-focus-request/v1"
FOCUS_REPLY_SCHEMA = "vera.gui-helper-focus-reply/v1"
SELF_SCHEMA = "vera.gui-helper-self-status/v1"
RESOLVE_EXECUTABLE = (
    "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/MacOS/Resolve"
)


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise gui.GuiRollRefused("signed GUI helper: " + reason)


def _deadline(seconds: int) -> str:
    return (
        (datetime.now(UTC) + timedelta(seconds=seconds))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


class SignedHelperDesktop:
    """Exact signed process, self Accessibility, fixed focus/read-only menus."""

    def __init__(self, actor_pin: dict[str, Any], spool: Path = SPOOL):
        protocol.validate_actor_pin(actor_pin, installed=True)
        carrier._private(spool)
        self.actor_pin = actor_pin
        self.spool = spool
        self.client = protocol.HelperClient(spool)

    def readiness(self) -> int:
        """Desktop probe from the *actual* LaunchAgent, not our Python TCC."""
        record = json.loads(carrier._read(self.spool / "self-status.json", 4096))
        binary = self.actor_pin["binary"]
        _require(
            type(record) is dict
            and set(record)
            == {
                "schema",
                "helperPid",
                "bundleIdentifier",
                "executablePath",
                "accessibilityTrusted",
                "observedAt",
            }
            and record["schema"] == SELF_SCHEMA
            and record["bundleIdentifier"] == protocol.BUNDLE_ID
            and record["executablePath"] == binary["executablePath"]
            and record["accessibilityTrusted"] is True
            and type(record["helperPid"]) is int
            and type(record["observedAt"]) in {float, int}
            and 0 <= time.time() - record["observedAt"] <= 12
            and protocol.observe_helper_pid(
                record["helperPid"], binary["executablePath"]
            ),
            "LaunchAgent process, executable or Accessibility not ready",
        )
        return int(record["helperPid"])

    def resolve_pid(self) -> int:
        """Dedicated Mac runner desktop census, without System Events/TCC."""
        try:
            libproc = ctypes.CDLL("/usr/lib/libproc.dylib")
            count = libproc.proc_listallpids(None, 0)
            _require(0 < count <= 65536, "process census unavailable")
            pids = (ctypes.c_int * (count + 64))()
            total = libproc.proc_listallpids(pids, ctypes.sizeof(pids))
            _require(0 < total <= len(pids), "process census changed")
            found = [
                int(pid)
                for pid in pids[:total]
                if pid > 0 and protocol.observe_helper_pid(int(pid), RESOLVE_EXECUTABLE)
            ]
        except (OSError, ValueError) as error:
            raise gui.GuiRollRefused(
                "native Resolve process census unavailable"
            ) from error
        _require(len(found) == 1, "exactly one installed Resolve process required")
        return found[0]

    def _wait(self, path: Path, seconds: float) -> bytes:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                return carrier._read(path, 32768)
            except FileNotFoundError:
                time.sleep(0.1)
        raise gui.GuiRollUnknown(
            "signed GUI helper reply absent; never retry an intent"
        )

    def focus(
        self,
        job_id: str,
        stage_id: str,
        pid: int,
        window: str,
        *,
        operation: str = "focus",
    ) -> dict[str, Any]:
        """One bounded focus or independent read-only menu inspection."""
        self.readiness()
        _require(operation in {"focus", "inspect"}, "unsupported helper operation")
        token = hashlib.sha256(
            (job_id + ":" + stage_id + ":" + operation).encode()
        ).hexdigest()[:32]
        request_id = "focus-" + token
        request: dict[str, Any] = {
            "schema": FOCUS_SCHEMA,
            "requestId": request_id,
            "deadlineAt": _deadline(25),
            "operation": operation,
            "resolvePid": pid,
            "resolveBundleIdentifier": gui.RESOLVE_BUNDLE_ID,
            "windowName": window,
        }
        raw = queue.canonical(request)
        _require(
            type(pid) is int and pid > 0 and gui._safe_name(window),
            "exact Resolve PID/window required before focus",
        )
        carrier._once(self.spool / (request_id + ".focus-request.json"), raw)
        reply_raw = self._wait(self.spool / (request_id + ".focus-reply.json"), 8)
        reply = json.loads(reply_raw)
        _require(
            type(reply) is dict
            and set(reply)
            == {
                "schema",
                "requestId",
                "requestSha256",
                "helperPid",
                "status",
                "detail",
                "observation",
            }
            and queue.canonical(reply) == reply_raw
            and reply["schema"] == FOCUS_REPLY_SCHEMA
            and reply["requestId"] == request_id
            and reply["requestSha256"] == hashlib.sha256(raw).hexdigest()
            and reply["status"] == "ready"
            and reply["helperPid"] == self.readiness()
            and type(reply["detail"]) is str
            and type(reply["observation"]) is dict,
            "focus/read-only menu response refused or tampered",
        )
        observed = reply["observation"]
        _require(
            set(observed)
            == {
                "resolvePid",
                "bundleIdentifier",
                "windowName",
                "mainWindow",
                "foreground",
                "noModalOrSheet",
                "rollEnabled",
            }
            and type(observed["resolvePid"]) is int
            and observed["resolvePid"] == pid
            and observed["bundleIdentifier"] == gui.RESOLVE_BUNDLE_ID
            and observed["windowName"] == window
            and all(
                observed[key] is True
                for key in ("mainWindow", "foreground", "noModalOrSheet", "rollEnabled")
            ),
            "PID, foreground, exact window/modal or Roll menu differed",
        )
        return cast(dict[str, Any], observed)

    def roll(self, request: dict[str, Any]) -> dict[str, Any]:
        """Publish exactly once after host journal fsync; never infer success."""
        self.readiness()
        raw = queue.canonical(request)
        expected = {key: request[key] for key in protocol.OWNER_KEYS}
        self.client.publish_once(raw, expected=expected)
        try:
            self._wait(self.spool / (request["requestId"] + ".reply.json"), 35)
            reply = self.client.read_reply(raw)
        except (
            OSError,
            ValueError,
            queue.QueueError,
            protocol.HelperProtocolError,
        ) as error:
            raise gui.GuiRollUnknown(
                "helper dispatch uncertain; never retry"
            ) from error
        _require(
            reply["helperPid"] == self.readiness(), "helper changed after dispatch"
        )
        if reply["status"] != "dispatched-unknown":
            raise gui.GuiRollUnknown("helper refused or uncertain; never retry")
        return reply
