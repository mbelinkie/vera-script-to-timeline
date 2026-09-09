CREATE TABLE public_page_capture_settings (
    setting_name text PRIMARY KEY,
    enabled boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO public_page_capture_settings (setting_name, enabled)
VALUES ('public_page_capture_execution', false);

CREATE TABLE captures (
    project_id uuid NOT NULL,
    capture_id uuid NOT NULL,
    state text NOT NULL DEFAULT 'draft',
    current_configuration_version bigint NOT NULL,
    next_revision_number bigint NOT NULL DEFAULT 1,
    row_version bigint NOT NULL DEFAULT 1,
    created_by_kind text NOT NULL,
    created_by_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_captures PRIMARY KEY (project_id, capture_id),
    CONSTRAINT ck_capture_state
        CHECK (state IN ('draft', 'active', 'paused', 'retired')),
    CONSTRAINT ck_capture_versions_positive
        CHECK (
            current_configuration_version > 0
            AND next_revision_number > 0
            AND row_version > 0
        ),
    CONSTRAINT ck_capture_creator_kind
        CHECK (created_by_kind IN ('user', 'service'))
);

CREATE TABLE capture_configurations (
    project_id uuid NOT NULL,
    capture_id uuid NOT NULL,
    configuration_version bigint NOT NULL,
    schema_version text NOT NULL,
    canonical_url_digest bytea NOT NULL,
    redacted_url_display text NOT NULL,
    query_key_names jsonb NOT NULL,
    restricted_request_envelope bytea NOT NULL,
    restricted_request_key_version integer NOT NULL,
    region_intent jsonb NOT NULL,
    acquisition_policy text NOT NULL,
    periodic_execution_enabled boolean NOT NULL DEFAULT false,
    capture_profile_id uuid NOT NULL,
    capture_profile_version bigint NOT NULL,
    settings_json jsonb NOT NULL,
    settings_digest bytea NOT NULL,
    previous_configuration_digest bytea,
    created_by_kind text NOT NULL,
    created_by_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_capture_configuration_version
        PRIMARY KEY (project_id, capture_id, configuration_version),
    CONSTRAINT fk_capture_configuration_capture
        FOREIGN KEY (project_id, capture_id)
        REFERENCES captures (project_id, capture_id),
    CONSTRAINT ck_capture_configuration_schema
        CHECK (schema_version = 'public-page-capture-api/v1'),
    CONSTRAINT ck_capture_configuration_digests
        CHECK (
            octet_length(canonical_url_digest) = 32
            AND octet_length(settings_digest) = 32
            AND (
                previous_configuration_digest IS NULL
                OR octet_length(previous_configuration_digest) = 32
            )
        ),
    CONSTRAINT ck_capture_configuration_redacted_url
        CHECK (
            char_length(redacted_url_display) BETWEEN 1 AND 2048
            AND redacted_url_display !~* '(access_token|api[_-]?key|auth|credential|jwt|password|secret|session|sig(nature)?|token)=[^&[:space:]]+'
        ),
    CONSTRAINT ck_capture_configuration_json
        CHECK (
            jsonb_typeof(query_key_names) = 'array'
            AND jsonb_typeof(region_intent) = 'object'
            AND jsonb_typeof(settings_json) = 'object'
        ),
    CONSTRAINT ck_capture_configuration_policy
        CHECK (
            acquisition_policy IN ('now', 'on_build', 'periodic_reserved')
            AND (
                acquisition_policy <> 'periodic_reserved'
                OR periodic_execution_enabled = false
            )
        ),
    CONSTRAINT ck_capture_configuration_positive
        CHECK (
            configuration_version > 0
            AND restricted_request_key_version > 0
            AND capture_profile_version > 0
        ),
    CONSTRAINT ck_capture_configuration_creator_kind
        CHECK (created_by_kind IN ('user', 'service'))
);

ALTER TABLE captures
    ADD CONSTRAINT fk_capture_current_configuration
    FOREIGN KEY (
        project_id,
        capture_id,
        current_configuration_version
    )
    REFERENCES capture_configurations (
        project_id,
        capture_id,
        configuration_version
    )
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE capture_jobs (
    project_id uuid NOT NULL,
    job_id uuid NOT NULL,
    capture_id uuid NOT NULL,
    configuration_version bigint NOT NULL,
    trigger_kind text NOT NULL,
    trigger_reference_kind text,
    trigger_reference_id uuid,
    trigger_reference_digest bytea,
    initiating_principal_kind text NOT NULL,
    initiating_principal_id uuid NOT NULL,
    initiating_role text NOT NULL,
    commit_recheck_mode text NOT NULL,
    authorization_decision_id uuid NOT NULL,
    membership_version bigint,
    authorization_decided_at timestamptz NOT NULL,
    request_id uuid NOT NULL,
    idempotency_key_digest bytea NOT NULL,
    request_fingerprint bytea NOT NULL,
    settings_json jsonb NOT NULL,
    settings_digest bytea NOT NULL,
    capture_profile_id uuid NOT NULL,
    capture_profile_version bigint NOT NULL,
    capture_profile_json jsonb NOT NULL,
    profile_digest bytea NOT NULL,
    retry_budget integer NOT NULL,
    conditional_selection_intent jsonb,
    state text NOT NULL,
    output_revision_id uuid,
    row_version bigint NOT NULL DEFAULT 1,
    requested_at timestamptz NOT NULL,
    enqueued_at timestamptz,
    available_at timestamptz,
    terminal_at timestamptz,
    CONSTRAINT pk_capture_jobs PRIMARY KEY (project_id, job_id),
    CONSTRAINT uq_capture_job_capture
        UNIQUE (project_id, job_id, capture_id),
    CONSTRAINT fk_capture_job_configuration
        FOREIGN KEY (project_id, capture_id, configuration_version)
        REFERENCES capture_configurations (
            project_id,
            capture_id,
            configuration_version
        ),
    CONSTRAINT ck_capture_job_trigger
        CHECK (
            trigger_kind IN ('now', 'on_build')
            AND (
                (
                    trigger_kind = 'now'
                    AND trigger_reference_kind = 'command'
                    AND trigger_reference_id IS NOT NULL
                    AND trigger_reference_digest IS NULL
                )
                OR (
                    trigger_kind = 'on_build'
                    AND trigger_reference_kind IN ('preview_build', 'release_build')
                    AND trigger_reference_id IS NOT NULL
                    AND octet_length(trigger_reference_digest) = 32
                )
            )
        ),
    CONSTRAINT ck_capture_job_state
        CHECK (
            state IN (
                'requested',
                'queued',
                'leased',
                'running',
                'committed_ready',
                'committed_review_required',
                'rejected',
                'failed',
                'cancelled'
            )
        ),
    CONSTRAINT ck_capture_job_output
        CHECK (
            (
                state IN ('committed_ready', 'committed_review_required')
                AND output_revision_id IS NOT NULL
                AND terminal_at IS NOT NULL
            )
            OR (
                state NOT IN ('committed_ready', 'committed_review_required')
                AND output_revision_id IS NULL
                AND (
                    state NOT IN ('rejected', 'failed', 'cancelled')
                    OR terminal_at IS NOT NULL
                )
            )
        ),
    CONSTRAINT ck_capture_job_digests
        CHECK (
            octet_length(idempotency_key_digest) = 32
            AND octet_length(request_fingerprint) = 32
            AND octet_length(settings_digest) = 32
            AND octet_length(profile_digest) = 32
        ),
    CONSTRAINT ck_capture_job_json
        CHECK (
            jsonb_typeof(settings_json) = 'object'
            AND jsonb_typeof(capture_profile_json) = 'object'
            AND (
                conditional_selection_intent IS NULL
                OR jsonb_typeof(conditional_selection_intent) = 'object'
            )
        ),
    CONSTRAINT ck_capture_job_authorization
        CHECK (
            initiating_principal_kind IN ('user', 'service')
            AND initiating_role IN ('producer', 'editor', 'viewer', 'service')
            AND commit_recheck_mode IN (
                'every_request',
                'commit_time',
                'immutable_reference'
            )
        ),
    CONSTRAINT ck_capture_job_positive
        CHECK (
            capture_profile_version > 0
            AND retry_budget BETWEEN 0 AND 8
            AND row_version > 0
            AND (membership_version IS NULL OR membership_version > 0)
        )
);

ALTER TABLE capture_jobs
    ADD CONSTRAINT uq_capture_job_idempotency_scope
    UNIQUE (
        project_id,
        capture_id,
        initiating_principal_id,
        trigger_kind,
        idempotency_key_digest
    );

CREATE UNIQUE INDEX uq_capture_job_build
    ON capture_jobs (
        project_id,
        capture_id,
        trigger_reference_kind,
        trigger_reference_id,
        trigger_reference_digest
    )
    WHERE trigger_kind = 'on_build';

CREATE TABLE capture_leases (
    project_id uuid NOT NULL,
    lease_id uuid NOT NULL,
    job_id uuid NOT NULL,
    capture_id uuid NOT NULL,
    epoch bigint NOT NULL,
    worker_installation_id uuid NOT NULL,
    capability_jti_digest bytea NOT NULL,
    capability_scope_digest bytea NOT NULL,
    state text NOT NULL,
    issued_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    heartbeat_at timestamptz,
    terminal_at timestamptz,
    row_version bigint NOT NULL DEFAULT 1,
    CONSTRAINT pk_capture_leases PRIMARY KEY (project_id, lease_id),
    CONSTRAINT uq_capture_lease_job
        UNIQUE (project_id, lease_id, job_id, capture_id),
    CONSTRAINT fk_capture_lease_job
        FOREIGN KEY (project_id, job_id, capture_id)
        REFERENCES capture_jobs (project_id, job_id, capture_id),
    CONSTRAINT uq_capture_lease_epoch
        UNIQUE (project_id, job_id, epoch),
    CONSTRAINT uq_capture_lease_jti
        UNIQUE (capability_jti_digest),
    CONSTRAINT ck_capture_lease_state
        CHECK (state IN ('issued', 'active', 'released', 'expired', 'revoked')),
    CONSTRAINT ck_capture_lease_digests
        CHECK (
            octet_length(capability_jti_digest) = 32
            AND octet_length(capability_scope_digest) = 32
        ),
    CONSTRAINT ck_capture_lease_time
        CHECK (
            epoch > 0
            AND row_version > 0
            AND expires_at > issued_at
            AND (
                state IN ('issued', 'active')
                OR terminal_at IS NOT NULL
            )
        )
);

CREATE UNIQUE INDEX uq_capture_active_lease
    ON capture_leases (project_id, job_id)
    WHERE state IN ('issued', 'active');

CREATE TABLE capture_attempts (
    project_id uuid NOT NULL,
    attempt_id uuid NOT NULL,
    job_id uuid NOT NULL,
    capture_id uuid NOT NULL,
    lease_id uuid NOT NULL,
    attempt_number integer NOT NULL,
    state text NOT NULL,
    clean_profile_id uuid NOT NULL,
    browser_version text NOT NULL,
    adapter_version text NOT NULL,
    security_policy_version text NOT NULL,
    profile_version bigint NOT NULL,
    profile_digest bytea NOT NULL,
    started_at timestamptz NOT NULL,
    navigation_started_at timestamptz,
    staged_at timestamptz,
    terminal_at timestamptz,
    terminal_code text,
    diagnostic_digest bytea,
    row_version bigint NOT NULL DEFAULT 1,
    CONSTRAINT pk_capture_attempts PRIMARY KEY (project_id, attempt_id),
    CONSTRAINT uq_capture_attempt_job
        UNIQUE (project_id, attempt_id, job_id, capture_id),
    CONSTRAINT fk_capture_attempt_job
        FOREIGN KEY (project_id, job_id, capture_id)
        REFERENCES capture_jobs (project_id, job_id, capture_id),
    CONSTRAINT fk_capture_attempt_lease
        FOREIGN KEY (project_id, lease_id, job_id, capture_id)
        REFERENCES capture_leases (project_id, lease_id, job_id, capture_id),
    CONSTRAINT uq_capture_attempt_lease
        UNIQUE (project_id, lease_id),
    CONSTRAINT uq_capture_attempt_number
        UNIQUE (project_id, job_id, attempt_number),
    CONSTRAINT ck_capture_attempt_state
        CHECK (
            state IN (
                'started',
                'staged',
                'committed',
                'failed',
                'cancelled',
                'abandoned'
            )
        ),
    CONSTRAINT ck_capture_attempt_profile_digest
        CHECK (octet_length(profile_digest) = 32),
    CONSTRAINT ck_capture_attempt_diagnostic
        CHECK (
            diagnostic_digest IS NULL
            OR octet_length(diagnostic_digest) = 32
        ),
    CONSTRAINT ck_capture_attempt_positive
        CHECK (
            attempt_number > 0
            AND profile_version > 0
            AND row_version > 0
        ),
    CONSTRAINT ck_capture_attempt_terminal
        CHECK (
            (
                state IN ('failed', 'cancelled', 'abandoned')
                AND terminal_at IS NOT NULL
                AND terminal_code IS NOT NULL
            )
            OR state NOT IN ('failed', 'cancelled', 'abandoned')
        )
);

CREATE TABLE capture_artifacts (
    project_id uuid NOT NULL,
    artifact_id uuid NOT NULL,
    kind text NOT NULL,
    access_class text NOT NULL,
    object_store_id uuid NOT NULL,
    digest bytea NOT NULL,
    byte_length bigint NOT NULL,
    mime_type text NOT NULL,
    width integer,
    height integer,
    encoding text,
    color text,
    alpha text,
    provenance_schema text,
    verifier_profile text NOT NULL,
    verifier_version integer NOT NULL,
    verified_at timestamptz NOT NULL,
    encryption_key_version integer NOT NULL,
    created_by_service_id uuid NOT NULL,
    created_at timestamptz NOT NULL,
    CONSTRAINT pk_capture_artifacts PRIMARY KEY (project_id, artifact_id),
    CONSTRAINT uq_capture_artifact_object
        UNIQUE (project_id, object_store_id),
    CONSTRAINT ck_capture_artifact_kind
        CHECK (
            (
                kind = 'capture_raster'
                AND access_class = 'project_visual'
                AND mime_type = 'image/png'
                AND width > 0
                AND height > 0
                AND encoding = 'png'
                AND color = 'srgb'
                AND alpha IN ('opaque', 'present')
                AND provenance_schema IS NULL
            )
            OR (
                kind = 'capture_provenance'
                AND access_class = 'restricted_provenance'
                AND mime_type = 'application/json'
                AND width IS NULL
                AND height IS NULL
                AND encoding = 'json'
                AND color = 'not_applicable'
                AND alpha = 'not_applicable'
                AND provenance_schema = 'public-page-capture-provenance/v1'
            )
        ),
    CONSTRAINT ck_capture_artifact_integrity
        CHECK (
            octet_length(digest) = 32
            AND byte_length > 0
            AND verifier_version > 0
            AND encryption_key_version > 0
        )
);

ALTER TABLE capture_artifacts
    ADD CONSTRAINT uq_capture_artifact_exact_candidate
    UNIQUE NULLS NOT DISTINCT (
        project_id,
        kind,
        digest,
        byte_length,
        mime_type,
        width,
        height,
        encoding,
        color,
        alpha,
        verifier_profile,
        verifier_version
    );

CREATE TABLE capture_provenance_manifests (
    project_id uuid NOT NULL,
    provenance_id uuid NOT NULL,
    capture_id uuid NOT NULL,
    job_id uuid NOT NULL,
    attempt_id uuid NOT NULL,
    evidence_type text NOT NULL,
    provenance_artifact_id uuid NOT NULL,
    schema_version text NOT NULL,
    manifest_digest bytea NOT NULL,
    manifest_length bigint NOT NULL,
    redaction_version text NOT NULL,
    sanitized_summary jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    CONSTRAINT pk_capture_provenance_manifests
        PRIMARY KEY (project_id, provenance_id),
    CONSTRAINT uq_capture_provenance_artifact
        UNIQUE (project_id, provenance_artifact_id),
    CONSTRAINT uq_capture_provenance_attempt
        UNIQUE (project_id, attempt_id),
    CONSTRAINT fk_capture_provenance_attempt
        FOREIGN KEY (project_id, attempt_id, job_id, capture_id)
        REFERENCES capture_attempts (
            project_id,
            attempt_id,
            job_id,
            capture_id
        ),
    CONSTRAINT fk_capture_provenance_artifact
        FOREIGN KEY (project_id, provenance_artifact_id)
        REFERENCES capture_artifacts (project_id, artifact_id),
    CONSTRAINT ck_capture_provenance_evidence
        CHECK (
            evidence_type IN (
                'revision_observation',
                'terminal_attempt_evidence'
            )
        ),
    CONSTRAINT ck_capture_provenance_schema
        CHECK (
            schema_version = 'public-page-capture-provenance/v1'
            AND redaction_version = 'vera-url-redaction-v1'
        ),
    CONSTRAINT ck_capture_provenance_integrity
        CHECK (
            octet_length(manifest_digest) = 32
            AND manifest_length > 0
            AND jsonb_typeof(sanitized_summary) = 'object'
        )
);

CREATE TABLE capture_revisions (
    project_id uuid NOT NULL,
    revision_id uuid NOT NULL,
    capture_id uuid NOT NULL,
    configuration_version bigint NOT NULL,
    job_id uuid NOT NULL,
    winning_attempt_id uuid NOT NULL,
    revision_number bigint NOT NULL,
    raster_artifact_id uuid NOT NULL,
    provenance_id uuid NOT NULL,
    status text NOT NULL,
    settings_digest bytea NOT NULL,
    profile_digest bytea NOT NULL,
    committed_at timestamptz NOT NULL,
    CONSTRAINT pk_capture_revisions PRIMARY KEY (project_id, revision_id),
    CONSTRAINT uq_capture_revision_capture
        UNIQUE (project_id, revision_id, capture_id),
    CONSTRAINT fk_capture_revision_configuration
        FOREIGN KEY (project_id, capture_id, configuration_version)
        REFERENCES capture_configurations (
            project_id,
            capture_id,
            configuration_version
        ),
    CONSTRAINT fk_capture_revision_job
        FOREIGN KEY (project_id, job_id, capture_id)
        REFERENCES capture_jobs (project_id, job_id, capture_id),
    CONSTRAINT fk_capture_revision_attempt
        FOREIGN KEY (project_id, winning_attempt_id, job_id, capture_id)
        REFERENCES capture_attempts (
            project_id,
            attempt_id,
            job_id,
            capture_id
        ),
    CONSTRAINT fk_capture_revision_artifact
        FOREIGN KEY (project_id, raster_artifact_id)
        REFERENCES capture_artifacts (project_id, artifact_id),
    CONSTRAINT fk_capture_revision_provenance
        FOREIGN KEY (project_id, provenance_id)
        REFERENCES capture_provenance_manifests (project_id, provenance_id),
    CONSTRAINT uq_capture_revision_number
        UNIQUE (project_id, capture_id, revision_number),
    CONSTRAINT uq_capture_revision_job
        UNIQUE (project_id, job_id),
    CONSTRAINT uq_capture_revision_attempt
        UNIQUE (project_id, winning_attempt_id),
    CONSTRAINT uq_capture_revision_provenance
        UNIQUE (project_id, provenance_id),
    CONSTRAINT ck_capture_revision_status
        CHECK (status IN ('ready', 'review_required')),
    CONSTRAINT ck_capture_revision_digests
        CHECK (
            octet_length(settings_digest) = 32
            AND octet_length(profile_digest) = 32
            AND revision_number > 0
        )
);

ALTER TABLE capture_jobs
    ADD CONSTRAINT fk_capture_job_output_revision
    FOREIGN KEY (project_id, output_revision_id)
    REFERENCES capture_revisions (project_id, revision_id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE capture_change_signals (
    project_id uuid NOT NULL,
    change_signal_id uuid NOT NULL,
    capture_id uuid NOT NULL,
    current_revision_id uuid NOT NULL,
    baseline_revision_id uuid,
    current_artifact_id uuid NOT NULL,
    baseline_artifact_id uuid,
    signal text NOT NULL,
    difference_final_url boolean,
    difference_redirect_chain boolean,
    difference_profile boolean,
    difference_region boolean,
    difference_warnings boolean,
    difference_load_evidence boolean,
    algorithm text NOT NULL,
    algorithm_version integer NOT NULL,
    computed_at timestamptz NOT NULL,
    materiality text NOT NULL,
    materiality_version integer NOT NULL,
    CONSTRAINT pk_capture_change_signals
        PRIMARY KEY (project_id, change_signal_id),
    CONSTRAINT fk_capture_change_current_revision
        FOREIGN KEY (project_id, current_revision_id, capture_id)
        REFERENCES capture_revisions (project_id, revision_id, capture_id),
    CONSTRAINT fk_capture_change_baseline_revision
        FOREIGN KEY (project_id, baseline_revision_id, capture_id)
        REFERENCES capture_revisions (project_id, revision_id, capture_id),
    CONSTRAINT fk_capture_change_current_artifact
        FOREIGN KEY (project_id, current_artifact_id)
        REFERENCES capture_artifacts (project_id, artifact_id),
    CONSTRAINT fk_capture_change_baseline_artifact
        FOREIGN KEY (project_id, baseline_artifact_id)
        REFERENCES capture_artifacts (project_id, artifact_id),
    CONSTRAINT uq_capture_change_current_revision
        UNIQUE (project_id, current_revision_id),
    CONSTRAINT ck_capture_change_signal
        CHECK (
            (
                signal = 'initial_observation'
                AND baseline_revision_id IS NULL
                AND baseline_artifact_id IS NULL
            )
            OR (
                signal IN (
                    'same_exact_bytes',
                    'different_exact_bytes',
                    'not_comparable'
                )
                AND baseline_revision_id IS NOT NULL
                AND baseline_artifact_id IS NOT NULL
            )
        ),
    CONSTRAINT ck_capture_change_algorithm
        CHECK (
            algorithm = 'exact_bytes_and_provenance'
            AND algorithm_version = 1
            AND materiality = 'non_semantic_no_automatic_replacement_selection_or_notification'
            AND materiality_version = 1
        )
);

CREATE TABLE capture_revision_use_decisions (
    project_id uuid NOT NULL,
    decision_id uuid NOT NULL,
    capture_id uuid NOT NULL,
    revision_id uuid NOT NULL,
    decision text NOT NULL,
    context_kind text NOT NULL,
    context_resource_id uuid NOT NULL,
    context_version_digest bytea NOT NULL,
    context_occurrence_id uuid,
    actor_kind text NOT NULL,
    actor_id uuid NOT NULL,
    authorization_decision_id uuid NOT NULL,
    warning_set_digest bytea NOT NULL,
    effect_digest bytea NOT NULL,
    recorded_at timestamptz NOT NULL,
    CONSTRAINT pk_capture_revision_use_decisions
        PRIMARY KEY (project_id, decision_id),
    CONSTRAINT fk_capture_use_revision
        FOREIGN KEY (project_id, revision_id, capture_id)
        REFERENCES capture_revisions (project_id, revision_id, capture_id),
    CONSTRAINT uq_capture_use_effect UNIQUE (project_id, effect_digest),
    CONSTRAINT uq_capture_use_context
        UNIQUE NULLS NOT DISTINCT (
            project_id,
            revision_id,
            context_kind,
            context_resource_id,
            context_version_digest,
            context_occurrence_id,
            decision
        ),
    CONSTRAINT ck_capture_use_decision
        CHECK (decision IN ('preview_acknowledged', 'release_accepted')),
    CONSTRAINT ck_capture_use_digests
        CHECK (
            octet_length(context_version_digest) = 32
            AND octet_length(warning_set_digest) = 32
            AND octet_length(effect_digest) = 32
        ),
    CONSTRAINT ck_capture_use_actor
        CHECK (actor_kind IN ('user', 'service'))
);

CREATE TABLE capture_revision_selections (
    project_id uuid NOT NULL,
    selection_id uuid NOT NULL,
    capture_id uuid NOT NULL,
    revision_id uuid NOT NULL,
    target_kind text NOT NULL,
    target_resource_id uuid NOT NULL,
    target_version_digest bytea NOT NULL,
    target_occurrence_id uuid,
    target_sequence bigint NOT NULL,
    previous_selection_id uuid,
    expected_previous_selection_id uuid,
    reason text NOT NULL,
    actor_kind text NOT NULL,
    actor_id uuid NOT NULL,
    authorization_decision_id uuid NOT NULL,
    required_use_decision_id uuid,
    effect_digest bytea NOT NULL,
    selected_at timestamptz NOT NULL,
    CONSTRAINT pk_capture_revision_selections
        PRIMARY KEY (project_id, selection_id),
    CONSTRAINT fk_capture_selection_revision
        FOREIGN KEY (project_id, revision_id, capture_id)
        REFERENCES capture_revisions (project_id, revision_id, capture_id),
    CONSTRAINT fk_capture_selection_previous
        FOREIGN KEY (project_id, previous_selection_id)
        REFERENCES capture_revision_selections (project_id, selection_id),
    CONSTRAINT fk_capture_selection_expected
        FOREIGN KEY (project_id, expected_previous_selection_id)
        REFERENCES capture_revision_selections (project_id, selection_id),
    CONSTRAINT fk_capture_selection_use
        FOREIGN KEY (project_id, required_use_decision_id)
        REFERENCES capture_revision_use_decisions (project_id, decision_id),
    CONSTRAINT uq_capture_selection_target_sequence
        UNIQUE NULLS NOT DISTINCT (
            project_id,
            target_kind,
            target_resource_id,
            target_version_digest,
            target_occurrence_id,
            target_sequence
        ),
    CONSTRAINT uq_capture_selection_effect
        UNIQUE (project_id, effect_digest),
    CONSTRAINT ck_capture_selection_reason
        CHECK (reason IN ('manual', 'capture_and_use', 'checkpoint_restore')),
    CONSTRAINT ck_capture_selection_integrity
        CHECK (
            octet_length(target_version_digest) = 32
            AND octet_length(effect_digest) = 32
            AND target_sequence > 0
            AND actor_kind IN ('user', 'service')
        )
);

CREATE TABLE capture_revision_protections (
    project_id uuid NOT NULL,
    protection_id uuid NOT NULL,
    capture_id uuid NOT NULL,
    revision_id uuid NOT NULL,
    reason text NOT NULL,
    source_kind text NOT NULL,
    source_resource_id uuid NOT NULL,
    source_version_digest bytea NOT NULL,
    source_occurrence_id uuid,
    actor_kind text NOT NULL,
    actor_id uuid NOT NULL,
    authorization_decision_id uuid NOT NULL,
    effect_digest bytea NOT NULL,
    added_at timestamptz NOT NULL,
    CONSTRAINT pk_capture_revision_protections
        PRIMARY KEY (project_id, protection_id),
    CONSTRAINT fk_capture_protection_revision
        FOREIGN KEY (project_id, revision_id, capture_id)
        REFERENCES capture_revisions (project_id, revision_id, capture_id),
    CONSTRAINT uq_capture_protection_source
        UNIQUE NULLS NOT DISTINCT (
            project_id,
            revision_id,
            reason,
            source_kind,
            source_resource_id,
            source_version_digest,
            source_occurrence_id
        ),
    CONSTRAINT uq_capture_protection_effect
        UNIQUE (project_id, effect_digest),
    CONSTRAINT ck_capture_protection_reason
        CHECK (
            reason IN (
                'draft_selection',
                'document_revision',
                'checkpoint',
                'preview_build',
                'release_build',
                'explicit_pin',
                'selection_evidence',
                'review_hold',
                'integrity_hold'
            )
        ),
    CONSTRAINT ck_capture_protection_integrity
        CHECK (
            octet_length(source_version_digest) = 32
            AND octet_length(effect_digest) = 32
            AND actor_kind IN ('user', 'service')
        )
);

CREATE TABLE capture_protection_releases (
    project_id uuid NOT NULL,
    release_id uuid NOT NULL,
    protection_id uuid NOT NULL,
    actor_kind text NOT NULL,
    actor_id uuid NOT NULL,
    authorization_decision_id uuid NOT NULL,
    reason text NOT NULL,
    effect_digest bytea NOT NULL,
    released_at timestamptz NOT NULL,
    CONSTRAINT pk_capture_protection_releases
        PRIMARY KEY (project_id, release_id),
    CONSTRAINT fk_capture_protection_release
        FOREIGN KEY (project_id, protection_id)
        REFERENCES capture_revision_protections (project_id, protection_id),
    CONSTRAINT uq_capture_protection_release
        UNIQUE (project_id, protection_id),
    CONSTRAINT uq_capture_protection_release_effect
        UNIQUE (project_id, effect_digest),
    CONSTRAINT ck_capture_protection_release_integrity
        CHECK (
            octet_length(effect_digest) = 32
            AND actor_kind IN ('user', 'service')
            AND char_length(reason) BETWEEN 1 AND 256
        )
);

CREATE TABLE capture_audit_events (
    project_id uuid NOT NULL,
    event_id uuid NOT NULL,
    primary_object_kind text NOT NULL,
    primary_object_id uuid NOT NULL,
    object_sequence bigint NOT NULL,
    event_type text NOT NULL,
    actor_kind text NOT NULL,
    actor_id uuid NOT NULL,
    request_id uuid NOT NULL,
    correlation_id uuid NOT NULL,
    policy_version text NOT NULL,
    profile_version bigint,
    before_state text,
    after_state text,
    result_code text NOT NULL,
    safe_details jsonb NOT NULL,
    corrected_event_id uuid,
    server_time timestamptz NOT NULL,
    CONSTRAINT pk_capture_audit_events PRIMARY KEY (project_id, event_id),
    CONSTRAINT fk_capture_audit_correction
        FOREIGN KEY (project_id, corrected_event_id)
        REFERENCES capture_audit_events (project_id, event_id),
    CONSTRAINT uq_capture_audit_object_sequence
        UNIQUE (
            project_id,
            primary_object_kind,
            primary_object_id,
            object_sequence
        ),
    CONSTRAINT ck_capture_audit_integrity
        CHECK (
            object_sequence > 0
            AND actor_kind IN ('user', 'service')
            AND (profile_version IS NULL OR profile_version > 0)
            AND jsonb_typeof(safe_details) = 'object'
        )
);

CREATE INDEX ix_capture_jobs_queue
    ON capture_jobs (state, available_at, requested_at)
    WHERE state = 'queued';
CREATE INDEX ix_capture_jobs_history
    ON capture_jobs (project_id, capture_id, requested_at DESC);
CREATE INDEX ix_capture_leases_expiry
    ON capture_leases (expires_at)
    WHERE state IN ('issued', 'active');
CREATE INDEX ix_capture_revisions_history
    ON capture_revisions (
        project_id,
        capture_id,
        revision_number DESC
    );
CREATE INDEX ix_capture_selections_target
    ON capture_revision_selections (
        project_id,
        target_kind,
        target_resource_id,
        target_version_digest,
        target_occurrence_id,
        target_sequence DESC
    );
CREATE INDEX ix_capture_protections_active
    ON capture_revision_protections (project_id, revision_id, added_at);
CREATE INDEX ix_capture_protection_releases_lookup
    ON capture_protection_releases (project_id, protection_id);
CREATE INDEX ix_capture_audit_time
    ON capture_audit_events (project_id, server_time, event_id);
CREATE INDEX ix_capture_audit_correlation
    ON capture_audit_events (project_id, correlation_id, server_time);

CREATE FUNCTION deny_capture_immutable_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'capture records are immutable'
        USING ERRCODE = '55000';
END;
$$;

CREATE FUNCTION deny_capture_delete()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'capture projection rows cannot be deleted'
        USING ERRCODE = '55000';
END;
$$;

CREATE TRIGGER tr_capture_configurations_immutable
    BEFORE UPDATE OR DELETE ON capture_configurations
    FOR EACH ROW EXECUTE FUNCTION deny_capture_immutable_change();
CREATE TRIGGER tr_capture_artifacts_immutable
    BEFORE UPDATE OR DELETE ON capture_artifacts
    FOR EACH ROW EXECUTE FUNCTION deny_capture_immutable_change();
CREATE TRIGGER tr_capture_provenance_immutable
    BEFORE UPDATE OR DELETE ON capture_provenance_manifests
    FOR EACH ROW EXECUTE FUNCTION deny_capture_immutable_change();
CREATE TRIGGER tr_capture_revisions_immutable
    BEFORE UPDATE OR DELETE ON capture_revisions
    FOR EACH ROW EXECUTE FUNCTION deny_capture_immutable_change();
CREATE TRIGGER tr_capture_change_signals_immutable
    BEFORE UPDATE OR DELETE ON capture_change_signals
    FOR EACH ROW EXECUTE FUNCTION deny_capture_immutable_change();
CREATE TRIGGER tr_capture_use_decisions_immutable
    BEFORE UPDATE OR DELETE ON capture_revision_use_decisions
    FOR EACH ROW EXECUTE FUNCTION deny_capture_immutable_change();
CREATE TRIGGER tr_capture_selections_immutable
    BEFORE UPDATE OR DELETE ON capture_revision_selections
    FOR EACH ROW EXECUTE FUNCTION deny_capture_immutable_change();
CREATE TRIGGER tr_capture_protections_immutable
    BEFORE UPDATE OR DELETE ON capture_revision_protections
    FOR EACH ROW EXECUTE FUNCTION deny_capture_immutable_change();
CREATE TRIGGER tr_capture_protection_releases_immutable
    BEFORE UPDATE OR DELETE ON capture_protection_releases
    FOR EACH ROW EXECUTE FUNCTION deny_capture_immutable_change();
CREATE TRIGGER tr_capture_audit_immutable
    BEFORE UPDATE OR DELETE ON capture_audit_events
    FOR EACH ROW EXECUTE FUNCTION deny_capture_immutable_change();
CREATE TRIGGER tr_captures_no_delete
    BEFORE DELETE ON captures
    FOR EACH ROW EXECUTE FUNCTION deny_capture_delete();
CREATE TRIGGER tr_capture_jobs_no_delete
    BEFORE DELETE ON capture_jobs
    FOR EACH ROW EXECUTE FUNCTION deny_capture_delete();
CREATE TRIGGER tr_capture_leases_no_delete
    BEFORE DELETE ON capture_leases
    FOR EACH ROW EXECUTE FUNCTION deny_capture_delete();
CREATE TRIGGER tr_capture_attempts_no_delete
    BEFORE DELETE ON capture_attempts
    FOR EACH ROW EXECUTE FUNCTION deny_capture_delete();

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vera_capture_reader') THEN
        CREATE ROLE vera_capture_reader NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vera_capture_api') THEN
        CREATE ROLE vera_capture_api NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vera_capture_worker') THEN
        CREATE ROLE vera_capture_worker NOLOGIN;
    END IF;
END;
$$;

REVOKE ALL ON public_page_capture_settings, captures,
    capture_configurations, capture_jobs, capture_leases, capture_attempts,
    capture_artifacts, capture_provenance_manifests, capture_revisions,
    capture_change_signals, capture_revision_use_decisions,
    capture_revision_selections, capture_revision_protections,
    capture_protection_releases, capture_audit_events
    FROM vera_capture_reader, vera_capture_api, vera_capture_worker;
GRANT SELECT ON captures, capture_configurations, capture_jobs,
    capture_artifacts, capture_revisions, capture_change_signals,
    capture_revision_use_decisions, capture_revision_selections,
    capture_revision_protections, capture_protection_releases,
    capture_audit_events
    TO vera_capture_reader;
GRANT SELECT ON captures, capture_configurations, capture_jobs,
    capture_leases, capture_attempts, capture_artifacts,
    capture_provenance_manifests, capture_revisions,
    capture_change_signals, capture_revision_use_decisions,
    capture_revision_selections, capture_revision_protections,
    capture_protection_releases, capture_audit_events
    TO vera_capture_api, vera_capture_worker;
GRANT SELECT ON public_page_capture_settings TO vera_capture_worker;
GRANT INSERT ON captures, capture_configurations, capture_jobs,
    capture_revision_use_decisions, capture_revision_selections,
    capture_revision_protections, capture_protection_releases,
    capture_audit_events
    TO vera_capture_api;
GRANT UPDATE (
    current_configuration_version,
    row_version,
    updated_at
) ON captures TO vera_capture_api;
GRANT UPDATE (
    state,
    output_revision_id,
    row_version,
    enqueued_at,
    available_at,
    terminal_at
) ON capture_jobs TO vera_capture_worker;
GRANT INSERT ON capture_leases, capture_attempts, capture_artifacts,
    capture_provenance_manifests, capture_revisions,
    capture_change_signals, capture_revision_selections,
    capture_revision_protections, capture_audit_events
    TO vera_capture_worker;
GRANT UPDATE (
    next_revision_number,
    row_version,
    updated_at
) ON captures TO vera_capture_worker;
GRANT UPDATE (
    state,
    expires_at,
    heartbeat_at,
    terminal_at,
    row_version
) ON capture_leases TO vera_capture_worker;
GRANT UPDATE (
    state,
    navigation_started_at,
    staged_at,
    terminal_at,
    terminal_code,
    diagnostic_digest,
    row_version
) ON capture_attempts TO vera_capture_worker;
