import {
  exportPrompter,
  type PrompterExportResult,
  type PrompterExportSettings,
} from "@vera/contracts/prompter-export";
import type { ValidationDiagnostic } from "@vera/contracts/script-validator";
import { checkedDocument } from "@vera/project-documents";

export interface PrompterExpectedSnapshot {
  projectId: string;
  revision: number;
  digest: string;
}

export type PreparedSavedPrompter =
  | {
      status: 200;
      body: {
        projectId: string;
        revision: number;
        digest: string;
        sourceDocument: Extract<PrompterExportResult, { ok: true }>["sidecar"]["sourceDocument"];
        text: string;
        sidecarJson: string;
        textSha256: string;
        sidecarSha256: string;
      };
    }
  | { status: 409; body: { error: "saved_script_changed" } }
  | { status: 422; body: { error: "prompter_validation_failed"; diagnostics: ValidationDiagnostic[] } }
  | {
      status: 503;
      body: { error:
        | "saved_script_unavailable"
        | "saved_script_invalid"
        | "saved_script_digest_mismatch"
        | "prompter_export_unavailable" };
    };

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

const storedDigestPattern = /^sha256:[a-f0-9]{64}$/u;

/**
 * Prepare the exact frozen prompter pair for an already-authorized saved head.
 *
 * This is not an authorization boundary: callers must obtain `view` from the
 * project API after the existing browser/session and view_document checks.
 * Never accept a browser-supplied document here as a source of authority.
 */
export function prepareSavedPrompter(
  view: unknown,
  expected: PrompterExpectedSnapshot,
  settings: PrompterExportSettings,
): PreparedSavedPrompter {
  if (!isRecord(view) || view.projectId !== expected.projectId ||
      !Number.isSafeInteger(view.revision) || (view.revision as number) < 0 ||
      typeof view.digest !== "string" || !storedDigestPattern.test(view.digest)) {
    return { status: 503, body: { error: "saved_script_unavailable" } };
  }

  let saved: ReturnType<typeof checkedDocument>;
  try {
    // Re-validate identity and hash the actual serialized saved document,
    // independently of the service's reported content digest.
    saved = checkedDocument(view.document, expected.projectId);
  } catch {
    return { status: 503, body: { error: "saved_script_invalid" } };
  }
  if (saved.digest !== view.digest) {
    return { status: 503, body: { error: "saved_script_digest_mismatch" } };
  }
  if (view.revision !== expected.revision || view.digest !== expected.digest) {
    return { status: 409, body: { error: "saved_script_changed" } };
  }

  // Database revision/digest are *not* the document's frozen live-head
  // sequence/hash. The accepted #37 exporter owns sidecar source identity.
  let result: PrompterExportResult;
  try {
    result = exportPrompter(saved.document, settings);
  } catch {
    // Exporter internal exceptions are not user validation diagnostics and
    // must not leak content or partial output to the browser.
    return { status: 503, body: { error: "prompter_export_unavailable" } };
  }
  if (!result.ok) {
    return { status: 422, body: {
      error: "prompter_validation_failed",
      diagnostics: result.diagnostics,
    } };
  }
  return { status: 200, body: {
    projectId: expected.projectId,
    revision: view.revision,
    digest: view.digest,
    sourceDocument: result.sidecar.sourceDocument,
    text: result.text,
    sidecarJson: result.sidecarJson,
    textSha256: result.sidecar.textSha256,
    sidecarSha256: result.sidecarSha256,
  } };
}
