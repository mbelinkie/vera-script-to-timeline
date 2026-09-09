"""Resolve-launched entry point for the bounded Workflow Integration spike."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .studio_spike import CapabilityResult, run_injected_delivery


def run_workflow_integration(
    resolve: Any,
    attestation_path: Path,
) -> CapabilityResult:
    """Build one uniquely named test project from Resolve's injected object."""
    return run_injected_delivery(
        attestation_path,
        resolve,
        action="startup",
    )
