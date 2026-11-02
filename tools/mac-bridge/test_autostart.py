"""Pure tests for macOS startup staging. Never actually load a LaunchAgent."""
import contextlib
import io
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch

import autostart as mod


class LaunchAgentTests(unittest.TestCase):
    def test_plist_only_login_agent_no_runtime_secret(self):
        data = plistlib.loads(mod.plist_data())
        self.assertEqual(data["Label"], "com.vera.mac-bridge")
        self.assertEqual(data["LimitLoadToSessionType"], "Aqua")
        self.assertTrue(data["RunAtLoad"])
        self.assertEqual(data["KeepAlive"], {"SuccessfulExit": False})
        self.assertNotIn("EnvironmentVariables", data)
        self.assertNotIn("sk-", mod.plist_data().decode())
        self.assertNotIn("CONTROL_PLANE_API_KEY", mod.plist_data().decode())

    def test_wrapper_fetches_keychain_not_config(self):
        text = mod.wrapper_source().decode()
        self.assertIn("security find-generic-password", text)
        self.assertIn("export CONTROL_PLANE_API_KEY", text)
        self.assertIn("exec ", text)
        self.assertIn("vera-shell", text)
        self.assertNotIn("sk-", text)

    def test_prepare_is_idempotent_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            binary_source = home / "Downloads" / "tunnel-client"
            binary_source.parent.mkdir()
            binary_source.write_bytes(b"binary proof")
            binary_source.chmod(0o700)
            root = home / "bridge"
            binary_dest = root / "bin" / "tunnel-client"
            wrapper = root / "run-tunnel.zsh"
            plist = home / "Library" / "LaunchAgents" / "com.vera.mac-bridge.plist"
            profile = home / ".config" / "tunnel-client" / "vera-shell.yaml"
            profile.parent.mkdir(parents=True)
            profile.write_text("placeholder: true")
            with patch.multiple(mod, HOME=home, ROOT=root, BINARY_SOURCE=binary_source,
                                BINARY_DEST=binary_dest, WRAPPER=wrapper, PLIST=plist):
                # autostart.py itself and its server.py reside in the repository.
                with contextlib.redirect_stdout(io.StringIO()):
                    mod.prepare()
                    mod.prepare()
                self.assertEqual(binary_dest.read_bytes(), b"binary proof")
                self.assertTrue(plist.is_file())
                self.assertEqual(plist.stat().st_mode & 0o777, 0o600)
                self.assertEqual(wrapper.stat().st_mode & 0o777, 0o700)
                self.assertEqual(plistlib.loads(plist.read_bytes())["ProgramArguments"][-1], str(wrapper))
                wrapper.write_text("not ours")
                with self.assertRaisesRegex(RuntimeError, "Refusing to overwrite"):
                    mod.prepare()

    def test_symlink_dest_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = root / "real"
            target.write_text("something")
            link = root / "link"
            link.symlink_to(target)
            with self.assertRaisesRegex(RuntimeError, "symlink"):
                mod._safe_write(link, b"new", 0o600)


if __name__ == "__main__":
    unittest.main()
