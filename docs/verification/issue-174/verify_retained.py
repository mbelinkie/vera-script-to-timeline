"""Read-only independent hash, sampling and synchronization evidence checks."""

import argparse
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()


def fraction(value: dict[str, int]) -> Fraction:
    return Fraction(value["numerator"], value["denominator"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    root = parser.parse_args().directory.resolve()
    record = json.loads((root / "qualification.json").read_bytes())
    checked = 0
    maximum_residual, maximum_drift = 0.0, 0.0
    for case in record["cases"]:
        assert (
            digest(root / case["case"] / "case.json")
            == (record["caseRecordHashes"][case["case"]])
        )
        for path_key, hash_key in (
            ("source", "sourceHash"),
            ("receipt", "receiptHash"),
            ("video", "videoHash"),
            ("audioPath", "audioHash"),
            ("operatorPair", "operatorPairHash"),
        ):
            if path_key in case:
                assert digest(root / case[path_key]) == case[hash_key], case["case"]
                checked += 1
        receipt = json.loads((root / case["receipt"]).read_bytes())
        source_rate = fraction(case["descriptor"]["logicalSourceBounds"]["frameRate"])
        target = fraction(receipt["binding"]["targetRate"])
        duration = fraction(case["requestedRange"]["duration"])
        origin = case["descriptor"]["sourceFrameMap"]["packageFrameZeroLogicalFrame"]
        start = case["requestedRange"]["sourceInFrame"] - origin
        expected = [
            start + math.floor(j * source_rate / target)
            for j in range(math.ceil(duration * target))
        ]
        assert case["expectedSelectedOrdinals"] == expected
        if receipt["binding"]["mode"] == "derived_cfr":
            assert case["decodedOrdinals"] == expected
        assert all(
            Fraction(index - start) / source_rate < duration for index in expected
        )
        assert (
            Fraction(0)
            <= fraction(case["geometry"]["sourceCoverSurplus"])
            < 1 / source_rate
        )
        assert (
            Fraction(0)
            <= fraction(case["geometry"]["terminalQuantization"])
            < 1 / target
        )
        assert case["independentRepeatVideoHash"] == case["videoHash"]
        if case["audio"]:
            assert fraction(case["audio"]["endpointError"]) <= Fraction(1, 48000)
            assert case["independentRepeatAudioHash"] == case["audioHash"]
        if "syncMeasurements" in case:
            sync = case["syncMeasurements"]
            assert sync["maxResidualMilliseconds"] <= 1
            assert sync["driftMilliseconds"] <= 1
            maximum_residual = max(maximum_residual, sync["maxResidualMilliseconds"])
            maximum_drift = max(maximum_drift, sync["driftMilliseconds"])
    print(
        json.dumps(
            {
                "cases": len(record["cases"]),
                "artifactHashesVerified": checked,
                "maximumSyncResidualMilliseconds": maximum_residual,
                "maximumSyncDriftMilliseconds": maximum_drift,
                "humanVisualAudibleAcceptance": "pending",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
