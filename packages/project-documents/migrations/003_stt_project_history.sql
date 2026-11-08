-- Forward-only attributed document history extensions. Authorization, project
-- documents 001 and comments 002 must be installed before this migration.
-- Revision rows in 001 already carry actor, mutation ID, server order and time;
-- do not duplicate them or change the immutable history they represent.

CREATE TABLE stt_document_checkpoints (
  project_id uuid NOT NULL REFERENCES stt_projects(id),
  checkpoint_id uuid NOT NULL,
  name text NOT NULL CHECK (length(name) BETWEEN 1 AND 120 AND name = btrim(name)),
  source_revision bigint NOT NULL CHECK (source_revision >= 0),
  document_id uuid NOT NULL,
  document_json text NOT NULL CHECK (octet_length(document_json) BETWEEN 2 AND 8388608),
  source_digest text NOT NULL CHECK (source_digest ~ '^sha256:[a-f0-9]{64}$'),
  created_by uuid NOT NULL REFERENCES vera_identity_actors(id),
  client_mutation_id uuid NOT NULL,
  request_digest text NOT NULL CHECK (request_digest ~ '^sha256:[a-f0-9]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, checkpoint_id),
  UNIQUE (project_id, created_by, client_mutation_id),
  -- Preserve the checkpoint's source tuple for restore provenance FKs.
  UNIQUE (project_id, checkpoint_id, source_revision, source_digest),
  FOREIGN KEY (project_id, source_revision)
    REFERENCES stt_document_revisions(project_id, revision)
);

CREATE UNIQUE INDEX ux_stt_checkpoint_name
  ON stt_document_checkpoints(project_id, lower(name));

-- Approval is a separate append-only Producer action, never inherited by a
-- restored head or inferred from the snapshot or the checkpoint creator.
CREATE TABLE stt_checkpoint_approvals (
  project_id uuid NOT NULL,
  checkpoint_id uuid NOT NULL,
  approved_by uuid NOT NULL REFERENCES vera_identity_actors(id),
  client_mutation_id uuid NOT NULL,
  request_digest text NOT NULL CHECK (request_digest ~ '^sha256:[a-f0-9]{64}$'),
  approved_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, checkpoint_id),
  UNIQUE (project_id, approved_by, client_mutation_id),
  FOREIGN KEY (project_id, checkpoint_id)
    REFERENCES stt_document_checkpoints(project_id, checkpoint_id)
);

-- Restore is provenance for a newly INSERTed revision in 001, not an update
-- of a checkpoint, source revision or existing live-head history row.
CREATE TABLE stt_document_restores (
  project_id uuid NOT NULL,
  new_revision bigint NOT NULL CHECK (new_revision > 0),
  checkpoint_id uuid NOT NULL,
  source_revision bigint NOT NULL CHECK (source_revision >= 0),
  source_digest text NOT NULL CHECK (source_digest ~ '^sha256:[a-f0-9]{64}$'),
  restored_by uuid NOT NULL REFERENCES vera_identity_actors(id),
  client_mutation_id uuid NOT NULL,
  restored_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, new_revision),
  UNIQUE (project_id, restored_by, client_mutation_id),
  FOREIGN KEY (project_id, new_revision)
    REFERENCES stt_document_revisions(project_id, revision),
  FOREIGN KEY (project_id, checkpoint_id, source_revision, source_digest)
    REFERENCES stt_document_checkpoints(project_id, checkpoint_id, source_revision, source_digest)
);

CREATE TRIGGER tr_stt_checkpoint_immutable
  BEFORE UPDATE OR DELETE ON stt_document_checkpoints
  FOR EACH ROW EXECUTE FUNCTION stt_revision_immutable();
CREATE TRIGGER tr_stt_checkpoint_approval_immutable
  BEFORE UPDATE OR DELETE ON stt_checkpoint_approvals
  FOR EACH ROW EXECUTE FUNCTION stt_revision_immutable();
CREATE TRIGGER tr_stt_document_restore_immutable
  BEFORE UPDATE OR DELETE ON stt_document_restores
  FOR EACH ROW EXECUTE FUNCTION stt_revision_immutable();
