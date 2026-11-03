"""Synthetic, intentionally unimplemented VERA #379 role-policy target.

This is a calibration fixture, NOT the suite authorization service.
"""


def allows_project_action(
    actor_id: object,
    project_id: object,
    action: object,
    membership: object,
) -> bool:
    """Decide role authority using a *current* single-project membership record.

    The complete behavior is defined by the frozen sibling check and README.
    """
    raise NotImplementedError("DeepSeek #379 synthetic authorization task pending")
