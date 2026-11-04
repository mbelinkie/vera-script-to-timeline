export type ProjectRole = "producer" | "editor" | "viewer";
export type ProjectAction =
  | "view_document" | "view_history" | "view_comments" | "view_build_results"
  | "edit_document" | "comment" | "create_checkpoint" | "preview_build"
  | "approve_checkpoint" | "release_build" | "manage_members"
  | "manage_settings" | "link_research" | "choose_release_destination"
  | "apply_regeneration_plan"
  | "capture_create" | "capture_configure" | "capture_read"
  | "capture_request_now" | "capture_request_on_build" | "capture_commit"
  | "capture_select" | "capture_use_preview" | "capture_use_release"
  | "capture_pin";

const VIEWER: readonly string[] = [
  "view_document", "view_history", "view_comments", "view_build_results",
  "capture_read",
];
const EDITOR: readonly string[] = [
  ...VIEWER, "edit_document", "comment", "create_checkpoint", "preview_build",
  "capture_create", "capture_configure", "capture_request_now",
  "capture_request_on_build", "capture_commit", "capture_select",
  "capture_use_preview",
];
const PRODUCER: readonly string[] = [
  ...EDITOR, "approve_checkpoint", "release_build", "manage_members",
  "manage_settings", "link_research", "choose_release_destination",
  "apply_regeneration_plan", "capture_use_release", "capture_pin",
];

// This is a CLOSED permission matrix. Unknown fields/actions/roles are denied.
// In particular, "read_research" is NEVER a valid authorization result.
export function canPerformProjectAction(
  role: unknown,
  action: unknown,
): boolean {
  if (typeof action !== "string") return false;
  switch (role) {
    case "viewer": return VIEWER.includes(action);
    case "editor": return EDITOR.includes(action);
    case "producer": return PRODUCER.includes(action);
    default: return false;
  }
}
