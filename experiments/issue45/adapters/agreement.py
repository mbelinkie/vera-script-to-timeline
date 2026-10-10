"""Agreement check: a structurally different aligner re-times the same units.

Study evidence: MFA's gross failures (a short phrase-initial word moved onto a
breath 0.5-2.5 s early, words stretched over an untranscribed false start)
land exactly on take starts. Qwen3-ForcedAligner-0.6B (Apache-2.0, 80 ms
grid), run on the identical segments, flagged 73/75 of them at tau 70 ms, so
boundaries it disagrees with become `needs_review` rather than silent bad cuts.

The partner runs in its own container (vendored `engines/qwen/`); configure
`VERA_QWEN_COMMAND` (e.g. `sh .../engines/qwen/run_qwen.sh`). Attaching the
agreement block creates a new immutable alignment artifact.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from experiments.issue45.adapters.local_engines import (
    EngineConfig,
    prepare_segments,
    run_engine,
)
from experiments.issue45.artifacts import (
    AudioRef,
    Json,
    agreement_block,
    to_ms,
    tool,
    with_id,
)
from experiments.issue45.ports import PortRefusal

QWEN_REVISION = "c7cbfc2048c462b0d63a45797104fc9db3ad62b7"


class QwenAgreement:
    def __init__(self, config: EngineConfig, *, tau_ms: int = 70) -> None:
        self.config, self.tau_ms = config, tau_ms

    def check(
        self,
        audio: AudioRef,
        recognition: Json,
        alignment: Json,
        *,
        reconciliation: Json | None = None,
    ) -> Json:
        if not self.config.qwen_command:
            raise PortRefusal(
                "aligner",
                "runtime-missing",
                "Agreement partner (VERA_QWEN_COMMAND) is not configured.",
            )
        if alignment["identity"]["recognitionArtifactId"] != recognition["artifactId"]:
            raise PortRefusal(
                "aligner", "input-invalid", "Alignment and recognition do not match."
            )
        _, payload = prepare_segments(self.config, audio, recognition, reconciliation)
        with tempfile.TemporaryDirectory(prefix="vera-qwen-") as tmp:
            seg_file, out = Path(tmp) / "segments.json", Path(tmp) / "result.json"
            seg_file.write_text(json.dumps(payload))
            run_engine(
                [
                    *self.config.qwen_command,
                    "--segments",
                    str(seg_file),
                    "--audio-dir",
                    str(audio.path.parent),
                    "--out",
                    str(out),
                ],
                port="aligner",
                env=None,
                timeout=self.config.timeout_s,
            )
            result = json.loads(out.read_text())
        partner_times: dict[tuple[int, int], tuple[int | None, int | None]] = {}
        for r in result["words"]:
            ok = r["status"] == "aligned"
            partner_times[(r["i"], r.get("sub", 0))] = (
                to_ms(r["start"]) if ok else None,
                to_ms(r["end"]) if ok else None,
            )
        partner = tool(
            "qwen3-forced-aligner-0.6b",
            QWEN_REVISION,
            {"language": "English", "gridMs": 80},
        )
        block = agreement_block(alignment["words"], partner_times, partner, self.tau_ms)
        body = {k: v for k, v in alignment.items() if k != "artifactId"}
        body["agreement"] = block
        return with_id(body)
