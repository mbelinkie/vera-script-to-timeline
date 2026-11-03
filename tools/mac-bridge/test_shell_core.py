"""Run without the MCP dependency: python3 -m unittest discover -p 'test_*.py'."""

import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import shell_core as core


class ValidationTests(unittest.TestCase):
    def setUp(self):
        core._trusted_until = 0.0
        self.addCleanup(lambda: setattr(core, "_trusted_until", 0.0))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        if not Path(core.SHELL_BIN).exists():
            sh = patch.object(core, "SHELL_BIN", "/bin/sh")
            sh.start()
            self.addCleanup(sh.stop)
        self.config = patch.dict("os.environ", {"VERA_WORKSPACE": str(self.root)})
        self.config.start()
        self.addCleanup(self.config.stop)

    def test_valid(self):
        self.assertEqual(
            core.validate("git status --short", "vera", 10), self.root.resolve()
        )

    def test_invalid_scope_and_inputs(self):
        for command, cwd, seconds in [
            ("", "vera", 2),
            ("echo ok\nrm -rf ~", "vera", 2),
            ("echo ok", "/tmp", 2),
            ("echo ok", "vera", 0),
            ("echo ok", "vera", 120),
            ("x" * 241, "vera", 2),
            ("echo ok", "vera", True),
        ]:
            with (
                self.subTest(command=command[:24], cwd=cwd, seconds=seconds),
                self.assertRaises(ValueError),
            ):
                core.validate(command, cwd, seconds)

    def test_command_rejects_display_format_controls(self):
        for char in ("\u202e", "\u2066", "\u200b", "\u2028"):
            with self.subTest(char=char), self.assertRaises(ValueError):
                core.validate(f"echo{char}safe", "vera", 5)

    @patch.object(core, "audit")
    @patch.object(core, "execute_bounded")
    @patch.object(core, "confirm_on_mac", return_value=False)
    def test_local_denial_prevents_execution(self, approval, execute, audit):
        result = core.mac_exec_local("echo hello", "vera", 5)
        self.assertEqual(result["status"], "denied")
        execute.assert_not_called()
        approval.assert_called_once()

    @patch.object(core, "audit")
    @patch.object(
        core,
        "execute_bounded",
        return_value={
            "status": "completed",
            "exit_code": 0,
            "stdout": "ok\n",
            "stderr": "",
            "truncated": False,
        },
    )
    @patch.object(core, "confirm_on_mac", return_value=True)
    def test_approval_runs_exact_command(self, approval, execute, audit):
        result = core.mac_exec_local("echo ok", "vera", 5)
        self.assertEqual(result["stdout"], "ok\n")
        execute.assert_called_once_with("echo ok", self.root.resolve(), 5)

    @patch.object(core, "audit")
    @patch.object(core, "execute_bounded")
    @patch.object(core, "confirm_on_mac")
    def test_invalid_request_cannot_open_approval(self, approval, execute, audit):
        result = core.mac_exec_local("echo x", "../../etc", 5)
        self.assertEqual(result["status"], "rejected")
        approval.assert_not_called()
        execute.assert_not_called()

    def test_output_bounded(self):
        result = core.execute_bounded("printf hi", self.root, 5)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["stdout"], "hi")

    def test_timeout(self):
        result = core.execute_bounded("sleep 3", self.root, 1)
        self.assertEqual(result["status"], "timed_out")

    def test_output_limit(self):
        result = core.execute_bounded("yes abcdef", self.root, 3)
        self.assertEqual(result["status"], "output_limit")
        self.assertTrue(result["truncated"])
        self.assertLessEqual(len(result["stdout"].encode()), core.MAX_OUTPUT_BYTES)


class TrustWindowTests(ValidationTests):
    """The window is global to the MCP process; it cannot identify ChatGPT threads."""

    @patch.object(core, "audit")
    def test_reject_invalid_duration_without_dialog(self, audit):
        with patch.object(core.subprocess, "run") as proc:
            for value in (0, 16, 1.0, True, "10"):
                with self.subTest(value=value):
                    self.assertEqual(core.trust_enable(value)["status"], "rejected")
            proc.assert_not_called()
        self.assertEqual(core.trust_status()["status"], "inactive")

    @patch.object(core, "audit")
    @patch.object(core.subprocess, "run")
    def test_local_enable_requires_explicit_positive_response(self, run, audit):
        run.return_value = subprocess.CompletedProcess([], 0, "Deny\n", "")
        self.assertEqual(core.trust_enable(10)["result"], "denied")
        self.assertEqual(core.trust_remaining_seconds(), 0)
        run.return_value = subprocess.CompletedProcess([], 0, "Enable\n", "")
        status = core.trust_enable(10)
        self.assertEqual(status["status"], "active")
        self.assertGreater(status["remaining_seconds"], 0)
        self.assertLessEqual(status["remaining_seconds"], 600)
        self.assertEqual(status["scope"], "all_chats_with_bridge_access")

    @patch.object(core, "audit")
    @patch.object(
        core,
        "execute_bounded",
        return_value={
            "status": "completed",
            "exit_code": 0,
            "stdout": "yes\n",
            "stderr": "",
            "truncated": False,
        },
    )
    @patch.object(core, "confirm_on_mac", return_value=False)
    def test_active_window_skips_per_command_popup(self, confirm, execute, audit):
        core._trusted_until = time.monotonic() + 60
        result = core.mac_exec_local("echo yes", "home", 5)
        self.assertEqual(result["approval_mode"], "temporary_trust")
        self.assertEqual(result["status"], "completed")
        confirm.assert_not_called()
        execute.assert_called_once()

    @patch.object(core, "audit")
    @patch.object(core, "execute_bounded")
    @patch.object(core, "confirm_on_mac", return_value=False)
    def test_expired_window_requires_popup_again(self, confirm, execute, audit):
        core._trusted_until = time.monotonic() - 1
        result = core.mac_exec_local("echo no", "home", 5)
        self.assertEqual(result["status"], "denied")
        confirm.assert_called_once()
        execute.assert_not_called()

    @patch.object(core, "audit")
    def test_revocation_is_immediate(self, audit):
        core._trusted_until = time.monotonic() + 100
        self.assertGreater(core.trust_remaining_seconds(), 0)
        self.assertEqual(core.trust_disable()["status"], "inactive")
        self.assertEqual(core.trust_remaining_seconds(), 0)

    @patch.object(core, "audit")
    @patch.object(core.subprocess, "run")
    def test_declined_extension_cancels_existing_grant(self, run, audit):
        core._trusted_until = time.monotonic() + 100
        run.return_value = subprocess.CompletedProcess([], 0, "Deny\n", "")
        self.assertEqual(core.trust_enable(5)["result"], "denied")
        self.assertEqual(core.trust_remaining_seconds(), 0)

    @patch.object(core, "audit")
    @patch.object(
        core.subprocess, "run", side_effect=subprocess.TimeoutExpired("osascript", 45)
    )
    def test_gui_timeout_fails_closed(self, run, audit):
        self.assertEqual(core.trust_enable(5)["result"], "denied")
        self.assertEqual(core.trust_remaining_seconds(), 0)

    def test_enable_audit_failure_never_exposes_trust(self):
        audit_started = threading.Event()
        finish_audit = threading.Event()
        enable_result = []
        exec_result = []

        def audit(record):
            if (
                record.get("operation") == "trust_enable"
                and record.get("status") == "enabled"
            ):
                audit_started.set()
                finish_audit.wait(timeout=3)
                return False
            return True

        with (
            patch.object(
                core.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, "Enable\n", ""),
            ),
            patch.object(core, "audit", side_effect=audit),
            patch.object(core, "confirm_on_mac", return_value=False) as approval,
            patch.object(core, "execute_bounded") as execute,
        ):
            enabling = threading.Thread(
                target=lambda: enable_result.append(core.trust_enable(5))
            )
            enabling.start()
            self.assertTrue(audit_started.wait(timeout=2))
            running = threading.Thread(
                target=lambda: exec_result.append(
                    core.mac_exec_local("echo denied", "home", 5)
                )
            )
            running.start()
            finish_audit.set()
            enabling.join(timeout=3)
            running.join(timeout=3)

        self.assertFalse(enabling.is_alive())
        self.assertFalse(running.is_alive())
        self.assertEqual(enable_result[0]["result"], "audit_unavailable")
        self.assertEqual(exec_result[0]["status"], "denied")
        self.assertEqual(core.trust_remaining_seconds(), 0)
        approval.assert_called_once()
        execute.assert_not_called()


class ApprovalAppearanceTests(unittest.TestCase):
    def test_run_once_highlighted_but_cancel_denies(self):
        self.assertIn('default button "Deny"', core.APPROVAL_SCRIPT)
        self.assertIn('cancel button "Deny"', core.APPROVAL_SCRIPT)

    def test_trust_dialog_still_defaults_to_deny(self):
        self.assertIn('default button "Deny"', core.TRUST_SCRIPT)
        self.assertIn('cancel button "Deny"', core.TRUST_SCRIPT)


class ReviewSafetyTests(ValidationTests):
    @patch.object(core, "audit")
    def test_bad_command_type_returns_rejection(self, audit):
        result = core.mac_exec_local(None, "home", 5)
        self.assertEqual(result["status"], "rejected")
        self.assertIn("command", result["error"])

    @patch.object(core, "audit", return_value=False)
    @patch.object(core, "execute_bounded")
    @patch.object(core, "confirm_on_mac", return_value=True)
    def test_failed_audit_prevents_shell_execution(self, approval, execute, audit):
        result = core.mac_exec_local("echo safe", "home", 5)
        self.assertEqual(result["status"], "audit_unavailable")
        approval.assert_called_once()
        execute.assert_not_called()

    @patch.object(core, "audit")
    @patch.object(core, "execute_bounded")
    @patch.object(core, "confirm_on_mac")
    def test_concurrent_operation_is_refused(self, approval, execute, audit):
        self.assertTrue(core._exec_lock.acquire(blocking=False))
        try:
            result = core.mac_exec_local("echo safe", "home", 5)
            self.assertEqual(result["status"], "busy")
            approval.assert_not_called()
            execute.assert_not_called()
        finally:
            core._exec_lock.release()

    @patch.object(core, "audit")
    @patch.object(core.subprocess, "run")
    def test_disable_revokes_in_flight_trust_dialog(self, run, audit):
        def approve_after_revocation(*args, **kwargs):
            core.trust_disable()
            return subprocess.CompletedProcess([], 0, "Enable", "")

        run.side_effect = approve_after_revocation
        result = core.trust_enable(5)
        self.assertEqual(result["result"], "canceled")
        self.assertEqual(core.trust_remaining_seconds(), 0)

    @patch.object(core, "audit", side_effect=[True, False])
    @patch.object(
        core,
        "execute_bounded",
        return_value={
            "status": "completed",
            "exit_code": 0,
            "stdout": "changed",
            "stderr": "",
            "truncated": False,
        },
    )
    @patch.object(core, "confirm_on_mac", return_value=True)
    def test_final_audit_failure_is_reported_after_execution(
        self, approval, execute, audit
    ):
        result = core.mac_exec_local("echo changed", "home", 5)
        self.assertEqual(result["status"], "audit_incomplete")
        self.assertEqual(result["execution_status"], "completed")
        execute.assert_called_once()

    @patch.object(core, "audit")
    def test_stale_trust_generation_does_not_launch(self, audit):
        core._trusted_until = time.monotonic() + 60
        stale_generation = core._trust_generation
        core.trust_disable()
        marker = self.root / "should-not-exist"
        result = core.execute_bounded(
            f"touch {marker}",
            self.root,
            5,
            trust_generation=stale_generation,
        )
        self.assertEqual(result["status"], "trust_revoked")
        self.assertFalse(marker.exists())


class WorkspaceConfigurationTests(ValidationTests):
    def test_mac_local_workspace_path_works_without_env(self):
        config = self.root / "workspace"
        config.write_text(str(self.root), encoding="utf-8")
        with (
            patch.dict("os.environ", {"VERA_WORKSPACE": ""}),
            patch.object(core, "WORKSPACE_CONFIG", config),
        ):
            self.assertEqual(core.resolve_cwd("vera"), self.root.resolve())

    def test_workspace_file_cannot_be_symlink(self):
        actual = self.root / "actual"
        actual.write_text(str(self.root), encoding="utf-8")
        link = self.root / "workspace"
        link.symlink_to(actual)
        with (
            patch.dict("os.environ", {"VERA_WORKSPACE": ""}),
            patch.object(core, "WORKSPACE_CONFIG", link),
            self.assertRaises(ValueError),
        ):
            core.resolve_cwd("vera")

    def test_workspace_file_requires_absolute_path(self):
        config = self.root / "workspace"
        config.write_text("relative/path", encoding="utf-8")
        with (
            patch.dict("os.environ", {"VERA_WORKSPACE": ""}),
            patch.object(core, "WORKSPACE_CONFIG", config),
            self.assertRaises(ValueError),
        ):
            core.resolve_cwd("vera")


if __name__ == "__main__":
    unittest.main()
