"""Audited #473 proof-only adapter for an already source-pinned native host.

This is a *separate* corrected proof reader, never a replacement for native
operation code or the original source-admission graph. Native sessions and
their source seal remain pinned to 3ea32582. The new proof reader is bound by
an additional immutable SHA and loaded only after both original/current
source bytes have been checked. No native data or historical receipts change.

Reason: the real M4 campaign identity is `synthetic-312` while its observed
visual edit has logical A semantics. The original Python observation helper
incorrectly relabeled the signed native geometry with a fake `A` case ID,
which the unchanged TS verifier rightly rejects. The corrected proof reader
keeps the native case ID in its signed evidence and applies strict A semantics
only for that explicitly enumerated synthetic case. All other behavior is
byte-identical to original source outside this reviewed code change.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path.home() / ".local/state/vera/issue-473-studio-05"
FROZEN_PROOF = (
    ROOT / "pinned-code/python/vera_timeline_agent/qualification_output_proof_v2.py"
)
CORRECTED_PROOF = (
    Path.home()
    / ".local/state/vera/issue-473-studio-01/checkout/python"
    / "vera_timeline_agent/qualification_output_proof_v2.py"
)
ORIGINAL_SHA = "24c520a22fd026b5bdb37d96744aa2ba368839d474c94d91a4414a389fd2665f"
CORRECTED_SHA = "27fd10d483898d95ee3980863702862736dfbefcab7e58bf6941869342710f80"
NAME = "vera_timeline_agent.qualification_output_proof_v2"


def need(value: bool, reason: str) -> None:
    if not value:
        raise RuntimeError("#473 proof-only source adapter refused: " + reason)


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load() -> ModuleType:
    """Install audited proof-only algorithm; original native host is untouched."""
    import vera_timeline_agent
    from vera_timeline_agent import qualification_output_proof_v2 as original
    from vera_timeline_agent import roundtrip_v2_records as graph

    need(
        FROZEN_PROOF.is_file()
        and not FROZEN_PROOF.is_symlink()
        and CORRECTED_PROOF.is_file()
        and not CORRECTED_PROOF.is_symlink(),
        "original and corrected proof files must exist as independent files",
    )
    need(
        sha(FROZEN_PROOF.read_bytes()) == ORIGINAL_SHA
        and sha(CORRECTED_PROOF.read_bytes()) == CORRECTED_SHA,
        "proof source identities changed",
    )
    need(
        graph.ROOT.resolve() == (ROOT / "pinned-code").resolve()
        and graph.proof_source_hashes_v2()[
            "python/vera_timeline_agent/qualification_output_proof_v2.py"
        ]
        == "sha256:" + ORIGINAL_SHA,
        "signed native source graph was replaced or remapped",
    )
    existing = sys.modules.get(NAME)
    existing_file = getattr(existing, "__file__", None)
    if (
        existing is not None
        and isinstance(existing_file, str)
        and Path(existing_file).resolve() == CORRECTED_PROOF.resolve()
    ):
        return existing
    need(
        existing is original
        and Path(original.__file__).resolve() == FROZEN_PROOF.resolve(),
        "expected original native proof module not loaded",
    )
    spec = importlib.util.spec_from_file_location(NAME, CORRECTED_PROOF)
    need(
        spec is not None and spec.loader is not None,
        "corrected proof source loader unavailable",
    )
    assert spec is not None and spec.loader is not None
    reader = importlib.util.module_from_spec(spec)
    sys.modules[NAME] = reader
    try:
        spec.loader.exec_module(reader)
    except BaseException:
        sys.modules[NAME] = original
        raise
    need(
        isinstance(reader, ModuleType)
        and reader.ROOT == graph.ROOT
        and reader.proof_source_hashes_v2 is graph.proof_source_hashes_v2,
        "corrected proof algorithm would change native-source ancestry",
    )
    vera_timeline_agent.qualification_output_proof_v2 = reader
    return reader
