from typing import get_args

from vera_timeline_agent.generated.contracts import (
    PublicPageCaptureApiV1,
    PublicPageCaptureProvenanceV1,
    PublicPageCaptureWorkerV1,
)


def test_generated_public_capture_roots_are_importable() -> None:
    assert len(get_args(PublicPageCaptureApiV1.__value__)) == 12
    assert len(get_args(PublicPageCaptureWorkerV1.__value__)) == 17
    assert PublicPageCaptureProvenanceV1.__value__.__name__ == "ProvenanceRecord"
