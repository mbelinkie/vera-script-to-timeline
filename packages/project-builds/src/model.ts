import { fingerprint } from "@vera/project-documents";

export type BuildClass = "preview" | "release";
export type BuildMode = "free" | "studio";

export interface SourcePin {
  readonly sourceId: string;
  readonly revision: string;
  readonly sha256: string;
}

/** Client expectation only: the server must bind each field to trusted stored records. */
export interface BuildIntent {
  readonly buildClass: BuildClass;
  readonly mode: BuildMode;
  readonly expectedRevision: number;
  readonly expectedDigest: string;
  readonly idempotencyKey: string;
  readonly selectedSources: readonly SourcePin[];
  readonly render: false;
  readonly delivery: false;
}

export class BuildInputRefusal extends Error {
  override readonly name = "BuildInputRefusal";
  readonly status = 400;
  constructor() { super("invalid_build_intent"); }
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const DIGEST = /^sha256:[0-9a-f]{64}$/u;
const REVISION = /^[^\\/]+$/u;
const INTENT_KEYS = [
  "buildClass", "mode", "expectedRevision", "expectedDigest",
  "idempotencyKey", "selectedSources", "render", "delivery",
] as const;
const PIN_KEYS = ["sourceId", "revision", "sha256"] as const;

function ownObject(value: unknown): value is Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype: unknown = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function exactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return Reflect.ownKeys(value).length === keys.length &&
    Reflect.ownKeys(value).every((key) => typeof key === "string" && keys.includes(key));
}

function uuid(value: unknown): value is string {
  return typeof value === "string" && UUID.test(value);
}

function digest(value: unknown): value is string {
  return typeof value === "string" && DIGEST.test(value);
}

/** No authorization or source verification takes place at this input boundary. */
export function parseBuildIntent(raw: unknown): BuildIntent {
  if (!ownObject(raw) || !exactKeys(raw, INTENT_KEYS) ||
      (raw.buildClass !== "preview" && raw.buildClass !== "release") ||
      (raw.mode !== "free" && raw.mode !== "studio") ||
      typeof raw.expectedRevision !== "number" ||
      !Number.isSafeInteger(raw.expectedRevision) || raw.expectedRevision < 0 ||
      !digest(raw.expectedDigest) || !uuid(raw.idempotencyKey) ||
      raw.render !== false || raw.delivery !== false ||
      !Array.isArray(raw.selectedSources) || raw.selectedSources.length > 256) {
    throw new BuildInputRefusal();
  }

  const ids = new Set<string>();
  const selectedSources: SourcePin[] = [];
  for (const entry of raw.selectedSources as unknown[]) {
    if (!ownObject(entry) || !exactKeys(entry, PIN_KEYS) ||
        !uuid(entry.sourceId) ||
        typeof entry.revision !== "string" || entry.revision.length < 1 ||
        entry.revision.length > 256 || entry.revision !== entry.revision.trim() ||
        !REVISION.test(entry.revision) ||
        Array.from(entry.revision).some((char) =>
          char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127) ||
        !digest(entry.sha256)) {
      throw new BuildInputRefusal();
    }
    const sourceId = entry.sourceId.toLowerCase();
    if (ids.has(sourceId)) throw new BuildInputRefusal();
    ids.add(sourceId);
    selectedSources.push(Object.freeze({
      sourceId, revision: entry.revision, sha256: entry.sha256,
    }));
  }
  // Source selection is a set; input order must not alter retry identity.
  selectedSources.sort((a, b) => a.sourceId < b.sourceId ? -1 : a.sourceId > b.sourceId ? 1 : 0);
  return Object.freeze({
    buildClass: raw.buildClass,
    mode: raw.mode,
    expectedRevision: raw.expectedRevision,
    expectedDigest: raw.expectedDigest,
    idempotencyKey: raw.idempotencyKey.toLowerCase(),
    selectedSources: Object.freeze(selectedSources),
    render: false,
    delivery: false,
  });
}

/** Digest of normalized intent, NOT a substitute for project/actor-scoped authorization. */
export function buildIntentFingerprint(intent: BuildIntent): string {
  return fingerprint(parseBuildIntent(intent));
}
