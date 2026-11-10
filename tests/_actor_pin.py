"""Synthetic signed-helper pin for NO-EFFECT tests, never an installed actor."""

from vera_timeline_agent import resolve_gui_helper_protocol as helper


def actor_pin() -> dict[str, object]:
    return {
        "schema": helper.ACTOR_SCHEMA,
        "sourceManifestSha256": helper.source_manifest_sha256(),
        "binary": {
            "executablePath": (
                "/Applications/VERA GUI Helper.app/Contents/MacOS/VERAGUIHelper"
            ),
            "sha256": "a" * 64,
            "codeDirectoryHash": "b" * 40,
            "designatedRequirement": (
                'anchor apple generic and identifier "org.vera.resolve-test-bench.gui" '
                "and certificate leaf[subject.OU] = ABCDEFGHIJ"
            ),
            "teamIdentifier": "ABCDEFGHIJ",
            "bundleIdentifier": helper.BUNDLE_ID,
        },
    }
