"""Actual file-boundary refusals for v2 document and JSON identities."""

import json
import subprocess
from pathlib import Path

import pytest
from issue177_package_fixture import make_package_case
from vera_timeline_agent.v2_package import V2PackageError, _compiler_hash


def test_compiler_hash_matches_actual_typescript_unicode_and_integer_canonicalization(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path)
    document = json.loads(case.document_path.read_bytes())
    payload = {
        key: value for key, value in document.items() if key != "liveContentHash"
    }
    unicode_payload = dict(payload, title="é🤖e\u0301\ud800", liveHeadSequence=1.0)
    root = Path(__file__).resolve().parents[1]
    script = """
import { registerHooks } from 'node:module';
import { readFileSync } from 'node:fs';
registerHooks({ resolve(specifier, context, next) {
  try { return next(specifier, context); }
  catch (error) {
    if ((specifier.startsWith('./') || specifier.startsWith('../'))
        && specifier.endsWith('.js'))
      return next(specifier.slice(0, -3) + '.ts', context);
    throw error;
  }
}});
const { sha256CanonicalJson } = await import(SOURCE);
const payloads = JSON.parse(readFileSync(0, 'utf8'));
console.log(JSON.stringify(payloads.map(sha256CanonicalJson)));
""".replace(
        "SOURCE",
        json.dumps((root / "packages/contracts/src/compiler-core.ts").as_uri()),
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        input=json.dumps([payload, unicode_payload]),
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout) == [
        _compiler_hash(payload),
        _compiler_hash(unicode_payload),
    ]
    assert document["liveContentHash"] == json.loads(result.stdout)[0]


def test_document_edit_with_stale_live_hash_refuses_before_publication(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path)
    document = json.loads(case.document_path.read_bytes())
    document["title"] += " changed without updating identity"
    case.document_path.write_text(json.dumps(document))
    with pytest.raises(V2PackageError, match="liveContentHash"):
        case.build()
    assert not case.project_root.exists()


def test_narration_text_identity_cannot_be_self_declared(tmp_path: Path) -> None:
    case = make_package_case(tmp_path)
    for path in (case.dependencies_path, case.manifest_path, case.report_path):
        value = json.loads(path.read_bytes())
        value["document"]["textHash"] = "sha256:" + "0" * 64
        path.write_text(json.dumps(value))
    with pytest.raises(V2PackageError, match="textHash"):
        case.build()
    assert not case.project_root.exists()


def test_settings_identity_must_bind_the_authoring_defaults(tmp_path: Path) -> None:
    case = make_package_case(tmp_path)
    for path in (case.dependencies_path, case.manifest_path, case.report_path):
        value = json.loads(path.read_bytes())
        value["document"]["settingsHash"] = "sha256:" + "0" * 64
        path.write_text(json.dumps(value))
    with pytest.raises(V2PackageError, match="settingsHash"):
        case.build()
    assert not case.project_root.exists()


@pytest.mark.parametrize(
    "attack", ["duplicate", "nested-duplicate", "bom", "nan", "overflow"]
)
def test_package_json_parser_refuses_ambiguous_input_before_publication(
    tmp_path: Path, attack: str
) -> None:
    case = make_package_case(tmp_path)
    original = case.document_path.read_bytes()
    if attack == "duplicate":
        changed = b'{"id":"ignored",' + original[1:]
    elif attack == "nested-duplicate":
        changed = b'{"untrusted":{"id":1,"id":2},' + original[1:]
    elif attack == "bom":
        changed = b"\xef\xbb\xbf" + original
    elif attack == "nan":
        changed = b'{"untrusted":NaN,' + original[1:]
    else:
        changed = b'{"untrusted":1e999,' + original[1:]
    case.document_path.write_bytes(changed)
    with pytest.raises(V2PackageError, match="could not read"):
        case.build()
    assert not case.project_root.exists()
