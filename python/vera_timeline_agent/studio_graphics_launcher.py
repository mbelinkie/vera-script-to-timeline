"""EV24 entry point through #109's audited operator-request runner."""

from pathlib import Path
from typing import Any

from .studio_graphics_workflow import (
    GRAPHIC_REQUEST,
    load_graphic_handoff,
    run_graphic_delivery,
)
from .workflow_launcher import run_installed_request as run_delivery_request


def run_installed_request(
    resolve: Any, request_path: Path, *, expected_request_sha256: str
) -> Path:
    return run_delivery_request(
        resolve,
        request_path,
        expected_request_sha256=expected_request_sha256,
        package_loader=load_graphic_handoff,
        runner=run_graphic_delivery,
        request_schema=GRAPHIC_REQUEST,
    )
