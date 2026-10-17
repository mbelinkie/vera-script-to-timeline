import { randomUUID } from "node:crypto";

import type {
  AbandonAttemptRequest,
  AbandonAttemptResponse,
  AddExplicitPinRequest,
  ArtifactDescriptor,
  AuditEventsViewMessage,
  AuthorizationDecisionRef,
  CaptureProfileV1,
  CaptureAuditEventView,
  CaptureConfigurationView,
  CaptureJobView,
  CaptureJobViewMessage,
  CaptureRevisionView,
  CaptureRevisionViewMessage,
  CaptureView,
  CaptureViewMessage,
  ChangeSignal,
  ClaimLeaseRequest,
  ClaimLeaseResponse,
  CommitAttemptRequest,
  CommitAttemptResponse,
  CreateCaptureRequest,
  CreateConfigurationVersionRequest,
  DraftOccurrenceReference,
  FailAttemptRequest,
  FailAttemptResponse,
  LeaseProof,
  PrincipalRef,
  PublicPageCaptureProvenanceV1,
  RecordNavigationStartRequest,
  RecordNavigationStartResponse,
  RecordRevisionUseDecisionRequest,
  ReleaseExplicitPinRequest,
  RenewLeaseRequest,
  RenewLeaseResponse,
  RequestCaptureJobRequest,
  RequestStagingGrantsRequest,
  RequestStagingGrantsResponse,
  SelectRevisionRequest,
  StagedObjectDescriptor,
  StagingGrant,
  StartAttemptRequest,
  StartAttemptResponse,
  VersionedExternalReference,
} from "@vera/contracts";

import type {
  AuthoringReferencePort,
  ProjectAuthorizationPort,
  WorkerAuthorizationPort,
} from "./authorization.js";
import {
  CapabilityError,
  CapabilitySigner,
  canonicalJson,
  keyedFingerprint,
  sha256,
  type CapabilityClaims,
  type JsonValue,
} from "./crypto.js";
import type { CaptureDatabase, SqlClient } from "./database.js";
import { RestrictedRequestCipher } from "./envelope.js";
import { CaptureServiceError, sanitizedDenial } from "./errors.js";
import {
  captureConfigurationVersionId,
  captureRasterArtifactId,
} from "./identities.js";
import {
  type ImmutableObjectStorePort,
  ObjectStoreError,
  type PromotedObject,
  type StagedObject,
  type VerifiedStagingGrant,
} from "./object-store.js";
import { CaptureDenied, inspectPublicUrl } from "./policy.js";
import {
  CAPTURE_PROFILE_V1,
  CAPTURE_PROFILE_V1_DIGEST,
  OUTPUT_HEIGHT,
  OUTPUT_WIDTH,
} from "./profile.js";
import { RasterVerificationError, verifyPng } from "./raster.js";
import { validateProvenance } from "./contracts.js";

type ExternalReference = DraftOccurrenceReference | VersionedExternalReference;
type AcquisitionPolicy = CreateCaptureRequest["acquisitionPolicy"];
type SelectionIntent = Extract<
  RequestCaptureJobRequest["trigger"],
  { kind: "now" }
>["selectionIntent"];

interface CaptureRow {
  readonly acquisition_policy: "now" | "on_build" | "periodic_reserved";
  readonly canonical_url_digest: Uint8Array;
  readonly capture_id: string;
  readonly capture_profile_id: string;
  readonly capture_profile_version: string | number;
  readonly configuration_created_at: Date | string;
  readonly configuration_created_by_id: string;
  readonly configuration_created_by_kind: "service" | "user";
  readonly configuration_version: string | number;
  readonly created_at: Date | string;
  readonly created_by_id: string;
  readonly created_by_kind: "service" | "user";
  readonly current_configuration_version: string | number;
  readonly previous_configuration_digest: Uint8Array | null;
  readonly project_id: string;
  readonly query_key_names: unknown;
  readonly redacted_url_display: string;
  readonly region_intent: unknown;
  readonly row_version: string | number;
  readonly settings_digest: Uint8Array;
  readonly state: CaptureView["lifecycle"];
  readonly updated_at: Date | string;
}

interface JobRow {
  readonly authorization_decided_at: Date | string;
  readonly authorization_decision_id: string;
  readonly available_at: Date | string | null;
  readonly capture_id: string;
  readonly capture_profile_id: string;
  readonly capture_profile_version: string | number;
  readonly conditional_selection_intent: unknown;
  readonly configuration_version: string | number;
  readonly commit_recheck_mode: AuthorizationDecisionRef["recheckMode"];
  readonly enqueued_at: Date | string | null;
  readonly idempotency_key_digest: Uint8Array;
  readonly initiating_principal_id: string;
  readonly initiating_principal_kind: PrincipalRef["principalKind"];
  readonly initiating_role: AuthorizationDecisionRef["role"];
  readonly job_id: string;
  readonly membership_version: string | number | null;
  readonly output_revision_id: string | null;
  readonly profile_digest: Uint8Array;
  readonly project_id: string;
  readonly request_fingerprint: Uint8Array;
  readonly request_id: string;
  readonly requested_at: Date | string;
  readonly retry_budget: number;
  readonly row_version: string | number;
  readonly settings_digest: Uint8Array;
  readonly state: CaptureJobView["state"];
  readonly terminal_at: Date | string | null;
  readonly trigger_kind: "now" | "on_build";
  readonly trigger_reference_digest: Uint8Array | null;
  readonly trigger_reference_id: string;
  readonly trigger_reference_kind: string;
}

interface ConfigurationSecretRow {
  readonly canonical_url_digest: Uint8Array;
  readonly configuration_version: string | number;
  readonly restricted_request_envelope: Uint8Array;
}

interface LeaseRow {
  readonly capability_jti_digest: Uint8Array;
  readonly capability_scope_digest: Uint8Array;
  readonly capture_id: string;
  readonly epoch: string | number;
  readonly expires_at: Date | string;
  readonly heartbeat_at: Date | string | null;
  readonly issued_at: Date | string;
  readonly job_id: string;
  readonly lease_id: string;
  readonly project_id: string;
  readonly row_version: string | number;
  readonly state: "active" | "expired" | "issued" | "released" | "revoked";
  readonly terminal_at: Date | string | null;
  readonly worker_installation_id: string;
}

interface AttemptRow {
  readonly adapter_version: string;
  readonly attempt_id: string;
  readonly attempt_number: number;
  readonly browser_version: string;
  readonly capture_id: string;
  readonly clean_profile_id: string;
  readonly diagnostic_digest: Uint8Array | null;
  readonly job_id: string;
  readonly lease_id: string;
  readonly navigation_started_at: Date | string | null;
  readonly profile_digest: Uint8Array;
  readonly profile_version: string | number;
  readonly project_id: string;
  readonly row_version: string | number;
  readonly security_policy_version: string;
  readonly staged_at: Date | string | null;
  readonly started_at: Date | string;
  readonly state: "abandoned" | "cancelled" | "committed" | "failed" | "staged" | "started";
  readonly terminal_at: Date | string | null;
  readonly terminal_code: string | null;
}

interface LeaseClaims extends CapabilityClaims {
  readonly baselineArtifactId: string;
  readonly baselineRasterDigest: string;
  readonly baselineRevisionId: string;
  readonly capabilityType: "lease";
  readonly captureId: string;
  readonly commitNonce: string;
  readonly configurationVersion: number;
  readonly jobId: string;
  readonly leaseEpoch: number;
  readonly leaseId: string;
  readonly plannedAttemptId: string;
  readonly profileDigest: string;
  readonly projectId: string;
  readonly settingsDigest: string;
  readonly workerInstallationId: string;
}

interface CurrentLease {
  readonly attempt: AttemptRow | null;
  readonly claims: LeaseClaims;
  readonly job: JobRow;
  readonly lease: LeaseRow;
}

interface ArtifactRow {
  readonly access_class: ArtifactDescriptor["accessClass"];
  readonly alpha: ArtifactDescriptor["alpha"];
  readonly artifact_id: string;
  readonly byte_length: string | number;
  readonly color: ArtifactDescriptor["color"];
  readonly created_at: Date | string;
  readonly digest: Uint8Array;
  readonly encoding: ArtifactDescriptor["encoding"];
  readonly height: number | null;
  readonly kind: ArtifactDescriptor["kind"];
  readonly mime_type: ArtifactDescriptor["mimeType"];
  readonly object_store_id: string;
  readonly project_id: string;
  readonly provenance_schema: string | null;
  readonly verified_at: Date | string;
  readonly verifier_profile: string;
  readonly verifier_version: number;
  readonly width: number | null;
}

interface BaselineRow {
  readonly configuration_version: string | number;
  readonly profile_digest: Uint8Array;
  readonly provenance_object_store_id: string;
  readonly raster_artifact_id: string;
  readonly raster_digest: Uint8Array;
  readonly raster_object_store_id: string;
  readonly region_intent: unknown;
  readonly revision_id: string;
  readonly settings_digest: Uint8Array;
  readonly warning_summary: unknown;
}

interface VerifiedStagedCandidate {
  readonly bytes: Buffer;
  readonly staged: StagedObject;
}

interface ComputedChange {
  readonly differences: ChangeSignal["differences"];
  readonly signal: ChangeSignal["signal"];
}

interface AuditIdentity {
  readonly correlationId: string;
  readonly objectId: string;
  readonly objectKind: string;
  readonly principal: PrincipalRef;
  readonly projectId: string;
  readonly requestId: string;
}

export interface CaptureServiceDependencies {
  readonly authorization: ProjectAuthorizationPort;
  readonly capabilities: CapabilitySigner;
  readonly cipher: RestrictedRequestCipher;
  readonly database: CaptureDatabase;
  readonly denialFingerprintKey: Buffer;
  readonly objects: ImmutableObjectStorePort;
  readonly references: AuthoringReferencePort;
  readonly workerAuthorization: WorkerAuthorizationPort;
  readonly id?: () => string;
  readonly now?: () => Date;
}

export interface CaptureMutationReceipt {
  readonly duplicateDelivery: boolean;
  readonly effectId: string;
  readonly recordedAt: string;
}

export interface CaptureArtifactRead {
  readonly bytes: Buffer;
  readonly descriptor: ArtifactDescriptor;
}

export interface StagingUploadAuthorization {
  readonly maxBytes: number;
  readonly mimeType: "application/json" | "image/png";
}

function integer(value: string | number): number {
  return typeof value === "number" ? value : Number.parseInt(value, 10);
}

function timestamp(value: Date | string): string {
  return new Date(value).toISOString();
}

function nullableTimestamp(value: Date | string | null): string | null {
  return value === null ? null : timestamp(value);
}

function digestBytes(value: string): Buffer {
  if (!/^sha256:[0-9a-f]{64}$/u.test(value)) {
    throw new CaptureServiceError(
      "request_invalid",
      "A required digest is malformed.",
      false,
      ["/digest"],
    );
  }
  return Buffer.from(value.slice(7), "hex");
}

function digestString(value: Uint8Array): string {
  return `sha256:${Buffer.from(value).toString("hex")}`;
}

function json<T>(value: unknown): T {
  if (typeof value === "string") return JSON.parse(value) as T;
  return value as T;
}

function safeRoleFor(action: string): AuthorizationDecisionRef["recheckMode"] {
  return action === "capture_commit" ? "commit_time" : "every_request";
}

function sameDigest(left: Uint8Array, right: string): boolean {
  return digestString(left) === right;
}

function grantsTuple(values: StagingGrant[]): [StagingGrant, StagingGrant] {
  if (values.length !== 2 || !values[0] || !values[1]) {
    throw new Error("The capture protocol requires exactly two staging grants.");
  }
  return [values[0], values[1]];
}

function referenceVersion(reference: ExternalReference): string {
  return reference.resourceVersionDigest;
}

function referenceOccurrence(reference: ExternalReference): string | null {
  return "occurrenceId" in reference ? reference.occurrenceId : null;
}

function capabilityScope(claims: CapabilityClaims): Record<string, boolean | number | string> {
  const scope: Record<string, boolean | number | string> = { ...claims };
  delete scope.exp;
  delete scope.iat;
  delete scope.jti;
  return scope;
}

function claimString(claims: CapabilityClaims, name: string): string {
  const value = claims[name];
  if (typeof value !== "string") throw new CapabilityError("capability_malformed");
  return value;
}

function claimInteger(claims: CapabilityClaims, name: string): number {
  const value = claims[name];
  if (typeof value !== "number" || !Number.isInteger(value) || value < 1) {
    throw new CapabilityError("capability_malformed");
  }
  return value;
}

function leaseClaims(claims: CapabilityClaims): LeaseClaims {
  if (claims.capabilityType !== "lease") {
    throw new CapabilityError("capability_scope_mismatch");
  }
  return {
    ...claims,
    baselineArtifactId: claimString(claims, "baselineArtifactId"),
    baselineRasterDigest: claimString(claims, "baselineRasterDigest"),
    baselineRevisionId: claimString(claims, "baselineRevisionId"),
    capabilityType: "lease",
    captureId: claimString(claims, "captureId"),
    commitNonce: claimString(claims, "commitNonce"),
    configurationVersion: claimInteger(claims, "configurationVersion"),
    jobId: claimString(claims, "jobId"),
    leaseEpoch: claimInteger(claims, "leaseEpoch"),
    leaseId: claimString(claims, "leaseId"),
    plannedAttemptId: claimString(claims, "plannedAttemptId"),
    profileDigest: claimString(claims, "profileDigest"),
    projectId: claimString(claims, "projectId"),
    settingsDigest: claimString(claims, "settingsDigest"),
    workerInstallationId: claimString(claims, "workerInstallationId"),
  };
}

export class CaptureService {
  private readonly id: () => string;
  private readonly now: () => Date;

  constructor(private readonly dependencies: CaptureServiceDependencies) {
    this.id = dependencies.id ?? randomUUID;
    this.now = dependencies.now ?? (() => new Date());
    if (dependencies.denialFingerprintKey.byteLength < 32) {
      throw new TypeError("Denial fingerprint keys must contain at least 32 bytes.");
    }
  }

  async createCapture(
    request: CreateCaptureRequest,
    principal: PrincipalRef,
  ): Promise<CaptureViewMessage> {
    const authorization = await this.dependencies.authorization.authorize(
      request.projectId,
      principal,
      "capture_create",
    );
    this.assertProfile(request.captureProfileId, request.captureProfileVersion);
    const inspected = this.inspectOrDeny(request.requestedUrl);
    const captureId = this.id();
    const settings = this.captureSettings(
      inspected.canonicalUrl,
      request.regionIntent,
      request.acquisitionPolicy,
      request.captureProfileId,
      request.captureProfileVersion,
    );
    const settingsDigest = sha256(settings);
    const keyDigest = sha256(request.idempotencyKey);
    const fingerprint = sha256({
      messageType: request.messageType,
      projectId: request.projectId,
      requestedUrl: inspected.canonicalUrl,
      regionIntent: request.regionIntent,
      acquisitionPolicy: request.acquisitionPolicy,
      captureProfileId: request.captureProfileId,
      captureProfileVersion: request.captureProfileVersion,
    } as unknown as JsonValue);
    const now = this.now();
    const context = {
      projectId: request.projectId,
      captureId,
      configurationVersion: 1,
      canonicalUrlDigest: sha256(inspected.canonicalUrl),
    };
    const envelope = this.dependencies.cipher.encrypt(
      inspected.canonicalUrl,
      context,
    );

    const resolvedCaptureId = await this.dependencies.database.transaction(
      async (client) => {
        await this.lockIdempotency(
          client,
          request.projectId,
          principal.principalId,
          "capture_create",
          keyDigest,
        );
        const existing = await client.query<{
          fingerprint: string;
          primary_object_id: string;
        }>(
          `SELECT
              safe_details ->> 'requestFingerprint' AS fingerprint,
              primary_object_id
             FROM capture_audit_events
            WHERE project_id = $1
              AND actor_id = $2
              AND event_type = 'capture_created'
              AND safe_details ->> 'idempotencyKeyDigest' = $3
            ORDER BY server_time
            LIMIT 1`,
          [request.projectId, principal.principalId, keyDigest],
        );
        if (existing.rows[0]) {
          if (existing.rows[0].fingerprint !== fingerprint) {
            throw new CaptureServiceError(
              "idempotency_key_reused",
              "The idempotency key was already used for a different request.",
            );
          }
          return existing.rows[0].primary_object_id;
        }

        await client.query(
          `INSERT INTO captures (
              project_id,
              capture_id,
              state,
              current_configuration_version,
              created_by_kind,
              created_by_id,
              created_at,
              updated_at
            ) VALUES ($1, $2, 'active', 1, $3, $4, $5, $5)`,
          [
            request.projectId,
            captureId,
            principal.principalKind,
            principal.principalId,
            now,
          ],
        );
        await client.query(
          `INSERT INTO capture_configurations (
              project_id,
              capture_id,
              configuration_version,
              schema_version,
              canonical_url_digest,
              redacted_url_display,
              query_key_names,
              restricted_request_envelope,
              restricted_request_key_version,
              region_intent,
              acquisition_policy,
              periodic_execution_enabled,
              capture_profile_id,
              capture_profile_version,
              settings_json,
              settings_digest,
              previous_configuration_digest,
              created_by_kind,
              created_by_id,
              created_at
            ) VALUES (
              $1, $2, 1, 'public-page-capture-api/v1', $3, $4, $5::jsonb,
              $6, $7, $8::jsonb, $9, false, $10, $11, $12::jsonb, $13,
              NULL, $14, $15, $16
            )`,
          [
            request.projectId,
            captureId,
            digestBytes(context.canonicalUrlDigest),
            inspected.redactedUrl,
            JSON.stringify(inspected.queryKeys),
            envelope,
            this.dependencies.cipher.keyVersion,
            JSON.stringify(request.regionIntent),
            request.acquisitionPolicy.kind,
            request.captureProfileId,
            request.captureProfileVersion,
            JSON.stringify(settings),
            digestBytes(settingsDigest),
            principal.principalKind,
            principal.principalId,
            now,
          ],
        );
        await this.appendAudit(
          client,
          {
            projectId: request.projectId,
            objectId: captureId,
            objectKind: "capture",
            principal,
            requestId: request.clientRequestId,
            correlationId: request.clientRequestId,
          },
          "capture_created",
          null,
          "active",
          "created",
          {
            authorizationDecisionId: authorization.decisionId,
            idempotencyKeyDigest: keyDigest,
            requestFingerprint: fingerprint,
            settingsDigest,
          },
          now,
        );
        return captureId;
      },
    );
    return await this.captureMessage(
      request.projectId,
      resolvedCaptureId,
      request.clientRequestId,
    );
  }

  async createConfigurationVersion(
    request: CreateConfigurationVersionRequest,
    principal: PrincipalRef,
  ): Promise<CaptureViewMessage> {
    const authorization = await this.dependencies.authorization.authorize(
      request.projectId,
      principal,
      "capture_configure",
    );
    this.assertProfile(request.captureProfileId, request.captureProfileVersion);
    const inspected = this.inspectOrDeny(request.requestedUrl);
    const keyDigest = sha256(request.idempotencyKey);
    const fingerprint = sha256({
      captureId: request.captureId,
      expectedCaptureRowVersion: request.expectedCaptureRowVersion,
      requestedUrl: inspected.canonicalUrl,
      regionIntent: request.regionIntent,
      acquisitionPolicy: request.acquisitionPolicy,
      captureProfileId: request.captureProfileId,
      captureProfileVersion: request.captureProfileVersion,
    } as unknown as JsonValue);
    const now = this.now();

    await this.dependencies.database.transaction(async (client) => {
      await this.lockIdempotency(
        client,
        request.projectId,
        principal.principalId,
        "capture_configure",
        keyDigest,
      );
      const existing = await client.query<{ fingerprint: string }>(
        `SELECT safe_details ->> 'requestFingerprint' AS fingerprint
           FROM capture_audit_events
          WHERE project_id = $1
            AND primary_object_id = $2
            AND actor_id = $3
            AND event_type = 'configuration_created'
            AND safe_details ->> 'idempotencyKeyDigest' = $4
          LIMIT 1`,
        [
          request.projectId,
          request.captureId,
          principal.principalId,
          keyDigest,
        ],
      );
      if (existing.rows[0]) {
        if (existing.rows[0].fingerprint !== fingerprint) {
          throw new CaptureServiceError(
            "idempotency_key_reused",
            "The idempotency key was already used for a different request.",
          );
        }
        return;
      }

      const capture = await client.query<{
        current_configuration_version: string | number;
        row_version: string | number;
        settings_digest: Uint8Array;
        state: string;
      }>(
        `SELECT
            c.current_configuration_version,
            c.row_version,
            c.state,
            cfg.settings_digest
           FROM captures c
           JOIN capture_configurations cfg
             ON cfg.project_id = c.project_id
            AND cfg.capture_id = c.capture_id
            AND cfg.configuration_version = c.current_configuration_version
          WHERE c.project_id = $1 AND c.capture_id = $2
          FOR UPDATE OF c`,
        [request.projectId, request.captureId],
      );
      const current = capture.rows[0];
      if (!current) this.notFound();
      if (integer(current.row_version) !== request.expectedCaptureRowVersion) {
        throw new CaptureServiceError(
          "version_conflict",
          "The capture changed before this configuration was applied.",
        );
      }
      if (current.state === "retired") {
        throw new CaptureServiceError(
          "version_conflict",
          "A retired capture cannot be reconfigured.",
        );
      }

      const version = integer(current.current_configuration_version) + 1;
      const canonicalUrlDigest = sha256(inspected.canonicalUrl);
      const settings = this.captureSettings(
        inspected.canonicalUrl,
        request.regionIntent,
        request.acquisitionPolicy,
        request.captureProfileId,
        request.captureProfileVersion,
      );
      const settingsDigest = sha256(settings);
      const envelope = this.dependencies.cipher.encrypt(inspected.canonicalUrl, {
        projectId: request.projectId,
        captureId: request.captureId,
        configurationVersion: version,
        canonicalUrlDigest,
      });
      await client.query(
        `INSERT INTO capture_configurations (
            project_id, capture_id, configuration_version, schema_version,
            canonical_url_digest, redacted_url_display, query_key_names,
            restricted_request_envelope, restricted_request_key_version,
            region_intent, acquisition_policy, periodic_execution_enabled,
            capture_profile_id, capture_profile_version, settings_json,
            settings_digest, previous_configuration_digest, created_by_kind,
            created_by_id, created_at
          ) VALUES (
            $1, $2, $3, 'public-page-capture-api/v1', $4, $5, $6::jsonb,
            $7, $8, $9::jsonb, $10, false, $11, $12, $13::jsonb, $14,
            $15, $16, $17, $18
          )`,
        [
          request.projectId,
          request.captureId,
          version,
          digestBytes(canonicalUrlDigest),
          inspected.redactedUrl,
          JSON.stringify(inspected.queryKeys),
          envelope,
          this.dependencies.cipher.keyVersion,
          JSON.stringify(request.regionIntent),
          request.acquisitionPolicy.kind,
          request.captureProfileId,
          request.captureProfileVersion,
          JSON.stringify(settings),
          digestBytes(settingsDigest),
          current.settings_digest,
          principal.principalKind,
          principal.principalId,
          now,
        ],
      );
      await client.query(
        `UPDATE captures
            SET current_configuration_version = $3,
                row_version = row_version + 1,
                updated_at = $4
          WHERE project_id = $1 AND capture_id = $2`,
        [request.projectId, request.captureId, version, now],
      );
      await this.appendAudit(
        client,
        {
          projectId: request.projectId,
          objectId: request.captureId,
          objectKind: "capture",
          principal,
          requestId: request.clientRequestId,
          correlationId: request.clientRequestId,
        },
        "configuration_created",
        current.state,
        current.state,
        "created",
        {
          authorizationDecisionId: authorization.decisionId,
          configurationVersion: version,
          idempotencyKeyDigest: keyDigest,
          requestFingerprint: fingerprint,
          settingsDigest,
        },
        now,
      );
    });
    return await this.captureMessage(
      request.projectId,
      request.captureId,
      request.clientRequestId,
    );
  }

  async getCapture(
    projectId: string,
    captureId: string,
    principal: PrincipalRef,
    requestId = this.id(),
  ): Promise<CaptureViewMessage> {
    await this.dependencies.authorization.authorize(
      projectId,
      principal,
      "capture_read",
    );
    return await this.captureMessage(projectId, captureId, requestId);
  }

  async requestCaptureJob(
    request: RequestCaptureJobRequest,
    principal: PrincipalRef,
  ): Promise<CaptureJobViewMessage> {
    const action =
      request.trigger.kind === "now"
        ? "capture_request_now"
        : "capture_request_on_build";
    const authorization = await this.dependencies.authorization.authorize(
      request.projectId,
      principal,
      action,
    );
    if (request.trigger.kind === "on_build") {
      await this.dependencies.references.validate(
        request.projectId,
        request.trigger.buildSnapshot,
        "build",
      );
    } else if (request.trigger.selectionIntent.kind === "conditional") {
      await this.dependencies.references.validate(
        request.projectId,
        request.trigger.selectionIntent.target,
        "select",
      );
    }
    const keyDigest = sha256(request.idempotencyKey);
    const fingerprint = sha256({
      captureId: request.captureId,
      expectedCaptureRowVersion: request.expectedCaptureRowVersion,
      trigger: request.trigger,
    } as unknown as JsonValue);
    const now = this.now();
    const proposedJobId = this.id();

    const { duplicate, jobId } = await this.dependencies.database.transaction(
      async (client) => {
        await this.lockIdempotency(
          client,
          request.projectId,
          principal.principalId,
          request.trigger.kind,
          keyDigest,
        );
        const existing = await client.query<JobRow>(
          `SELECT *
             FROM capture_jobs
            WHERE project_id = $1
              AND capture_id = $2
              AND initiating_principal_id = $3
              AND trigger_kind = $4
              AND idempotency_key_digest = $5`,
          [
            request.projectId,
            request.captureId,
            principal.principalId,
            request.trigger.kind,
            digestBytes(keyDigest),
          ],
        );
        if (existing.rows[0]) {
          if (!sameDigest(existing.rows[0].request_fingerprint, fingerprint)) {
            throw new CaptureServiceError(
              "idempotency_key_reused",
              "The idempotency key was already used for a different request.",
            );
          }
          return { duplicate: true, jobId: existing.rows[0].job_id };
        }

        if (request.trigger.kind === "on_build") {
          const build = request.trigger.buildSnapshot;
          const priorBuild = await client.query<JobRow>(
            `SELECT *
               FROM capture_jobs
              WHERE project_id = $1
                AND capture_id = $2
                AND trigger_kind = 'on_build'
                AND trigger_reference_kind = $3
                AND trigger_reference_id = $4
                AND trigger_reference_digest = $5
              LIMIT 1`,
            [
              request.projectId,
              request.captureId,
              build.kind,
              build.resourceId,
              digestBytes(build.resourceVersionDigest),
            ],
          );
          if (priorBuild.rows[0]) {
            return { duplicate: true, jobId: priorBuild.rows[0].job_id };
          }
        }

        const capture = await client.query<{
          capture_profile_id: string;
          capture_profile_version: string | number;
          current_configuration_version: string | number;
          row_version: string | number;
          settings_digest: Uint8Array;
          settings_json: unknown;
          state: string;
        }>(
          `SELECT
              c.current_configuration_version,
              c.row_version,
              c.state,
              cfg.capture_profile_id,
              cfg.capture_profile_version,
              cfg.settings_json,
              cfg.settings_digest
             FROM captures c
             JOIN capture_configurations cfg
               ON cfg.project_id = c.project_id
              AND cfg.capture_id = c.capture_id
              AND cfg.configuration_version = c.current_configuration_version
            WHERE c.project_id = $1 AND c.capture_id = $2
            FOR UPDATE OF c`,
          [request.projectId, request.captureId],
        );
        const current = capture.rows[0];
        if (!current) this.notFound();
        if (current.state !== "active") {
          throw new CaptureServiceError(
            "version_conflict",
            "Only an active capture can create a job.",
          );
        }
        if (integer(current.row_version) !== request.expectedCaptureRowVersion) {
          throw new CaptureServiceError(
            "version_conflict",
            "The capture changed before this job was requested.",
          );
        }
        this.assertProfile(
          current.capture_profile_id,
          integer(current.capture_profile_version),
        );
        const triggerReference =
          request.trigger.kind === "now"
            ? {
                kind: "command",
                id: request.trigger.commandId,
                digest: null,
              }
            : {
                kind: request.trigger.buildSnapshot.kind,
                id: request.trigger.buildSnapshot.resourceId,
                digest: digestBytes(
                  request.trigger.buildSnapshot.resourceVersionDigest,
                ),
              };
        const selectionIntent =
          request.trigger.kind === "now" &&
          request.trigger.selectionIntent.kind === "conditional"
            ? request.trigger.selectionIntent
            : null;
        await client.query(
          `INSERT INTO capture_jobs (
              project_id, job_id, capture_id, configuration_version,
              trigger_kind, trigger_reference_kind, trigger_reference_id,
              trigger_reference_digest, initiating_principal_kind,
              initiating_principal_id, initiating_role, commit_recheck_mode,
              authorization_decision_id, membership_version,
              authorization_decided_at, request_id, idempotency_key_digest,
              request_fingerprint, settings_json, settings_digest,
              capture_profile_id, capture_profile_version,
              capture_profile_json, profile_digest, retry_budget,
              conditional_selection_intent, state, row_version, requested_at,
              enqueued_at, available_at
            ) VALUES (
              $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
              $14, $15, $16, $17, $18, $19::jsonb, $20, $21, $22,
              $23::jsonb, $24, $25, $26::jsonb, 'queued', 1, $27, $27, $27
            )`,
          [
            request.projectId,
            proposedJobId,
            request.captureId,
            integer(current.current_configuration_version),
            request.trigger.kind,
            triggerReference.kind,
            triggerReference.id,
            triggerReference.digest,
            principal.principalKind,
            principal.principalId,
            authorization.role,
            authorization.recheckMode ?? safeRoleFor(action),
            authorization.decisionId,
            authorization.membershipVersion ?? null,
            new Date(authorization.decidedAt),
            request.clientRequestId,
            digestBytes(keyDigest),
            digestBytes(fingerprint),
            JSON.stringify(json<JsonValue>(current.settings_json)),
            current.settings_digest,
            current.capture_profile_id,
            integer(current.capture_profile_version),
            JSON.stringify(CAPTURE_PROFILE_V1),
            digestBytes(CAPTURE_PROFILE_V1_DIGEST),
            CAPTURE_PROFILE_V1.limits.retries,
            selectionIntent === null ? null : JSON.stringify(selectionIntent),
            now,
          ],
        );
        await this.appendAudit(
          client,
          {
            projectId: request.projectId,
            objectId: proposedJobId,
            objectKind: "capture_job",
            principal,
            requestId: request.clientRequestId,
            correlationId: request.clientRequestId,
          },
          "job_queued",
          "requested",
          "queued",
          "queued",
          {
            authorizationDecisionId: authorization.decisionId,
            idempotencyKeyDigest: keyDigest,
            requestFingerprint: fingerprint,
            trigger: request.trigger.kind,
          },
          now,
        );
        return { duplicate: false, jobId: proposedJobId };
      },
    );
    return await this.jobMessage(
      request.projectId,
      jobId,
      request.clientRequestId,
      duplicate,
    );
  }

  async getJob(
    projectId: string,
    jobId: string,
    principal: PrincipalRef,
    requestId = this.id(),
  ): Promise<CaptureJobViewMessage> {
    await this.dependencies.authorization.authorize(
      projectId,
      principal,
      "capture_read",
    );
    return await this.jobMessage(projectId, jobId, requestId, false);
  }

  async getRevision(
    projectId: string,
    revisionId: string,
    principal: PrincipalRef,
    requestId = this.id(),
  ): Promise<CaptureRevisionViewMessage> {
    await this.dependencies.authorization.authorize(
      projectId,
      principal,
      "capture_read",
    );
    return await this.revisionMessage(projectId, revisionId, requestId);
  }

  async getAuditEvents(
    projectId: string,
    captureId: string,
    principal: PrincipalRef,
    requestId = this.id(),
  ): Promise<AuditEventsViewMessage> {
    await this.dependencies.authorization.authorize(
      projectId,
      principal,
      "capture_read",
    );
    const events = await this.dependencies.database.transaction(async (client) => {
      const capture = await client.query(
        "SELECT 1 FROM captures WHERE project_id = $1 AND capture_id = $2",
        [projectId, captureId],
      );
      if (capture.rows.length === 0) this.notFound();
      const result = await client.query<{
        actor_id: string;
        actor_kind: PrincipalRef["principalKind"];
        after_state: string | null;
        before_state: string | null;
        corrected_event_id: string | null;
        correlation_id: string;
        event_id: string;
        event_type: string;
        object_sequence: string | number;
        policy_version: string;
        primary_object_id: string;
        primary_object_kind: string;
        profile_version: string | number | null;
        project_id: string;
        request_id: string;
        result_code: string;
        safe_details: unknown;
        server_time: Date | string;
      }>(
        `SELECT e.*
           FROM capture_audit_events e
          WHERE e.project_id = $1
            AND (
              (e.primary_object_kind = 'capture'
                AND e.primary_object_id = $2)
              OR e.primary_object_id IN (
                SELECT job_id FROM capture_jobs
                 WHERE project_id = $1 AND capture_id = $2
                UNION
                SELECT attempt_id FROM capture_attempts
                 WHERE project_id = $1 AND capture_id = $2
                UNION
                SELECT revision_id FROM capture_revisions
                 WHERE project_id = $1 AND capture_id = $2
              )
            )
          ORDER BY e.server_time, e.event_id
          LIMIT 1000`,
        [projectId, captureId],
      );
      return result.rows.map<CaptureAuditEventView>((row) => ({
        eventId: row.event_id,
        projectId: row.project_id,
        primaryObjectKind: row.primary_object_kind,
        primaryObjectId: row.primary_object_id,
        objectSequence: integer(row.object_sequence),
        eventType: row.event_type,
        principal: {
          principalKind: row.actor_kind,
          principalId: row.actor_id,
        },
        requestId: row.request_id,
        correlationId: row.correlation_id,
        policyVersion: integer(row.policy_version),
        profileVersion: integer(
          row.profile_version ?? CAPTURE_PROFILE_V1.profileVersion,
        ),
        beforeState: row.before_state,
        afterState: row.after_state,
        resultCode: row.result_code,
        safeDetails: json(row.safe_details),
        correctedEventId: row.corrected_event_id,
        serverTime: timestamp(row.server_time),
      }));
    });
    return {
      schemaVersion: "public-page-capture-api/v1",
      messageType: "audit_events_view",
      requestId,
      events,
    };
  }

  async recordRevisionUseDecision(
    request: RecordRevisionUseDecisionRequest,
    principal: PrincipalRef,
  ): Promise<CaptureMutationReceipt> {
    const action =
      request.decision === "release_accepted"
        ? "capture_use_release"
        : "capture_use_preview";
    const authorization = await this.dependencies.authorization.authorize(
      request.projectId,
      principal,
      action,
    );
    await this.dependencies.references.validate(
      request.projectId,
      request.context,
      "use",
    );
    const idempotencyKeyDigest = sha256(request.idempotencyKey);
    const fingerprint = sha256({
      revisionId: request.revisionId,
      context: request.context,
      decision: request.decision,
    } as unknown as JsonValue);
    const now = this.now();
    return await this.dependencies.database.transaction(async (client) => {
      await this.lockIdempotency(
        client,
        request.projectId,
        principal.principalId,
        "revision_use_decision",
        idempotencyKeyDigest,
      );
      const existing = await this.existingIdempotentEffect(
        client,
        request.projectId,
        request.revisionId,
        principal.principalId,
        "revision_use_decision_recorded",
        idempotencyKeyDigest,
        fingerprint,
      );
      if (existing) {
        return {
          effectId: existing.effectId,
          duplicateDelivery: true,
          recordedAt: existing.recordedAt,
        };
      }
      const revision = await client.query<{
        capture_id: string;
        sanitized_summary: unknown;
        status: CaptureRevisionView["status"];
      }>(
        `SELECT r.capture_id, r.status, pm.sanitized_summary
           FROM capture_revisions r
           JOIN capture_provenance_manifests pm
             ON pm.project_id = r.project_id
            AND pm.provenance_id = r.provenance_id
          WHERE r.project_id = $1 AND r.revision_id = $2`,
        [request.projectId, request.revisionId],
      );
      const row = revision.rows[0];
      if (!row) this.notFound();
      const warningCodes =
        json<{ warningCodes?: string[] }>(row.sanitized_summary).warningCodes ?? [];
      const warningSetDigest = sha256([...warningCodes].sort());
      const effectDigest = sha256({
        projectId: request.projectId,
        revisionId: request.revisionId,
        context: request.context,
        decision: request.decision,
      } as unknown as JsonValue);
      const decisionId = this.id();
      await client.query(
        `INSERT INTO capture_revision_use_decisions (
            project_id, decision_id, capture_id, revision_id, decision,
            context_kind, context_resource_id, context_version_digest,
            context_occurrence_id, actor_kind, actor_id,
            authorization_decision_id, warning_set_digest, effect_digest,
            recorded_at
          ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                    $12, $13, $14, $15)`,
        [
          request.projectId,
          decisionId,
          row.capture_id,
          request.revisionId,
          request.decision,
          request.context.kind,
          request.context.resourceId,
          digestBytes(referenceVersion(request.context)),
          referenceOccurrence(request.context),
          principal.principalKind,
          principal.principalId,
          authorization.decisionId,
          digestBytes(warningSetDigest),
          digestBytes(effectDigest),
          now,
        ],
      );
      await this.appendAudit(
        client,
        {
          projectId: request.projectId,
          objectId: request.revisionId,
          objectKind: "capture_revision",
          principal,
          requestId: request.clientRequestId,
          correlationId: request.clientRequestId,
        },
        "revision_use_decision_recorded",
        row.status,
        row.status,
        request.decision,
        {
          authorizationDecisionId: authorization.decisionId,
          effectId: decisionId,
          idempotencyKeyDigest,
          requestFingerprint: fingerprint,
        },
        now,
      );
      return {
        effectId: decisionId,
        duplicateDelivery: false,
        recordedAt: now.toISOString(),
      };
    });
  }

  async selectRevision(
    request: SelectRevisionRequest,
    principal: PrincipalRef,
  ): Promise<CaptureMutationReceipt> {
    const authorization = await this.dependencies.authorization.authorize(
      request.projectId,
      principal,
      "capture_select",
    );
    await this.dependencies.references.validate(
      request.projectId,
      request.target,
      "select",
    );
    const idempotencyKeyDigest = sha256(request.idempotencyKey);
    const fingerprint = sha256({
      revisionId: request.revisionId,
      target: request.target,
      expectedPreviousSelectionId: request.expectedPreviousSelectionId,
      reason: request.reason,
      requiredUseDecisionId: request.requiredUseDecisionId,
    } as unknown as JsonValue);
    const now = this.now();
    return await this.dependencies.database.transaction(async (client) => {
      await this.lockIdempotency(
        client,
        request.projectId,
        principal.principalId,
        "revision_select",
        idempotencyKeyDigest,
      );
      const existing = await this.existingIdempotentEffect(
        client,
        request.projectId,
        request.revisionId,
        principal.principalId,
        "revision_selected",
        idempotencyKeyDigest,
        fingerprint,
      );
      if (existing) {
        return {
          effectId: existing.effectId,
          duplicateDelivery: true,
          recordedAt: existing.recordedAt,
        };
      }
      const revisionResult = await client.query<{
        capture_id: string;
        job_id: string;
        status: CaptureRevisionView["status"];
      }>(
        `SELECT capture_id, job_id, status
           FROM capture_revisions
          WHERE project_id = $1 AND revision_id = $2`,
        [request.projectId, request.revisionId],
      );
      const revision = revisionResult.rows[0];
      if (!revision) this.notFound();
      if (revision.status === "review_required") {
        if (request.requiredUseDecisionId === null) {
          throw new CaptureServiceError(
            "revision_requires_review",
            "This revision requires an explicit use decision.",
          );
        }
        const requiredDecision =
          request.target.kind === "release_build"
            ? "release_accepted"
            : "preview_acknowledged";
        const use = await client.query(
          `SELECT 1 FROM capture_revision_use_decisions
            WHERE project_id = $1 AND decision_id = $2 AND revision_id = $3
              AND context_kind = $4 AND context_resource_id = $5
              AND context_version_digest = $6
              AND context_occurrence_id IS NOT DISTINCT FROM $7
              AND decision = $8`,
          [
            request.projectId,
            request.requiredUseDecisionId,
            request.revisionId,
            request.target.kind,
            request.target.resourceId,
            digestBytes(referenceVersion(request.target)),
            referenceOccurrence(request.target),
            requiredDecision,
          ],
        );
        if (use.rows.length === 0) {
          throw new CaptureServiceError(
            "revision_requires_review",
            "The required use decision does not authorize this target.",
          );
        }
      }
      const previousResult = await client.query<{
        selection_id: string;
        target_sequence: string | number;
      }>(
        `SELECT selection_id, target_sequence
           FROM capture_revision_selections
          WHERE project_id = $1 AND target_kind = $2
            AND target_resource_id = $3 AND target_version_digest = $4
            AND target_occurrence_id IS NOT DISTINCT FROM $5
          ORDER BY target_sequence DESC
          LIMIT 1`,
        [
          request.projectId,
          request.target.kind,
          request.target.resourceId,
          digestBytes(referenceVersion(request.target)),
          referenceOccurrence(request.target),
        ],
      );
      const previous = previousResult.rows[0] ?? null;
      if ((previous?.selection_id ?? null) !== request.expectedPreviousSelectionId) {
        throw new CaptureServiceError(
          "selection_conflict",
          "The target selection changed before this revision was selected.",
        );
      }
      const jobResult = await client.query<JobRow>(
        `SELECT * FROM capture_jobs WHERE project_id = $1 AND job_id = $2`,
        [request.projectId, revision.job_id],
      );
      const job = jobResult.rows[0];
      if (!job) this.notFound();
      const selectionId = this.id();
      const sequence = integer(previous?.target_sequence ?? 0) + 1;
      const effectDigest = sha256({
        projectId: request.projectId,
        revisionId: request.revisionId,
        target: request.target,
        sequence,
        reason: request.reason,
      } as unknown as JsonValue);
      await client.query(
        `INSERT INTO capture_revision_selections (
            project_id, selection_id, capture_id, revision_id, target_kind,
            target_resource_id, target_version_digest, target_occurrence_id,
            target_sequence, previous_selection_id,
            expected_previous_selection_id, reason, actor_kind, actor_id,
            authorization_decision_id, required_use_decision_id,
            effect_digest, selected_at
          ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                    $12, $13, $14, $15, $16, $17, $18)`,
        [
          request.projectId,
          selectionId,
          revision.capture_id,
          request.revisionId,
          request.target.kind,
          request.target.resourceId,
          digestBytes(referenceVersion(request.target)),
          referenceOccurrence(request.target),
          sequence,
          previous?.selection_id ?? null,
          request.expectedPreviousSelectionId,
          request.reason,
          principal.principalKind,
          principal.principalId,
          authorization.decisionId,
          request.requiredUseDecisionId,
          digestBytes(effectDigest),
          now,
        ],
      );
      await this.insertProtection(
        client,
        job,
        request.revisionId,
        this.protectionReason(request.target),
        request.target,
        principal,
        authorization.decisionId,
        request.clientRequestId,
        now,
      );
      await this.appendAudit(
        client,
        {
          projectId: request.projectId,
          objectId: request.revisionId,
          objectKind: "capture_revision",
          principal,
          requestId: request.clientRequestId,
          correlationId: request.clientRequestId,
        },
        "revision_selected",
        revision.status,
        revision.status,
        request.reason,
        {
          authorizationDecisionId: authorization.decisionId,
          effectId: selectionId,
          idempotencyKeyDigest,
          requestFingerprint: fingerprint,
        },
        now,
      );
      return {
        effectId: selectionId,
        duplicateDelivery: false,
        recordedAt: now.toISOString(),
      };
    });
  }

  async addExplicitPin(
    request: AddExplicitPinRequest,
    principal: PrincipalRef,
  ): Promise<CaptureMutationReceipt> {
    const authorization = await this.dependencies.authorization.authorize(
      request.projectId,
      principal,
      "capture_pin",
    );
    await this.dependencies.references.validate(
      request.projectId,
      request.source,
      "protect",
    );
    const idempotencyKeyDigest = sha256(request.idempotencyKey);
    const fingerprint = sha256({
      revisionId: request.revisionId,
      source: request.source,
    } as unknown as JsonValue);
    const now = this.now();
    return await this.dependencies.database.transaction(async (client) => {
      await this.lockIdempotency(
        client,
        request.projectId,
        principal.principalId,
        "explicit_pin_add",
        idempotencyKeyDigest,
      );
      const existing = await this.existingIdempotentEffect(
        client,
        request.projectId,
        request.revisionId,
        principal.principalId,
        "explicit_pin_added",
        idempotencyKeyDigest,
        fingerprint,
      );
      if (existing) {
        return {
          effectId: existing.effectId,
          duplicateDelivery: true,
          recordedAt: existing.recordedAt,
        };
      }
      const revisionResult = await client.query<{
        capture_id: string;
        job_id: string;
        status: CaptureRevisionView["status"];
      }>(
        `SELECT capture_id, job_id, status
           FROM capture_revisions
          WHERE project_id = $1 AND revision_id = $2`,
        [request.projectId, request.revisionId],
      );
      const revision = revisionResult.rows[0];
      if (!revision) this.notFound();
      const prior = await client.query<{ protection_id: string; added_at: Date | string }>(
        `SELECT protection_id, added_at
           FROM capture_revision_protections
          WHERE project_id = $1 AND revision_id = $2
            AND reason = 'explicit_pin' AND source_kind = $3
            AND source_resource_id = $4 AND source_version_digest = $5
            AND source_occurrence_id IS NOT DISTINCT FROM $6
          LIMIT 1`,
        [
          request.projectId,
          request.revisionId,
          request.source.kind,
          request.source.resourceId,
          digestBytes(referenceVersion(request.source)),
          referenceOccurrence(request.source),
        ],
      );
      if (prior.rows[0]) {
        return {
          effectId: prior.rows[0].protection_id,
          duplicateDelivery: true,
          recordedAt: timestamp(prior.rows[0].added_at),
        };
      }
      const jobResult = await client.query<JobRow>(
        "SELECT * FROM capture_jobs WHERE project_id = $1 AND job_id = $2",
        [request.projectId, revision.job_id],
      );
      const job = jobResult.rows[0];
      if (!job) this.notFound();
      const protectionId = await this.insertProtection(
        client,
        job,
        request.revisionId,
        "explicit_pin",
        request.source,
        principal,
        authorization.decisionId,
        request.clientRequestId,
        now,
      );
      await this.appendAudit(
        client,
        {
          projectId: request.projectId,
          objectId: request.revisionId,
          objectKind: "capture_revision",
          principal,
          requestId: request.clientRequestId,
          correlationId: request.clientRequestId,
        },
        "explicit_pin_added",
        revision.status,
        revision.status,
        "pinned",
        {
          authorizationDecisionId: authorization.decisionId,
          effectId: protectionId,
          idempotencyKeyDigest,
          requestFingerprint: fingerprint,
          sourceKind: request.source.kind,
        },
        now,
      );
      return {
        effectId: protectionId,
        duplicateDelivery: false,
        recordedAt: now.toISOString(),
      };
    });
  }

  async releaseExplicitPin(
    request: ReleaseExplicitPinRequest,
    principal: PrincipalRef,
  ): Promise<CaptureMutationReceipt> {
    const authorization = await this.dependencies.authorization.authorize(
      request.projectId,
      principal,
      "capture_pin",
    );
    const idempotencyKeyDigest = sha256(request.idempotencyKey);
    const fingerprint = sha256({
      pinId: request.pinId,
      reason: request.reason,
    });
    const now = this.now();
    return await this.dependencies.database.transaction(async (client) => {
      await this.lockIdempotency(
        client,
        request.projectId,
        principal.principalId,
        "explicit_pin_release",
        idempotencyKeyDigest,
      );
      const existing = await this.existingIdempotentEffect(
        client,
        request.projectId,
        request.pinId,
        principal.principalId,
        "explicit_pin_released",
        idempotencyKeyDigest,
        fingerprint,
      );
      if (existing) {
        return {
          effectId: existing.effectId,
          duplicateDelivery: true,
          recordedAt: existing.recordedAt,
        };
      }
      const pinResult = await client.query<{
        capture_id: string;
        reason: string;
        revision_id: string;
      }>(
        `SELECT capture_id, revision_id, reason
           FROM capture_revision_protections
          WHERE project_id = $1 AND protection_id = $2`,
        [request.projectId, request.pinId],
      );
      const pin = pinResult.rows[0];
      if (!pin || pin.reason !== "explicit_pin") this.notFound();
      const priorRelease = await client.query<{
        release_id: string;
        released_at: Date | string;
      }>(
        `SELECT release_id, released_at
           FROM capture_protection_releases
          WHERE project_id = $1 AND protection_id = $2`,
        [request.projectId, request.pinId],
      );
      if (priorRelease.rows[0]) {
        return {
          effectId: priorRelease.rows[0].release_id,
          duplicateDelivery: true,
          recordedAt: timestamp(priorRelease.rows[0].released_at),
        };
      }
      const releaseId = this.id();
      const effectDigest = sha256({
        projectId: request.projectId,
        pinId: request.pinId,
        reason: request.reason,
      });
      await client.query(
        `INSERT INTO capture_protection_releases (
            project_id, release_id, protection_id, actor_kind, actor_id,
            authorization_decision_id, reason, effect_digest, released_at
          ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
        [
          request.projectId,
          releaseId,
          request.pinId,
          principal.principalKind,
          principal.principalId,
          authorization.decisionId,
          request.reason,
          digestBytes(effectDigest),
          now,
        ],
      );
      await this.appendAudit(
        client,
        {
          projectId: request.projectId,
          objectId: request.pinId,
          objectKind: "capture_revision_protection",
          principal,
          requestId: request.clientRequestId,
          correlationId: request.clientRequestId,
        },
        "explicit_pin_released",
        "active",
        "released",
        "released",
        {
          authorizationDecisionId: authorization.decisionId,
          effectId: releaseId,
          idempotencyKeyDigest,
          requestFingerprint: fingerprint,
          revisionId: pin.revision_id,
        },
        now,
      );
      return {
        effectId: releaseId,
        duplicateDelivery: false,
        recordedAt: now.toISOString(),
      };
    });
  }

  async readRasterArtifact(
    projectId: string,
    revisionId: string,
    reference: ExternalReference,
    principal: PrincipalRef,
    requestId = this.id(),
  ): Promise<CaptureArtifactRead> {
    return await this.readRevisionArtifact(
      projectId,
      revisionId,
      reference,
      principal,
      requestId,
      "capture_raster",
    );
  }

  async readRestrictedProvenance(
    projectId: string,
    revisionId: string,
    reference: ExternalReference,
    principal: PrincipalRef,
    requestId = this.id(),
  ): Promise<CaptureArtifactRead> {
    return await this.readRevisionArtifact(
      projectId,
      revisionId,
      reference,
      principal,
      requestId,
      "capture_provenance",
    );
  }

  async claimLease(request: ClaimLeaseRequest): Promise<ClaimLeaseResponse> {
    await this.dependencies.workerAuthorization.authorize(
      request.workerInstallationId,
    );
    const now = this.now();
    const supported = request.supportedProfileDigests.map((digest) => {
      digestBytes(digest);
      return digest.slice("sha256:".length);
    });
    const leaseId = this.id();
    const plannedAttemptId = this.id();
    const commitNonce = this.id();

    const assignment = await this.dependencies.database.transaction(
      async (client) => {
        const enabled = await client.query<{ enabled: boolean }>(
          `SELECT enabled
             FROM public_page_capture_settings
            WHERE setting_name = 'public_page_capture_execution'`,
        );
        if (enabled.rows[0]?.enabled !== true) {
          throw new CaptureServiceError(
            "capture_worker_unavailable",
            "Public page capture execution is not enabled.",
            true,
          );
        }
        await this.expireStaleLeases(
          client,
          now,
          request.workerInstallationId,
          request.clientRequestId,
        );

        const queued = await client.query<
          JobRow &
            ConfigurationSecretRow & {
              readonly capture_profile_json: unknown;
            }
        >(
          `SELECT j.*, cfg.canonical_url_digest,
                  cfg.restricted_request_envelope,
                  j.capture_profile_json
             FROM capture_jobs j
             JOIN capture_configurations cfg
               ON cfg.project_id = j.project_id
              AND cfg.capture_id = j.capture_id
              AND cfg.configuration_version = j.configuration_version
            WHERE j.state = 'queued'
              AND j.available_at <= $1
              AND encode(j.profile_digest, 'hex') = ANY($2::text[])
            ORDER BY j.available_at, j.requested_at, j.job_id
            FOR UPDATE OF j SKIP LOCKED
            LIMIT 1`,
          [now, supported],
        );
        const job = queued.rows[0];
        if (!job) {
          throw new CaptureServiceError(
            "capture_worker_unavailable",
            "No compatible capture job is currently available.",
            true,
          );
        }
        const profile = json<CaptureProfileV1>(job.capture_profile_json);
        this.assertProfile(profile.profileId, profile.profileVersion);
        if (profile.profileDigest !== digestString(job.profile_digest)) {
          throw new CaptureServiceError(
            "object_verification_unavailable",
            "The queued capture profile could not be verified.",
            true,
          );
        }
        const epochResult = await client.query<{ next_epoch: string | number }>(
          `SELECT coalesce(max(epoch), 0) + 1 AS next_epoch
             FROM capture_leases
            WHERE project_id = $1 AND job_id = $2`,
          [job.project_id, job.job_id],
        );
        const leaseEpoch = integer(epochResult.rows[0]?.next_epoch ?? 1);
        const baselineResult = await client.query<{
          digest: Uint8Array;
          raster_artifact_id: string;
          revision_id: string;
        }>(
          `SELECT r.revision_id, r.raster_artifact_id, a.digest
             FROM capture_revisions r
             JOIN capture_artifacts a
               ON a.project_id = r.project_id
              AND a.artifact_id = r.raster_artifact_id
            WHERE r.project_id = $1 AND r.capture_id = $2
            ORDER BY r.revision_number DESC
            LIMIT 1`,
          [job.project_id, job.capture_id],
        );
        const baseline = baselineResult.rows[0];
        const expiresAt = new Date(
          now.getTime() + profile.limits.leaseMilliseconds,
        );
        const issued = this.dependencies.capabilities.issue(
          {
            audience: "vera-public-capture-worker/v1",
            baselineArtifactId: baseline?.raster_artifact_id ?? "",
            baselineRasterDigest: baseline
              ? digestString(baseline.digest)
              : "",
            baselineRevisionId: baseline?.revision_id ?? "",
            capabilityType: "lease",
            captureId: job.capture_id,
            commitNonce,
            configurationVersion: integer(job.configuration_version),
            jobId: job.job_id,
            leaseEpoch,
            leaseId,
            operations:
              "start,navigate,renew,stage,commit,fail,abandon",
            plannedAttemptId,
            profileDigest: digestString(job.profile_digest),
            projectId: job.project_id,
            settingsDigest: digestString(job.settings_digest),
            workerInstallationId: request.workerInstallationId,
          },
          now,
          expiresAt,
        );
        await client.query(
          `INSERT INTO capture_leases (
              project_id, lease_id, job_id, capture_id, epoch,
              worker_installation_id, capability_jti_digest,
              capability_scope_digest, state, issued_at, expires_at,
              heartbeat_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
                      'issued', $9, $10, $9)`,
          [
            job.project_id,
            leaseId,
            job.job_id,
            job.capture_id,
            leaseEpoch,
            request.workerInstallationId,
            digestBytes(issued.jtiDigest),
            digestBytes(issued.scopeDigest),
            now,
            expiresAt,
          ],
        );
        await client.query(
          `UPDATE capture_jobs
              SET state = 'leased', row_version = row_version + 1
            WHERE project_id = $1 AND job_id = $2`,
          [job.project_id, job.job_id],
        );
        await this.appendAudit(
          client,
          {
            projectId: job.project_id,
            objectId: job.job_id,
            objectKind: "capture_job",
            principal: {
              principalKind: "service",
              principalId: request.workerInstallationId,
            },
            requestId: request.clientRequestId,
            correlationId: job.request_id,
          },
          "lease_claimed",
          "queued",
          "leased",
          "claimed",
          { leaseEpoch, leaseId },
          now,
        );
        const exactRequestedUrl = this.dependencies.cipher.decrypt(
          Buffer.from(job.restricted_request_envelope),
          {
            projectId: job.project_id,
            captureId: job.capture_id,
            configurationVersion: integer(job.configuration_version),
            canonicalUrlDigest: digestString(job.canonical_url_digest),
          },
        );
        return {
          projectId: job.project_id,
          captureId: job.capture_id,
          configurationVersion: integer(job.configuration_version),
          jobId: job.job_id,
          leaseId,
          leaseEpoch,
          attemptId: null,
          leaseCapability: issued.token,
          capabilityJtiDigest: issued.jtiDigest,
          capabilityScopeDigest: issued.scopeDigest,
          commitNonce,
          issuedAt: now.toISOString(),
          expiresAt: expiresAt.toISOString(),
          exactRequestedUrl,
          settingsDigest: digestString(job.settings_digest),
          profile,
        };
      },
    );
    return {
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "lease_claimed",
      requestId: request.clientRequestId,
      assignment,
    };
  }

  async startAttempt(
    request: StartAttemptRequest,
  ): Promise<StartAttemptResponse> {
    const claims = await this.verifyLeaseCapability(request.lease);
    if (request.lease.attemptId !== null) this.invalidLease();
    const now = this.now();
    const started = await this.dependencies.database.transaction(
      async (client) => {
        const current = await this.currentLease(client, request.lease, claims);
        const profile = await this.jobProfile(client, current.job);
        if (
          request.adapterVersion !== profile.adapterVersion ||
          request.securityPolicyVersion !== profile.securityPolicyVersion
        ) {
          throw new CaptureServiceError(
            "request_invalid",
            "The worker runtime does not match the frozen capture profile.",
            false,
            ["/adapterVersion"],
          );
        }
        if (current.attempt) {
          if (
            current.attempt.attempt_id !== claims.plannedAttemptId ||
            current.attempt.clean_profile_id !== request.cleanProfileId ||
            current.attempt.browser_version !== request.browserBuild ||
            current.attempt.adapter_version !== request.adapterVersion ||
            current.attempt.security_policy_version !==
              request.securityPolicyVersion
          ) {
            throw new CaptureServiceError(
              "job_not_committable",
              "This lease already started a different capture attempt.",
            );
          }
          return {
            attemptId: current.attempt.attempt_id,
            startedAt: timestamp(current.attempt.started_at),
          };
        }
        if (current.job.state !== "leased" || current.lease.state !== "issued") {
          throw new CaptureServiceError(
            "job_not_committable",
            "The job cannot start another capture attempt.",
          );
        }
        const number = await client.query<{ next_number: string | number }>(
          `SELECT coalesce(max(attempt_number), 0) + 1 AS next_number
             FROM capture_attempts
            WHERE project_id = $1 AND job_id = $2`,
          [claims.projectId, claims.jobId],
        );
        await client.query(
          `INSERT INTO capture_attempts (
              project_id, attempt_id, job_id, capture_id, lease_id,
              attempt_number, state, clean_profile_id, browser_version,
              adapter_version, security_policy_version, profile_version,
              profile_digest, started_at
            ) VALUES ($1, $2, $3, $4, $5, $6, 'started', $7, $8,
                      $9, $10, $11, $12, $13)`,
          [
            claims.projectId,
            claims.plannedAttemptId,
            claims.jobId,
            claims.captureId,
            claims.leaseId,
            integer(number.rows[0]?.next_number ?? 1),
            request.cleanProfileId,
            request.browserBuild,
            request.adapterVersion,
            request.securityPolicyVersion,
            profile.profileVersion,
            digestBytes(profile.profileDigest),
            now,
          ],
        );
        await client.query(
          `UPDATE capture_leases
              SET state = 'active', heartbeat_at = $3,
                  row_version = row_version + 1
            WHERE project_id = $1 AND lease_id = $2`,
          [claims.projectId, claims.leaseId, now],
        );
        await client.query(
          `UPDATE capture_jobs
              SET state = 'running', row_version = row_version + 1
            WHERE project_id = $1 AND job_id = $2`,
          [claims.projectId, claims.jobId],
        );
        await this.appendAudit(
          client,
          {
            projectId: claims.projectId,
            objectId: claims.plannedAttemptId,
            objectKind: "capture_attempt",
            principal: {
              principalKind: "service",
              principalId: claims.workerInstallationId,
            },
            requestId: request.clientRequestId,
            correlationId: current.job.request_id,
          },
          "attempt_started",
          null,
          "started",
          "started",
          { leaseEpoch: claims.leaseEpoch, leaseId: claims.leaseId },
          now,
        );
        return {
          attemptId: claims.plannedAttemptId,
          startedAt: now.toISOString(),
        };
      },
    );
    return {
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "attempt_started",
      requestId: request.clientRequestId,
      attemptId: started.attemptId,
      jobId: claims.jobId,
      leaseId: claims.leaseId,
      leaseEpoch: claims.leaseEpoch,
      startedAt: started.startedAt,
      browserLaunchAuthorized: true,
    };
  }

  async recordNavigationStart(
    request: RecordNavigationStartRequest,
  ): Promise<RecordNavigationStartResponse> {
    const claims = await this.verifyLeaseCapability(request.lease);
    const now = this.now();
    const recordedAt = await this.dependencies.database.transaction(
      async (client) => {
        const current = await this.currentLease(
          client,
          request.lease,
          claims,
          true,
        );
        if (!current.attempt || current.attempt.state !== "started") {
          throw new CaptureServiceError(
            "job_not_committable",
            "The capture attempt is not ready to navigate.",
          );
        }
        const configuration = await client.query<{
          canonical_url_digest: Uint8Array;
        }>(
          `SELECT canonical_url_digest
             FROM capture_configurations
            WHERE project_id = $1 AND capture_id = $2
              AND configuration_version = $3`,
          [claims.projectId, claims.captureId, claims.configurationVersion],
        );
        if (
          !configuration.rows[0] ||
          !sameDigest(
            configuration.rows[0].canonical_url_digest,
            request.initialUrlDigest,
          )
        ) {
          throw new CaptureServiceError(
            "request_invalid",
            "The initial navigation does not match the authorized request.",
            false,
            ["/initialUrlDigest"],
          );
        }
        if (current.attempt.navigation_started_at !== null) {
          return timestamp(current.attempt.navigation_started_at);
        }
        const navigationStartedAt = new Date(request.navigationStartedAt);
        await client.query(
          `UPDATE capture_attempts
              SET navigation_started_at = $3, row_version = row_version + 1
            WHERE project_id = $1 AND attempt_id = $2`,
          [claims.projectId, claims.plannedAttemptId, navigationStartedAt],
        );
        await this.appendAudit(
          client,
          {
            projectId: claims.projectId,
            objectId: claims.plannedAttemptId,
            objectKind: "capture_attempt",
            principal: {
              principalKind: "service",
              principalId: claims.workerInstallationId,
            },
            requestId: request.clientRequestId,
            correlationId: current.job.request_id,
          },
          "navigation_started",
          "started",
          "started",
          "recorded",
          { leaseEpoch: claims.leaseEpoch },
          now,
        );
        return navigationStartedAt.toISOString();
      },
    );
    return {
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "navigation_start_recorded",
      requestId: request.clientRequestId,
      attemptId: claims.plannedAttemptId,
      recordedAt,
    };
  }

  async renewLease(request: RenewLeaseRequest): Promise<RenewLeaseResponse> {
    const claims = await this.verifyLeaseCapability(request.lease);
    const now = this.now();
    const expiresAt = await this.dependencies.database.transaction(
      async (client) => {
        const current = await this.currentLease(
          client,
          request.lease,
          claims,
          request.lease.attemptId !== null,
        );
        const profile = await this.jobProfile(client, current.job);
        const nextExpiry = new Date(
          now.getTime() + profile.limits.leaseMilliseconds,
        );
        await client.query(
          `UPDATE capture_leases
              SET expires_at = $3, heartbeat_at = $4,
                  state = CASE WHEN state = 'issued' THEN 'active' ELSE state END,
                  row_version = row_version + 1
            WHERE project_id = $1 AND lease_id = $2`,
          [claims.projectId, claims.leaseId, nextExpiry, now],
        );
        return nextExpiry;
      },
    );
    return {
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "lease_renewed",
      requestId: request.clientRequestId,
      leaseId: claims.leaseId,
      leaseEpoch: claims.leaseEpoch,
      expiresAt: expiresAt.toISOString(),
      renewedAt: now.toISOString(),
    };
  }

  async requestStagingGrants(
    request: RequestStagingGrantsRequest,
  ): Promise<RequestStagingGrantsResponse> {
    const claims = await this.verifyLeaseCapability(request.lease);
    if (
      request.purposes.length !== 2 ||
      request.purposes[0] !== "raster" ||
      request.purposes[1] !== "provenance"
    ) {
      throw new CaptureServiceError(
        "request_invalid",
        "Both required staging purposes must be requested in order.",
        false,
        ["/purposes"],
      );
    }
    const now = this.now();
    const grants = await this.dependencies.database.transaction(
      async (client) => {
        const current = await this.currentLease(
          client,
          request.lease,
          claims,
          true,
        );
        if (
          !current.attempt ||
          !["started", "staged"].includes(current.attempt.state)
        ) {
          throw new CaptureServiceError(
            "job_not_committable",
            "The attempt cannot stage capture output.",
          );
        }
        const profile = await this.jobProfile(client, current.job);
        const leaseExpiry = new Date(current.lease.expires_at);
        const shortExpiry = new Date(
          Math.min(
            leaseExpiry.getTime(),
            now.getTime() + profile.limits.heartbeatMilliseconds * 2,
          ),
        );
        if (shortExpiry.getTime() <= now.getTime()) this.invalidLease();
        const values = ["raster", "provenance"].map((purpose) => {
          const grantId = this.id();
          const mimeType =
            purpose === "raster" ? "image/png" : "application/json";
          const issued = this.dependencies.capabilities.issue(
            {
              attemptId: claims.plannedAttemptId,
              capabilityType: "staging",
              grantId,
              jobId: claims.jobId,
              leaseEpoch: claims.leaseEpoch,
              leaseId: claims.leaseId,
              maxBytes: profile.limits.rasterBytes,
              mimeType,
              projectId: claims.projectId,
              purpose,
              workerInstallationId: claims.workerInstallationId,
            },
            now,
            shortExpiry,
          );
          return {
            grantId,
            purpose,
            rawGrant: issued.token,
            grantDigest: issued.tokenDigest,
            attemptId: claims.plannedAttemptId,
            leaseEpoch: claims.leaseEpoch,
            maxBytes: profile.limits.rasterBytes,
            mimeType,
            issuedAt: now.toISOString(),
            expiresAt: shortExpiry.toISOString(),
          } as StagingGrant;
        });
        return grantsTuple(values);
      },
    );
    return {
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "staging_grants_issued",
      requestId: request.clientRequestId,
      grants,
    };
  }

  async authorizeStagingUpload(
    rawGrant: string,
    workerInstallationId: string,
  ): Promise<StagingUploadAuthorization> {
    try {
      await this.dependencies.workerAuthorization.authorize(workerInstallationId);
      const claims = this.dependencies.capabilities.verify(rawGrant, this.now(), {
        capabilityType: "staging",
        workerInstallationId,
      });
      const purpose = claimString(claims, "purpose");
      const mimeType = claimString(claims, "mimeType");
      const maxBytes = claimInteger(claims, "maxBytes");
      if (
        (purpose !== "raster" && purpose !== "provenance") ||
        (mimeType !== "image/png" && mimeType !== "application/json")
      ) {
        throw new CapabilityError("capability_scope_mismatch");
      }
      return { maxBytes, mimeType };
    } catch (error) {
      if (error instanceof CaptureServiceError) throw error;
      this.invalidLease();
    }
  }

  async stageObject(
    rawGrant: string,
    workerInstallationId: string,
    bytes: Buffer,
  ): Promise<StagedObject> {
    try {
      await this.dependencies.workerAuthorization.authorize(workerInstallationId);
      const claims = this.dependencies.capabilities.verify(rawGrant, this.now(), {
        capabilityType: "staging",
        workerInstallationId,
      });
      const projectId = claimString(claims, "projectId");
      const jobId = claimString(claims, "jobId");
      const leaseId = claimString(claims, "leaseId");
      const attemptId = claimString(claims, "attemptId");
      const grantId = claimString(claims, "grantId");
      const purpose = claimString(claims, "purpose");
      const mimeType = claimString(claims, "mimeType");
      const leaseEpoch = claimInteger(claims, "leaseEpoch");
      const maxBytes = claimInteger(claims, "maxBytes");
      if (
        (purpose !== "raster" && purpose !== "provenance") ||
        (mimeType !== "image/png" && mimeType !== "application/json")
      ) {
        throw new CapabilityError("capability_scope_mismatch");
      }
      await this.dependencies.database.transaction(async (client) => {
        const lease = await client.query<LeaseRow>(
          `SELECT * FROM capture_leases
            WHERE project_id = $1 AND lease_id = $2
            FOR UPDATE`,
          [projectId, leaseId],
        );
        const attempt = await client.query<AttemptRow>(
          `SELECT * FROM capture_attempts
            WHERE project_id = $1 AND attempt_id = $2`,
          [projectId, attemptId],
        );
        const current = lease.rows[0];
        const execution = attempt.rows[0];
        if (
          !current ||
          !execution ||
          current.job_id !== jobId ||
          current.worker_installation_id !== workerInstallationId ||
          integer(current.epoch) !== leaseEpoch ||
          !["issued", "active"].includes(current.state) ||
          new Date(current.expires_at).getTime() <= this.now().getTime() ||
          execution.lease_id !== leaseId ||
          !["started", "staged"].includes(execution.state)
        ) {
          this.invalidLease();
        }
      });
      const grant: VerifiedStagingGrant = {
        grantId,
        projectId,
        jobId,
        attemptId,
        leaseEpoch,
        purpose,
        mimeType,
        maxBytes,
        expiresAt: new Date(claims.exp * 1000).toISOString(),
      };
      const staged = await this.dependencies.objects.stage(
        grant,
        bytes,
        this.now(),
      );
      await this.dependencies.database.transaction(async (client) => {
        const current = await client.query<LeaseRow>(
          `SELECT * FROM capture_leases
            WHERE project_id = $1 AND lease_id = $2
            FOR UPDATE`,
          [projectId, leaseId],
        );
        if (
          !current.rows[0] ||
          !["issued", "active"].includes(current.rows[0].state) ||
          new Date(current.rows[0].expires_at).getTime() <= this.now().getTime()
        ) {
          this.invalidLease();
        }
        await client.query(
          `UPDATE capture_attempts
              SET state = 'staged', staged_at = coalesce(staged_at, $3),
                  row_version = row_version + 1
            WHERE project_id = $1 AND attempt_id = $2
              AND state IN ('started', 'staged')`,
          [projectId, attemptId, this.now()],
        );
      });
      return staged;
    } catch (error) {
      if (error instanceof ObjectStoreError) {
        if (
          [
            "staging_grant_consumed",
            "staging_grant_expired",
            "staging_scope_mismatch",
          ].includes(error.code)
        ) {
          this.invalidLease();
        }
        throw new CaptureServiceError(
          error.code === "staging_limit_exceeded"
            ? "capture_resource_limit"
            : "object_verification_unavailable",
          "The staged object could not be accepted.",
          false,
        );
      }
      if (error instanceof CaptureServiceError) throw error;
      this.invalidLease();
    }
  }

  async commitAttempt(
    request: CommitAttemptRequest,
  ): Promise<CommitAttemptResponse> {
    const claims = await this.verifyLeaseCapability(request.lease);
    if (request.commitNonce !== claims.commitNonce) this.invalidLease();
    const recovered = await this.recoverCommittedAttempt(
      claims,
      request.clientRequestId,
    );
    if (recovered) return recovered;

    const rasterCandidate = await this.verifyStagedObject(
      request.raster,
      claims,
      "raster",
    );
    const provenanceCandidate = await this.verifyStagedObject(
      request.provenanceObject,
      claims,
      "provenance",
    );
    let verifiedRaster: ReturnType<typeof verifyPng>;
    let provenance: PublicPageCaptureProvenanceV1;
    try {
      verifiedRaster = verifyPng(rasterCandidate.bytes, {
        expectedWidth: OUTPUT_WIDTH,
        expectedHeight: OUTPUT_HEIGHT,
        maxBytes: CAPTURE_PROFILE_V1.limits.rasterBytes,
        maxPixels: CAPTURE_PROFILE_V1.limits.outputPixels,
      });
      provenance = this.parseProvenance(provenanceCandidate.bytes);
    } catch (error) {
      if (
        error instanceof RasterVerificationError ||
        error instanceof ObjectStoreError
      ) {
        throw new CaptureServiceError(
          "object_verification_unavailable",
          "The staged capture output failed verification.",
          false,
        );
      }
      throw error;
    }
    this.assertRevisionProvenance(provenance, claims, verifiedRaster, request);

    const job = await this.loadJobForCapability(claims);
    const initiatingPrincipal: PrincipalRef = {
      principalKind: job.initiating_principal_kind,
      principalId: job.initiating_principal_id,
    };
    const commitAuthorization = await this.dependencies.authorization.authorize(
      claims.projectId,
      initiatingPrincipal,
      "capture_commit",
    );
    if (job.trigger_kind === "on_build") {
      await this.dependencies.references.validate(
        claims.projectId,
        this.jobBuildReference(job),
        "protect",
      );
    }
    let selectionAuthorization: AuthorizationDecisionRef | null = null;
    if (
      request.reviewClassification === "ready" &&
      job.trigger_kind === "now" &&
      job.conditional_selection_intent !== null
    ) {
      selectionAuthorization = await this.dependencies.authorization.authorize(
        claims.projectId,
        initiatingPrincipal,
        "capture_select",
      );
      await this.dependencies.references.validate(
        claims.projectId,
        json<Extract<SelectionIntent, { kind: "conditional" }>>(
          job.conditional_selection_intent,
        ).target,
        "select",
      );
    }

    const now = this.now();
    const revisionId = provenance.identity.revisionId;
    if (revisionId === null) {
      throw new CaptureServiceError(
        "request_invalid",
        "Revision provenance must name a revision.",
        false,
        ["/provenanceObject"],
      );
    }
    const publishedRevisionId = await this.dependencies.database.transaction(
      async (client) => {
        const current = await this.currentLease(
          client,
          request.lease,
          claims,
          true,
        );
        if (
          current.job.state !== "running" ||
          !current.attempt ||
          !["started", "staged"].includes(current.attempt.state)
        ) {
          throw new CaptureServiceError(
            "job_not_committable",
            "The capture attempt is not in a committable state.",
          );
        }
        const captureResult = await client.query<{
          next_revision_number: string | number;
        }>(
          `SELECT next_revision_number
             FROM captures
            WHERE project_id = $1 AND capture_id = $2
            FOR UPDATE`,
          [claims.projectId, claims.captureId],
        );
        if (!captureResult.rows[0]) this.notFound();
        await client.query(
          "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
          [`${claims.projectId}:${claims.captureId}:capture-commit`],
        );

        const baseline = await this.latestRevision(client, claims);
        const rasterArtifactId = captureRasterArtifactId(
          claims.projectId,
          verifiedRaster.digest,
          verifiedRaster.byteLength,
          verifiedRaster.width,
          verifiedRaster.height,
          verifiedRaster.alpha,
        );
        await client.query(
          "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
          [`${claims.projectId}:${rasterArtifactId}`],
        );
        const existingArtifact = await this.exactRasterArtifact(
          client,
          claims.projectId,
          rasterArtifactId,
          verifiedRaster,
        );
        const rasterReused = existingArtifact !== null;
        let rasterArtifact: ArtifactRow;
        if (existingArtifact) {
          if (
            !(await this.dependencies.objects.bytesEqual(
              existingArtifact.object_store_id,
              rasterCandidate.bytes,
            ))
          ) {
            throw new CaptureServiceError(
              "object_verification_unavailable",
              "An exact-byte artifact candidate failed byte verification.",
              false,
            );
          }
          rasterArtifact = existingArtifact;
        } else {
          const promoted = await this.dependencies.objects.promote(
            rasterCandidate.staged.stagingObjectId,
            claims.projectId,
            "capture_raster",
          );
          await this.insertRasterArtifact(
            client,
            claims,
            rasterArtifactId,
            promoted,
            verifiedRaster,
            now,
          );
          rasterArtifact = await this.artifactRow(
            client,
            claims.projectId,
            rasterArtifactId,
          );
        }

        const status = this.commitStatus(request);
        const change = await this.computeChange(
          baseline,
          rasterArtifact,
          provenance,
          claims,
        );
        const finalProvenance = await this.finalizeProvenance(
          client,
          provenance,
          current,
          commitAuthorization,
          rasterArtifact,
          rasterReused,
          baseline,
          change,
          status,
          request.warningCodes,
          now,
        );
        const finalProvenanceBytes = Buffer.from(
          canonicalJson(finalProvenance as unknown as JsonValue),
          "utf8",
        );
        if (
          finalProvenanceBytes.byteLength >
          CAPTURE_PROFILE_V1.limits.rasterBytes
        ) {
          throw new CaptureServiceError(
            "capture_resource_limit",
            "The provenance record exceeds the capture profile limit.",
            false,
          );
        }
        validateProvenance(finalProvenance);
        const finalStage = await this.dependencies.objects.stage(
          {
            grantId: this.id(),
            projectId: claims.projectId,
            jobId: claims.jobId,
            attemptId: claims.plannedAttemptId,
            leaseEpoch: claims.leaseEpoch,
            purpose: "provenance",
            mimeType: "application/json",
            maxBytes: CAPTURE_PROFILE_V1.limits.rasterBytes,
            expiresAt: new Date(now.getTime() + 60_000).toISOString(),
          },
          finalProvenanceBytes,
          now,
        );
        const promotedProvenance = await this.dependencies.objects.promote(
          finalStage.stagingObjectId,
          claims.projectId,
          "capture_provenance",
        );
        const provenanceArtifactId = this.id();
        const provenanceId = this.id();
        const changeSignalId = this.id();
        await this.insertProvenanceArtifact(
          client,
          claims,
          provenanceArtifactId,
          promotedProvenance,
          now,
        );
        await client.query(
          `INSERT INTO capture_provenance_manifests (
              project_id, provenance_id, capture_id, job_id, attempt_id,
              evidence_type, provenance_artifact_id, schema_version,
              manifest_digest, manifest_length, redaction_version,
              sanitized_summary, created_at
            ) VALUES ($1, $2, $3, $4, $5, 'revision_observation', $6,
                      'public-page-capture-provenance/v1', $7, $8,
                      'vera-url-redaction-v1', $9::jsonb, $10)`,
          [
            claims.projectId,
            provenanceId,
            claims.captureId,
            claims.jobId,
            claims.plannedAttemptId,
            provenanceArtifactId,
            digestBytes(promotedProvenance.digest),
            promotedProvenance.byteLength,
            JSON.stringify({
              evidenceClass: finalProvenance.network.evidenceClass,
              recordType: finalProvenance.recordType,
              status,
              warningCodes: request.warningCodes,
            }),
            now,
          ],
        );
        const revisionNumber = integer(
          captureResult.rows[0].next_revision_number,
        );
        await client.query(
          `INSERT INTO capture_revisions (
              project_id, revision_id, capture_id, configuration_version,
              job_id, winning_attempt_id, revision_number,
              raster_artifact_id, provenance_id, status, settings_digest,
              profile_digest, committed_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)`,
          [
            claims.projectId,
            revisionId,
            claims.captureId,
            claims.configurationVersion,
            claims.jobId,
            claims.plannedAttemptId,
            revisionNumber,
            rasterArtifact.artifact_id,
            provenanceId,
            status,
            current.job.settings_digest,
            current.job.profile_digest,
            now,
          ],
        );
        await this.insertChangeSignal(
          client,
          claims,
          revisionId,
          changeSignalId,
          rasterArtifact.artifact_id,
          baseline,
          change,
          now,
        );
        await this.applyCommitEffects(
          client,
          current.job,
          revisionId,
          status,
          initiatingPrincipal,
          selectionAuthorization,
          request.clientRequestId,
          now,
        );
        await client.query(
          `UPDATE capture_attempts
              SET state = 'committed', staged_at = coalesce(staged_at, $3),
                  terminal_at = $3, row_version = row_version + 1
            WHERE project_id = $1 AND attempt_id = $2`,
          [claims.projectId, claims.plannedAttemptId, now],
        );
        await client.query(
          `UPDATE capture_leases
              SET state = 'released', terminal_at = $3,
                  row_version = row_version + 1
            WHERE project_id = $1 AND lease_id = $2`,
          [claims.projectId, claims.leaseId, now],
        );
        const jobState =
          status === "ready"
            ? "committed_ready"
            : "committed_review_required";
        await client.query(
          `UPDATE capture_jobs
              SET state = $3, output_revision_id = $4, terminal_at = $5,
                  row_version = row_version + 1
            WHERE project_id = $1 AND job_id = $2`,
          [claims.projectId, claims.jobId, jobState, revisionId, now],
        );
        await client.query(
          `UPDATE captures
              SET next_revision_number = next_revision_number + 1,
                  row_version = row_version + 1, updated_at = $3
            WHERE project_id = $1 AND capture_id = $2`,
          [claims.projectId, claims.captureId, now],
        );
        await this.appendAudit(
          client,
          {
            projectId: claims.projectId,
            objectId: claims.jobId,
            objectKind: "capture_job",
            principal: {
              principalKind: "service",
              principalId: claims.workerInstallationId,
            },
            requestId: request.clientRequestId,
            correlationId: current.job.request_id,
          },
          "revision_committed",
          "running",
          jobState,
          status,
          {
            artifactId: rasterArtifact.artifact_id,
            changeSignalId,
            leaseEpoch: claims.leaseEpoch,
            provenanceId,
            revisionId,
          },
          now,
        );
        return revisionId;
      },
    );

    const [jobMessage, revisionMessage] = await Promise.all([
      this.jobMessage(
        claims.projectId,
        claims.jobId,
        request.clientRequestId,
        false,
      ),
      this.revisionMessage(
        claims.projectId,
        publishedRevisionId,
        request.clientRequestId,
      ),
    ]);
    return {
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "attempt_committed",
      requestId: request.clientRequestId,
      job: jobMessage.job,
      revision: revisionMessage.revision,
      recoveredExistingOutcome: false,
    };
  }

  async failAttempt(request: FailAttemptRequest): Promise<FailAttemptResponse> {
    const result = await this.recordTerminalAttempt(request, "failed");
    return {
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "attempt_failed",
      requestId: request.clientRequestId,
      jobId: result.jobId,
      attemptId: result.attemptId,
      jobState: result.jobState,
      recordedAt: result.recordedAt,
    };
  }

  async abandonAttempt(
    request: AbandonAttemptRequest,
  ): Promise<AbandonAttemptResponse> {
    const result = await this.recordTerminalAttempt(request, "abandoned");
    return {
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "attempt_abandoned",
      requestId: request.clientRequestId,
      jobId: result.jobId,
      attemptId: result.attemptId,
      recordedAt: result.recordedAt,
    };
  }

  private async recordTerminalAttempt(
    request: FailAttemptRequest | AbandonAttemptRequest,
    outcome: "abandoned" | "failed",
  ): Promise<{
    readonly attemptId: string;
    readonly jobId: string;
    readonly jobState: "failed" | "queued";
    readonly recordedAt: string;
  }> {
    const claims = await this.verifyLeaseCapability(request.lease);
    const existing = await this.recoverTerminalAttempt(claims);
    if (existing) return existing;
    const candidate = await this.verifyStagedObject(
      request.terminalEvidenceObject,
      claims,
      "provenance",
    );
    const evidence = this.parseProvenance(candidate.bytes);
    const terminal = evidence.terminal;
    if (
      evidence.recordType !== "terminal_attempt_evidence" ||
      evidence.identity.projectId !== claims.projectId ||
      evidence.identity.captureId !== claims.captureId ||
      evidence.identity.jobId !== claims.jobId ||
      evidence.identity.leaseEpoch !== claims.leaseEpoch ||
      evidence.identity.attemptId !== claims.plannedAttemptId ||
      evidence.identity.revisionId !== null ||
      evidence.runtime.installationId !== claims.workerInstallationId ||
      evidence.output !== null ||
      evidence.change !== null ||
      terminal === null ||
      (outcome === "abandoned"
        ? terminal.outcome !== "abandoned"
        : !["denied", "failed"].includes(terminal.outcome)) ||
      terminal.code !== request.terminalCode
    ) {
      throw new CaptureServiceError(
        "object_verification_unavailable",
        "Terminal attempt evidence does not match the worker outcome.",
        false,
      );
    }
    if (
      "navigationStarted" in request &&
      terminal.navigationStarted !== request.navigationStarted
    ) {
      throw new CaptureServiceError(
        "object_verification_unavailable",
        "Terminal navigation evidence is inconsistent.",
        false,
      );
    }
    const now = this.now();
    const promoted = await this.dependencies.objects.promote(
      candidate.staged.stagingObjectId,
      claims.projectId,
      "capture_provenance",
    );
    return await this.dependencies.database.transaction(async (client) => {
      const already = await this.terminalAttemptRow(client, claims);
      if (already) return already;
      const leaseResult = await client.query<LeaseRow>(
        `SELECT * FROM capture_leases
          WHERE project_id = $1 AND lease_id = $2
          FOR UPDATE`,
        [claims.projectId, claims.leaseId],
      );
      const lease = leaseResult.rows[0];
      if (!lease) this.invalidLease();
      this.assertPersistedLeaseIdentity(lease, claims);
      const jobResult = await client.query<JobRow>(
        `SELECT * FROM capture_jobs
          WHERE project_id = $1 AND job_id = $2
          FOR UPDATE`,
        [claims.projectId, claims.jobId],
      );
      const attemptResult = await client.query<AttemptRow>(
        `SELECT * FROM capture_attempts
          WHERE project_id = $1 AND attempt_id = $2
          FOR UPDATE`,
        [claims.projectId, claims.plannedAttemptId],
      );
      const job = jobResult.rows[0];
      const attempt = attemptResult.rows[0];
      if (
        !job ||
        !attempt ||
        attempt.lease_id !== claims.leaseId ||
        !["started", "staged"].includes(attempt.state) ||
        job.output_revision_id !== null
      ) {
        throw new CaptureServiceError(
          "job_not_committable",
          "The capture attempt can no longer record this outcome.",
          false,
        );
      }
      if (
        outcome === "failed" &&
        (!["issued", "active"].includes(lease.state) ||
          new Date(lease.expires_at).getTime() <= now.getTime())
      ) {
        this.invalidLease();
      }
      const provenanceArtifactId = this.id();
      const provenanceId = this.id();
      await this.insertProvenanceArtifact(
        client,
        claims,
        provenanceArtifactId,
        promoted,
        now,
      );
      await client.query(
        `INSERT INTO capture_provenance_manifests (
            project_id, provenance_id, capture_id, job_id, attempt_id,
            evidence_type, provenance_artifact_id, schema_version,
            manifest_digest, manifest_length, redaction_version,
            sanitized_summary, created_at
          ) VALUES ($1, $2, $3, $4, $5, 'terminal_attempt_evidence', $6,
                    'public-page-capture-provenance/v1', $7, $8,
                    'vera-url-redaction-v1', $9::jsonb, $10)`,
        [
          claims.projectId,
          provenanceId,
          claims.captureId,
          claims.jobId,
          claims.plannedAttemptId,
          provenanceArtifactId,
          digestBytes(promoted.digest),
          promoted.byteLength,
          JSON.stringify({
            navigationStarted: terminal.navigationStarted,
            outcome: terminal.outcome,
            terminalCode: request.terminalCode,
          }),
          now,
        ],
      );
      const retryRequested =
        outcome === "abandoned" ||
        ("retryable" in request && request.retryable);
      const retryAllowed =
        retryRequested && attempt.attempt_number <= job.retry_budget;
      const anotherLease = await client.query(
        `SELECT 1 FROM capture_leases
          WHERE project_id = $1 AND job_id = $2 AND epoch > $3
            AND state IN ('issued', 'active')
          LIMIT 1`,
        [claims.projectId, claims.jobId, claims.leaseEpoch],
      );
      const preserveNewerJob = anotherLease.rows.length > 0;
      const jobState: "failed" | "queued" = retryAllowed
        ? "queued"
        : "failed";
      await client.query(
        `UPDATE capture_attempts
            SET state = $3, terminal_at = $4, terminal_code = $5,
                diagnostic_digest = $6, row_version = row_version + 1
          WHERE project_id = $1 AND attempt_id = $2`,
        [
          claims.projectId,
          claims.plannedAttemptId,
          outcome,
          now,
          request.terminalCode,
          digestBytes(promoted.digest),
        ],
      );
      await client.query(
        `UPDATE capture_leases
            SET state = CASE
                  WHEN state IN ('issued', 'active') THEN $3
                  ELSE state
                END,
                terminal_at = coalesce(terminal_at, $4),
                row_version = row_version + 1
          WHERE project_id = $1 AND lease_id = $2`,
        [
          claims.projectId,
          claims.leaseId,
          outcome === "failed" ? "released" : "revoked",
          now,
        ],
      );
      if (
        !preserveNewerJob &&
        ![
          "committed_ready",
          "committed_review_required",
          "cancelled",
          "rejected",
        ].includes(job.state)
      ) {
        await client.query(
          `UPDATE capture_jobs
              SET state = $3,
                  available_at = CASE WHEN $3 = 'queued' THEN $4 ELSE available_at END,
                  terminal_at = CASE WHEN $3 = 'failed' THEN $4 ELSE NULL END,
                  row_version = row_version + 1
            WHERE project_id = $1 AND job_id = $2`,
          [claims.projectId, claims.jobId, jobState, now],
        );
      }
      await this.appendAudit(
        client,
        {
          projectId: claims.projectId,
          objectId: claims.plannedAttemptId,
          objectKind: "capture_attempt",
          principal: {
            principalKind: "service",
            principalId: claims.workerInstallationId,
          },
          requestId: request.clientRequestId,
          correlationId: job.request_id,
        },
        outcome === "failed" ? "attempt_failed" : "attempt_abandoned",
        attempt.state,
        outcome,
        request.terminalCode,
        {
          jobState,
          leaseEpoch: claims.leaseEpoch,
          provenanceId,
          retryAllowed,
        },
        now,
      );
      return {
        attemptId: claims.plannedAttemptId,
        jobId: claims.jobId,
        jobState,
        recordedAt: now.toISOString(),
      };
    });
  }

  private async recoverTerminalAttempt(
    claims: LeaseClaims,
  ): Promise<{
    readonly attemptId: string;
    readonly jobId: string;
    readonly jobState: "failed" | "queued";
    readonly recordedAt: string;
  } | null> {
    return await this.dependencies.database.transaction(async (client) => {
      const leaseResult = await client.query<LeaseRow>(
        `SELECT * FROM capture_leases
          WHERE project_id = $1 AND lease_id = $2`,
        [claims.projectId, claims.leaseId],
      );
      const lease = leaseResult.rows[0];
      if (!lease) this.invalidLease();
      this.assertPersistedLeaseIdentity(lease, claims);
      return await this.terminalAttemptRow(client, claims);
    });
  }

  private async terminalAttemptRow(
    client: SqlClient,
    claims: LeaseClaims,
  ): Promise<{
    readonly attemptId: string;
    readonly jobId: string;
    readonly jobState: "failed" | "queued";
    readonly recordedAt: string;
  } | null> {
    const result = await client.query<{
      attempt_state: AttemptRow["state"];
      job_state: JobRow["state"];
      terminal_at: Date | string | null;
    }>(
      `SELECT a.state AS attempt_state, a.terminal_at, j.state AS job_state
         FROM capture_attempts a
         JOIN capture_jobs j
           ON j.project_id = a.project_id AND j.job_id = a.job_id
        WHERE a.project_id = $1 AND a.attempt_id = $2`,
      [claims.projectId, claims.plannedAttemptId],
    );
    const row = result.rows[0];
    if (!row || !["failed", "abandoned"].includes(row.attempt_state)) {
      return null;
    }
    return {
      attemptId: claims.plannedAttemptId,
      jobId: claims.jobId,
      jobState: row.job_state === "failed" ? "failed" : "queued",
      recordedAt: timestamp(row.terminal_at ?? this.now()),
    };
  }

  private async expireStaleLeases(
    client: SqlClient,
    now: Date,
    workerInstallationId: string,
    requestId: string,
  ): Promise<void> {
    const result = await client.query<
      LeaseRow & {
        readonly attempt_id: string | null;
        readonly attempt_state: AttemptRow["state"] | null;
        readonly request_id: string;
        readonly retry_budget: number;
      }
    >(
      `SELECT l.*, j.request_id, j.retry_budget,
              a.attempt_id, a.state AS attempt_state
         FROM capture_leases l
         JOIN capture_jobs j
           ON j.project_id = l.project_id AND j.job_id = l.job_id
         LEFT JOIN capture_attempts a
           ON a.project_id = l.project_id AND a.lease_id = l.lease_id
        WHERE l.state IN ('issued', 'active')
          AND l.expires_at <= $1
          AND j.output_revision_id IS NULL
          AND j.state IN ('leased', 'running')
        ORDER BY l.expires_at, l.lease_id
        FOR UPDATE OF l, j SKIP LOCKED
        LIMIT 100`,
      [now],
    );
    for (const lease of result.rows) {
      const retryAllowed = integer(lease.epoch) <= lease.retry_budget;
      const nextJobState: "failed" | "queued" = retryAllowed
        ? "queued"
        : "failed";
      if (
        lease.attempt_id !== null &&
        lease.attempt_state !== null &&
        ["started", "staged"].includes(lease.attempt_state)
      ) {
        await client.query(
          `UPDATE capture_attempts
              SET state = 'abandoned', terminal_at = $3,
                  terminal_code = 'lease_expired', diagnostic_digest = $4,
                  row_version = row_version + 1
            WHERE project_id = $1 AND attempt_id = $2
              AND state IN ('started', 'staged')`,
          [
            lease.project_id,
            lease.attempt_id,
            now,
            digestBytes(
              sha256({
                jobId: lease.job_id,
                leaseEpoch: integer(lease.epoch),
                outcome: "abandoned",
                terminalCode: "lease_expired",
              }),
            ),
          ],
        );
      }
      await client.query(
        `UPDATE capture_leases
            SET state = 'expired', terminal_at = $3,
                row_version = row_version + 1
          WHERE project_id = $1 AND lease_id = $2
            AND state IN ('issued', 'active')`,
        [lease.project_id, lease.lease_id, now],
      );
      await client.query(
        `UPDATE capture_jobs
            SET state = $3, available_at = CASE WHEN $3 = 'queued' THEN $4 ELSE available_at END,
                terminal_at = CASE WHEN $3 = 'failed' THEN $4 ELSE NULL END,
                row_version = row_version + 1
          WHERE project_id = $1 AND job_id = $2
            AND output_revision_id IS NULL
            AND state IN ('leased', 'running')`,
        [lease.project_id, lease.job_id, nextJobState, now],
      );
      await this.appendAudit(
        client,
        {
          projectId: lease.project_id,
          objectId: lease.attempt_id ?? lease.job_id,
          objectKind:
            lease.attempt_id === null ? "capture_job" : "capture_attempt",
          principal: {
            principalKind: "service",
            principalId: workerInstallationId,
          },
          requestId,
          correlationId: lease.request_id,
        },
        "lease_expired",
        lease.attempt_state ?? lease.state,
        lease.attempt_id === null ? nextJobState : "abandoned",
        "lease_expired",
        {
          jobState: nextJobState,
          leaseEpoch: integer(lease.epoch),
          leaseId: lease.lease_id,
          retryAllowed,
        },
        now,
      );
    }
  }

  private async verifyStagedObject(
    descriptor: StagedObjectDescriptor,
    claims: LeaseClaims,
    purpose: "provenance" | "raster",
  ): Promise<VerifiedStagedCandidate> {
    try {
      const [staged, bytes] = await Promise.all([
        this.dependencies.objects.describeStaged(descriptor.stagingObjectId),
        this.dependencies.objects.readStaged(descriptor.stagingObjectId),
      ]);
      if (
        staged.grantId !== descriptor.grantId ||
        staged.projectId !== claims.projectId ||
        staged.jobId !== claims.jobId ||
        staged.attemptId !== claims.plannedAttemptId ||
        staged.leaseEpoch !== claims.leaseEpoch ||
        staged.purpose !== purpose ||
        descriptor.purpose !== purpose ||
        staged.digest !== descriptor.digest ||
        staged.byteLength !== descriptor.byteLength ||
        staged.mimeType !== descriptor.mimeType ||
        sha256(bytes) !== descriptor.digest ||
        bytes.byteLength !== descriptor.byteLength
      ) {
        throw new ObjectStoreError("staging_scope_mismatch");
      }
      return { bytes, staged };
    } catch (error) {
      if (error instanceof CaptureServiceError) throw error;
      throw new CaptureServiceError(
        "object_verification_unavailable",
        "The staged object could not be verified.",
        false,
      );
    }
  }

  private parseProvenance(bytes: Buffer): PublicPageCaptureProvenanceV1 {
    let value: unknown;
    try {
      value = JSON.parse(bytes.toString("utf8"));
      validateProvenance(value);
      if (
        canonicalJson(value as JsonValue) !==
        bytes.toString("utf8")
      ) {
        throw new Error("noncanonical provenance");
      }
    } catch {
      throw new CaptureServiceError(
        "object_verification_unavailable",
        "The provenance record failed schema or canonical-byte verification.",
        false,
      );
    }
    return value as PublicPageCaptureProvenanceV1;
  }

  private assertRevisionProvenance(
    provenance: PublicPageCaptureProvenanceV1,
    claims: LeaseClaims,
    raster: ReturnType<typeof verifyPng>,
    request: CommitAttemptRequest,
  ): void {
    const output = provenance.output;
    if (
      provenance.recordType !== "revision_observation" ||
      provenance.identity.projectId !== claims.projectId ||
      provenance.identity.captureId !== claims.captureId ||
      provenance.identity.configurationVersionId !==
        captureConfigurationVersionId(
          claims.projectId,
          claims.captureId,
          claims.configurationVersion,
        ) ||
      provenance.identity.jobId !== claims.jobId ||
      provenance.identity.leaseEpoch !== claims.leaseEpoch ||
      provenance.identity.attemptId !== claims.plannedAttemptId ||
      provenance.identity.revisionId === null ||
      provenance.request.settingsDigest !== claims.settingsDigest ||
      provenance.request.captureProfileDigest !== claims.profileDigest ||
      provenance.runtime.installationId !== claims.workerInstallationId ||
      !output ||
      output.raster.digest !== raster.digest ||
      output.raster.byteLength !== raster.byteLength ||
      output.raster.mediaType !== "image/png" ||
      output.width !== raster.width ||
      output.height !== raster.height
    ) {
      throw new CaptureServiceError(
        "object_verification_unavailable",
        "The provenance record does not match the staged attempt.",
        false,
      );
    }
    const provenanceWarningCodes = provenance.honesty.warnings
      .map(({ code }) => code)
      .sort();
    const requestWarningCodes = [...request.warningCodes].sort();
    if (
      canonicalJson(provenanceWarningCodes) !==
      canonicalJson(requestWarningCodes)
    ) {
      throw new CaptureServiceError(
        "object_verification_unavailable",
        "The warning evidence does not match the commit request.",
        false,
      );
    }
  }

  private commitStatus(
    request: CommitAttemptRequest,
  ): "ready" | "review_required" {
    if (
      request.warningCodes.length > 0 &&
      request.reviewClassification !== "review_required"
    ) {
      throw new CaptureServiceError(
        "job_not_committable",
        "Capture warnings require review before use.",
        false,
      );
    }
    return request.reviewClassification;
  }

  private async loadJobForCapability(claims: LeaseClaims): Promise<JobRow> {
    return await this.dependencies.database.transaction(async (client) => {
      const leaseResult = await client.query<LeaseRow>(
        `SELECT * FROM capture_leases
          WHERE project_id = $1 AND lease_id = $2`,
        [claims.projectId, claims.leaseId],
      );
      const lease = leaseResult.rows[0];
      if (!lease) this.invalidLease();
      this.assertPersistedLeaseIdentity(lease, claims);
      const result = await client.query<JobRow>(
        `SELECT * FROM capture_jobs
          WHERE project_id = $1 AND job_id = $2`,
        [claims.projectId, claims.jobId],
      );
      const job = result.rows[0];
      if (!job) this.invalidLease();
      return job;
    });
  }

  private jobBuildReference(job: JobRow): VersionedExternalReference {
    if (
      job.trigger_kind !== "on_build" ||
      job.trigger_reference_digest === null ||
      (job.trigger_reference_kind !== "preview_build" &&
        job.trigger_reference_kind !== "release_build")
    ) {
      throw new CaptureServiceError(
        "job_not_committable",
        "The build trigger could not be revalidated.",
      );
    }
    return {
      projectId: job.project_id,
      kind: job.trigger_reference_kind,
      resourceId: job.trigger_reference_id,
      resourceVersionDigest: digestString(job.trigger_reference_digest),
    };
  }

  private async recoverCommittedAttempt(
    claims: LeaseClaims,
    requestId: string,
  ): Promise<CommitAttemptResponse | null> {
    const revisionId = await this.dependencies.database.transaction(
      async (client) => {
        const leaseResult = await client.query<LeaseRow>(
          `SELECT * FROM capture_leases
            WHERE project_id = $1 AND lease_id = $2`,
          [claims.projectId, claims.leaseId],
        );
        const lease = leaseResult.rows[0];
        if (!lease) this.invalidLease();
        this.assertPersistedLeaseIdentity(lease, claims);
        const jobResult = await client.query<JobRow>(
          `SELECT * FROM capture_jobs
            WHERE project_id = $1 AND job_id = $2`,
          [claims.projectId, claims.jobId],
        );
        const job = jobResult.rows[0];
        if (!job) this.invalidLease();
        if (job.output_revision_id === null) return null;
        const revision = await client.query<{
          revision_id: string;
          winning_attempt_id: string;
        }>(
          `SELECT revision_id, winning_attempt_id
             FROM capture_revisions
            WHERE project_id = $1 AND revision_id = $2`,
          [claims.projectId, job.output_revision_id],
        );
        if (
          !revision.rows[0] ||
          revision.rows[0].winning_attempt_id !== claims.plannedAttemptId
        ) {
          throw new CaptureServiceError(
            "job_not_committable",
            "Another capture attempt already committed this job.",
            false,
          );
        }
        return revision.rows[0].revision_id;
      },
    );
    if (revisionId === null) return null;
    const [job, revision] = await Promise.all([
      this.jobMessage(claims.projectId, claims.jobId, requestId, true),
      this.revisionMessage(claims.projectId, revisionId, requestId),
    ]);
    return {
      schemaVersion: "public-page-capture-worker/v1",
      messageType: "attempt_committed",
      requestId,
      job: job.job,
      revision: revision.revision,
      recoveredExistingOutcome: true,
    };
  }

  private assertPersistedLeaseIdentity(
    lease: LeaseRow,
    claims: LeaseClaims,
  ): void {
    if (
      lease.job_id !== claims.jobId ||
      lease.capture_id !== claims.captureId ||
      lease.worker_installation_id !== claims.workerInstallationId ||
      integer(lease.epoch) !== claims.leaseEpoch ||
      !sameDigest(lease.capability_jti_digest, sha256(claims.jti)) ||
      !sameDigest(
        lease.capability_scope_digest,
        sha256(capabilityScope(claims)),
      )
    ) {
      this.invalidLease();
    }
  }

  private async latestRevision(
    client: SqlClient,
    claims: LeaseClaims,
  ): Promise<BaselineRow | null> {
    const result = await client.query<BaselineRow>(
      `SELECT r.revision_id, r.configuration_version, r.raster_artifact_id,
              r.settings_digest, r.profile_digest, cfg.region_intent,
              ra.digest AS raster_digest,
              ra.object_store_id AS raster_object_store_id,
              pa.object_store_id AS provenance_object_store_id,
              pm.sanitized_summary AS warning_summary
         FROM capture_revisions r
         JOIN capture_configurations cfg
           ON cfg.project_id = r.project_id
          AND cfg.capture_id = r.capture_id
          AND cfg.configuration_version = r.configuration_version
         JOIN capture_artifacts ra
           ON ra.project_id = r.project_id
          AND ra.artifact_id = r.raster_artifact_id
         JOIN capture_provenance_manifests pm
           ON pm.project_id = r.project_id
          AND pm.provenance_id = r.provenance_id
         JOIN capture_artifacts pa
           ON pa.project_id = pm.project_id
          AND pa.artifact_id = pm.provenance_artifact_id
        WHERE r.project_id = $1 AND r.capture_id = $2
        ORDER BY r.revision_number DESC
        LIMIT 1`,
      [claims.projectId, claims.captureId],
    );
    return result.rows[0] ?? null;
  }

  private async exactRasterArtifact(
    client: SqlClient,
    projectId: string,
    expectedArtifactId: string,
    raster: ReturnType<typeof verifyPng>,
  ): Promise<ArtifactRow | null> {
    const result = await client.query<ArtifactRow>(
      `SELECT * FROM capture_artifacts
        WHERE project_id = $1
          AND kind = 'capture_raster'
          AND digest = $2
          AND byte_length = $3
          AND mime_type = 'image/png'
          AND width = $4 AND height = $5
          AND encoding = 'png' AND color = 'srgb' AND alpha = $6
          AND verifier_profile = $7 AND verifier_version = $8
        LIMIT 1`,
      [
        projectId,
        digestBytes(raster.digest),
        raster.byteLength,
        raster.width,
        raster.height,
        raster.alpha,
        raster.verifierProfile,
        raster.verifierVersion,
      ],
    );
    const artifact = result.rows[0] ?? null;
    if (artifact && artifact.artifact_id !== expectedArtifactId) {
      throw new CaptureServiceError(
        "object_verification_unavailable",
        "The exact-byte artifact identity is inconsistent.",
        false,
      );
    }
    return artifact;
  }

  private async artifactRow(
    client: SqlClient,
    projectId: string,
    artifactId: string,
  ): Promise<ArtifactRow> {
    const result = await client.query<ArtifactRow>(
      `SELECT * FROM capture_artifacts
        WHERE project_id = $1 AND artifact_id = $2`,
      [projectId, artifactId],
    );
    const artifact = result.rows[0];
    if (!artifact) {
      throw new CaptureServiceError(
        "object_verification_unavailable",
        "The verified artifact reference is unavailable.",
        true,
      );
    }
    return artifact;
  }

  private async insertRasterArtifact(
    client: SqlClient,
    claims: LeaseClaims,
    artifactId: string,
    promoted: PromotedObject,
    raster: ReturnType<typeof verifyPng>,
    now: Date,
  ): Promise<void> {
    if (
      promoted.projectId !== claims.projectId ||
      promoted.kind !== "capture_raster" ||
      promoted.digest !== raster.digest ||
      promoted.byteLength !== raster.byteLength ||
      promoted.mimeType !== "image/png"
    ) {
      throw new CaptureServiceError(
        "object_verification_unavailable",
        "The immutable raster promotion receipt is inconsistent.",
        false,
      );
    }
    await client.query(
      `INSERT INTO capture_artifacts (
          project_id, artifact_id, kind, access_class, object_store_id,
          digest, byte_length, mime_type, width, height, encoding, color,
          alpha, provenance_schema, verifier_profile, verifier_version,
          verified_at, encryption_key_version, created_by_service_id,
          created_at
        ) VALUES ($1, $2, 'capture_raster', 'project_visual', $3, $4, $5,
                  'image/png', $6, $7, 'png', 'srgb', $8, NULL, $9, $10,
                  $11, 1, $12, $11)`,
      [
        claims.projectId,
        artifactId,
        promoted.objectStoreId,
        digestBytes(promoted.digest),
        promoted.byteLength,
        raster.width,
        raster.height,
        raster.alpha,
        raster.verifierProfile,
        raster.verifierVersion,
        now,
        claims.workerInstallationId,
      ],
    );
  }

  private async insertProvenanceArtifact(
    client: SqlClient,
    claims: LeaseClaims,
    artifactId: string,
    promoted: PromotedObject,
    now: Date,
  ): Promise<void> {
    if (
      promoted.projectId !== claims.projectId ||
      promoted.kind !== "capture_provenance" ||
      promoted.mimeType !== "application/json"
    ) {
      throw new CaptureServiceError(
        "object_verification_unavailable",
        "The immutable provenance promotion receipt is inconsistent.",
        false,
      );
    }
    await client.query(
      `INSERT INTO capture_artifacts (
          project_id, artifact_id, kind, access_class, object_store_id,
          digest, byte_length, mime_type, width, height, encoding, color,
          alpha, provenance_schema, verifier_profile, verifier_version,
          verified_at, encryption_key_version, created_by_service_id,
          created_at
        ) VALUES ($1, $2, 'capture_provenance', 'restricted_provenance',
                  $3, $4, $5, 'application/json', NULL, NULL, 'json',
                  'not_applicable', 'not_applicable',
                  'public-page-capture-provenance/v1', 'canonical_json_schema',
                  1, $6, 1, $7, $6)`,
      [
        claims.projectId,
        artifactId,
        promoted.objectStoreId,
        digestBytes(promoted.digest),
        promoted.byteLength,
        now,
        claims.workerInstallationId,
      ],
    );
  }

  private async computeChange(
    baseline: BaselineRow | null,
    currentArtifact: ArtifactRow,
    currentProvenance: PublicPageCaptureProvenanceV1,
    claims: LeaseClaims,
  ): Promise<ComputedChange> {
    if (!baseline) {
      return {
        signal: "initial_observation",
        differences: {
          finalUrl: null,
          redirectChain: null,
          profile: null,
          region: null,
          warnings: null,
          loadEvidence: null,
        },
      };
    }
    const baselineBytes = await this.dependencies.objects.read(
      baseline.provenance_object_store_id,
    );
    const baselineProvenance = this.parseProvenance(baselineBytes);
    const profileChanged =
      digestString(baseline.profile_digest) !== claims.profileDigest;
    const regionChanged =
      canonicalJson(json<JsonValue>(baseline.region_intent)) !==
      canonicalJson(currentProvenance.request.regionIntent);
    const currentWarnings = currentProvenance.honesty.warnings.map(
      ({ code }) => code,
    );
    const baselineWarnings = json<{ warningCodes?: string[] }>(
      baseline.warning_summary,
    ).warningCodes ?? baselineProvenance.honesty.warnings.map(({ code }) => code);
    const comparable = !profileChanged && !regionChanged;
    const sameRaster =
      digestString(baseline.raster_digest) ===
        digestString(currentArtifact.digest) &&
      (await this.dependencies.objects.bytesEqual(
        baseline.raster_object_store_id,
        await this.dependencies.objects.read(currentArtifact.object_store_id),
      ));
    return {
      signal: comparable
        ? sameRaster
          ? "same_exact_bytes"
          : "different_exact_bytes"
        : "not_comparable",
      differences: {
        finalUrl:
          baselineProvenance.network.finalUrl !==
          currentProvenance.network.finalUrl,
        redirectChain:
          canonicalJson(
            baselineProvenance.network.redirectChain as unknown as JsonValue,
          ) !==
          canonicalJson(
            currentProvenance.network.redirectChain as unknown as JsonValue,
          ),
        profile: profileChanged,
        region: regionChanged,
        warnings:
          canonicalJson([...baselineWarnings].sort()) !==
          canonicalJson([...currentWarnings].sort()),
        loadEvidence:
          canonicalJson({
            response: baselineProvenance.network.response,
            frame: baselineProvenance.network.frameManifestDigest,
            subresource: baselineProvenance.network.subresourceManifestDigest,
          } as unknown as JsonValue) !==
          canonicalJson({
            response: currentProvenance.network.response,
            frame: currentProvenance.network.frameManifestDigest,
            subresource: currentProvenance.network.subresourceManifestDigest,
          } as unknown as JsonValue),
      },
    };
  }

  private async finalizeProvenance(
    client: SqlClient,
    candidate: PublicPageCaptureProvenanceV1,
    current: CurrentLease,
    authorization: AuthorizationDecisionRef,
    raster: ArtifactRow,
    rasterReused: boolean,
    baseline: BaselineRow | null,
    change: ComputedChange,
    status: "ready" | "review_required",
    warningCodes: readonly string[],
    now: Date,
  ): Promise<PublicPageCaptureProvenanceV1> {
    const configuration = await client.query<
      ConfigurationSecretRow & {
        readonly query_key_names: unknown;
        readonly redacted_url_display: string;
        readonly region_intent: unknown;
      }
    >(
      `SELECT canonical_url_digest, configuration_version,
              restricted_request_envelope, redacted_url_display,
              query_key_names, region_intent
         FROM capture_configurations
        WHERE project_id = $1 AND capture_id = $2
          AND configuration_version = $3`,
      [
        current.claims.projectId,
        current.claims.captureId,
        current.claims.configurationVersion,
      ],
    );
    const config = configuration.rows[0];
    if (!config) this.notFound();
    const canonicalUrlDigest = digestString(config.canonical_url_digest);
    const exactUrl = this.dependencies.cipher.decrypt(
      Buffer.from(config.restricted_request_envelope),
      {
        projectId: current.claims.projectId,
        captureId: current.claims.captureId,
        configurationVersion: current.claims.configurationVersion,
        canonicalUrlDigest,
      },
    );
    const region = json<
      | { kind: "full_viewport" }
      | { height: number; kind: "rectangle"; width: number; x: number; y: number }
    >(config.region_intent);
    const provenanceRegion =
      region.kind === "full_viewport"
        ? region
        : {
            kind: "element" as const,
            selector: `vera-rectangle-${region.x}-${region.y}-${region.width}-${region.height}`,
          };
    const classification =
      change.signal === "initial_observation"
        ? "first_observation"
        : change.signal === "same_exact_bytes"
          ? "no_change"
          : change.signal === "different_exact_bytes"
            ? "changed"
            : "uncertain";
    const originReference =
      current.job.trigger_kind === "on_build"
        ? {
            kind: current.job.trigger_reference_kind as
              | "preview_build"
              | "release_build",
            referenceId: current.job.trigger_reference_id,
            revision: current.claims.configurationVersion,
          }
        : null;
    const warnings = candidate.honesty.warnings.filter(({ code }) =>
      warningCodes.includes(code),
    );
    const leaseHistory = [
      ...candidate.timing.leaseHistory.filter(({ event }) => event !== "committed"),
      {
        event: "committed" as const,
        leaseEpoch: current.claims.leaseEpoch,
        at: now.toISOString(),
        deadline: timestamp(current.lease.expires_at),
        workerInstallationId: current.claims.workerInstallationId,
      },
    ];
    const milestones = [
      ...candidate.timing.milestones.filter(({ name }) => name !== "committed"),
      {
        name: "committed" as const,
        wallAt: now.toISOString(),
        monotonicMilliseconds: candidate.timing.durationMilliseconds,
      },
    ].slice(-16);
    const final = {
      ...candidate,
      identity: {
        ...candidate.identity,
        configurationVersionId: captureConfigurationVersionId(
          current.claims.projectId,
          current.claims.captureId,
          current.claims.configurationVersion,
        ),
      },
      authorization: {
        principal: authorization.principal,
        role: authorization.role,
        action: "capture.commit" as const,
        decisionId: authorization.decisionId,
        decision: "allowed" as const,
        decidedAt: authorization.decidedAt,
        commitRecheck: true as const,
        originReference,
      },
      request: {
        triggerKind: current.job.trigger_kind,
        requestedUrl: exactUrl,
        redactedRequestedUrl: config.redacted_url_display,
        requestedUrlDigest: canonicalUrlDigest,
        requestedUrlFingerprint: keyedFingerprint(
          this.dependencies.denialFingerprintKey,
          exactUrl,
        ).replace("hmac-sha256-v1:", "hmac-sha256:"),
        queryKeyNames: json<string[]>(config.query_key_names),
        settingsDigest: current.claims.settingsDigest,
        captureProfileId: "vera-public-page-capture-v1" as const,
        captureProfileDigest: current.claims.profileDigest,
        regionIntent: provenanceRegion,
        idempotencyScopeDigest: sha256({
          projectId: current.claims.projectId,
          captureId: current.claims.captureId,
          triggerKind: current.job.trigger_kind,
          principalId: current.job.initiating_principal_id,
          settingsDigest: current.claims.settingsDigest,
        }),
        idempotencyKeyDigest: digestString(
          current.job.idempotency_key_digest,
        ),
        requestedAt: timestamp(current.job.requested_at),
        enqueuedAt: timestamp(current.job.enqueued_at ?? current.job.requested_at),
      },
      timing: {
        ...candidate.timing,
        retryNumber: current.attempt
          ? current.attempt.attempt_number - 1
          : 0,
        retryBudget: 2 as const,
        leaseHistory,
        milestones,
      },
      output: {
        raster: {
          artifactId: raster.artifact_id,
          digest: digestString(raster.digest),
          byteLength: integer(raster.byte_length),
          mediaType: "image/png" as const,
        },
        encoding: "png" as const,
        width: OUTPUT_WIDTH as 3840,
        height: OUTPUT_HEIGHT as 2160,
        capturedRegion: {
          x: 0,
          y: 0,
          width: OUTPUT_WIDTH,
          height: OUTPUT_HEIGHT,
        },
        decoder: "pngjs-7",
        byteIdentity: rasterReused
          ? ("exact_byte_reuse" as const)
          : ("new_raster" as const),
        baselineRevisionId: baseline?.revision_id ?? null,
        reusedRasterArtifactId: rasterReused ? raster.artifact_id : null,
        stagedAt: timestamp(current.attempt?.staged_at ?? now),
        committedAt: now.toISOString(),
      },
      change: {
        classification,
        baselineRevisionId: baseline?.revision_id ?? null,
        pixelChanged:
          change.signal === "same_exact_bytes" ? false : null,
        byteChanged:
          change.signal === "initial_observation"
            ? null
            : change.signal === "same_exact_bytes"
              ? false
              : change.signal === "different_exact_bytes"
                ? true
                : null,
        reviewRequired: status === "review_required",
        signals: candidate.change?.signals ?? [],
      },
      honesty: {
        ...candidate.honesty,
        classification:
          status === "review_required"
            ? ("partial" as const)
            : ("complete" as const),
        partialReason:
          status === "review_required"
            ? candidate.honesty.partialReason ?? "Capture warnings require review."
            : null,
        warnings,
      },
      terminal: null,
    };
    return final as unknown as PublicPageCaptureProvenanceV1;
  }

  private async insertChangeSignal(
    client: SqlClient,
    claims: LeaseClaims,
    revisionId: string,
    changeSignalId: string,
    artifactId: string,
    baseline: BaselineRow | null,
    change: ComputedChange,
    now: Date,
  ): Promise<void> {
    await client.query(
      `INSERT INTO capture_change_signals (
          project_id, change_signal_id, capture_id, current_revision_id,
          baseline_revision_id, current_artifact_id, baseline_artifact_id,
          signal, difference_final_url, difference_redirect_chain,
          difference_profile, difference_region, difference_warnings,
          difference_load_evidence, algorithm, algorithm_version,
          computed_at, materiality, materiality_version
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                  $12, $13, $14, 'exact_bytes_and_provenance', 1, $15,
                  'non_semantic_no_automatic_replacement_selection_or_notification',
                  1)`,
      [
        claims.projectId,
        changeSignalId,
        claims.captureId,
        revisionId,
        baseline?.revision_id ?? null,
        artifactId,
        baseline?.raster_artifact_id ?? null,
        change.signal,
        change.differences.finalUrl,
        change.differences.redirectChain,
        change.differences.profile,
        change.differences.region,
        change.differences.warnings,
        change.differences.loadEvidence,
        now,
      ],
    );
  }

  private async applyCommitEffects(
    client: SqlClient,
    job: JobRow,
    revisionId: string,
    status: "ready" | "review_required",
    principal: PrincipalRef,
    selectionAuthorization: AuthorizationDecisionRef | null,
    requestId: string,
    now: Date,
  ): Promise<void> {
    if (status !== "ready") return;
    if (job.trigger_kind === "on_build") {
      const source = this.jobBuildReference(job);
      await this.insertProtection(
        client,
        job,
        revisionId,
        source.kind,
        source,
        principal,
        job.authorization_decision_id,
        requestId,
        now,
      );
      return;
    }
    if (job.conditional_selection_intent === null) return;
    if (!selectionAuthorization) {
      throw new CaptureServiceError(
        "authorization_unavailable",
        "Selection authorization could not be verified at commit.",
        true,
      );
    }
    const intent = json<Extract<SelectionIntent, { kind: "conditional" }>>(
      job.conditional_selection_intent,
    );
    const target = intent.target;
    const currentSelection = await client.query<{
      selection_id: string;
      target_sequence: string | number;
    }>(
      `SELECT selection_id, target_sequence
         FROM capture_revision_selections
        WHERE project_id = $1 AND target_kind = $2
          AND target_resource_id = $3 AND target_version_digest = $4
          AND target_occurrence_id IS NOT DISTINCT FROM $5
        ORDER BY target_sequence DESC
        LIMIT 1`,
      [
        job.project_id,
        target.kind,
        target.resourceId,
        digestBytes(referenceVersion(target)),
        referenceOccurrence(target),
      ],
    );
    const previous = currentSelection.rows[0] ?? null;
    if ((previous?.selection_id ?? null) !== intent.expectedPreviousSelectionId) {
      return;
    }
    const selectionId = this.id();
    const sequence = integer(previous?.target_sequence ?? 0) + 1;
    const effectDigest = sha256({
      projectId: job.project_id,
      revisionId,
      target,
      sequence,
      reason: "capture_and_use",
    } as unknown as JsonValue);
    await client.query(
      `INSERT INTO capture_revision_selections (
          project_id, selection_id, capture_id, revision_id, target_kind,
          target_resource_id, target_version_digest, target_occurrence_id,
          target_sequence, previous_selection_id,
          expected_previous_selection_id, reason, actor_kind, actor_id,
          authorization_decision_id, required_use_decision_id, effect_digest,
          selected_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                  'capture_and_use', $12, $13, $14, NULL, $15, $16)`,
      [
        job.project_id,
        selectionId,
        job.capture_id,
        revisionId,
        target.kind,
        target.resourceId,
        digestBytes(referenceVersion(target)),
        referenceOccurrence(target),
        sequence,
        previous?.selection_id ?? null,
        intent.expectedPreviousSelectionId,
        principal.principalKind,
        principal.principalId,
        selectionAuthorization.decisionId,
        digestBytes(effectDigest),
        now,
      ],
    );
    await this.insertProtection(
      client,
      job,
      revisionId,
      "draft_selection",
      target,
      principal,
      selectionAuthorization.decisionId,
      requestId,
      now,
    );
  }

  private async insertProtection(
    client: SqlClient,
    job: JobRow,
    revisionId: string,
    reason: string,
    source: ExternalReference,
    principal: PrincipalRef,
    authorizationDecisionId: string,
    _requestId: string,
    now: Date,
  ): Promise<string> {
    const protectionId = this.id();
    const effectDigest = sha256({
      projectId: job.project_id,
      revisionId,
      reason,
      source,
    } as unknown as JsonValue);
    await client.query(
      `INSERT INTO capture_revision_protections (
          project_id, protection_id, capture_id, revision_id, reason,
          source_kind, source_resource_id, source_version_digest,
          source_occurrence_id, actor_kind, actor_id,
          authorization_decision_id, effect_digest, added_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                  $12, $13, $14)`,
      [
        job.project_id,
        protectionId,
        job.capture_id,
        revisionId,
        reason,
        source.kind,
        source.resourceId,
        digestBytes(referenceVersion(source)),
        referenceOccurrence(source),
        principal.principalKind,
        principal.principalId,
        authorizationDecisionId,
        digestBytes(effectDigest),
        now,
      ],
    );
    return protectionId;
  }

  private async readRevisionArtifact(
    projectId: string,
    revisionId: string,
    reference: ExternalReference,
    principal: PrincipalRef,
    requestId: string,
    kind: "capture_provenance" | "capture_raster",
  ): Promise<CaptureArtifactRead> {
    const authorization = await this.dependencies.authorization.authorize(
      projectId,
      principal,
      "capture_read",
    );
    if (reference.projectId !== projectId) {
      throw new CaptureServiceError(
        "request_invalid",
        "The visible reference does not belong to this project.",
        false,
        ["/reference/projectId"],
      );
    }
    await this.dependencies.references.validate(projectId, reference, "read");
    const artifact = await this.dependencies.database.transaction(
      async (client) => {
        const result = await client.query<ArtifactRow>(
          `SELECT a.*
             FROM capture_revisions r
             JOIN capture_provenance_manifests pm
               ON pm.project_id = r.project_id
              AND pm.provenance_id = r.provenance_id
             JOIN capture_artifacts a
               ON a.project_id = r.project_id
              AND a.artifact_id = CASE
                    WHEN $3 = 'capture_raster' THEN r.raster_artifact_id
                    ELSE pm.provenance_artifact_id
                  END
            WHERE r.project_id = $1 AND r.revision_id = $2
              AND a.kind = $3
              AND (
                EXISTS (
                  SELECT 1
                    FROM capture_revision_protections p
                   WHERE p.project_id = r.project_id
                     AND p.revision_id = r.revision_id
                     AND p.source_kind = $4
                     AND p.source_resource_id = $5
                     AND p.source_version_digest = $6
                     AND p.source_occurrence_id IS NOT DISTINCT FROM $7
                     AND NOT EXISTS (
                       SELECT 1 FROM capture_protection_releases pr
                        WHERE pr.project_id = p.project_id
                          AND pr.protection_id = p.protection_id
                     )
                )
                OR EXISTS (
                  SELECT 1
                    FROM capture_revision_selections s
                   WHERE s.project_id = r.project_id
                     AND s.revision_id = r.revision_id
                     AND s.target_kind = $4
                     AND s.target_resource_id = $5
                     AND s.target_version_digest = $6
                     AND s.target_occurrence_id IS NOT DISTINCT FROM $7
                )
                OR EXISTS (
                  SELECT 1
                    FROM capture_revision_use_decisions u
                   WHERE u.project_id = r.project_id
                     AND u.revision_id = r.revision_id
                     AND u.context_kind = $4
                     AND u.context_resource_id = $5
                     AND u.context_version_digest = $6
                     AND u.context_occurrence_id IS NOT DISTINCT FROM $7
                )
              )`,
          [
            projectId,
            revisionId,
            kind,
            reference.kind,
            reference.resourceId,
            digestBytes(referenceVersion(reference)),
            referenceOccurrence(reference),
          ],
        );
        const row = result.rows[0];
        if (!row) this.notFound();
        return row;
      },
    );
    let bytes: Buffer;
    try {
      bytes = await this.dependencies.objects.read(artifact.object_store_id);
      if (
        bytes.byteLength !== integer(artifact.byte_length) ||
        sha256(bytes) !== digestString(artifact.digest)
      ) {
        throw new ObjectStoreError("retained_object_mismatch");
      }
      if (kind === "capture_raster") {
        if (artifact.width === null || artifact.height === null) {
          throw new ObjectStoreError("retained_raster_mismatch");
        }
        const raster = verifyPng(bytes, {
          expectedWidth: artifact.width,
          expectedHeight: artifact.height,
          maxBytes: integer(artifact.byte_length),
          maxPixels: artifact.width * artifact.height,
        });
        if (
          artifact.mime_type !== "image/png" ||
          raster.width !== artifact.width ||
          raster.height !== artifact.height ||
          raster.alpha !== artifact.alpha
        ) {
          throw new ObjectStoreError("retained_raster_mismatch");
        }
      } else {
        const provenance = this.parseProvenance(bytes);
        if (
          artifact.mime_type !== "application/json" ||
          provenance.recordType !== "revision_observation" ||
          provenance.identity.projectId !== projectId ||
          provenance.identity.revisionId !== revisionId
        ) {
          throw new ObjectStoreError("retained_provenance_mismatch");
        }
      }
    } catch (error) {
      if (error instanceof CaptureServiceError) throw error;
      throw new CaptureServiceError(
        "object_verification_unavailable",
        "The retained capture artifact could not be verified.",
        true,
      );
    }
    await this.dependencies.database.transaction(async (client) => {
      await this.appendAudit(
        client,
        {
          projectId,
          objectId: revisionId,
          objectKind: "capture_revision",
          principal,
          requestId,
          correlationId: requestId,
        },
        "artifact_read",
        null,
        null,
        "served",
        {
          accessClass: artifact.access_class,
          artifactId: artifact.artifact_id,
          authorizationDecisionId: authorization.decisionId,
          kind,
          referenceKind: reference.kind,
        },
        this.now(),
      );
    });
    return {
      bytes,
      descriptor: this.artifactDescriptor(artifact),
    };
  }

  private artifactDescriptor(row: ArtifactRow): ArtifactDescriptor {
    if (row.kind === "capture_raster") {
      if (
        row.width === null ||
        row.height === null ||
        row.encoding !== "png" ||
        row.color !== "srgb" ||
        (row.alpha !== "opaque" && row.alpha !== "present")
      ) {
        throw new CaptureServiceError(
          "object_verification_unavailable",
          "The retained raster descriptor is inconsistent.",
          true,
        );
      }
      return {
        artifactId: row.artifact_id,
        projectId: row.project_id,
        kind: "capture_raster",
        digest: digestString(row.digest),
        byteLength: integer(row.byte_length),
        mimeType: "image/png",
        width: row.width,
        height: row.height,
        encoding: "png",
        color: "srgb",
        alpha: row.alpha,
        verifierProfile: row.verifier_profile,
        verifierVersion: row.verifier_version,
        verifiedAt: timestamp(row.verified_at),
        accessClass: "project_visual",
      };
    }
    if (
      row.encoding !== "json" ||
      row.color !== "not_applicable" ||
      row.alpha !== "not_applicable"
    ) {
      throw new CaptureServiceError(
        "object_verification_unavailable",
        "The retained provenance descriptor is inconsistent.",
        true,
      );
    }
    return {
      artifactId: row.artifact_id,
      projectId: row.project_id,
      kind: "capture_provenance",
      digest: digestString(row.digest),
      byteLength: integer(row.byte_length),
      mimeType: "application/json",
      encoding: "json",
      color: "not_applicable",
      alpha: "not_applicable",
      verifierProfile: row.verifier_profile,
      verifierVersion: row.verifier_version,
      verifiedAt: timestamp(row.verified_at),
      accessClass: "restricted_provenance",
    };
  }

  private async verifyLeaseCapability(proof: LeaseProof): Promise<LeaseClaims> {
    try {
      await this.dependencies.workerAuthorization.authorize(
        proof.workerInstallationId,
      );
      const raw = this.dependencies.capabilities.verify(
        proof.leaseCapability,
        this.now(),
        {
          capabilityType: "lease",
          jobId: proof.jobId,
          leaseEpoch: proof.leaseEpoch,
          leaseId: proof.leaseId,
          workerInstallationId: proof.workerInstallationId,
        },
        { allowExpired: true },
      );
      const claims = leaseClaims(raw);
      if (
        proof.attemptId !== null &&
        proof.attemptId !== claims.plannedAttemptId
      ) {
        throw new CapabilityError("capability_scope_mismatch");
      }
      return claims;
    } catch {
      this.invalidLease();
    }
  }

  private async currentLease(
    client: SqlClient,
    proof: LeaseProof,
    claims: LeaseClaims,
    requireAttempt = false,
  ): Promise<CurrentLease> {
    const leaseResult = await client.query<LeaseRow>(
      `SELECT * FROM capture_leases
        WHERE project_id = $1 AND lease_id = $2
        FOR UPDATE`,
      [claims.projectId, claims.leaseId],
    );
    const lease = leaseResult.rows[0];
    if (!lease) this.invalidLease();
    const jtiDigest = sha256(claims.jti);
    const scopeDigest = sha256(
      capabilityScope(claims),
    );
    if (
      lease.job_id !== claims.jobId ||
      lease.capture_id !== claims.captureId ||
      lease.worker_installation_id !== claims.workerInstallationId ||
      integer(lease.epoch) !== claims.leaseEpoch ||
      !sameDigest(lease.capability_jti_digest, jtiDigest) ||
      !sameDigest(lease.capability_scope_digest, scopeDigest)
    ) {
      this.invalidLease();
    }
    if (
      !["issued", "active"].includes(lease.state) ||
      new Date(lease.expires_at).getTime() <= this.now().getTime()
    ) {
      const newer = await client.query(
        `SELECT 1 FROM capture_leases
          WHERE project_id = $1 AND job_id = $2 AND epoch > $3
          LIMIT 1`,
        [claims.projectId, claims.jobId, claims.leaseEpoch],
      );
      if (newer.rows.length > 0) {
        throw new CaptureServiceError(
          "job_not_committable",
          "The lease is no longer current for this job.",
          false,
          ["/leaseEpoch"],
        );
      }
      this.invalidLease();
    }
    const jobResult = await client.query<JobRow>(
      `SELECT * FROM capture_jobs
        WHERE project_id = $1 AND job_id = $2
        FOR UPDATE`,
      [claims.projectId, claims.jobId],
    );
    const job = jobResult.rows[0];
    if (
      !job ||
      job.capture_id !== claims.captureId ||
      integer(job.configuration_version) !== claims.configurationVersion ||
      !sameDigest(job.settings_digest, claims.settingsDigest) ||
      !sameDigest(job.profile_digest, claims.profileDigest)
    ) {
      this.invalidLease();
    }
    const attemptResult = await client.query<AttemptRow>(
      `SELECT * FROM capture_attempts
        WHERE project_id = $1 AND lease_id = $2`,
      [claims.projectId, claims.leaseId],
    );
    const attempt = attemptResult.rows[0] ?? null;
    if (
      (attempt !== null &&
        (attempt.attempt_id !== claims.plannedAttemptId ||
          attempt.job_id !== claims.jobId ||
          attempt.capture_id !== claims.captureId)) ||
      (requireAttempt &&
        (!attempt || proof.attemptId !== claims.plannedAttemptId))
    ) {
      this.invalidLease();
    }
    return { attempt, claims, job, lease };
  }

  private async jobProfile(
    client: SqlClient,
    job: JobRow,
  ): Promise<CaptureProfileV1> {
    const result = await client.query<{ capture_profile_json: unknown }>(
      `SELECT capture_profile_json
         FROM capture_jobs
        WHERE project_id = $1 AND job_id = $2`,
      [job.project_id, job.job_id],
    );
    const profile = json<CaptureProfileV1>(result.rows[0]?.capture_profile_json);
    if (!profile || profile.profileDigest !== digestString(job.profile_digest)) {
      throw new CaptureServiceError(
        "object_verification_unavailable",
        "The frozen capture profile could not be verified.",
        true,
      );
    }
    return profile;
  }

  private invalidLease(): never {
    throw new CaptureServiceError(
      "invalid_or_expired_job_capability",
      "The worker capability is invalid or expired.",
      false,
      ["/lease/leaseCapability"],
    );
  }

  private assertProfile(profileId: string, profileVersion: number): void {
    if (
      profileId !== CAPTURE_PROFILE_V1.profileId ||
      profileVersion !== CAPTURE_PROFILE_V1.profileVersion
    ) {
      throw new CaptureServiceError(
        "request_invalid",
        "The capture profile is not supported.",
        false,
        ["/captureProfileId"],
      );
    }
  }

  private inspectOrDeny(raw: string): ReturnType<typeof inspectPublicUrl> {
    try {
      return inspectPublicUrl(raw);
    } catch (error) {
      if (!(error instanceof CaptureDenied)) throw error;
      throw sanitizedDenial(
        error,
        keyedFingerprint(this.dependencies.denialFingerprintKey, raw),
      );
    }
  }

  private captureSettings(
    canonicalUrl: string,
    regionIntent: CreateCaptureRequest["regionIntent"],
    acquisitionPolicy: AcquisitionPolicy,
    captureProfileId: string,
    captureProfileVersion: number,
  ): JsonValue {
    return {
      canonicalUrlDigest: sha256(canonicalUrl),
      regionIntent,
      acquisitionPolicy,
      captureProfileId,
      captureProfileVersion,
    } as unknown as JsonValue;
  }

  private async lockIdempotency(
    client: SqlClient,
    projectId: string,
    principalId: string,
    operation: string,
    keyDigest: string,
  ): Promise<void> {
    await client.query("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", [
      [projectId, principalId, operation, keyDigest].join(":"),
    ]);
  }

  private async existingIdempotentEffect(
    client: SqlClient,
    projectId: string,
    objectId: string,
    actorId: string,
    eventType: string,
    idempotencyKeyDigest: string,
    requestFingerprint: string,
  ): Promise<{ readonly effectId: string; readonly recordedAt: string } | null> {
    const result = await client.query<{
      safe_details: unknown;
      server_time: Date | string;
    }>(
      `SELECT safe_details, server_time
         FROM capture_audit_events
        WHERE project_id = $1
          AND primary_object_id = $2
          AND actor_id = $3
          AND event_type = $4
          AND safe_details ->> 'idempotencyKeyDigest' = $5
        ORDER BY server_time, event_id
        LIMIT 1`,
      [projectId, objectId, actorId, eventType, idempotencyKeyDigest],
    );
    const row = result.rows[0];
    if (!row) return null;
    const details = json<{
      effectId?: string;
      requestFingerprint?: string;
    }>(row.safe_details);
    if (
      details.requestFingerprint !== requestFingerprint ||
      typeof details.effectId !== "string"
    ) {
      throw new CaptureServiceError(
        "idempotency_key_reused",
        "The idempotency key was already used for a different request.",
      );
    }
    return {
      effectId: details.effectId,
      recordedAt: timestamp(row.server_time),
    };
  }

  private protectionReason(
    reference: ExternalReference,
  ):
    | "checkpoint"
    | "document_revision"
    | "draft_selection"
    | "integrity_hold"
    | "preview_build"
    | "release_build"
    | "review_hold"
    | "selection_evidence" {
    switch (reference.kind) {
      case "draft_occurrence":
        return "draft_selection";
      case "document_checkpoint":
        return "checkpoint";
      case "document_revision":
      case "integrity_hold":
      case "preview_build":
      case "release_build":
      case "review_hold":
      case "selection_evidence":
        return reference.kind;
    }
  }

  private async appendAudit(
    client: SqlClient,
    identity: AuditIdentity,
    eventType: string,
    beforeState: string | null,
    afterState: string | null,
    resultCode: string,
    safeDetails: Readonly<Record<string, boolean | null | number | string>>,
    at: Date,
  ): Promise<void> {
    const sequence = await client.query<{ next_sequence: string | number }>(
      `SELECT coalesce(max(object_sequence), 0) + 1 AS next_sequence
         FROM capture_audit_events
        WHERE project_id = $1
          AND primary_object_kind = $2
          AND primary_object_id = $3`,
      [identity.projectId, identity.objectKind, identity.objectId],
    );
    await client.query(
      `INSERT INTO capture_audit_events (
          project_id, event_id, primary_object_kind, primary_object_id,
          object_sequence, event_type, actor_kind, actor_id, request_id,
          correlation_id, policy_version, profile_version, before_state,
          after_state, result_code, safe_details, corrected_event_id,
          server_time
        ) VALUES (
          $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, '1', 1, $11, $12,
          $13, $14::jsonb, NULL, $15
        )`,
      [
        identity.projectId,
        this.id(),
        identity.objectKind,
        identity.objectId,
        integer(sequence.rows[0]?.next_sequence ?? 1),
        eventType,
        identity.principal.principalKind,
        identity.principal.principalId,
        identity.requestId,
        identity.correlationId,
        beforeState,
        afterState,
        resultCode,
        JSON.stringify(safeDetails),
        at,
      ],
    );
  }

  private notFound(): never {
    throw new CaptureServiceError(
      "resource_not_found",
      "The requested capture resource was not found.",
    );
  }

  private async captureMessage(
    projectId: string,
    captureId: string,
    requestId: string,
  ): Promise<CaptureViewMessage> {
    return await this.dependencies.database.transaction(async (client) => {
      const result = await client.query<CaptureRow>(
        `SELECT
            c.project_id,
            c.capture_id,
            c.state,
            c.current_configuration_version,
            c.row_version,
            c.created_by_kind,
            c.created_by_id,
            c.created_at,
            c.updated_at,
            cfg.configuration_version,
            cfg.canonical_url_digest,
            cfg.redacted_url_display,
            cfg.query_key_names,
            cfg.region_intent,
            cfg.acquisition_policy,
            cfg.capture_profile_id,
            cfg.capture_profile_version,
            cfg.settings_digest,
            cfg.previous_configuration_digest,
            cfg.created_by_kind AS configuration_created_by_kind,
            cfg.created_by_id AS configuration_created_by_id,
            cfg.created_at AS configuration_created_at
           FROM captures c
           JOIN capture_configurations cfg
             ON cfg.project_id = c.project_id
            AND cfg.capture_id = c.capture_id
            AND cfg.configuration_version = c.current_configuration_version
          WHERE c.project_id = $1 AND c.capture_id = $2`,
        [projectId, captureId],
      );
      const row = result.rows[0];
      if (!row) this.notFound();
      const policy: CaptureConfigurationView["acquisitionPolicy"] =
        row.acquisition_policy === "periodic_reserved"
          ? { kind: "periodic_reserved", execution: "disabled" }
          : { kind: row.acquisition_policy };
      const configuration: CaptureConfigurationView = {
        captureId: row.capture_id,
        configurationVersion: integer(row.configuration_version),
        requestedUrl: {
          display: row.redacted_url_display,
          canonicalDigest: digestString(row.canonical_url_digest),
          queryKeys: json<string[]>(row.query_key_names),
        },
        regionIntent: json(row.region_intent),
        acquisitionPolicy: policy,
        captureProfileId: row.capture_profile_id,
        captureProfileVersion: integer(row.capture_profile_version),
        settingsDigest: digestString(row.settings_digest),
        ...(row.previous_configuration_digest
          ? {
              previousConfigurationDigest: digestString(
                row.previous_configuration_digest,
              ),
            }
          : {}),
        createdBy: {
          principalKind: row.configuration_created_by_kind,
          principalId: row.configuration_created_by_id,
        },
        createdAt: timestamp(row.configuration_created_at),
      };
      const capture: CaptureView = {
        captureId: row.capture_id,
        projectId: row.project_id,
        lifecycle: row.state,
        currentConfigurationVersion: integer(
          row.current_configuration_version,
        ),
        rowVersion: integer(row.row_version),
        createdBy: {
          principalKind: row.created_by_kind,
          principalId: row.created_by_id,
        },
        createdAt: timestamp(row.created_at),
        updatedAt: timestamp(row.updated_at),
        configuration,
      };
      return {
        schemaVersion: "public-page-capture-api/v1",
        messageType: "capture_view",
        requestId,
        capture,
      };
    });
  }

  private async revisionMessage(
    projectId: string,
    revisionId: string,
    requestId: string,
  ): Promise<CaptureRevisionViewMessage> {
    return await this.dependencies.database.transaction(async (client) => {
      const result = await client.query<{
        baseline_artifact_id: string | null;
        baseline_revision_id: string | null;
        capture_id: string;
        change_signal_id: string;
        committed_at: Date | string;
        computed_at: Date | string;
        configuration_version: string | number;
        current_artifact_id: string;
        difference_final_url: boolean | null;
        difference_load_evidence: boolean | null;
        difference_profile: boolean | null;
        difference_redirect_chain: boolean | null;
        difference_region: boolean | null;
        difference_warnings: boolean | null;
        job_id: string;
        profile_digest: Uint8Array;
        project_id: string;
        provenance_access_class: ArtifactDescriptor["accessClass"];
        provenance_alpha: ArtifactDescriptor["alpha"];
        provenance_artifact_id: string;
        provenance_byte_length: string | number;
        provenance_color: ArtifactDescriptor["color"];
        provenance_digest: Uint8Array;
        provenance_encoding: ArtifactDescriptor["encoding"];
        provenance_kind: ArtifactDescriptor["kind"];
        provenance_mime_type: ArtifactDescriptor["mimeType"];
        provenance_verified_at: Date | string;
        provenance_verifier_profile: string;
        provenance_verifier_version: number;
        raster_access_class: ArtifactDescriptor["accessClass"];
        raster_alpha: ArtifactDescriptor["alpha"];
        raster_artifact_id: string;
        raster_byte_length: string | number;
        raster_color: ArtifactDescriptor["color"];
        raster_digest: Uint8Array;
        raster_encoding: ArtifactDescriptor["encoding"];
        raster_height: number;
        raster_kind: ArtifactDescriptor["kind"];
        raster_mime_type: ArtifactDescriptor["mimeType"];
        raster_verified_at: Date | string;
        raster_verifier_profile: string;
        raster_verifier_version: number;
        raster_width: number;
        revision_number: string | number;
        sanitized_summary: unknown;
        settings_digest: Uint8Array;
        signal: ChangeSignal["signal"];
        status: CaptureRevisionView["status"];
        winning_attempt_id: string;
      }>(
        `SELECT r.project_id, r.revision_id, r.capture_id,
                r.configuration_version, r.job_id, r.winning_attempt_id,
                r.revision_number, r.status, r.settings_digest,
                r.profile_digest, r.committed_at,
                ra.artifact_id AS raster_artifact_id,
                ra.kind AS raster_kind, ra.access_class AS raster_access_class,
                ra.digest AS raster_digest,
                ra.byte_length AS raster_byte_length,
                ra.mime_type AS raster_mime_type, ra.width AS raster_width,
                ra.height AS raster_height, ra.encoding AS raster_encoding,
                ra.color AS raster_color, ra.alpha AS raster_alpha,
                ra.verifier_profile AS raster_verifier_profile,
                ra.verifier_version AS raster_verifier_version,
                ra.verified_at AS raster_verified_at,
                pa.artifact_id AS provenance_artifact_id,
                pa.kind AS provenance_kind,
                pa.access_class AS provenance_access_class,
                pa.digest AS provenance_digest,
                pa.byte_length AS provenance_byte_length,
                pa.mime_type AS provenance_mime_type,
                pa.encoding AS provenance_encoding,
                pa.color AS provenance_color, pa.alpha AS provenance_alpha,
                pa.verifier_profile AS provenance_verifier_profile,
                pa.verifier_version AS provenance_verifier_version,
                pa.verified_at AS provenance_verified_at,
                pm.sanitized_summary,
                cs.change_signal_id, cs.baseline_revision_id,
                cs.current_artifact_id, cs.baseline_artifact_id, cs.signal,
                cs.difference_final_url, cs.difference_redirect_chain,
                cs.difference_profile, cs.difference_region,
                cs.difference_warnings, cs.difference_load_evidence,
                cs.computed_at
           FROM capture_revisions r
           JOIN capture_artifacts ra
             ON ra.project_id = r.project_id
            AND ra.artifact_id = r.raster_artifact_id
           JOIN capture_provenance_manifests pm
             ON pm.project_id = r.project_id
            AND pm.provenance_id = r.provenance_id
           JOIN capture_artifacts pa
             ON pa.project_id = pm.project_id
            AND pa.artifact_id = pm.provenance_artifact_id
           JOIN capture_change_signals cs
             ON cs.project_id = r.project_id
            AND cs.current_revision_id = r.revision_id
          WHERE r.project_id = $1 AND r.revision_id = $2`,
        [projectId, revisionId],
      );
      const row = result.rows[0];
      if (!row) this.notFound();
      const artifact: ArtifactDescriptor = {
        artifactId: row.raster_artifact_id,
        projectId: row.project_id,
        kind: "capture_raster",
        digest: digestString(row.raster_digest),
        byteLength: integer(row.raster_byte_length),
        mimeType: "image/png",
        width: row.raster_width,
        height: row.raster_height,
        encoding: "png",
        color: "srgb",
        alpha: row.raster_alpha as "opaque" | "present",
        verifierProfile: row.raster_verifier_profile,
        verifierVersion: row.raster_verifier_version,
        verifiedAt: timestamp(row.raster_verified_at),
        accessClass: "project_visual",
      };
      const provenance: ArtifactDescriptor = {
        artifactId: row.provenance_artifact_id,
        projectId: row.project_id,
        kind: "capture_provenance",
        digest: digestString(row.provenance_digest),
        byteLength: integer(row.provenance_byte_length),
        mimeType: "application/json",
        encoding: "json",
        color: "not_applicable",
        alpha: "not_applicable",
        verifierProfile: row.provenance_verifier_profile,
        verifierVersion: row.provenance_verifier_version,
        verifiedAt: timestamp(row.provenance_verified_at),
        accessClass: "restricted_provenance",
      };
      const changeSignal: ChangeSignal = {
        changeSignalId: row.change_signal_id,
        captureId: row.capture_id,
        currentRevisionId: revisionId,
        baselineRevisionId: row.baseline_revision_id,
        currentArtifactId: row.current_artifact_id,
        baselineArtifactId: row.baseline_artifact_id,
        signal: row.signal,
        differences: {
          finalUrl: row.difference_final_url,
          redirectChain: row.difference_redirect_chain,
          profile: row.difference_profile,
          region: row.difference_region,
          warnings: row.difference_warnings,
          loadEvidence: row.difference_load_evidence,
        },
        algorithm: "exact_bytes_and_provenance",
        algorithmVersion: 1,
        computedAt: timestamp(row.computed_at),
        materiality:
          "non_semantic_no_automatic_replacement_selection_or_notification",
      };
      const warningCodes =
        json<{ warningCodes?: string[] }>(row.sanitized_summary).warningCodes ?? [];
      return {
        schemaVersion: "public-page-capture-api/v1",
        messageType: "capture_revision_view",
        requestId,
        revision: {
          revisionId,
          projectId: row.project_id,
          captureId: row.capture_id,
          configurationVersion: integer(row.configuration_version),
          jobId: row.job_id,
          winningAttemptId: row.winning_attempt_id,
          revisionNumber: integer(row.revision_number),
          artifact,
          provenance,
          changeSignal,
          status: row.status,
          warningCodes,
          settingsDigest: digestString(row.settings_digest),
          profileDigest: digestString(row.profile_digest),
          committedAt: timestamp(row.committed_at),
          observationStatement:
            "Stored bytes and provenance are reproducible; the live page may later differ.",
        },
      };
    });
  }

  private async jobMessage(
    projectId: string,
    jobId: string,
    requestId: string,
    duplicateDelivery: boolean,
  ): Promise<CaptureJobViewMessage> {
    return await this.dependencies.database.transaction(async (client) => {
      const result = await client.query<JobRow>(
        "SELECT * FROM capture_jobs WHERE project_id = $1 AND job_id = $2",
        [projectId, jobId],
      );
      const row = result.rows[0];
      if (!row) this.notFound();
      const trigger: CaptureJobView["trigger"] =
        row.trigger_kind === "now"
          ? {
              kind: "now",
              commandId: row.trigger_reference_id,
              selectionIntent:
                json<SelectionIntent>(row.conditional_selection_intent) ?? {
                  kind: "none",
                },
            }
          : {
              kind: "on_build",
              buildSnapshot: {
                projectId: row.project_id,
                kind: row.trigger_reference_kind as
                  | "preview_build"
                  | "release_build",
                resourceId: row.trigger_reference_id,
                resourceVersionDigest: digestString(
                  row.trigger_reference_digest!,
                ),
              },
            };
      let conditionalSelectionResult: CaptureJobView["conditionalSelectionResult"] =
        "not_requested";
      if (
        row.conditional_selection_intent !== null &&
        row.state === "committed_review_required"
      ) {
        conditionalSelectionResult = "blocked_review";
      } else if (
        row.conditional_selection_intent !== null &&
        row.state === "committed_ready"
      ) {
        const selected = await client.query(
          `SELECT 1
             FROM capture_revision_selections
            WHERE project_id = $1
              AND revision_id = $2
              AND reason = 'capture_and_use'
            LIMIT 1`,
          [projectId, row.output_revision_id],
        );
        conditionalSelectionResult =
          selected.rows.length > 0 ? "applied" : "conflict";
      }
      const authorization: AuthorizationDecisionRef = {
        decisionId: row.authorization_decision_id,
        action:
          row.trigger_kind === "now"
            ? "capture_request_now"
            : "capture_request_on_build",
        principal: {
          principalKind: row.initiating_principal_kind,
          principalId: row.initiating_principal_id,
        },
        projectId: row.project_id,
        role: row.initiating_role,
        ...(row.membership_version === null
          ? {}
          : { membershipVersion: integer(row.membership_version) }),
        decidedAt: timestamp(row.authorization_decided_at),
        recheckMode: row.commit_recheck_mode,
      };
      const job: CaptureJobView = {
        jobId: row.job_id,
        projectId: row.project_id,
        captureId: row.capture_id,
        configurationVersion: integer(row.configuration_version),
        trigger,
        idempotencyFingerprint: digestString(row.request_fingerprint),
        initiatingAuthorization: authorization,
        settingsDigest: digestString(row.settings_digest),
        captureProfileId: row.capture_profile_id,
        captureProfileVersion: integer(row.capture_profile_version),
        profileDigest: digestString(row.profile_digest),
        retryBudget: row.retry_budget,
        state: row.state,
        outputRevisionId: row.output_revision_id,
        conditionalSelectionResult,
        requestedAt: timestamp(row.requested_at),
        enqueuedAt: nullableTimestamp(row.enqueued_at),
        availableAt: nullableTimestamp(row.available_at),
        terminalAt: nullableTimestamp(row.terminal_at),
        rowVersion: integer(row.row_version),
        duplicateDelivery,
      };
      return {
        schemaVersion: "public-page-capture-api/v1",
        messageType: "capture_job_view",
        requestId,
        job,
      };
    });
  }
}
