"""Convert study outputs into the #168 draft artifacts and validate them.

Proves the draft schemas (docs/plans/issue-168/schemas) can carry real
pipeline output: a recogniser transcript (T-C / T-CR) becomes a
RecognitionArtifactV1, an MFA RESULT becomes an AlignmentArtifactV1, and an
optional partner aligner (Qwen/Charsiu RESULT) fills the agreement block at
tau 70 ms. Artifact ids are sha256 of canonical JSON (sorted keys, compact,
UTF-8) without the artifactId field.

Usage (validation needs the repo's jsonschema: run with `uv run --frozen python`):
  to_artifacts.py --tc T-C.json --audio X.wav --kind asr-cloud --provider P --model M \
      [--consent-policy ID] --result MFA.json --segments SEG.json [--partner QWEN.json] \
      --out-dir DIR
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMAS = HERE.parents[1] / "docs/plans/issue-168/schemas"
TAU_MS = 70


def chash(obj: object) -> str:
    raw = json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def with_id(body: dict) -> dict:
    return {**body, "artifactId": chash(body)}


def ms(x: float | None) -> int | None:
    return None if x is None else max(0, round(x * 1000))


def audio_identity(path: Path) -> dict:
    import wave

    with wave.open(str(path)) as w:
        return {
            "hash": file_hash(path),
            "sampleRate": w.getframerate(),
            "durationSamples": w.getnframes(),
        }


def recognition(tc: dict, audio: dict, args: argparse.Namespace) -> dict:
    prov = tc.get("provenance", {})
    precision = (
        "word_start_with_derived_end"
        if "derived" in json.dumps(prov).lower()
        else "word"
    )
    tokens = []
    for n, w in enumerate(tc["words"]):
        kind = (
            "event"
            if w.get("type") == "event"
            else ("filler" if w.get("type") == "filler" else "word")
        )
        tokens.append(
            {
                "index": n,
                "display": str(w["text"]),
                "kind": kind,
                "anchorStartMs": ms(w.get("start")),
                "anchorEndMs": ms(w.get("end")),
                "anchorPrecision": precision if w.get("start") is not None else "none",
                "providerConfidence": w.get("confidence"),
            }
        )
    cloud = args.kind == "asr-cloud"
    consent = {
        "processing": "cloud" if cloud else "local",
        "policyId": args.consent_policy,
    }
    if cloud:
        consent["cloudProvider"] = args.provider
    return with_id(
        {
            "schemaVersion": "recognition-artifact/v1",
            "identity": {
                "audio": audio,
                "prep": [],
                "recognizer": {
                    "kind": args.kind,
                    "provider": args.provider,
                    "model": args.model,
                    "modelRevision": prov.get("snapshot"),
                    "parametersHash": chash(prov),
                    "keytermsHash": None,
                },
                "language": "en",
            },
            "consent": consent,
            "tokens": tokens,
        }
    )


def alignment(
    rec: dict, result: dict, seg: dict, audio: dict, partner: dict | None
) -> dict:
    texts = {
        (int(e["i"]), int(e.get("sub", 0))): e["text"]
        for s in seg["segments"]
        for e in s["words"]
    }
    words = []
    for r in result["words"]:
        ok = r["status"] == "aligned"
        words.append(
            {
                "tokenIndex": r["i"],
                "sub": r.get("sub", 0),
                "text": texts[(r["i"], r.get("sub", 0))],
                "startMs": ms(r["start"]) if ok else None,
                "endMs": ms(r["end"]) if ok else None,
                "status": "acoustic" if ok else "unaligned",
                "alignerScore": None,
            }
        )
    tool = {
        "name": "montreal-forced-aligner",
        "version": str(result.get("tool", {}).get("version", "3.4.3")),
        "acousticModel": "english_us_arpa",
        "dictionary": "english_us_arpa",
        "extraDictionaryHash": None,
        "parametersHash": chash(result.get("tool", {})),
    }
    body = {
        "schemaVersion": "alignment-artifact/v1",
        "words": words,
        "identity": {
            "recognitionArtifactId": rec["artifactId"],
            "reconcileArtifactId": None,
            "audio": audio,
            "prep": [],
            "aligner": tool,
            "segmentation": {
                "name": "silero-vad",
                "version": "6.2.1",
                "parametersHash": chash({"maxSegS": 30, "padS": 0.3}),
            },
        },
    }
    if partner is not None:
        p = {(r["i"], r.get("sub", 0)): r for r in partner["words"]}
        bounds = []
        for w in words:
            if w["status"] != "acoustic":
                continue
            pr = p.get((w["tokenIndex"], w["sub"]))
            pok = pr is not None and pr.get("status") == "aligned"
            for side, mine, key in (
                ("onset", w["startMs"], "start"),
                ("offset", w["endMs"], "end"),
            ):
                delta = (mine - ms(pr[key])) if pok else None
                bounds.append(
                    {
                        "tokenIndex": w["tokenIndex"],
                        "sub": w["sub"],
                        "side": side,
                        "deltaMs": delta,
                        "verdict": "accepted"
                        if delta is not None and abs(delta) <= TAU_MS
                        else "needs_review",
                    }
                )
        body["agreement"] = {
            "partner": {
                "name": partner.get("aligner", "partner"),
                "version": "study",
                "parametersHash": chash(partner.get("tool", {})),
            },
            "tauMs": TAU_MS,
            "boundaries": bounds,
        }
    return with_id(body)


def validate(doc: dict, schema_name: str) -> list[str]:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    schemas = {p.name: json.loads(p.read_text()) for p in SCHEMAS.glob("*.schema.json")}
    registry = Registry().with_resources(
        [(s["$id"], Resource.from_contents(s)) for s in schemas.values()]
        + [(name, Resource.from_contents(s)) for name, s in schemas.items()]
    )
    v = Draft202012Validator(schemas[schema_name], registry=registry)
    return [
        f"{'/'.join(map(str, e.path))}: {e.message}"[:200] for e in v.iter_errors(doc)
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("--tc", "--audio", "--result", "--segments", "--out-dir"):
        parser.add_argument(name, type=Path, required=True)
    parser.add_argument("--partner", type=Path)
    parser.add_argument(
        "--kind",
        required=True,
        choices=["asr-local", "asr-cloud", "caption", "reference-text"],
    )
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--consent-policy")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    audio = audio_identity(args.audio)
    rec = recognition(json.loads(args.tc.read_text()), audio, args)
    ali = alignment(
        rec,
        json.loads(args.result.read_text()),
        json.loads(args.segments.read_text()),
        audio,
        json.loads(args.partner.read_text()) if args.partner else None,
    )
    for doc, name, schema in (
        (rec, "recognition", "recognition-artifact-v1.schema.json"),
        (ali, "alignment", "alignment-artifact-v1.schema.json"),
    ):
        (args.out_dir / f"{args.tc.stem}.{name}.json").write_text(
            json.dumps(doc, indent=1, ensure_ascii=False)
        )
        errors = validate(doc, schema)
        extra = ""
        if name == "alignment" and "agreement" in doc:
            b = doc["agreement"]["boundaries"]
            extra = f", needs_review {sum(x['verdict'] == 'needs_review' for x in b)}/{len(b)} boundaries"
        print(
            f"{args.tc.stem} {name}: {'VALID' if not errors else 'INVALID'}"
            f" ({len(doc.get('tokens', doc.get('words', [])))} items{extra})"
        )
        for e in errors[:5]:
            print("   ", e)


if __name__ == "__main__":
    main()
