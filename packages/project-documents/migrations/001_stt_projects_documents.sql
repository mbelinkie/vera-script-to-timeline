-- Forward-only Script-to-Timeline project/document service schema.
-- The existing identity/membership migration MUST be applied first. Never
-- add an FK from vera_project_members: other authorized consumers use it.
CREATE TABLE stt_projects (
  id uuid PRIMARY KEY,
  title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 300),
  created_by uuid NOT NULL REFERENCES vera_identity_actors(id),
  client_create_request_id uuid NOT NULL,
  create_request_digest text NOT NULL CHECK (create_request_digest ~ '^sha256:[a-f0-9]{64}$'),
  project_version bigint NOT NULL DEFAULT 1 CHECK (project_version > 0),
  linked_research_project_ids uuid[] NOT NULL DEFAULT '{}'
    CHECK (cardinality(linked_research_project_ids) = 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (created_by, client_create_request_id)
);

CREATE TABLE stt_document_heads (
  project_id uuid PRIMARY KEY REFERENCES stt_projects(id),
  document_id uuid NOT NULL UNIQUE,
  revision bigint NOT NULL CHECK (revision >= 0),
  document_json text NOT NULL,
  content_digest text NOT NULL CHECK (content_digest ~ '^sha256:[a-f0-9]{64}$'),
  updated_by uuid NOT NULL REFERENCES vera_identity_actors(id),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE stt_document_revisions (
  project_id uuid NOT NULL REFERENCES stt_projects(id),
  revision bigint NOT NULL CHECK (revision >= 0),
  document_id uuid NOT NULL,
  expected_revision bigint,
  actor_id uuid NOT NULL REFERENCES vera_identity_actors(id),
  client_mutation_id uuid NOT NULL,
  request_digest text NOT NULL CHECK (request_digest ~ '^sha256:[a-f0-9]{64}$'),
  content_digest text NOT NULL CHECK (content_digest ~ '^sha256:[a-f0-9]{64}$'),
  document_json text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, revision),
  UNIQUE (project_id, actor_id, client_mutation_id)
);

CREATE TABLE stt_project_settings (
  project_id uuid PRIMARY KEY REFERENCES stt_projects(id),
  settings_id uuid NOT NULL UNIQUE,
  settings_revision bigint NOT NULL CHECK (settings_revision > 0),
  settings_json text NOT NULL,
  content_digest text NOT NULL CHECK (content_digest ~ '^sha256:[a-f0-9]{64}$'),
  updated_by uuid NOT NULL REFERENCES vera_identity_actors(id),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE stt_settings_revisions (
  project_id uuid NOT NULL REFERENCES stt_projects(id),
  settings_revision bigint NOT NULL CHECK (settings_revision > 0),
  settings_id uuid NOT NULL,
  expected_revision bigint,
  actor_id uuid NOT NULL REFERENCES vera_identity_actors(id),
  client_mutation_id uuid NOT NULL,
  request_digest text NOT NULL CHECK (request_digest ~ '^sha256:[a-f0-9]{64}$'),
  content_digest text NOT NULL CHECK (content_digest ~ '^sha256:[a-f0-9]{64}$'),
  settings_json text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, settings_revision),
  UNIQUE (project_id, actor_id, client_mutation_id)
);

CREATE TABLE stt_project_title_mutations (
  project_id uuid NOT NULL REFERENCES stt_projects(id),
  project_version bigint NOT NULL CHECK (project_version > 1),
  expected_project_version bigint NOT NULL CHECK (expected_project_version > 0),
  actor_id uuid NOT NULL REFERENCES vera_identity_actors(id),
  client_mutation_id uuid NOT NULL,
  request_digest text NOT NULL CHECK (request_digest ~ '^sha256:[a-f0-9]{64}$'),
  title text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, project_version),
  UNIQUE (project_id, actor_id, client_mutation_id)
);

-- Accepted historical records are never mutable or deletable by the API.
CREATE FUNCTION stt_revision_immutable() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
  RAISE EXCEPTION 'STT revision history is append-only';
END
$body$;
CREATE TRIGGER tr_stt_document_revision_immutable
  BEFORE UPDATE OR DELETE ON stt_document_revisions
  FOR EACH ROW EXECUTE FUNCTION stt_revision_immutable();
CREATE TRIGGER tr_stt_settings_revision_immutable
  BEFORE UPDATE OR DELETE ON stt_settings_revisions
  FOR EACH ROW EXECUTE FUNCTION stt_revision_immutable();
CREATE TRIGGER tr_stt_project_title_mutation_immutable
  BEFORE UPDATE OR DELETE ON stt_project_title_mutations
  FOR EACH ROW EXECUTE FUNCTION stt_revision_immutable();
