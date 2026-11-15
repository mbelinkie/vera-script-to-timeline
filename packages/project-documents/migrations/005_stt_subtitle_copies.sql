-- Additive, per-Research-occurrence English subtitle-copy sidecar. The script
-- document and Research source snapshot remain unchanged. Every accepted copy
-- (including superseded/stale/orphan copies) lives in immutable revisions.
-- Requires identity and project-document migration 001; never cascade history.

CREATE TABLE stt_subtitle_copy_revisions (
  project_id uuid NOT NULL REFERENCES stt_projects(id),
  occurrence_id uuid NOT NULL,
  track_id uuid NOT NULL,
  revision bigint NOT NULL CHECK (revision > 0),
  expected_revision bigint NOT NULL CHECK (expected_revision >= 0),
  operation text NOT NULL CHECK (operation IN ('derive', 'edit', 'approve', 'rederive')),
  actor_id uuid NOT NULL REFERENCES vera_identity_actors(id),
  client_mutation_id uuid NOT NULL,
  request_digest text NOT NULL CHECK (request_digest ~ '^sha256:[a-f0-9]{64}$'),
  -- These frozen bytes are Research provenance, not mutable script-owned copy.
  source_json text NOT NULL CHECK (octet_length(source_json) BETWEEN 2 AND 2097152),
  source_digest text NOT NULL CHECK (source_digest ~ '^sha256:[a-f0-9]{64}$'),
  baseline_english text NOT NULL CHECK (length(btrim(baseline_english)) > 0),
  track_json text NOT NULL CHECK (octet_length(track_json) BETWEEN 2 AND 4194304),
  content_digest text NOT NULL CHECK (content_digest ~ '^sha256:[a-f0-9]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, occurrence_id, revision),
  UNIQUE (project_id, actor_id, client_mutation_id),
  -- A head may point only at a revision matching its exact source and content.
  UNIQUE (project_id, occurrence_id, track_id, revision, source_digest, content_digest),
  CHECK (revision = expected_revision + 1),
  CHECK ((revision = 1) = (operation = 'derive'))
);

-- Enforce contiguous history and source/baseline immutability at the DB
-- boundary, even when a caller bypasses the authorized application service.
-- Only an explicit rederive can move to a different pinned Research source.
CREATE FUNCTION stt_subtitle_copy_revision_guard() RETURNS trigger LANGUAGE plpgsql AS $body$
DECLARE
  previous stt_subtitle_copy_revisions%ROWTYPE;
BEGIN
  IF NEW.revision > 1 THEN
    SELECT * INTO previous FROM stt_subtitle_copy_revisions
      WHERE project_id = NEW.project_id AND occurrence_id = NEW.occurrence_id
        AND revision = NEW.expected_revision;
    IF NOT FOUND OR previous.track_id <> NEW.track_id THEN
      RAISE EXCEPTION 'STT subtitle copy revision history is not contiguous';
    END IF;
    IF NEW.operation = 'rederive' THEN
      IF previous.source_digest = NEW.source_digest THEN
        RAISE EXCEPTION 'STT subtitle rederive requires changed source';
      END IF;
    ELSIF previous.source_digest <> NEW.source_digest OR
          previous.source_json <> NEW.source_json OR
          previous.baseline_english <> NEW.baseline_english THEN
      RAISE EXCEPTION 'STT subtitle source provenance is immutable';
    END IF;
  END IF;
  RETURN NEW;
END
$body$;

CREATE TRIGGER tr_stt_subtitle_copy_revision_guard
  BEFORE INSERT ON stt_subtitle_copy_revisions
  FOR EACH ROW EXECUTE FUNCTION stt_subtitle_copy_revision_guard();
CREATE TRIGGER tr_stt_subtitle_copy_revision_immutable
  BEFORE UPDATE OR DELETE ON stt_subtitle_copy_revisions
  FOR EACH ROW EXECUTE FUNCTION stt_revision_immutable();

-- Mutable CAS pointer only: no source or English text is stored exclusively
-- here. The matching immutable revision is the source of truth for reads.
CREATE TABLE stt_subtitle_copy_heads (
  project_id uuid NOT NULL REFERENCES stt_projects(id),
  occurrence_id uuid NOT NULL,
  track_id uuid NOT NULL,
  revision bigint NOT NULL CHECK (revision > 0),
  source_digest text NOT NULL CHECK (source_digest ~ '^sha256:[a-f0-9]{64}$'),
  content_digest text NOT NULL CHECK (content_digest ~ '^sha256:[a-f0-9]{64}$'),
  updated_by uuid NOT NULL REFERENCES vera_identity_actors(id),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, occurrence_id),
  UNIQUE (project_id, track_id),
  FOREIGN KEY (project_id, occurrence_id, track_id, revision, source_digest, content_digest)
    REFERENCES stt_subtitle_copy_revisions(
      project_id, occurrence_id, track_id, revision, source_digest, content_digest)
);

CREATE FUNCTION stt_subtitle_copy_head_guard() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'STT subtitle copy heads cannot be deleted';
  END IF;
  IF TG_OP = 'INSERT' THEN
    IF NEW.revision <> 1 THEN
      RAISE EXCEPTION 'STT subtitle copy head must start at revision 1';
    END IF;
  ELSIF NEW.project_id <> OLD.project_id OR
        NEW.occurrence_id <> OLD.occurrence_id OR
        NEW.track_id <> OLD.track_id OR
        NEW.revision <> OLD.revision + 1 THEN
    RAISE EXCEPTION 'STT subtitle copy head requires next-revision CAS';
  END IF;
  RETURN NEW;
END
$body$;

CREATE TRIGGER tr_stt_subtitle_copy_head_guard
  BEFORE INSERT OR UPDATE OR DELETE ON stt_subtitle_copy_heads
  FOR EACH ROW EXECUTE FUNCTION stt_subtitle_copy_head_guard();
