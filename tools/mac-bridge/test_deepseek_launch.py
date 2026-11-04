"""Run without the MCP dependency: python3 -m unittest test_deepseek_launch -v."""

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import deepseek_launch as dl

FAKE_GH = r"""#!/bin/sh
printf '%s\n' "$*" >> "$GH_LOG"
if [ "$1 $2" = "issue view" ]; then cat "$GH_VIEW"; exit 0; fi
if [ "$1 $2" = "issue comment" ]; then
  cat > "$GH_BODY"; echo "https://github.com/x/y/issues/5#issuecomment-1"; exit 0
fi
exit 0
"""


class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        gh = self.dir / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        self.log, self.view, self.body = (
            self.dir / "log",
            self.dir / "view.json",
            self.dir / "body",
        )
        self.set_view(
            {
                "state": "OPEN",
                "labels": [
                    {"name": "deepseek-failed"},
                    {"name": "deepseek"},
                    {"name": "type:implementation"},
                ],
                "url": "https://github.com/x/y/issues/5",
                "comments": [],
            }
        )
        env = {
            "VERA_BRIDGE_PATH": str(self.dir),
            "GH_LOG": str(self.log),
            "GH_VIEW": str(self.view),
            "GH_BODY": str(self.body),
        }
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        # Fake gh needs these variables; the real env filter would drop them.
        keep = patch.object(
            dl, "_env", lambda: {**os.environ, "PATH": f"{self.dir}:/usr/bin:/bin"}
        )
        keep.start()
        self.addCleanup(keep.stop)

    def set_view(self, data):
        self.view.write_text(json.dumps(data))

    def test_launch_posts_marked_brief_and_relabels(self):
        result = dl.launch(
            "research", "#5", "Implement X in file Y and run vitest for Z. " * 2, "pro"
        )
        self.assertEqual(result["status"], "launched")
        self.assertEqual(result["repo"], "mbelinkie/vera-research-video-clips")
        body = self.body.read_text()
        self.assertTrue(body.startswith(dl.BRIEF_MARK))
        log = self.log.read_text()
        self.assertIn("--remove-label deepseek", log)
        self.assertIn("--add-label deepseek-pro", log)
        self.assertNotIn("sh -c", log)

    def test_rejects_unknown_repo_model_short_brief_and_running(self):
        with self.assertRaises(dl.LaunchError):
            dl.launch("someone/else", 5, "x" * 100)
        with self.assertRaises(dl.LaunchError):
            dl.launch("timeline", 5, "x" * 100, "gpt")
        with self.assertRaises(dl.LaunchError):
            dl.launch("timeline", 5, "too short")
        with self.assertRaises(dl.LaunchError):
            dl.launch("timeline", 0, "x" * 100)
        self.set_view(
            {"state": "OPEN", "labels": [{"name": "deepseek-running"}], "url": "u"}
        )
        with self.assertRaises(dl.LaunchError):
            dl.launch("timeline", 5, "x" * 100)
        self.set_view({"state": "CLOSED", "labels": [], "url": "u"})
        with self.assertRaises(dl.LaunchError):
            dl.launch("timeline", 5, "x" * 100)

    def test_rejects_design_and_excluded_issues(self):
        self.set_view(
            {"state": "OPEN", "labels": [{"name": "type:design"}], "url": "u"}
        )
        with self.assertRaises(dl.LaunchError):
            dl.launch("timeline", 5, "x" * 100)
        labels = [{"name": "type:bug"}, {"name": "deepseek-excluded"}]
        self.set_view({"state": "OPEN", "labels": labels, "url": "u"})
        with self.assertRaises(dl.LaunchError):
            dl.launch("timeline", 5, "x" * 100)

    def test_status(self):
        self.set_view(
            {
                "state": "OPEN",
                "url": "u",
                "labels": [{"name": "deepseek-done"}, {"name": "bug"}],
                "comments": [
                    {"body": dl.STATUS_MARK + "\nstarted"},
                    {"body": dl.STATUS_MARK + "\nDraft PR ready: link"},
                ],
            }
        )
        result = dl.status("timeline", 5)
        self.assertEqual(result["deepseek"], "draft-ready")
        self.assertEqual(result["labels"], ["deepseek-done"])
        self.assertEqual(result["latest_update"], "Draft PR ready: link")


if __name__ == "__main__":
    unittest.main()
