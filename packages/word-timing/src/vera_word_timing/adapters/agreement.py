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
import shutil
import tempfile
from pathlib import Path

from vera_word_timing.adapters.local_engines import (
    EngineConfig,
    prepare_segments,
    run_engine,
)
from vera_word_timing.artifacts import (
    AudioRef,
    Json,
    agreement_block,
    to_ms,
    tool,
    with_id,
)
from vera_word_timing.ports import PortRefusal, check_alignment_inputs

QWEN_REVISION = "c7cbfc2048c462b0d63a45797104fc9db3ad62b7"
# Model-card languages the word-timing study exercised (Italian: Qwen-only,
# unverified). Swedish is not listed and agreed with MFA only 74% of the time
# in the study, so the check refuses it rather than give a misleading answer.
QWEN_LANGUAGES = {"en": "English", "de": "German", "fr": "French", "it": "Italian"}


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
        check_alignment_inputs(audio, recognition, reconciliation)
        if alignment["identity"]["recognitionArtifactId"] != recognition["artifactId"]:
            raise PortRefusal(
                "aligner", "input-invalid", "Alignment and recognition do not match."
            )
        expected_reconcile = (
            None if reconciliation is None else reconciliation["artifactId"]
        )
        if alignment["identity"]["reconcileArtifactId"] != expected_reconcile:
            raise PortRefusal(
                "aligner",
                "input-invalid",
                "Pass the same script reconciliation the alignment was made with.",
            )
        if alignment["identity"]["audio"]["hash"] != audio.original_hash:
            raise PortRefusal(
                "aligner", "input-invalid", "The audio does not match the alignment."
            )
        if not self.config.qwen_command:
            raise PortRefusal(
                "aligner",
                "runtime-missing",
                "Agreement partner (VERA_QWEN_COMMAND) is not configured.",
            )
        language = recognition["identity"]["language"].split("-")[0]
        if language not in QWEN_LANGUAGES:
            raise PortRefusal(
                "aligner",
                "capability-missing",
                f"The agreement partner does not support language {language!r}.",
            )
        _, payload = prepare_segments(self.config, audio, recognition, reconciliation)
        partner_units = [
            (w["i"], w.get("sub", 0), w["text"])
            for seg in payload["segments"]
            for w in seg["words"]
        ]
        aligned_units = [
            (w["tokenIndex"], w["sub"], w["text"]) for w in alignment["words"]
        ]
        if partner_units != aligned_units:
            # The partner must judge exactly the units (texts and order) MFA timed.
            raise PortRefusal(
                "aligner",
                "input-invalid",
                "The agreement partner's units differ from the alignment's units.",
            )
        self.config.work_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="vera-qwen-", dir=self.config.work_dir
        ) as tmp:
            seg_file, out = Path(tmp) / "segments.json", Path(tmp) / "result.json"
            seg_file.write_text(json.dumps(payload))
            # Colima mounts only the home directory: stage the audio beside the
            # hand-off files so the container can always read it.
            staged = Path(tmp) / audio.path.name
            shutil.copyfile(audio.path, staged)
            run_engine(
                [
                    *self.config.qwen_command,
                    "--segments",
                    str(seg_file),
                    "--audio-dir",
                    str(staged.parent),
                    "--out",
                    str(out),
                ],
                port="aligner",
                env={"VERA_QWEN_LANGUAGE": QWEN_LANGUAGES[language]},
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
            {"language": QWEN_LANGUAGES[language], "gridMs": 80},
        )
        block = agreement_block(alignment["words"], partner_times, partner, self.tau_ms)
        body = {k: v for k, v in alignment.items() if k != "artifactId"}
        body["agreement"] = block
        return with_id(body)
