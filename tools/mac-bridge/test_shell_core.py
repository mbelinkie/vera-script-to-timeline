"""Run without the MCP dependency: python3 -m unittest discover -p 'test_*.py'."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import shell_core as core


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        if not Path(core.SHELL_BIN).exists():
            sh = patch.object(core, "SHELL_BIN", "/bin/sh")
            sh.start()
            self.addCleanup(sh.stop)
        self.config = patch.dict('os.environ', {'VERA_WORKSPACE': str(self.root)})
        self.config.start()
        self.addCleanup(self.config.stop)

    def test_valid(self):
        self.assertEqual(core.validate('git status --short', 'vera', 10), self.root.resolve())

    def test_invalid_scope_and_inputs(self):
        for command, cwd, seconds in [('', 'vera', 2), ('echo ok\nrm -rf ~', 'vera', 2),
                                      ('echo ok', '/tmp', 2), ('echo ok', 'vera', 0),
                                      ('echo ok', 'vera', 120), ('x' * 241, 'vera', 2),
                                      ('echo ok', 'vera', True)]:
            with self.subTest(command=command[:24], cwd=cwd, seconds=seconds):
                with self.assertRaises(ValueError):
                    core.validate(command, cwd, seconds)

    @patch.object(core, 'audit')
    @patch.object(core, 'execute_bounded')
    @patch.object(core, 'confirm_on_mac', return_value=False)
    def test_local_denial_prevents_execution(self, approval, execute, audit):
        result = core.mac_exec_local('echo hello', 'vera', 5)
        self.assertEqual(result['status'], 'denied')
        execute.assert_not_called()
        approval.assert_called_once()

    @patch.object(core, 'audit')
    @patch.object(core, 'execute_bounded', return_value={'status': 'completed', 'exit_code': 0,
                                                         'stdout': 'ok\n', 'stderr': '', 'truncated': False})
    @patch.object(core, 'confirm_on_mac', return_value=True)
    def test_approval_runs_exact_command(self, approval, execute, audit):
        result = core.mac_exec_local('echo ok', 'vera', 5)
        self.assertEqual(result['stdout'], 'ok\n')
        execute.assert_called_once_with('echo ok', self.root.resolve(), 5)

    @patch.object(core, 'audit')
    @patch.object(core, 'execute_bounded')
    @patch.object(core, 'confirm_on_mac')
    def test_invalid_request_cannot_open_approval(self, approval, execute, audit):
        result = core.mac_exec_local('echo x', '../../etc', 5)
        self.assertEqual(result['status'], 'rejected')
        approval.assert_not_called()
        execute.assert_not_called()

    def test_output_bounded(self):
        result = core.execute_bounded('printf hi', self.root, 5)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['stdout'], 'hi')

    def test_timeout(self):
        result = core.execute_bounded('sleep 3', self.root, 1)
        self.assertEqual(result['status'], 'timed_out')

    def test_output_limit(self):
        result = core.execute_bounded('yes abcdef', self.root, 3)
        self.assertEqual(result['status'], 'output_limit')
        self.assertTrue(result['truncated'])
        self.assertLessEqual(len(result['stdout'].encode()), core.MAX_OUTPUT_BYTES)


if __name__ == '__main__':
    unittest.main()
