-- Additive service-only schema. Project existence is established by #380,
-- so project_id is an external UUID rather than an FK to an unbuilt table.
CREATE TABLE IF NOT EXISTS vera_identity_actors (
    id uuid PRIMARY KEY,
    issuer text NOT NULL CHECK (length(btrim(issuer)) > 0),
    subject text NOT NULL CHECK (length(btrim(subject)) > 0),
    disabled_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (issuer, subject)
);
CREATE TABLE IF NOT EXISTS vera_project_members (
    project_id uuid NOT NULL,
    actor_id uuid NOT NULL REFERENCES vera_identity_actors(id),
    role text NOT NULL CHECK (role IN ('producer', 'editor', 'viewer')),
    active boolean NOT NULL DEFAULT true,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    changed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, actor_id)
);
CREATE INDEX IF NOT EXISTS ix_vera_project_members_current
    ON vera_project_members (actor_id, project_id) WHERE active;
CREATE TABLE IF NOT EXISTS vera_project_write_sessions (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    membership_version integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz,
    FOREIGN KEY (project_id, actor_id)
        REFERENCES vera_project_members(project_id, actor_id)
);
CREATE INDEX IF NOT EXISTS ix_vera_project_write_sessions_active
    ON vera_project_write_sessions(project_id, actor_id)
    WHERE revoked_at IS NULL;
CREATE TABLE IF NOT EXISTS vera_project_membership_audit (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    actor_id uuid NOT NULL REFERENCES vera_identity_actors(id),
    target_actor_id uuid NOT NULL REFERENCES vera_identity_actors(id),
    old_role text,
    new_role text,
    change_kind text NOT NULL CHECK (change_kind IN ('bootstrap', 'grant', 'change', 'revoke')),
    membership_version integer NOT NULL CHECK (membership_version > 0),
    occurred_at timestamptz NOT NULL DEFAULT now()
);
-- Actor attribution cannot be rewritten by normal application operations.
CREATE OR REPLACE FUNCTION vera_membership_audit_immutable()
RETURNS trigger LANGUAGE plpgsql AS $function$
BEGIN
    RAISE EXCEPTION 'membership audit is append-only';
END
$function$;
DO $block$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'tr_vera_membership_audit_immutable'
    ) THEN
        CREATE TRIGGER tr_vera_membership_audit_immutable
        BEFORE UPDATE OR DELETE ON vera_project_membership_audit
        FOR EACH ROW EXECUTE FUNCTION vera_membership_audit_immutable();
    END IF;
END
$block$;
