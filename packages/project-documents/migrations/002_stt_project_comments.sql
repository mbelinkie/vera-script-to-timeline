-- Comment state is authoring-only data. Do not add columns to typed document
-- or build tables: a build may read stt_document_heads, never these tables.
-- Migration 001 and the project-authorization migration must already exist.
CREATE TABLE stt_comment_heads (
  project_id uuid PRIMARY KEY REFERENCES stt_projects(id),
  document_id uuid NOT NULL,
  document_revision bigint NOT NULL CHECK (document_revision >= 0),
  comment_revision bigint NOT NULL CHECK (comment_revision >= 0),
  state_json text NOT NULL CHECK (octet_length(state_json) BETWEEN 2 AND 8388608),
  state_digest text NOT NULL CHECK (state_digest ~ '^sha256:[a-f0-9]{64}$'),
  updated_by uuid NOT NULL REFERENCES vera_identity_actors(id),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Only public client operations have event rows. Internal document replaces
-- remain in the replay state, so event revisions can have gaps.
CREATE TABLE stt_comment_events (
  project_id uuid NOT NULL REFERENCES stt_projects(id),
  comment_revision bigint NOT NULL CHECK (comment_revision > 0),
  expected_comment_revision bigint NOT NULL CHECK (expected_comment_revision >= 0),
  document_revision bigint NOT NULL CHECK (document_revision >= 0),
  actor_id uuid NOT NULL REFERENCES vera_identity_actors(id),
  client_mutation_id uuid NOT NULL,
  request_digest text NOT NULL CHECK (request_digest ~ '^sha256:[a-f0-9]{64}$'),
  operation_json text NOT NULL CHECK (octet_length(operation_json) BETWEEN 2 AND 262144),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, comment_revision),
  UNIQUE (project_id, actor_id, client_mutation_id),
  CHECK (comment_revision = expected_comment_revision + 1)
);

CREATE TRIGGER tr_stt_comment_event_immutable
  BEFORE UPDATE OR DELETE ON stt_comment_events
  FOR EACH ROW EXECUTE FUNCTION stt_revision_immutable();
