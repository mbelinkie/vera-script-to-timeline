"""Verify the retained paste plus its unexplained Out change; no Resolve calls."""

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
index = json.loads((HERE / "evidence-index.json").read_text())
for artifact in index["artifacts"]:
    assert (
        hashlib.sha256((HERE / artifact["publishedPath"]).read_bytes()).hexdigest()
        == artifact["publishedSha256"]
    )
spec = importlib.util.spec_from_file_location(
    "copy_checker",
    HERE
    / "sources/editorial-reviewed-sources-20261001T071930/r1-copy-evidence-check.py",
)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
before, after = [
    json.loads(gzip.decompress((HERE / name).read_bytes()))
    for name in ("before.json.gz", "after.json.gz")
]
for pair in (before, after):
    checker.consistency(pair)
new_ids = {
    "video": "7dc4a98b-33cb-4feb-9727-b2bca434138e",
    "audio": "a9175c87-6bc0-4c07-a167-3b7c9de70fba",
}
old_ids = {
    checker.uid(item)
    for timeline in before["timelinePasses"][0]["timelines"]
    for track in timeline["tracks"]
    for item in track["items"]
}
assert set(new_ids.values()).isdisjoint(old_ids)
expected = checker.expected_copy(before, new_ids)
for pool in expected["poolPasses"]:
    proxy = next(
        i for i in pool["items"] if i["uid"] == "de8efefa-310d-451c-863c-d6b847e8b82e"
    )
    mapping = next(
        m
        for m in pool["timelineMappings"]
        if m["timelineUid"]["value"] == checker.MATRIX
    )
    for properties in (
        proxy["evidence"]["GetClipProperty"]["value"],
        mapping["poolItemProperties"]["value"],
    ):
        assert properties["Out"] == "00:00:08:00"
        properties["Out"] = ""
assert expected == after, "Additional unexpected paste delta"
print("Recorded copy fields plus exactly four Out clearings verified; stop retained.")
