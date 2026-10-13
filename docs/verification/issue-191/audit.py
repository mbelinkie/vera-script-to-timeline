"""Assert the issue's frozen boundary and retain exact source/runtime pins."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args]).decode().strip()


root = Path.cwd()
directory = root / "docs/verification/issue-191"
frozen = json.loads((directory / "frozen-source-pins.json").read_text())
integration_baseline = "4e31565f88e71e0c1d1cd1be5e52c34df2819347"
subprocess.check_call(
    ["git", "merge-base", "--is-ancestor", integration_baseline, "HEAD"]
)
for name, pin in frozen["files"].items():
    assert sha((root / name).read_bytes()) == pin, name
    original = subprocess.check_output(["git", "show", frozen["baseline"] + ":" + name])
    assert sha(original) == pin, name

allowed = {
    "docs/plans/issue-191-selected-phrase-proof.md",
    "packages/contracts/src/issue-189-v2-omission.ts",
    "packages/contracts/src/issue-189-v2-replacement.ts",
    "packages/contracts/src/issue-191-proof-cli.ts",
    "packages/contracts/test/issue-191-omission.test.ts",
    "python/vera_timeline_agent/roundtrip_v2_audio.py",
    "python/vera_timeline_agent/roundtrip_v2_narration.py",
    "tests/test_issue191_audio.py",
    "tests/test_issue191_narration.py",
}
for line in git("diff", "--name-status", integration_baseline).splitlines():
    kind, name = line.split("\t")
    assert kind == "A" and (
        name in allowed or name.startswith("docs/verification/issue-191/")
    ), line
assert not git("diff", "--name-only"), "Uncommitted tracked changes"

source = sorted(name for name in allowed if not name.startswith("docs/"))
lock = json.loads((root / "package-lock.json").read_text())
installed_count = 0
unsupported_optional = []
for name, metadata in lock["packages"].items():
    if name.startswith("node_modules/") and not metadata.get("link"):
        if not (root / name / "package.json").exists():
            assert metadata.get("optional") and (
                (metadata.get("os") and "darwin" not in metadata["os"])
                or (metadata.get("cpu") and "x64" not in metadata["cpu"])
            ), name
            unsupported_optional.append(name)
            continue
        installed = json.loads((root / name / "package.json").read_text())
        assert installed["version"] == metadata["version"], name
        installed_count += 1
for name, version in json.loads((root / "package.json").read_text())[
    "devDependencies"
].items():
    installed = json.loads((root / "node_modules" / name / "package.json").read_text())
    assert (
        installed["version"]
        == version
        == lock["packages"]["node_modules/" + name]["version"]
    ), name

node = Path(
    "/Users/matthewbelinkie/.local/share/vera/toolchains/node-v24.19.0-darwin-x64/bin/node"
)
node_version = subprocess.check_output([str(node), "--version"]).decode().strip()
assert node_version == "v24.19.0"
result = {
    "baseline": frozen["baseline"],
    "integrationBaseline": integration_baseline,
    "sourceCommit": git("rev-parse", "HEAD"),
    "frozenFileCount": len(frozen["files"]),
    "frozenAndTrackedBoundary": "passed",
    "sourceHashes": {name: sha((root / name).read_bytes()) for name in source},
    "nodeVersion": node_version,
    "nodeBinaryHash": sha(node.read_bytes()),
    "pythonVersion": sys.version.split()[0],
    "pythonBinaryHash": sha(Path(sys.executable).resolve().read_bytes()),
    "packageLockHash": sha((root / "package-lock.json").read_bytes()),
    "uvLockHash": sha((root / "uv.lock").read_bytes()),
    "rootDevDependencyVersionsMatchLock": True,
    "installedLockPackageCount": installed_count,
    "unsupportedOptionalPackageCount": len(unsupported_optional),
}
print(json.dumps(result, indent=2) + "\n")
