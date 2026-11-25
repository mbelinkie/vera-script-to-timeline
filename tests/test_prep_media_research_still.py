from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from vera_timeline_agent.prep_media_research_still import (
    KeptStillResponse,
    ResearchStillError,
    acquire_research_still,
    materialize_research_quote_picture,
    materialize_research_still,
)

PROJECT_ID = "00000000-0000-4000-8000-000000006731"
ITEM_ID = "00000000-0000-4000-8000-000000006732"
SOURCE_ID = "00000000-0000-4000-8000-000000006733"


@dataclass
class FakeReader:
    item: dict[str, Any]
    manifest: dict[str, Any]
    body: bytes

    def read(self, snapshot: Mapping[str, Any]) -> KeptStillResponse:
        return KeptStillResponse(self.item, self.manifest, self.body, "image/webp")


def _webp() -> bytes:
    output = BytesIO()
    Image.new("RGB", (8, 6), (20, 40, 80)).save(output, format="WEBP", lossless=True)
    return output.getvalue()


def _case(body: bytes | None = None) -> tuple[dict[str, Any], FakeReader]:
    body = body or _webp()
    digest = hashlib.sha256(body).hexdigest()
    original = {
        "versionId": "asset-version-7",
        "sha256": digest,
        "byteCount": len(body),
        "mimeType": "image/webp",
        "width": 8,
        "height": 6,
    }
    provenance = {
        "kind": "url",
        "sourceUrl": "https://gone.invalid/original.webp",
        "inputSha256": "a" * 64,
    }
    snapshot = {
        "researchProjectId": PROJECT_ID,
        "itemId": ITEM_ID,
        "itemVersion": 7,
        "sourceId": SOURCE_ID,
        "title": "Saved test still",
        "credit": "Synthetic",
        "licence": "CC0",
        "usageNote": "Generated fixture",
        "provenance": provenance,
        "original": original,
    }
    item = {
        "kind": "still",
        "projectId": PROJECT_ID,
        "id": ITEM_ID,
        "sourceId": SOURCE_ID,
        "version": 7,
        "content": {
            "title": "Saved test still",
            "credit": "Synthetic",
            "licence": "CC0",
            "usageNote": "Generated fixture",
        },
    }
    reader = FakeReader(
        item,
        {"assets": {"original": original}, "provenance": provenance},
        body,
    )
    return snapshot, reader


def test_kept_webp_materializes_without_following_dead_origin(tmp_path: Path) -> None:
    snapshot, reader = _case()
    materialized = materialize_research_still(
        snapshot,
        tmp_path / "Media",
        reader=reader,
        research_origin="http://127.0.0.1:43111",
    )

    assert materialized.original_path.suffix == ".webp"
    assert materialized.source_path.suffix == ".png"
    assert materialized.original_path.read_bytes() == reader.body
    assert materialized.original_hash == f"sha256:{snapshot['original']['sha256']}"
    assert materialized.source_hash != materialized.original_hash
    assert Image.open(materialized.source_path).size == (8, 6)
    assert "gone.invalid" not in str(materialized.source_path)


def test_quote_picture_uses_only_the_exact_retained_copy(tmp_path: Path) -> None:
    snapshot, reader = _case()
    pin = {
        "researchProjectId": PROJECT_ID,
        "ownerKind": "source",
        "ownerId": SOURCE_ID,
        "revisionId": ITEM_ID,
        "original": snapshot["original"],
    }
    cache_root = tmp_path / ".local/state/vera/research-quote-pictures"
    cache = cache_root / PROJECT_ID / ITEM_ID
    cache.mkdir(parents=True)
    retained = cache / pin["original"]["sha256"]
    retained.write_bytes(reader.body)
    materialized = materialize_research_quote_picture(
        pin, tmp_path / "Media", home=tmp_path
    )
    assert materialized.original_path.read_bytes() == reader.body
    assert materialized.snapshot["itemId"] == ITEM_ID
    assert "Research Quote Pictures" in materialized.source_path.parts

    retained.write_bytes(bytes(len(reader.body)))
    with pytest.raises(ResearchStillError, match="differ from their pin"):
        materialize_research_quote_picture(pin, tmp_path / "Media", home=tmp_path)


def test_rotated_kept_webp_preserves_original_and_materializes_display_size(
    tmp_path: Path,
) -> None:
    image = Image.new("RGB", (8, 6), (20, 40, 80))
    exif = image.getexif()
    exif[274] = 6
    data = BytesIO()
    image.save(data, format="WEBP", lossless=True, exif=exif.tobytes())
    snapshot, reader = _case(data.getvalue())

    result = materialize_research_still(snapshot, tmp_path / "Media", reader=reader)

    assert result.original_path.read_bytes() == data.getvalue()
    with Image.open(result.source_path) as normalized:
        assert normalized.size == (6, 8)
        assert normalized.getexif().get(274) is None


@pytest.mark.parametrize("mutation", ["project", "version"])
def test_changed_or_cross_project_item_is_refused(mutation: str) -> None:
    snapshot, reader = _case()
    if mutation == "project":
        reader.item["projectId"] = "00000000-0000-4000-8000-000000006734"
    else:
        reader.item["version"] = 8

    with pytest.raises(ResearchStillError, match=r"identity|version|metadata"):
        acquire_research_still(snapshot, reader=reader)


def test_missing_kept_manifest_is_refused() -> None:
    snapshot, reader = _case()
    reader.manifest["assets"] = {}

    with pytest.raises(ResearchStillError, match="original"):
        acquire_research_still(snapshot, reader=reader)


@pytest.mark.parametrize("truncate", [True, False])
def test_corrupt_kept_bytes_are_refused(truncate: bool) -> None:
    snapshot, reader = _case()
    reader.body = (
        reader.body[:-1]
        if truncate
        else reader.body[:-1] + bytes([reader.body[-1] ^ 1])
    )

    with pytest.raises(
        ResearchStillError, match="byte count" if truncate else "SHA-256"
    ):
        acquire_research_still(snapshot, reader=reader)
