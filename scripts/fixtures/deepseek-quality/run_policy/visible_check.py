import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

FIXTURE_ROOT = Path(__file__).resolve().parents[1]
INVOKE = FIXTURE_ROOT / "invoke.mjs"
NODE = shutil.which("node")


def evaluate(*payloads):
    if NODE is None:
        raise RuntimeError("node is required for this synthetic fixture")
    with tempfile.TemporaryDirectory(prefix="deepseek-quality-visible-") as temp:
        input_path = Path(temp) / "inputs.json"
        input_path.write_text(json.dumps(list(payloads)), encoding="utf-8")
        result = subprocess.run(
            [
                NODE,
                str(INVOKE),
                str(input_path),
                str(FIXTURE_ROOT / "run_policy" / "target.ts"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode != 0:
        raise AssertionError("invoke.mjs returned a wrapper error")
    return json.loads(result.stdout)


def payload(**changes):
    expected = {
        "repository": "sample/project",
        "workflow_head": "a" * 40,
        "not_before": "2030-01-02T03:04:05Z",
    }
    actual = {
        "repository": "sample/project",
        "workflow_head": "a" * 40,
        "started_at": "2030-01-02T03:05:00Z",
        "run_id": 731,
        "url": "https://github.com/sample/project/actions/runs/731",
        "conclusion": "success",
    }
    now = "2030-01-02T03:10:00Z"
    actual.update(changes.get("actual", {}))
    expected.update(changes.get("expected", {}))
    return {"expected": expected, "actual": actual, "now": now}


class RunPolicyCheck(unittest.TestCase):
    def test_valid_run_is_accepted(self):
        self.assertEqual(
            evaluate(payload()),
            [{"ok": True, "reason": "ok"}],
        )

    def test_wrong_workflow_head_is_rejected(self):
        self.assertEqual(
            evaluate(payload(actual={"workflow_head": "b" * 40})),
            [{"ok": False, "reason": "workflow_head_mismatch"}],
        )

    def test_run_before_window_is_rejected(self):
        self.assertEqual(
            evaluate(payload(actual={"started_at": "2030-01-02T03:00:00Z"})),
            [{"ok": False, "reason": "started_before_window"}],
        )


if __name__ == "__main__":
    unittest.main()
