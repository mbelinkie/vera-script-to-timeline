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

    Viewer may view_document; editor may also edit_document, comment and
    preview_authority. Producer may additionally release_authority,
    approve_checkpoint, manage_members and link_research. Never allow
    read_research. Require matching nonempty, whitespace-trimmed string IDs,
    literal active=True, a known role and action; otherwise return False.
    Ignore extra membership fields. The sibling check defines the examples.
    """
    raise NotImplementedError("DeepSeek #379 synthetic authorization task pending")
