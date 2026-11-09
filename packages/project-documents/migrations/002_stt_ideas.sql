-- Independent Ideas sidecar. File number 002 is the Ideas feature's initial
-- migration, NOT a replacement for existing comments 002 or history 003.
-- Apply after existing project-documents migrations; own receipt is version 4.
-- The frozen script-document/v2, compiler and build tables are untouched.

-- A compound FK prevents cross-project Ideas / Draft document mismatches.
CREATE UNIQUE INDEX ux_stt_document_head_project_identity
  ON stt_document_heads(project_id, document_id);

-- Older projects have NO row here, which means a synthetic empty v1 outline
-- at revision 0. First authorized write inserts revision 1 and its head.
CREATE TABLE stt_idea_heads (
  project_id uuid PRIMARY KEY REFERENCES stt_projects(id),
  document_id uuid NOT NULL,
  revision bigint NOT NULL CHECK (revision > 0),
  ideas_json text NOT NULL CHECK (octet_length(ideas_json) BETWEEN 2 AND 524288),
  content_digest text NOT NULL CHECK (content_digest ~ '^sha256:[a-f0-9]{64}$'),
  updated_by uuid NOT NULL REFERENCES vera_identity_actors(id),
  updated_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (project_id, document_id)
    REFERENCES stt_document_heads(project_id, document_id)
);

-- Immutable source-of-truth snapshots; all writes are append-only. CAS on
-- stt_idea_heads and, on promotion, stt_document_heads is done in ONE SQL tx.
CREATE TABLE stt_idea_revisions (
  project_id uuid NOT NULL REFERENCES stt_projects(id),
  revision bigint NOT NULL CHECK (revision > 0),
  expected_revision bigint NOT NULL CHECK (expected_revision >= 0),
  document_id uuid NOT NULL,
  actor_id uuid NOT NULL REFERENCES vera_identity_actors(id),
  client_mutation_id uuid NOT NULL,
  operation text NOT NULL CHECK (operation IN ('put_ideas', 'promote_idea')),
  request_digest text NOT NULL CHECK (request_digest ~ '^sha256:[a-f0-9]{64}$'),
  content_digest text NOT NULL CHECK (content_digest ~ '^sha256:[a-f0-9]{64}$'),
  ideas_json text NOT NULL CHECK (octet_length(ideas_json) BETWEEN 2 AND 524288),
  document_revision bigint,
  document_digest text CHECK (document_digest ~ '^sha256:[a-f0-9]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, revision),
  UNIQUE (project_id, actor_id, client_mutation_id),
  CHECK (revision = expected_revision + 1),
  CHECK ((operation = 'promote_idea') = (document_revision IS NOT NULL)),
  CHECK ((document_revision IS NULL) = (document_digest IS NULL)),
  FOREIGN KEY (project_id, document_id)
    REFERENCES stt_document_heads(project_id, document_id),
  FOREIGN KEY (project_id, document_revision)
    REFERENCES stt_document_revisions(project_id, revision)
);

-- Separate exact operation receipts for replays and cross-endpoint key
-- detection. Each receipt refers to already written immutable snapshots.
CREATE TABLE stt_ideas_mutation_receipts (
  project_id uuid NOT NULL REFERENCES stt_projects(id),
  actor_id uuid NOT NULL REFERENCES vera_identity_actors(id),
  client_mutation_id uuid NOT NULL,
  operation text NOT NULL CHECK (operation IN ('put_ideas', 'promote_idea')),
  request_digest text NOT NULL CHECK (request_digest ~ '^sha256:[a-f0-9]{64}$'),
  ideas_revision bigint NOT NULL,
  ideas_digest text NOT NULL CHECK (ideas_digest ~ '^sha256:[a-f0-9]{64}$'),
  document_revision bigint,
  document_digest text CHECK (document_digest ~ '^sha256:[a-f0-9]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, actor_id, client_mutation_id),
  UNIQUE (project_id, ideas_revision),
  CHECK ((operation = 'promote_idea') = (document_revision IS NOT NULL)),
  CHECK ((document_revision IS NULL) = (document_digest IS NULL)),
  FOREIGN KEY (project_id, ideas_revision)
    REFERENCES stt_idea_revisions(project_id, revision),
  FOREIGN KEY (project_id, document_revision)
    REFERENCES stt_document_revisions(project_id, revision)
);

CREATE TRIGGER tr_stt_idea_revision_immutable
  BEFORE UPDATE OR DELETE ON stt_idea_revisions
  FOR EACH ROW EXECUTE FUNCTION stt_revision_immutable();
CREATE TRIGGER tr_stt_ideas_receipt_immutable
  BEFORE UPDATE OR DELETE ON stt_ideas_mutation_receipts
  FOR EACH ROW EXECUTE FUNCTION stt_revision_immutable();
