-- Forward-only live-collaboration schema (#384). Apply after the project
-- documents, history and Ideas migrations, in the same PostgreSQL database.
-- Binary Yjs data is stored as base64 text so every SQL port reads it alike.

-- One row per project: the merged Yjs state and how it relates to the saved
-- script. document_revision/ideas_revision name the saved heads this state
-- last agreed with; materialized_sequence is the live sequence those heads
-- contain. When it trails live_sequence, the saved script is behind the live
-- text (either not written yet, or the merge cannot be saved as a script).
CREATE TABLE stt_live_heads (
  project_id uuid PRIMARY KEY REFERENCES stt_projects(id),
  live_sequence bigint NOT NULL CHECK (live_sequence > 0),
  state_base64 text NOT NULL,
  document_revision bigint NOT NULL CHECK (document_revision >= 0),
  ideas_revision bigint NOT NULL CHECK (ideas_revision >= 0),
  materialized_sequence bigint NOT NULL CHECK (materialized_sequence >= 0),
  materialization text NOT NULL CHECK (materialization IN ('current', 'pending', 'unstorable')),
  diagnostics_json text NOT NULL DEFAULT '[]',
  last_actor_id uuid NOT NULL REFERENCES vera_identity_actors(id),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (materialized_sequence <= live_sequence)
);

-- Durable, attributed log of every accepted change, in server order.
CREATE TABLE stt_live_updates (
  project_id uuid NOT NULL REFERENCES stt_projects(id),
  live_sequence bigint NOT NULL CHECK (live_sequence > 0),
  actor_id uuid NOT NULL REFERENCES vera_identity_actors(id),
  origin text NOT NULL CHECK (origin IN ('seed', 'client', 'document_save')),
  update_base64 text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, live_sequence)
);

-- Which person owns each Yjs client ID. A client ID never changes owner, so
-- every character in the merged text names exactly one author.
CREATE TABLE stt_live_clients (
  project_id uuid NOT NULL REFERENCES stt_projects(id),
  yjs_client_id bigint NOT NULL CHECK (yjs_client_id >= 0),
  actor_id uuid NOT NULL REFERENCES vera_identity_actors(id),
  origin text NOT NULL CHECK (origin IN ('seed', 'client', 'document_save')),
  first_live_sequence bigint NOT NULL CHECK (first_live_sequence > 0),
  PRIMARY KEY (project_id, yjs_client_id)
);

-- Which live sequence each saved revision was written from.
CREATE TABLE stt_live_materializations (
  project_id uuid NOT NULL REFERENCES stt_projects(id),
  live_sequence bigint NOT NULL CHECK (live_sequence > 0),
  document_revision bigint,
  ideas_revision bigint,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, live_sequence),
  CHECK (document_revision IS NOT NULL OR ideas_revision IS NOT NULL)
);

CREATE TRIGGER tr_stt_live_update_immutable
  BEFORE UPDATE OR DELETE ON stt_live_updates
  FOR EACH ROW EXECUTE FUNCTION stt_revision_immutable();
CREATE TRIGGER tr_stt_live_client_immutable
  BEFORE UPDATE OR DELETE ON stt_live_clients
  FOR EACH ROW EXECUTE FUNCTION stt_revision_immutable();
CREATE TRIGGER tr_stt_live_materialization_immutable
  BEFORE UPDATE OR DELETE ON stt_live_materializations
  FOR EACH ROW EXECUTE FUNCTION stt_revision_immutable();
