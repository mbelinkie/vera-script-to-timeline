-- Additive backend-only build/pairing state. Requires the existing
-- authorization and project-documents migrations first.
-- No user or agent credential plaintext and no media/local filesystem paths.

CREATE TABLE stt_build_pairing_offers (
  id uuid PRIMARY KEY,
  project_id uuid NOT NULL REFERENCES stt_projects(id),
  created_by uuid NOT NULL REFERENCES vera_identity_actors(id),
  offer_digest text NOT NULL UNIQUE CHECK (offer_digest ~ '^sha256:[a-f0-9]{64}$'),
  agent_label text NOT NULL CHECK (length(btrim(agent_label)) BETWEEN 1 AND 128),
  protocol_version text NOT NULL CHECK (length(protocol_version) BETWEEN 1 AND 64),
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  consumed_at timestamptz,
  revoked_at timestamptz,
  CHECK (expires_at > created_at),
  UNIQUE (project_id, id)
);

CREATE TABLE stt_project_build_agents (
  id uuid PRIMARY KEY,
  project_id uuid NOT NULL REFERENCES stt_projects(id),
  pairing_offer_id uuid NOT NULL UNIQUE,
  credential_digest text NOT NULL UNIQUE CHECK (credential_digest ~ '^sha256:[a-f0-9]{64}$'),
  credential_version bigint NOT NULL DEFAULT 1 CHECK (credential_version > 0),
  protocol_version text NOT NULL CHECK (length(protocol_version) BETWEEN 1 AND 64),
  capabilities jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(capabilities) = 'object'),
  paired_at timestamptz NOT NULL DEFAULT now(),
  last_heartbeat_at timestamptz,
  revoked_at timestamptz,
  FOREIGN KEY (project_id, pairing_offer_id)
    REFERENCES stt_build_pairing_offers(project_id, id),
  UNIQUE (project_id, id)
);
CREATE INDEX stt_project_build_agents_project_idx
  ON stt_project_build_agents(project_id) WHERE revoked_at IS NULL;

-- Immutable submission: class, frozen bytes, source identity and actor NEVER
-- change after insertion. A service status and lease belong in a separate row.
CREATE TABLE stt_build_submissions (
  id uuid PRIMARY KEY,
  project_id uuid NOT NULL REFERENCES stt_projects(id),
  target_id uuid NOT NULL UNIQUE,
  submitted_by uuid NOT NULL REFERENCES vera_identity_actors(id),
  idempotency_key uuid NOT NULL,
  request_digest text NOT NULL CHECK (request_digest ~ '^sha256:[a-f0-9]{64}$'),
  build_class text NOT NULL CHECK (build_class IN ('preview','release')),
  mode text NOT NULL CHECK (mode IN ('free','studio')),
  expected_revision bigint NOT NULL CHECK (expected_revision >= 0),
  document_id uuid NOT NULL,
  document_json text NOT NULL CHECK (octet_length(document_json) BETWEEN 1 AND 524288),
  document_digest text NOT NULL CHECK (document_digest ~ '^sha256:[a-f0-9]{64}$'),
  settings_revision bigint NOT NULL CHECK (settings_revision > 0),
  settings_json text NOT NULL CHECK (octet_length(settings_json) BETWEEN 1 AND 524288),
  settings_digest text NOT NULL CHECK (settings_digest ~ '^sha256:[a-f0-9]{64}$'),
  snapshot_digest text NOT NULL CHECK (snapshot_digest ~ '^sha256:[a-f0-9]{64}$'),
  submitted_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, id),
  UNIQUE (project_id, submitted_by, idempotency_key)
);
CREATE INDEX stt_build_submissions_project_idx
  ON stt_build_submissions(project_id, submitted_at DESC);

-- This is an *asserted selection* until the server verifies each accepted
-- external dependency against its authoritative source. Never implicitly
-- merge an entire Research project or accept an arbitrary path.
CREATE TABLE stt_build_source_pins (
  project_id uuid NOT NULL,
  job_id uuid NOT NULL,
  source_id uuid NOT NULL,
  source_revision text NOT NULL CHECK (
    length(source_revision) BETWEEN 1 AND 256 AND source_revision = btrim(source_revision)),
  source_digest text NOT NULL CHECK (source_digest ~ '^sha256:[a-f0-9]{64}$'),
  PRIMARY KEY (job_id, source_id),
  FOREIGN KEY (project_id, job_id) REFERENCES stt_build_submissions(project_id, id)
);

-- Service assignment/status mirror only. The local #157 SQLite BuildJobStore
-- continues to own actual stage attempts, stage leases and execution.
CREATE TABLE stt_build_dispatches (
  project_id uuid NOT NULL,
  job_id uuid PRIMARY KEY,
  assigned_agent_id uuid,
  lease_epoch bigint NOT NULL DEFAULT 0 CHECK (lease_epoch >= 0),
  lease_expires_at timestamptz,
  status text NOT NULL DEFAULT 'blocked' CHECK (
    status IN ('blocked','queued','leased','running','needs_action',
      'stale_snapshot','waiting_reconcile','ready_to_import','import_confirmed',
      'verified_package','verified_native','refused','failed','cancelled')),
  reason_code text CHECK (reason_code ~ '^[a-z][a-z0-9_]{0,79}$'),
  updated_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (project_id, job_id) REFERENCES stt_build_submissions(project_id, id),
  FOREIGN KEY (project_id, assigned_agent_id)
    REFERENCES stt_project_build_agents(project_id, id),
  CHECK (assigned_agent_id IS NOT NULL OR lease_expires_at IS NULL)
);
CREATE INDEX stt_build_dispatches_status_idx
  ON stt_build_dispatches(status, lease_expires_at);

-- Untrusted progress claims are NOT a verified native result. Events
-- and evidence are append-only even when a dispatch is cancelled or retried.
CREATE TABLE stt_build_events (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_id uuid NOT NULL,
  job_id uuid NOT NULL,
  agent_id uuid,
  lease_epoch bigint NOT NULL CHECK (lease_epoch >= 0),
  stage_key text CHECK (length(stage_key) BETWEEN 1 AND 256),
  status text NOT NULL CHECK (
    status IN ('accepted','blocked','queued','leased','running','needs_action',
      'stale_snapshot','waiting_reconcile','ready_to_import','import_confirmed',
      'verified_package','verified_native','refused','failed','cancelled')),
  evidence_kind text NOT NULL DEFAULT 'untrusted_report' CHECK (
    evidence_kind IN ('untrusted_report','synthetic','verified_package','native_readback')),
  receipt_digest text CHECK (receipt_digest ~ '^sha256:[a-f0-9]{64}$'),
  reason_code text CHECK (reason_code ~ '^[a-z][a-z0-9_]{0,79}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (project_id, job_id) REFERENCES stt_build_submissions(project_id, id),
  FOREIGN KEY (project_id, agent_id) REFERENCES stt_project_build_agents(project_id, id),
  UNIQUE (id, project_id, job_id)
);
CREATE INDEX stt_build_events_by_job_idx ON stt_build_events(job_id, id);

CREATE TABLE stt_build_evidence (
  id uuid PRIMARY KEY,
  project_id uuid NOT NULL,
  job_id uuid NOT NULL,
  event_id bigint NOT NULL,
  stage_key text NOT NULL CHECK (length(stage_key) BETWEEN 1 AND 256),
  receipt_digest text NOT NULL CHECK (receipt_digest ~ '^sha256:[a-f0-9]{64}$'),
  output_digest text NOT NULL CHECK (output_digest ~ '^sha256:[a-f0-9]{64}$'),
  evidence_kind text NOT NULL CHECK (
    evidence_kind IN ('synthetic','verified_package','native_readback')),
  verification_digest text NOT NULL CHECK (verification_digest ~ '^sha256:[a-f0-9]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (project_id, job_id) REFERENCES stt_build_submissions(project_id, id),
  FOREIGN KEY (event_id, project_id, job_id)
    REFERENCES stt_build_events(id, project_id, job_id),
  UNIQUE (job_id, stage_key, receipt_digest)
);
CREATE INDEX stt_build_evidence_job_idx ON stt_build_evidence(job_id, created_at);

CREATE FUNCTION stt_build_record_immutable() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
  RAISE EXCEPTION 'STT frozen build history is append-only';
END
$body$;
CREATE TRIGGER tr_stt_build_submissions_immutable
  BEFORE UPDATE OR DELETE ON stt_build_submissions
  FOR EACH ROW EXECUTE FUNCTION stt_build_record_immutable();
CREATE TRIGGER tr_stt_build_source_pins_immutable
  BEFORE UPDATE OR DELETE ON stt_build_source_pins
  FOR EACH ROW EXECUTE FUNCTION stt_build_record_immutable();
CREATE TRIGGER tr_stt_build_events_immutable
  BEFORE UPDATE OR DELETE ON stt_build_events
  FOR EACH ROW EXECUTE FUNCTION stt_build_record_immutable();
CREATE TRIGGER tr_stt_build_evidence_immutable
  BEFORE UPDATE OR DELETE ON stt_build_evidence
  FOR EACH ROW EXECUTE FUNCTION stt_build_record_immutable();
