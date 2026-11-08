-- When #380 has no settings yet, no immutable build snapshot may be fabricated.
-- Retain a scoped, append-only refusal instead. It is NOT a dispatch or job.
CREATE TABLE stt_build_preflight_refusals (
  project_id uuid NOT NULL REFERENCES stt_projects(id),
  submitted_by uuid NOT NULL REFERENCES vera_identity_actors(id),
  idempotency_key uuid NOT NULL,
  request_digest text NOT NULL CHECK (request_digest ~ '^sha256:[a-f0-9]{64}$'),
  expected_revision bigint NOT NULL CHECK (expected_revision >= 0),
  reason_code text NOT NULL CHECK (reason_code IN ('settings_unavailable')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, submitted_by, idempotency_key)
);
CREATE TRIGGER tr_stt_build_preflight_refusals_immutable
  BEFORE UPDATE OR DELETE ON stt_build_preflight_refusals
  FOR EACH ROW EXECUTE FUNCTION stt_build_record_immutable();
