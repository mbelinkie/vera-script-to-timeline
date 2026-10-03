"""Verify one-shot disarming even when a native action raises after mutation."""

import ast
import hashlib
import json
import tempfile
from pathlib import Path


def demo():
    source = Path(__file__).with_name("VERA Issue 141 Observation.py").read_text()
    for mode in ("success", "refusal", "throw"):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            probe = root / "fake_probe.py"
            probe.write_text(
                "import json\nfrom pathlib import Path\n"
                "def run(resolve, config):\n"
                "    root=Path(__file__).parent\n"
                "    current=json.loads((root/'vera-issue-141-observation.json')"
                ".read_text())\n"
                "    assert config['action']=='r4-reprepare'\n"
                "    assert current['action']=='observe'\n"
                "    (root/'invoked.json').write_text(json.dumps(config))\n"
                + (
                    "    raise RuntimeError('failed after mutation')\n"
                    if mode == "throw"
                    else "    return {'status': '" + mode + "'}\n"
                )
            )
            config = {
                "action": "r4-reprepare",
                "probePath": str(probe),
                "probeSha256": hashlib.sha256(probe.read_bytes()).hexdigest(),
            }
            path = root / "vera-issue-141-observation.json"
            path.write_text(json.dumps(config))
            tree = ast.parse(source)
            for node in tree.body:
                if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "PLUGIN_ROOT"
                    for target in node.targets
                ):
                    node.value = ast.Call(
                        func=ast.Name(id="Path", ctx=ast.Load()),
                        args=[ast.Constant(value=str(root))],
                        keywords=[],
                    )
            ast.fix_missing_locations(tree)
            exec(compile(tree, "one-shot-launcher", "exec"), {"resolve": object()})
            assert json.loads(path.read_text())["action"] == "observe"
            assert json.loads((root / "invoked.json").read_text()) == config
            result = next(root.glob("vera-issue-141-observation-result-*.json"))
            assert json.loads(result.read_text())["status"] == (
                "launcher-failed" if mode == "throw" else mode
            )
    print("One-shot launcher checks passed")


if __name__ == "__main__":
    demo()
