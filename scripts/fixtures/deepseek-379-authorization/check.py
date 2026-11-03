"""Frozen stdlib-only independent checks for the VERA #379 synthetic fixture.

Uses isolated Python and imports only its explicit sibling target. No GitHub,
network, project code or private data is used. This is not a service-level proof.
"""

import runpy
import unittest
from pathlib import Path

TARGET = Path(__file__).resolve().with_name("target.py")
allows_project_action = runpy.run_path(str(TARGET)).get("allows_project_action")
if not callable(allows_project_action):
    raise RuntimeError("target.py must export callable allows_project_action")

ACTOR = "user-ada"
OTHER_ACTOR = "user-grace"
PROJECT = "project-alpha"
OTHER_PROJECT = "project-beta"
ACTIONS = (
    "view_document",
    "edit_document",
    "comment",
    "preview_authority",
    "release_authority",
    "approve_checkpoint",
    "manage_members",
    "link_research",
    "read_research",
)


def member(role="viewer", **overrides):
    return {
        "userId": ACTOR,
        "projectId": PROJECT,
        "role": role,
        "active": True,
        **overrides,
    }


def decide(action, membership, actor_id=ACTOR, project_id=PROJECT):
    result = allows_project_action(actor_id, project_id, action, membership)
    if type(result) is not bool:
        raise AssertionError(f"Expected actual bool, received {type(result).__name__}")
    return result


class RolePolicyTests(unittest.TestCase):
    def test_viewer_can_only_view_document(self):
        for action in ACTIONS:
            with self.subTest(action=action):
                self.assertIs(decide(action, member("viewer")), action == "view_document")

    def test_editor_can_view_write_comment_and_preview(self):
        permitted = {"view_document", "edit_document", "comment", "preview_authority"}
        for action in ACTIONS:
            with self.subTest(action=action):
                self.assertIs(decide(action, member("editor")), action in permitted)

    def test_producer_has_project_actions_but_not_research_read(self):
        for action in ACTIONS:
            with self.subTest(action=action):
                self.assertIs(decide(action, member("producer")), action != "read_research")

    def test_missing_membership_denies_every_action(self):
        for action in ACTIONS:
            with self.subTest(action=action):
                self.assertIs(decide(action, None), False)

    def test_revoked_member_denies_read_and_write(self):
        for action in ACTIONS:
            with self.subTest(action=action):
                self.assertIs(decide(action, member("producer", active=False)), False)

    def test_every_request_uses_supplied_current_membership(self):
        self.assertIs(decide("edit_document", member("editor")), True)
        self.assertIs(decide("edit_document", member("viewer")), False)
        self.assertIs(decide("edit_document", member("editor", active=False)), False)

    def test_other_user_membership_does_not_grant_access(self):
        self.assertIs(decide("view_document", member("producer", userId=OTHER_ACTOR)), False)
        self.assertIs(decide("release_authority", member("producer", userId=OTHER_ACTOR)), False)

    def test_other_project_membership_does_not_grant_access(self):
        self.assertIs(decide("view_document", member("producer", projectId=OTHER_PROJECT)), False)
        self.assertIs(decide("release_authority", member("producer", projectId=OTHER_PROJECT)), False)

    def test_research_link_does_not_confer_research_read_access(self):
        self.assertIs(decide("link_research", member("producer")), True)
        self.assertIs(decide("read_research", member("producer", linkedResearchProjectIds=["research-1"])), False)
        self.assertIs(decide("read_research", member("editor")), False)

    def test_unknown_action_is_denied_without_wildcards(self):
        for action in ("", "delete_all", "create_release", "View_Document", "*"):
            with self.subTest(action=action):
                self.assertIs(decide(action, member("producer")), False)

    def test_role_names_are_closed_and_case_sensitive(self):
        for role in ("admin", "owner", "Producer", "EDITOR", "", None, 1):
            with self.subTest(role=role):
                self.assertIs(decide("view_document", member(role)), False)

    def test_actor_and_project_ids_must_be_nonempty_exact_strings(self):
        for bad in (None, "", "  ", 12, [ACTOR], f" {ACTOR}"):
            with self.subTest(bad=bad):
                self.assertIs(decide("view_document", member("producer"), actor_id=bad), False)
                self.assertIs(decide("view_document", member("producer"), project_id=bad), False)

    def test_missing_membership_fields_fail_closed(self):
        complete = member("producer")
        for key in ("userId", "projectId", "role", "active"):
            partial = {k: v for k, v in complete.items() if k != key}
            with self.subTest(missing=key):
                self.assertIs(decide("view_document", partial), False)

    def test_malformed_membership_payload_fails_closed(self):
        for payload in ([], "producer", 1, True, object()):
            with self.subTest(payload_type=type(payload).__name__):
                self.assertIs(decide("view_document", payload), False)

    def test_active_flag_requires_literal_true(self):
        for flag in (1, "true", "yes", None, [], False):
            with self.subTest(flag=repr(flag)):
                self.assertIs(decide("view_document", member("producer", active=flag)), False)

    def test_invalid_action_values_fail_closed(self):
        for action in (None, 1, [], {"name": "view_document"}):
            with self.subTest(action_type=type(action).__name__):
                self.assertIs(decide(action, member("producer")), False)

    def test_no_implicit_membership_via_link_or_owner_fields(self):
        payload = {"ownerUserId": ACTOR, "linkedResearchProjectIds": ["research-1"]}
        self.assertIs(decide("view_document", payload), False)
        self.assertIs(decide("read_research", payload), False)


if __name__ == "__main__":
    unittest.main(failfast=True, verbosity=1)
