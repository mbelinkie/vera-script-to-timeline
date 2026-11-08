"""Native-effect-free acceptance gate for a #312 guarded reverse queue result.

This deliberately does not dispatch native effects.  #447's build-only M2
adapter and #448's independent M3 children must not be treated as a substitute
for the output host's authenticated same-target edit/inference chain.  The gate
is the acceptance half of a future closed multi-stage adapter, not permission to
run historical requests, edit Resolve via shell, or bypass the native queue.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .qualification_output_controller_v2 import load_output_session
from .qualification_output_native_v2 import verify_native_result
from .qualification_output_proof_v2 import (
    QualificationOutputProofV2,
    _load_terminal_output_with_comparison,
)

EXPECTED_RATE = {"numerator": 24000, "denominator": 1001}
EXPECTED_EXTENT = 1407
BEFORE_BOUNDARY = 327
AFTER_BOUNDARY = 351


class ReverseRefusal(ValueError):
    """Evidence is missing, inauthentic, or outside the supported edit case."""


def _require(value: bool, reason: str) -> None:
    if not value:
        raise ReverseRefusal(reason)


def _items(geometry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = geometry.get("items")
    if not isinstance(rows, list) or len(rows) != 11:
        raise ReverseRefusal("11 real native events required")
    items: dict[str, dict[str, Any]] = {}
    for row in rows:
        _require(isinstance(row, dict), "native item must be an object")
        uid = row.get("itemUid")
        _require(
            isinstance(uid, str) and bool(uid) and uid not in items,
            "unique item UID required",
        )
        assert isinstance(uid, str)
        items[uid] = row
    return items


def verify_supported_boundary(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, Any]:
    """Require *only* the supported adjoining held-picture boundary transfer.

    This comparison follows full host authentication: caller-supplied geometry
    alone never constitutes a native proof.  The actual source-in handling of
    the right-hand held picture must remain unchanged.
    """
    for geometry in (before, after):
        _require(
            geometry.get("rate") == EXPECTED_RATE
            and type(geometry.get("extentFrames")) is int
            and geometry["extentFrames"] == EXPECTED_EXTENT,
            "qualified 24000/1001, 1407-frame programme required",
        )
        tracks = geometry.get("tracks")
        _require(
            isinstance(tracks, list) and len(tracks) == 6, "six native tracks required"
        )
    _require(before["tracks"] == after["tracks"], "native tracks changed")
    _require(
        before.get("sourceMappings") == after.get("sourceMappings"),
        "native media/source mapping changed",
    )
    _require(
        before.get("context", {}).get("target")
        == after.get("context", {}).get("target"),
        "native target changed across the edit",
    )
    old, new = _items(before), _items(after)
    _require(old.keys() == new.keys(), "native item identity changed")
    changed = [uid for uid in old if old[uid] != new[uid]]
    _require(len(changed) == 2, "exactly two boundary picture items may change")
    left = next(
        (
            uid
            for uid in changed
            if type(old[uid].get("recordStart")) is int
            and type(old[uid].get("recordDuration")) is int
            and old[uid]["recordStart"] + old[uid]["recordDuration"] == BEFORE_BOUNDARY
        ),
        None,
    )
    _require(left is not None, "original picture boundary 327 not found")
    assert left is not None
    right = next((uid for uid in changed if uid != left), None)
    assert right is not None
    a, b = old[left], old[right]
    a2, b2 = new[left], new[right]
    _require(
        a.get("kind") == b.get("kind") == "video"
        and a.get("trackId") == b.get("trackId")
        and a.get("eventId") != b.get("eventId")
        and b.get("recordStart") == BEFORE_BOUNDARY
        and a2.get("recordStart") == a.get("recordStart")
        and a2.get("recordDuration") == a["recordDuration"] + 24
        and b2.get("recordStart") == AFTER_BOUNDARY
        and type(b.get("recordDuration")) is int
        and b["recordDuration"] > 24
        and b2.get("recordDuration") == b["recordDuration"] - 24,
        "actual supported +24-frame adjacent picture transfer required",
    )
    _require(
        b["recordStart"] + b["recordDuration"]
        == b2["recordStart"] + b2["recordDuration"],
        "right picture end must remain fixed",
    )
    for old_item, new_item, allowed in (
        (a, a2, {"recordDuration", "sourceDuration"}),
        (b, b2, {"recordStart", "recordDuration", "sourceStart", "sourceDuration"}),
    ):
        _require(
            {k: v for k, v in old_item.items() if k not in allowed}
            == {k: v for k, v in new_item.items() if k not in allowed},
            "picture media, source, track, links or native settings changed",
        )
    _require(
        type(a.get("sourceDuration")) is int
        and a2.get("sourceDuration") == a["sourceDuration"] + 24
        and type(b.get("sourceDuration")) is int
        and b2.get("sourceDuration") == b["sourceDuration"] - 24
        and b2.get("sourceStart") == b.get("sourceStart"),
        "held-picture source extent or source-in changed unexpectedly",
    )
    return {
        "leftItemUid": left,
        "rightItemUid": right,
        "fromFrame": 327,
        "toFrame": 351,
    }


def verify_reverse_receipts(
    *,
    proof_path: Path,
    proof_sha256: str,
    pristine_result_path: Path,
    pristine_result_sha256: str,
    edited_result_path: Path,
    edited_result_sha256: str,
    fresh_session_path: Path,
    fresh_session_sha256: str,
    fresh_result_path: Path,
    fresh_result_sha256: str,
) -> dict[str, Any]:
    """Cryptographic acceptance; never starts or retries a native job.

    The output proof's verifier authenticates both chains, genuine inference,
    explicit accepted revision, current source graph, and both decisions.
    The separate *revised output session* reauthenticates the signed, one-use
    accepted-revision-to-fresh-target reservation, admitted package and final
    PCM comparison. Matching an unrelated M2 build manifest is NOT sufficient.
    Pure proof recomputation may retain immutable artifacts; no native effect.
    """
    proof = QualificationOutputProofV2(proof_path, proof_sha256)
    accepted, candidate = proof.accepted_revision()
    _require(accepted.get("outcome") == "accept", "explicit accepted revision required")
    pristine = verify_native_result(pristine_result_path, pristine_result_sha256)
    edited = verify_native_result(edited_result_path, edited_result_sha256)
    for result, phase, context in (
        (pristine, "pristine", proof.baseline.context),
        (edited, "edited", proof.edited.context),
    ):
        _require(
            result.get("status") == "complete"
            and result.get("action") == "capture_post"
            and result.get("context") == context
            and context.get("phase") == phase
            and result.get("target") == context.get("target")
            and isinstance(result.get("nativeGeometry"), dict),
            "complete authenticated output capture and exact phase identity required",
        )
    _require(
        pristine_result_path != edited_result_path
        and pristine_result_sha256 != edited_result_sha256,
        "pre/post must be separate one-use host results",
    )
    boundary = verify_supported_boundary(
        pristine["nativeGeometry"], edited["nativeGeometry"]
    )
    fresh = load_output_session(fresh_session_path, fresh_session_sha256)
    _require(
        fresh.context.get("phase") == "rebuild"
        and fresh.context.get("caseId") == proof.baseline.context.get("caseId")
        and fresh.revised_preflight is not None
        and fresh.context.get("target") != pristine["target"]
        and fresh.context["target"].get("projectUid")
        != pristine["target"].get("projectUid")
        and fresh.context["target"].get("timelineUid")
        != pristine["target"].get("timelineUid"),
        "signed accepted-revision reservation and independent fresh target required",
    )
    revised_manifest = candidate.get("revision", {}).get("manifestJson")
    _require(
        isinstance(revised_manifest, str), "actual accepted revised manifest required"
    )
    _require(
        json.loads(revised_manifest) == fresh.admission.manifest,
        "fresh revised admission differs from the accepted manifest",
    )
    fresh_result = verify_native_result(fresh_result_path, fresh_result_sha256)
    _require(
        fresh_result_path not in {pristine_result_path, edited_result_path}
        and fresh_result_sha256 not in {pristine_result_sha256, edited_result_sha256}
        and fresh_result.get("status") == "complete"
        and fresh_result.get("action") == "capture_post"
        and fresh_result.get("context") == fresh.context
        and fresh_result.get("target") == fresh.context["target"],
        "fresh rebuild must have its own authenticated final native capture",
    )
    # Requires saved/reopened readback, real PCM decode and compared_consistent
    # terminal history. A mere complete native capture is NOT final acceptance.
    _load_terminal_output_with_comparison(fresh)
    return {
        "status": "verified",
        "provenance": "host_authenticated_no_replay",
        "boundary": boundary,
        "pristineResultSha256": pristine_result_sha256,
        "editedResultSha256": edited_result_sha256,
        "acceptedProofSha256": proof_sha256,
        "freshSessionSha256": fresh_session_sha256,
        "freshResultSha256": fresh_result_sha256,
    }


def main(argv: list[str] | None = None) -> int:
    """Validate host-authenticated output proof and fresh rebuild."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--proof-sha256", required=True)
    parser.add_argument("--pristine", type=Path, required=True)
    parser.add_argument("--pristine-sha256", required=True)
    parser.add_argument("--edited", type=Path, required=True)
    parser.add_argument("--edited-sha256", required=True)
    parser.add_argument("--fresh-session", type=Path, required=True)
    parser.add_argument("--fresh-session-sha256", required=True)
    parser.add_argument("--fresh-capture", type=Path, required=True)
    parser.add_argument("--fresh-capture-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = verify_reverse_receipts(
            proof_path=args.proof,
            proof_sha256=args.proof_sha256,
            pristine_result_path=args.pristine,
            pristine_result_sha256=args.pristine_sha256,
            edited_result_path=args.edited,
            edited_result_sha256=args.edited_sha256,
            fresh_session_path=args.fresh_session,
            fresh_session_sha256=args.fresh_session_sha256,
            fresh_result_path=args.fresh_capture,
            fresh_result_sha256=args.fresh_capture_sha256,
        )
    except (OSError, ValueError, KeyError, TypeError, RuntimeError):
        # Never expose private native host paths, source media or receipt data.
        print(json.dumps({"status": "blocked", "reason": "unverified_reverse_chain"}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
