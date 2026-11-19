-- The authoring UI needs only the current successful build's music diagnostics.
-- Keep this small projection separate from immutable remote build receipts.
CREATE TABLE stt_project_latest_music_warnings (
  project_id uuid PRIMARY KEY REFERENCES stt_projects(id),
  document_id uuid NOT NULL,
  document_revision bigint NOT NULL CHECK (document_revision >= 0),
  build_id uuid NOT NULL,
  music_warnings jsonb NOT NULL CHECK (
    jsonb_typeof(music_warnings) = 'array' AND jsonb_array_length(music_warnings) <= 32
  ),
  built_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);
