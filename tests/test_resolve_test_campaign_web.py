"""HTTP privacy/auth/CSRF and additive Tailscale Serve invariants (no Resolve)."""

from __future__ import annotations

import http.client
import json
import plistlib
import socket
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_resolve_test_campaign import example_campaign, write_campaign
from vera_timeline_agent import resolve_test_campaign as campaign
from vera_timeline_agent import resolve_test_campaign_web as web
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent import resolve_test_queue_native as native

HOST = "example.tail123.ts.net"
LOGIN = "producer@example.com"


@pytest.fixture
def web_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(native, "preflight", lambda _plan: {})
    store = queue.Store(tmp_path / "queue")
    plan = example_campaign(tmp_path, 2)
    cid = campaign.enqueue_campaign(store, write_campaign(tmp_path, plan))
    web.provision_secret(store)
    token = web.read_secret(store)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    monitor = web.Monitor(store, HOST, LOGIN, port)
    thread = threading.Thread(target=monitor.serve_forever, daemon=True)
    thread.start()

    def request(
        method: str,
        url: str,
        *,
        data: object | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps(data).encode() if data is not None else None
        prepared = {"Host": HOST, "Tailscale-User-Login": LOGIN}
        if data is not None:
            prepared.update(
                {"Content-Type": "application/json", "Origin": "https://" + HOST}
            )
        prepared.update(headers or {})
        try:
            conn.request(method, url, body, headers=prepared)
            response = conn.getresponse()
            payload = response.read()
            return response.status, dict(response.getheaders()), payload
        finally:
            conn.close()

    try:
        yield SimpleNamespace(
            store=store, cid=cid, token=token, monitor=monitor, request=request
        )
    finally:
        monitor.shutdown()
        monitor.server_close()
        thread.join(timeout=3)


def test_authenticated_get_and_audited_idempotent_post(web_setup: Any) -> None:
    request, cid = web_setup.request, web_setup.cid
    base = f"/resolve-tests/api/campaign/{cid}"
    assert request("GET", "/")[0] == 200  # login page only, no status/secret
    assert request("GET", "/api/campaigns")[0] == 401
    assert request("POST", "/api/login", data={"token": "invalid"})[0] == 401
    code, headers, body = request(
        "POST", "/resolve-tests/api/login", data={"token": web_setup.token}
    )
    assert code == 200 and b"authenticated" in body
    cookie = headers["Set-Cookie"].split(";", 1)[0]
    assert "Secure; HttpOnly; SameSite=Strict" in headers["Set-Cookie"]
    assert web_setup.token.encode() not in body
    auth = {"Cookie": cookie}
    assert request("GET", "/api/campaigns", headers=auth)[0] == 200
    assert (
        request(
            "GET",
            "/api/campaigns",
            headers={**auth, "Tailscale-User-Login": "other@example.com"},
        )[0]
        == 401
    )
    status, _, report_bytes = request("GET", base + "/report", headers=auth)
    assert status == 200
    report = json.loads(report_bytes)
    assert report["status"]["campaignId"] == cid
    assert report["status"]["totalTrials"] == 2
    assert web_setup.token not in report_bytes.decode()
    code, _, session_bytes = request("GET", "/api/session", headers=auth)
    assert code == 200
    csrf = json.loads(session_bytes)["csrf"]
    authorized = {**auth, "X-VERA-CSRF": csrf}
    command = {"action": "pause", "commandId": "monitor-pause-1"}
    assert request("POST", base + "/control", data=command, headers=auth)[0] == 403
    assert (
        request(
            "POST",
            base + "/control",
            data=command,
            headers={**authorized, "Origin": "https://evil.example"},
        )[0]
        == 403
    )
    assert (
        request(
            "POST",
            base + "/control",
            data=command,
            headers={**authorized, "Sec-Fetch-Site": "cross-site"},
        )[0]
        == 403
    )
    code, _, answer = request(
        "POST", base + "/control", data=command, headers=authorized
    )
    assert code == 200 and json.loads(answer)["outcome"] == "accepted"
    code, _, answer = request(
        "POST", base + "/control", data=command, headers=authorized
    )
    assert code == 200 and json.loads(answer)["replayed"] is True
    assert (
        request(
            "POST",
            base + "/control",
            data={"action": "cancel", "commandId": command["commandId"]},
            headers=authorized,
        )[0]
        == 409
    )
    assert (
        request(
            "POST",
            base + "/control",
            data={"action": "resume", "commandId": "monitor-resume-2"},
            headers=authorized,
        )[0]
        == 200
    )
    code, _, md = request("GET", base + "/report.md", headers=auth)
    assert code == 200 and b"Native campaign" in md
    with web_setup.store.connect() as db:
        commands = db.execute(
            "SELECT action,actor FROM campaign_commands ORDER BY at"
        ).fetchall()
    assert [row[0] for row in commands] == ["pause", "resume"]
    assert all(row[1].startswith("tailnet-") for row in commands)


def test_forged_headers_and_malformed_requests_fail_closed(web_setup: Any) -> None:
    request, cid = web_setup.request, web_setup.cid
    path = f"/api/campaign/{cid}/control"
    mutation = {"action": "cancel", "commandId": "evil-1"}
    assert request("POST", path, data=mutation)[0] == 403
    assert (
        request(
            "GET", "/api/campaigns", headers={"Tailscale-User-Login": "bad@example.com"}
        )[0]
        == 401
    )
    assert (
        request(
            "POST",
            "/api/login",
            data={"token": web_setup.token},
            headers={"Host": "evil.example"},
        )[0]
        == 403
    )
    assert (
        request(
            "POST",
            "/api/login",
            data={"token": web_setup.token},
            headers={"Tailscale-User-Login": "bad@example.com"},
        )[0]
        == 403
    )
    assert (
        request(
            "POST",
            "/api/login",
            data={"token": web_setup.token},
            headers={"Origin": "https://evil.example"},
        )[0]
        == 403
    )
    assert request("GET", f"/api/campaign/{cid}/../report")[0] == 401
    with web_setup.store.connect() as db:
        assert db.execute("SELECT count(*) FROM campaign_commands").fetchone()[0] == 0
        assert (
            db.execute("SELECT state FROM campaigns WHERE id=?", (cid,)).fetchone()[0]
            == "queued"
        )


def test_monitor_lifetime_is_independent_of_queue(web_setup: Any) -> None:
    # Server does not call parent.start or a queue worker. Shutting it down
    # does not remove/mark terminal a queued campaign or its immutable data.
    report = campaign.publish_campaign(web_setup.store, web_setup.cid)
    assert report["status"]["state"] == "queued"
    assert (web_setup.store.root / web_setup.cid / "plan.json").is_file()
    assert campaign.campaign_agent_plist(web_setup.store.root, "/venv/python")
    worker = plistlib.loads(
        campaign.campaign_agent_plist(web_setup.store.root, "/venv/python")
    )
    monitor = plistlib.loads(
        web.agent_plist(web_setup.store, HOST, LOGIN, 51762, "/venv/python")
    )
    original = plistlib.loads(queue.agent_plist(web_setup.store.root, "/venv/python"))
    assert len({worker["Label"], monitor["Label"], original["Label"]}) == 3
    assert worker["ProgramArguments"][-2:] == ["worker", "once"]
    assert monitor["ProgramArguments"][-1] == "serve"
    assert all("secret" not in str(x).lower() for x in monitor["ProgramArguments"])
    web_setup.monitor.shutdown()
    assert (
        campaign.publish_campaign(web_setup.store, web_setup.cid)["status"]["state"]
        == "queued"
    )


def test_private_secret_never_rotates_and_rejects_symlinks(tmp_path: Path) -> None:
    store = queue.Store(tmp_path / "queue")
    web.provision_secret(store)
    token = web.read_secret(store)
    web.provision_secret(store)
    assert token == web.read_secret(store)
    path = web.secret_path(store)
    path.chmod(0o644)
    with pytest.raises(queue.QueueError, match="private"):
        web.read_secret(store)
    path.unlink()
    path.symlink_to(tmp_path / "other")
    with pytest.raises(queue.QueueError, match="symlink"):
        web.provision_secret(store)


def test_tailscale_additive_path_preserves_existing_dashboard() -> None:
    host = "example.tail123.ts.net:443"
    config: dict[str, Any] = {
        "TCP": {"443": {"HTTPS": True}},
        "Web": {host: {"Handlers": {"/": {"Proxy": "http://127.0.0.1:51761"}}}},
    }
    commands: list[list[str]] = []

    def runner(args: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        if args == ["tailscale", "serve", "status", "--json"]:
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps(config))
        assert args == [
            "tailscale",
            "serve",
            "--bg",
            "--set-path=/resolve-tests/",
            "http://127.0.0.1:51762",
        ]
        config["Web"][host]["Handlers"]["/resolve-tests/"] = {
            "Proxy": "http://127.0.0.1:51762"
        }
        return subprocess.CompletedProcess(args, 0, stdout="")

    web.configure_tailscale_path(51762, runner=runner)
    assert config["Web"][host]["Handlers"]["/"] == {"Proxy": "http://127.0.0.1:51761"}
    assert len(commands) == 3
    with pytest.raises(queue.QueueError, match="already exists"):
        web.configure_tailscale_path(51762, runner=runner)
    assert len(commands) == 4  # only status; never overwrite a mounted path
    config["AllowFunnel"] = {host: True}
    with pytest.raises(queue.QueueError, match="Funnel"):
        web.configure_tailscale_path(51762, runner=runner)


def test_tailscale_refuses_absent_root_and_detects_root_damage() -> None:
    host = "node.tail123.ts.net:443"
    config = {"Web": {host: {"Handlers": {}}}}

    def runner(args: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        if args[-2:] == ["status", "--json"]:
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps(config))
        config["Web"][host]["Handlers"]["/"] = {"Proxy": "http://127.0.0.1:bad"}
        return subprocess.CompletedProcess(args, 0, stdout="")

    with pytest.raises(queue.QueueError, match="root"):
        web.configure_tailscale_path(51762, runner=runner)
    config["Web"][host]["Handlers"]["/"] = {"Proxy": "http://127.0.0.1:51761"}
    with pytest.raises(queue.QueueError, match="conflicts"):
        web.configure_tailscale_path(51761, runner=runner)
    with pytest.raises(queue.QueueError, match="CRITICAL"):
        web.configure_tailscale_path(51762, runner=runner)
