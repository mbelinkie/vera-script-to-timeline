"""Issue 257 acceptance test across the native probe and host finalizer."""

from __future__ import annotations

import hashlib
import importlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from test_issue257_sample_precision_compare import (
    _native_pcm,
    _source_wav,
)
from vera_timeline_agent import sample_precision_compare_v2 as compare_module
from vera_timeline_agent import sample_precision_probe_v2 as probe
from vera_timeline_agent import workflow_v2_cli

_probe_fixtures: Any = importlib.import_module("test_issue257_sample_precision_probe")
_environment = _probe_fixtures._environment
_NativeState = _probe_fixtures._NativeState
_Resolve = _probe_fixtures._Resolve


def test_native_result_finalizes_from_canonical_request_after_installed_copy_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, _ = _environment(tmp_path, monkeypatch)
    fixture_request = json.loads((tmp_path / "evidence" / "request.json").read_text())
    source_path = Path(fixture_request["sourcePath"])
    review_path = Path(fixture_request["reviewPath"])

    samples = [
        ((index * 7919) % (1 << 20)) - (1 << 19)
        for index in range(compare_module.SAMPLE_COUNT)
    ]
    source_wav, source_pcm = _source_wav(samples)
    source_path.write_bytes(source_wav)
    source_sha = hashlib.sha256(source_wav).hexdigest()
    source_pcm_sha = hashlib.sha256(source_pcm).hexdigest()
    monkeypatch.setattr(probe, "SOURCE_SHA256", source_sha)
    monkeypatch.setattr(probe, "SOURCE_PCM_SHA256", source_pcm_sha)
    review = json.loads(review_path.read_text())
    review["originalSourceAudioHash"] = f"sha256:{source_sha}"
    review["sourcePcmSha256"] = f"sha256:{source_pcm_sha}"
    review_path.write_text(json.dumps(review, sort_keys=True), encoding="utf-8")
    monkeypatch.setattr(
        probe, "REVIEW_SHA256", hashlib.sha256(review_path.read_bytes()).hexdigest()
    )

    release_root = tmp_path / "pipeline-release"
    workflow_v2_cli.build_sample_precision_release_v2(release_root)
    installed_root = tmp_path / "installed-plugin"
    shutil.copytree(release_root, installed_root)
    installed_module = (
        installed_root
        / "vera-delivery-v2/python/vera_timeline_agent/sample_precision_probe_v2.py"
    )
    monkeypatch.setattr(probe, "__file__", str(installed_module))
    monkeypatch.setattr(probe, "PROBE_STATE_ROOT", tmp_path / "native-state")

    canonical_request = probe.prepare_probe_request(
        release_root=release_root,
        output=tmp_path / "pipeline-evidence",
        source=source_path,
        review=review_path,
        target=fixture_request["target"],
        producer_authorization=fixture_request["producerAuthorization"],
        task_id=fixture_request["taskId"],
    )
    request_bytes = canonical_request.read_bytes()
    request_sha = hashlib.sha256(request_bytes).hexdigest()
    installed_request = installed_root / "vera-delivery-v2/request.json"
    installed_request.write_bytes(request_bytes)
    installed_request.chmod(0o400)
    monkeypatch.setattr(compare_module, "_INSTALLED_REQUEST_PATH", installed_request)

    request = probe.load_probe_request(canonical_request, request_sha)
    state = _NativeState(request)
    result_path = probe.run_sample_precision_probe(
        _Resolve(state), installed_request, expected_request_sha256=request_sha
    )
    result: dict[str, Any] = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["requestPath"] == str(installed_request)
    assert result["hostRequestPath"] == str(canonical_request)
    assert result["requestSha256"] == result["hostRequestSha256"] == request_sha
    assert [row["stage"] for row in result["effects"]] == [
        stage for stage, _ in compare_module._EFFECT_SEQUENCE
    ]
    assert all(Path(row["journalPath"]).is_file() for row in result["effects"])

    installed_request.rename(installed_request.with_name("request.archived.json"))
    installed_request.write_bytes(b"replacement after native execution\n")
    native_pcm = _native_pcm(samples)
    monkeypatch.setattr(
        compare_module,
        "_decode_probe_mov",
        lambda _path, _sha: (native_pcm, {"decoderIdentitySha256": "c" * 64}),
    )
    final_path = compare_module.finalize_probe(
        canonical_request, result_path, tmp_path / "finalization.json"
    )
    final = json.loads(final_path.read_text(encoding="utf-8"))
    assert final["status"] == "supported"
    assert final["geometry"]["status"] == "pass"
    assert final["pcm"]["status"] == "pass"
    assert final["nativeRequestPath"] == str(installed_request)
