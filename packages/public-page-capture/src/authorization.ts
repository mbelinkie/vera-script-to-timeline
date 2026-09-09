import type {
  AuthorizationDecisionRef,
  DraftOccurrenceReference,
  PrincipalRef,
  VersionedExternalReference,
} from "@vera/contracts";

import { CaptureServiceError } from "./errors.js";

export type CaptureAction =
  | "capture_create"
  | "capture_configure"
  | "capture_read"
  | "capture_request_now"
  | "capture_request_on_build"
  | "capture_commit"
  | "capture_select"
  | "capture_use_preview"
  | "capture_use_release"
  | "capture_pin";

export type ExternalReference =
  | DraftOccurrenceReference
  | VersionedExternalReference;

export interface ProjectAuthorizationPort {
  authorize(
    projectId: string,
    principal: PrincipalRef,
    action: CaptureAction,
  ): Promise<AuthorizationDecisionRef>;
}

export interface AuthoringReferencePort {
  validate(
    projectId: string,
    reference: ExternalReference,
    action: "build" | "read" | "select" | "protect" | "use",
  ): Promise<void>;
}

export interface WorkerAuthorizationPort {
  authorize(workerInstallationId: string): Promise<void>;
}

export class StaticWorkerAuthorization implements WorkerAuthorizationPort {
  constructor(private readonly installationIds: ReadonlySet<string>) {}

  authorize(workerInstallationId: string): Promise<void> {
    if (!this.installationIds.has(workerInstallationId)) {
      return Promise.reject(
        new CaptureServiceError(
          "authentication_required",
          "Worker authentication is required.",
        ),
      );
    }
    return Promise.resolve();
  }
}

export class AuthorizationUnavailable extends CaptureServiceError {
  constructor() {
    super(
      "authorization_unavailable",
      "The authorization service could not make a current decision.",
      true,
    );
  }
}
