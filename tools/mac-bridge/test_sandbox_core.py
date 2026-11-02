"""Focused tests for the unprompted OS-enforced workspace tool.

Live probes only run on macOS. Outside paths are disposable test fixtures;
nothing under VERA's real checkout or the bridge's configuration is modified.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import sandbox_core as sb


class PolicyTests(unittest.TestCase):
    def test_policy_is_deny_default_and_has_no_mach_or_network_grants(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname).resolve()
            policy = sb.profile_for(root)
            self.assertIn("(deny default)", policy)
            self.assertIn("(deny network*)", policy)
            self.assertNotIn("(allow network", policy)
            self.assertNotIn("mach-lookup", policy)
            self.assertNotIn("(allow mach", policy)
            self.assertIn(f"(subpath {sb._sbpl_path(root)})", policy)
            self.assertIn('(subpath "/usr/bin")', policy)
            self.assertIn('(subpath "/usr/local/Cellar")', policy)
            self.assertNotIn('(subpath "/usr")', policy)
            self.assertNotIn('(subpath "/Library")', policy)
            self.assertNotIn("/usr/local/etc", policy)
            self.assertNotIn(str(Path.home() / ".ssh"), policy)

    def test_missing_sandbox_refused(self):
        with patch.object(sb, "SANDBOX_BIN", Path("/nonexistent/sandbox-exec")):
            info = sb.workspace_info()
            self.assertFalse(info["available"])

    def test_malformed_command_refused_before_audit(self):
        with patch.object(sb, "audit") as audit:
            for command in ("", "echo hi\nid", "x" * 241, None):
                self.assertEqual(sb.workspace_exec(command)["status"], "rejected")
            for char in ("\u202e", "\u2066", "\u200b", "\u2028"):
                self.assertEqual(
                    sb.workspace_exec(f"echo{char}safe")["status"], "rejected"
                )
            audit.assert_not_called()


@unittest.skipUnless(sys.platform == "darwin", "macOS Seatbelt required")
class LiveSeatbeltTests(unittest.TestCase):
    def setUp(self):
        self.fixture = tempfile.TemporaryDirectory()
        self.addCleanup(self.fixture.cleanup)
        base = Path(self.fixture.name).resolve()
        self.workspace = base / "workspace"
        self.workspace.mkdir(mode=0o700)
        self.outside = base / "outside"
        self.outside.mkdir(mode=0o700)
        self.patch = patch.object(sb, "WORKSPACE_ROOT", self.workspace)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def run_sandbox(self, command, timeout=5):
        return sb._execute_sandboxed(command, self.workspace, timeout)

    def test_basic_echo_and_pwd(self):
        result = self.run_sandbox("pwd")
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["stdout"].strip(), str(self.workspace))
        self.assertTrue(sb.workspace_info()["available"])

    def test_workspace_write_succeeds(self):
        result = self.run_sandbox("printf ok > allowed.txt")
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual((self.workspace / "allowed.txt").read_text(), "ok")

    def test_git_status_works_but_git_metadata_is_read_only(self):
        subprocess.run(
            ["/usr/bin/git", "init", "--quiet", str(self.workspace)], check=True
        )
        config = self.workspace / ".git" / "config"
        original = config.read_bytes()
        result = self.run_sandbox("git status --short --branch")
        self.assertEqual(result["status"], "completed", result)
        write = self.run_sandbox(
            "printf '\\n[core]\\nfsmonitor = echo bad' >> .git/config"
        )
        self.assertNotEqual(write["exit_code"], 0, write)
        self.assertEqual(config.read_bytes(), original)

    def test_background_child_is_killed_when_shell_exits(self):
        result = self.run_sandbox(
            "(sleep 0.3; printf x > background-marker) >/dev/null 2>&1 &"
        )
        self.assertEqual(result["status"], "completed", result)
        time.sleep(0.5)
        self.assertFalse((self.workspace / "background-marker").exists())

    def test_cannot_write_sibling_directory(self):
        target = self.outside / "should-not-exist"
        result = self.run_sandbox(f"printf blocked > {sb._sbpl_path(target)}")
        self.assertNotEqual(result["exit_code"], 0, result)
        self.assertFalse(target.exists())

    def test_cannot_read_sibling_sentinel(self):
        sentinel = self.outside / "fake-secret"
        sentinel.write_text("DO_NOT_DISCLOSE_TEST_SENTINEL", encoding="utf-8")
        result = self.run_sandbox(f"cat {sb._sbpl_path(sentinel)}")
        self.assertNotEqual(result["exit_code"], 0, result)
        self.assertNotIn("DO_NOT_DISCLOSE_TEST_SENTINEL", result["stdout"])

    def test_symlink_escape_cannot_write(self):
        (self.workspace / "escape").symlink_to(self.outside, target_is_directory=True)
        target = self.outside / "via-symlink"
        result = self.run_sandbox("printf nope > escape/via-symlink")
        self.assertNotEqual(result["exit_code"], 0, result)
        self.assertFalse(target.exists())

    def test_child_process_inherits_boundaries(self):
        target = self.outside / "from-child"
        result = self.run_sandbox(
            f"/bin/zsh -f -c 'printf nope > {sb._sbpl_path(target)}'"
        )
        self.assertNotEqual(result["exit_code"], 0, result)
        self.assertFalse(target.exists())

    def test_timeout_kills_process_group(self):
        result = self.run_sandbox("sleep 3", timeout=1)
        self.assertEqual(result["status"], "timed_out", result)

    def test_no_inherited_tunnel_key(self):
        with patch.dict(os.environ, {"CONTROL_PLANE_API_KEY": "TEST_KEY_NEVER_OUTPUT"}):
            result = self.run_sandbox('printf "%s" "$CONTROL_PLANE_API_KEY"')
        self.assertEqual(result["stdout"], "")
        self.assertEqual(result["exit_code"], 0)

    def test_loopback_network_is_denied(self):
        result = self.run_sandbox(
            "/usr/bin/curl -sS --connect-timeout 1 http://127.0.0.1:1"
        )
        self.assertNotEqual(result["exit_code"], 0, result)
        # A refusal alone is insufficient; require the kernel denial evidence.
        self.assertIn("not permitted", result["stderr"].lower(), result)


@unittest.skipUnless(sys.platform == "darwin", "macOS Seatbelt required")
class DispatchSafetyTests(LiveSeatbeltTests):
    def test_audit_failure_prevents_execution(self):
        with (
            patch.object(sb, "audit", return_value=False),
            patch.object(sb, "_execute_sandboxed") as runner,
        ):
            self.assertEqual(sb.workspace_exec("pwd")["status"], "audit_unavailable")
            runner.assert_not_called()

    def test_final_audit_failure_is_reported_after_execution(self):
        completed = {
            "status": "completed",
            "exit_code": 0,
            "stdout": "ok",
            "stderr": "",
            "truncated": False,
        }
        with (
            patch.object(sb, "audit", side_effect=[True, False]),
            patch.object(sb, "_execute_sandboxed", return_value=completed),
        ):
            result = sb.workspace_exec("pwd")
        self.assertEqual(result["status"], "audit_incomplete")
        self.assertEqual(result["execution_status"], "completed")

    def test_concurrent_command_returns_busy(self):
        self.assertTrue(sb._workspace_lock.acquire(blocking=False))
        try:
            with patch.object(sb, "_execute_sandboxed") as runner:
                result = sb.workspace_exec("pwd")
                self.assertEqual(result["status"], "busy")
                runner.assert_not_called()
        finally:
            sb._workspace_lock.release()

    def test_symlink_root_is_not_accepted(self):
        symlink = self.outside / "redirected"
        symlink.symlink_to(self.workspace, target_is_directory=True)
        with patch.object(sb, "WORKSPACE_ROOT", symlink):
            self.assertFalse(sb.workspace_info()["available"])

    def test_child_output_is_bounded(self):
        result = self.run_sandbox("/usr/bin/yes abcdef", timeout=3)
        self.assertEqual(result["status"], "output_limit", result)
        self.assertTrue(result["truncated"])
        self.assertLessEqual(len(result["stdout"].encode()), sb.MAX_OUTPUT_BYTES)


if __name__ == "__main__":
    unittest.main()
