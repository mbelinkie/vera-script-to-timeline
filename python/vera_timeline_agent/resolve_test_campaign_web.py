"""Opt-in, loopback-only M3 campaign monitor; never a native worker.

Tailscale Serve supplies an asserted login, but direct loopback callers can
forge that header. Therefore a separately provisioned 256-bit local secret is
required to establish a short-lived, in-memory browser session. Neither the
secret nor a session is accepted as a substitute for the Tailscale identity.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import platform
import plistlib
import re
import secrets
import stat
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from . import resolve_test_campaign as campaign
from . import resolve_test_queue as queue

LABEL = "org.vera.resolve-test-campaign-monitor.m3"
MOUNT = "/resolve-tests/"
DEFAULT_PORT = 51762
_HOST = re.compile(r"[a-z0-9][a-z0-9.-]{2,252}\Z")
_SESSION_SECONDS = 3600
_MAX_BODY = 4096


def secret_path(store: queue.Store) -> Path:
    return store.root / "campaign-monitor-secret"


def provision_secret(store: queue.Store) -> None:
    """Creation is explicit; never rotate a secret or replace a symlink."""
    path = secret_path(store)
    queue.reject_unsafe_path(path, "monitor secret")
    value = secrets.token_urlsafe(32).encode("ascii") + b"\n"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        read_secret(store)  # valid existing secret; do not rotate browser access
        return
    with os.fdopen(fd, "wb") as output:
        output.write(value)
        output.flush()
        os.fsync(output.fileno())
    queue.sync_directory(path.parent)


def read_secret(store: queue.Store) -> str:
    path = secret_path(store)
    queue.reject_unsafe_path(path, "monitor secret")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        if (
            (st.st_mode & 0o777) != 0o600
            or not stat.S_ISREG(st.st_mode)
            or st.st_uid != os.getuid()
        ):
            raise queue.QueueError("monitor secret must be private and regular")
        raw = os.read(fd, 128)
    finally:
        os.close(fd)
    try:
        token = raw.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise queue.QueueError("invalid monitor secret") from exc
    if not re.fullmatch(r"[A-Za-z0-9_-]{40,64}", token):
        raise queue.QueueError("invalid monitor secret")
    return token


def _root_proxy(config: dict[str, Any]) -> tuple[str, str]:
    web = config.get("Web")
    if not isinstance(web, dict):
        raise queue.QueueError("Tailscale Serve HTTPS root is not configured")
    roots = [
        (host, routes["Handlers"]["/"]["Proxy"])
        for host, routes in web.items()
        if isinstance(routes, dict)
        and isinstance(routes.get("Handlers"), dict)
        and isinstance(routes["Handlers"].get("/"), dict)
        and isinstance(routes["Handlers"]["/"].get("Proxy"), str)
        and host.endswith(":443")
    ]
    if len(roots) != 1:
        raise queue.QueueError("expected exactly one existing HTTPS root proxy")
    host, proxy = roots[0]
    if not proxy.startswith("http://127.0.0.1:"):
        raise queue.QueueError("existing HTTPS root proxy is not loopback")
    if config.get("AllowFunnel", {}).get(host):
        raise queue.QueueError("public Funnel is forbidden for monitor")
    return host, proxy


def configure_tailscale_path(
    port: int,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    """Add exactly one Serve mount; verify the pre-existing '/' stays identical.

    This never resets Serve, replaces the root or invokes Funnel. Failure to
    verify the postcondition is reported, not silently swallowed.
    """
    queue.limited_int(port, "port", 1024, 65535)

    def snapshot() -> dict[str, Any]:
        result = runner(
            ["tailscale", "serve", "status", "--json"],
            check=True,
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        if not isinstance(data, dict):
            raise queue.QueueError("invalid Tailscale Serve status")
        return data

    before = snapshot()
    hostname, original = _root_proxy(before)
    if original.rstrip("/") == f"http://127.0.0.1:{port}":
        raise queue.QueueError("monitor port conflicts with existing root dashboard")
    routes = before["Web"][hostname]["Handlers"]
    if any(key.rstrip("/") == MOUNT.rstrip("/") for key in routes):
        raise queue.QueueError("monitor Serve mount already exists; inspect manually")
    runner(
        [
            "tailscale",
            "serve",
            "--bg",
            f"--set-path={MOUNT}",
            f"http://127.0.0.1:{port}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    after = snapshot()
    if _root_proxy(after) != (hostname, original):
        raise queue.QueueError(
            "CRITICAL: original Tailscale '/' proxy changed; inspect Serve status"
        )
    after_routes = after["Web"][hostname]["Handlers"]
    if not any(
        key.rstrip("/") == MOUNT.rstrip("/")
        and isinstance(value, dict)
        and value.get("Proxy") == f"http://127.0.0.1:{port}"
        for key, value in after_routes.items()
    ):
        raise queue.QueueError("Tailscale monitor path was not installed as expected")


def agent_plist(
    store: queue.Store, host: str, login: str, port: int, executable: str
) -> bytes:
    return plistlib.dumps(
        {
            "Label": LABEL,
            "ProgramArguments": [
                executable,
                "-m",
                "vera_timeline_agent.resolve_test_campaign_web",
                "--root",
                str(store.root),
                "--host",
                host,
                "--operator",
                login,
                "--port",
                str(port),
                "serve",
            ],
            "RunAtLoad": True,
            "KeepAlive": True,
            "ProcessType": "Background",
            "StandardOutPath": str(store.root / "monitor.stdout.log"),
            "StandardErrorPath": str(store.root / "monitor.stderr.log"),
        },
        sort_keys=True,
    )


def install_agent(store: queue.Store, host: str, login: str, port: int) -> None:
    if platform.system() != "Darwin":
        raise queue.QueueError("LaunchAgent installation requires macOS")
    read_secret(store)
    payload = agent_plist(store, host, login, port, sys.executable)
    plist = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    plist.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    queue.reject_unsafe_path(plist, "LaunchAgent")
    if plist.exists():
        if plist.read_bytes() != payload:
            raise queue.QueueError("monitor LaunchAgent differs; refusing overwrite")
    else:
        fd = os.open(plist, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
    loaded = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if loaded.returncode != 0:
        subprocess.run(
            ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)],
            check=True,
            capture_output=True,
            text=True,
        )


class Monitor(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request: Any, client_address: Any) -> None:
        # BaseServer's default traceback contains exception text, which may
        # include private file locators. Never disclose it to monitor logs.
        return

    def __init__(self, store: queue.Store, host: str, login: str, port: int) -> None:
        if not _HOST.fullmatch(host) or ":" in host or "." not in host:
            raise queue.QueueError("expected exact Tailscale HTTPS host")
        if not login or "@" not in login or "\n" in login:
            raise queue.QueueError("expected exact Tailscale-User-Login")
        queue.limited_int(port, "port", 1024, 65535)
        self.store = store
        self.host = host
        self.login = login
        self.secret = read_secret(store)
        self.sessions: dict[str, tuple[str, str, float]] = {}
        self.session_lock = threading.Lock()
        super().__init__(("127.0.0.1", port), MonitorHandler)


class MonitorHandler(BaseHTTPRequestHandler):
    server: Monitor
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: Any) -> None:
        # Never log paths, cookies, secrets, user headers or request bodies.
        return

    def _send(
        self,
        status: int,
        payload: bytes,
        content_type: str = "application/json",
        *,
        cookie: str | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store, private")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'unsafe-inline'; "
            "style-src 'unsafe-inline'; connect-src 'self'; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
        )
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status: int, obj: object) -> None:
        self._send(status, queue.canonical(obj))

    def _path(self) -> str | None:
        parsed = urlsplit(self.path)
        if parsed.query or parsed.fragment or not parsed.path.startswith("/"):
            return None
        path = parsed.path
        if path == MOUNT.rstrip("/"):
            return "/"
        if path.startswith(MOUNT):
            path = "/" + path[len(MOUNT) :]
        return path

    def _identity(self) -> bool:
        return (
            self.client_address[0] == "127.0.0.1"
            and self.headers.get("Host") == self.server.host
            and self.headers.get("Tailscale-User-Login") == self.server.login
            and len(self.headers.get_all("Tailscale-User-Login", [])) == 1
        )

    def _session(self) -> tuple[str, str] | None:
        if not self._identity():
            return None
        cookies = self.headers.get_all("Cookie", [])
        if len(cookies) != 1:
            return None
        values = [v.strip() for v in cookies[0].split(";")]
        sessions = [
            v.split("=", 1)[1] for v in values if v.startswith("__Secure-vera_m3=")
        ]
        if len(sessions) != 1:
            return None
        with self.server.session_lock:
            entry = self.server.sessions.get(sessions[0])
            if (
                not entry
                or time.monotonic() >= entry[2]
                or entry[0] != self.server.login
            ):
                return None
            return entry[0], entry[1]

    def _origin(self) -> bool:
        return (
            self.headers.get("Origin") == f"https://{self.server.host}"
            and len(self.headers.get_all("Origin", [])) == 1
            and self.headers.get("Sec-Fetch-Site", "same-origin")
            in {"same-origin", "none"}
        )

    def _body(self) -> dict[str, Any] | None:
        if self.headers.get("Content-Type") != "application/json":
            return None
        length = self.headers.get("Content-Length", "")
        if (
            not length.isascii()
            or not length.isdecimal()
            or not 0 < int(length) <= _MAX_BODY
        ):
            return None
        try:
            obj = json.loads(self.rfile.read(int(length)))
        except (UnicodeError, ValueError):
            return None
        return obj if isinstance(obj, dict) else None

    def do_GET(self) -> None:
        path = self._path()
        if path == "/" and self._identity():
            self._send(200, _HTML.encode(), "text/html; charset=utf-8")
            return
        sess = self._session()
        if sess is None:
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        if path == "/api/session":
            self._json(200, {"csrf": sess[1]})
        elif path == "/api/campaigns":
            try:
                with self.server.store.connect() as db:
                    rows = db.execute(
                        "SELECT id FROM campaigns ORDER BY submitted_at DESC LIMIT 100"
                    ).fetchall()
                self._json(200, {"campaigns": [row[0] for row in rows]})
            except Exception:
                self._json(409, {"error": "report_unavailable"})
        elif path and path.startswith("/api/campaign/"):
            parts = path.split("/")
            if (
                len(parts) != 5
                or parts[4] not in {"status", "report", "report.md"}
                or not campaign.CAMPAIGN_ID_PATTERN.fullmatch(parts[3])
            ):
                self._json(404, {"error": "not_found"})
                return
            try:
                result = campaign.publish_campaign(self.server.store, parts[3])
                if parts[4] == "report.md":
                    markdown = (
                        self.server.store.root / parts[3] / "report.md"
                    ).read_bytes()
                    self._send(200, markdown, "text/markdown; charset=utf-8")
                else:
                    self._json(
                        200, result["status"] if parts[4] == "status" else result
                    )
            except Exception:
                self._json(404, {"error": "report_unavailable"})
        else:
            self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        path = self._path()
        if not self._identity() or not self._origin():
            self._json(403, {"error": "forbidden"})
            return
        body = self._body()
        if body is None:
            self._json(400, {"error": "invalid_request"})
            return
        if path == "/api/login":
            if (
                set(body) != {"token"}
                or not isinstance(body["token"], str)
                or not hmac.compare_digest(body["token"], self.server.secret)
            ):
                self._json(401, {"error": "unauthorized"})
                return
            session, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            with self.server.session_lock:
                self.server.sessions[session] = (
                    self.server.login,
                    csrf,
                    time.monotonic() + _SESSION_SECONDS,
                )
            self._send(
                200,
                queue.canonical({"authenticated": True}),
                cookie=(
                    f"__Secure-vera_m3={session}; Path={MOUNT}; Secure; HttpOnly; "
                    f"SameSite=Strict; Max-Age={_SESSION_SECONDS}"
                ),
            )
            return
        sess = self._session()
        if sess is None or not hmac.compare_digest(
            self.headers.get("X-VERA-CSRF", ""), sess[1]
        ):
            self._json(403, {"error": "forbidden"})
            return
        parts = path.split("/") if path else []
        if (
            len(parts) != 5
            or parts[1:3] != ["api", "campaign"]
            or parts[4] != "control"
            or not campaign.CAMPAIGN_ID_PATTERN.fullmatch(parts[3])
            or set(body) != {"action", "commandId"}
        ):
            self._json(404, {"error": "not_found"})
            return
        try:
            actor = "tailnet-" + hashlib.sha256(sess[0].encode()).hexdigest()[:16]
            result = campaign.control_campaign(
                self.server.store,
                parts[3],
                action=body["action"],
                command_id=body["commandId"],
                actor=actor,
                authorized=True,
            )
            self._json(200, result)
        except Exception:
            self._json(409, {"error": "control_refused"})


_HTML = (
    files("vera_timeline_agent")
    .joinpath("assets/resolve_campaign_monitor.html")
    .read_text(encoding="utf-8")
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Loopback-only, opt-in M3 monitor")
    p.add_argument("--root", type=Path, default=queue.DEFAULT_ROOT)
    p.add_argument("--host", help="exact tailnet HTTPS hostname (without scheme)")
    p.add_argument("--operator", help="exact permitted Tailscale-User-Login")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    sub = p.add_subparsers(dest="action", required=True)
    for action in (
        "init-secret",
        "show-secret",
        "serve",
        "install-launchd",
        "install-tailscale-path",
    ):
        sub.add_parser(action)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        store = queue.Store(args.root)
        if args.action == "init-secret":
            provision_secret(store)
            print("Private monitor access token provisioned (not printed).")
        elif args.action == "show-secret":
            print(read_secret(store))
        elif args.action == "install-tailscale-path":
            read_secret(store)
            configure_tailscale_path(args.port)
            print("Private monitor path added; existing '/' route verified unchanged.")
        else:
            if not args.host or not args.operator or not _HOST.fullmatch(args.host):
                raise queue.QueueError("--host and --operator are required")
            if args.action == "install-launchd":
                install_agent(store, args.host, args.operator, args.port)
                print("Separate opt-in monitor LaunchAgent installed.")
            else:
                with Monitor(store, args.host, args.operator, args.port) as server:
                    server.serve_forever(poll_interval=0.3)
        return 0
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"monitor refused: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
