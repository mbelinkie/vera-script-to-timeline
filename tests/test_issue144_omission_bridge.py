from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from test_issue144_row_narration import _setup
from vera_timeline_agent.roundtrip_build import (
    ROOT,
    PreparedBuild,
    _file_hash,
    _receipt_bytes,
    load_operator_json,
)
from vera_timeline_agent.roundtrip_narration import replace_row_narration
from vera_timeline_agent.roundtrip_proof import ProofSession


def _canonical_hash(node: str, path: Path) -> str:
    # Call the actual Node canonical serializer; no Python document/hash clone.
    source = """
import {readFileSync} from 'node:fs';
import {registerHooks} from 'node:module';
const url=process.argv[1];
const hook=registerHooks({resolve(specifier,context,next){
  if(context.parentURL===url&&specifier==='./script-validator.js')
    return next('./script-validator.ts',context);
  return next(specifier,context);
}});
const compiler=await import(url);hook.deregister();
process.stdout.write(compiler.sha256CanonicalJson(JSON.parse(readFileSync(process.argv[2],'utf8'))));
"""
    result = subprocess.run(
        [
            node,
            "--input-type=module",
            "--eval",
            source,
            (ROOT / "packages/contracts/src/compiler-core.ts").as_uri(),
            str(path),
        ],
        capture_output=True,
        check=True,
        timeout=120,
    )
    return result.stdout.decode()


def test_actual_service_handoff_finalizes_compiles_and_packages_new_whole_row(
    tmp_path: Path,
) -> None:
    prior, service, provider, _ = _setup(tmp_path, astral=True)
    session = ProofSession(prior.root)
    before = {name: raw for name, raw in prior.raw.items()}
    block = prior.document["activeDraft"]["blocks"][1]
    token = next(word for word in block["tokens"] if word["value"] == "Charlie")
    edit = prior.root / "trusted-edit.json"
    edit.write_bytes(
        _receipt_bytes(
            {
                "expectedDocumentHash": _canonical_hash(
                    prior.node, prior.root / "script-document.json"
                ),
                "blockId": block["id"],
                "tokenIds": [token["id"]],
            }
        )
    )
    # Internal pure operations only. This test does not supply an audio omission
    # verdict or authorize a public proof decision/native action.
    revision = session._semantic(
        "revise-omission", [prior.root / "script-document.json", edit]
    )
    assert revision["ok"], revision
    assert set(revision["artifacts"]) == {"script-document.json"}
    staged = prior.root / "bridge-build"
    staged.mkdir()
    revised = staged / "script-document.json"
    revised.write_text(revision["artifacts"]["script-document.json"])
    handoff = replace_row_narration(prior, revised, service, proof_root=prior.root)
    assert len(provider.requests) == 1
    assert provider.requests[0].text == "Alpha 😀 Bravo Delta Echo"
    assert (
        handoff["replacements"][0]["audioHash"]
        != prior.dependencies["narration"][0]["audioHash"]
    )
    handoff_path = prior.root / "just-computed-handoff.json"
    handoff_path.write_bytes(_receipt_bytes(handoff))
    paths = [revised, prior.root / "compiler-dependencies.json", handoff_path]
    finalized = session._semantic("finalize-omission", paths)
    assert finalized["ok"], finalized
    replay = replace_row_narration(prior, revised, service, proof_root=prior.root)
    assert replay == handoff and len(provider.requests) == 1
    assert session._semantic("finalize-omission", paths) == finalized
    for name in ("compiler-dependencies.json",):
        (staged / name).write_text(finalized["artifacts"][name])
    (staged / "proof-request.json").write_bytes(prior.raw["proof-request.json"])
    manifest = finalized["artifacts"]["timeline-manifest.json"]
    preview_path = prior.root / "preview-manifest.json"
    preview_path.write_text(manifest)
    preview = load_operator_json(preview_path)
    replacement = handoff["replacements"][0]
    plan: dict[str, Any] = {}
    for source in preview["sources"]:
        if source["kind"] == "placeholder":
            # The accepted package stage generates compiler-declared placeholders.
            continue
        if source["id"] in prior.plan:
            plan[source["id"]] = prior.plan[source["id"]]
        else:
            assert source["path"] == (f"Media/Narration/{replacement['assetId']}.wav")
            plan[source["id"]] = {
                "artifactId": replacement["assetId"],
                "origin": replacement["origin"],
                "policy": "copy",
            }
    (staged / "materialization-plan.json").write_bytes(_receipt_bytes(plan))
    rebuilt = PreparedBuild(staged)
    result = rebuilt.run()
    assert result["status"] == "waiting"
    assert rebuilt.manifest_path.read_text() == manifest
    assert (
        rebuilt.report_path.read_text() == finalized["artifacts"]["build-report.json"]
    )
    assert rebuilt.verified_package().build_id == preview["buildId"]
    assert preview["buildId"] != prior.dependencies["build"]["buildId"]
    assert rebuilt.dependencies["narration"][1] == prior.dependencies["narration"][1]
    for name, raw in before.items():
        assert (prior.root / name).read_bytes() == raw
    assert _file_hash(revised) == handoff["revisedDocumentHash"]
    assert not session.pointer.exists() and not rebuilt.intent_path.exists()
    assert len(provider.requests) == 1
