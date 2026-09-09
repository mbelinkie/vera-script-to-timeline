import { createHash, randomUUID } from "node:crypto";

import {
  deriveSpotlightMatte,
  type CapturePixelRect,
  type DerivationParameters,
} from "@vera/spotlight-matte";

const SCHEMA_VERSION = "spotlight-evidence/v1";
const CANONICALIZATION_VERSION = "vera.spotlight.canonical-json.v1";
const REMAP_VERSION = "vera.spotlight.remap.exact-context.v1";
const MILLION = 1_000_000;
const DIGEST = /^sha256:[a-f0-9]{64}$/u;

export interface OcrExecutionProfile {
  readonly providerId: string;
  readonly executionLocation: string;
  readonly providerApiVersion: string;
  readonly adapterName: string;
  readonly adapterVersion: string;
  readonly modelName: string;
  readonly modelVersion: string;
  readonly modelDigest: string;
  readonly profileId: string;
  readonly profileVersion: string;
  readonly profileDigest: string;
  readonly languagePolicy: string;
  readonly preprocessingPolicy: string;
  readonly geometryVersion: string;
  readonly readingOrderPolicy: string;
  readonly privacyPolicy: string;
  readonly costPolicy: string;
}

export const PINNED_VISION_PROFILE = {
  providerId: "apple-vision-local",
  executionLocation: "local",
  providerApiVersion: "VNRecognizeTextRequest-revision-3",
  adapterName: "vera-vision-local-adapter",
  adapterVersion: "1",
  modelName: "Apple Vision text recognition",
  modelVersion: "VNRecognizeTextRequest-r3",
  modelDigest: "unavailable:apple-opaque-framework-model",
  profileId: "vision-r3-accurate-en-US-no-language-correction-v1",
  profileVersion: "1",
  profileDigest: "sha256:c95cee13fa2e2f912ff65cb5dfeac62655cb345ccb78a7828935791baf8acd51",
  languagePolicy: "en-US-only-v1",
  preprocessingPolicy: "fixed-up-orientation-v1",
  geometryVersion: "vision-lower-left-outward-v1",
  readingOrderPolicy: "top-left-raw-ordinal-v1",
  privacyPolicy: "local-device-only-no-network-v1",
  costPolicy: "local-no-provider-charge-usd-zero-v1",
} as const satisfies OcrExecutionProfile;

export type OcrGranularity = "word" | "line";
export type PrincipalKind = "editor" | "producer" | "service";
export type RemapOutcome =
  | "unique_candidate"
  | "stale_missing"
  | "stale_ambiguous"
  | "stale_contradictory"
  | "stale_incompatible_profile"
  | "stale_manual_redraw_required"
  | "stale_invalid_evidence";

export interface RasterRef {
  readonly projectId: string;
  readonly captureRevisionId: string;
  readonly rasterArtifactId: string;
  readonly rasterDigest: string;
  readonly width: number;
  readonly height: number;
}

export interface ProviderRect {
  readonly leftMicros: number;
  readonly topMicros: number;
  readonly rightMicros: number;
  readonly bottomMicros: number;
}

export interface FrozenOcrElement {
  readonly granularity: OcrGranularity;
  readonly rawOrdinal: number;
  readonly text: string;
  readonly rect: ProviderRect;
  readonly confidenceMillionths: number | null;
  readonly lineRawOrdinal?: number;
}

export interface FrozenOcrResponse {
  readonly rawResponseBytes: Buffer;
  readonly elements: readonly FrozenOcrElement[];
}

interface VisionOutputElement {
  readonly text: string;
  readonly rawOrdinal: number;
  readonly lineRawOrdinal?: number;
  readonly confidenceMillionths?: number;
  readonly rect: CapturePixelRect;
}

interface VisionOutput {
  readonly candidate: string;
  readonly profile: string;
  readonly rasterWidth: number;
  readonly rasterHeight: number;
  readonly words: readonly VisionOutputElement[];
  readonly lines: readonly VisionOutputElement[];
}

function isVisionElement(value: unknown): value is VisionOutputElement {
  if (value === null || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  const rect = item.rect;
  return typeof item.text === "string" && typeof item.rawOrdinal === "number" && (item.lineRawOrdinal === undefined || typeof item.lineRawOrdinal === "number") && (item.confidenceMillionths === undefined || typeof item.confidenceMillionths === "number") && rect !== null && typeof rect === "object" && ["x", "y", "width", "height"].every((field) => typeof (rect as Record<string, unknown>)[field] === "number");
}

function isVisionOutput(value: unknown): value is VisionOutput {
  if (value === null || typeof value !== "object") return false;
  const output = value as Record<string, unknown>;
  return typeof output.candidate === "string" && typeof output.profile === "string" && typeof output.rasterWidth === "number" && typeof output.rasterHeight === "number" && Array.isArray(output.words) && output.words.every(isVisionElement) && Array.isArray(output.lines) && output.lines.every(isVisionElement);
}

export function frozenVisionResponse(rawResponseBytes: Buffer, raster: RasterRef): FrozenOcrResponse {
  let parsed: unknown;
  try { parsed = JSON.parse(rawResponseBytes.toString("utf8")) as unknown; } catch { throw new SpotlightError("invalid_provider_response", "Vision returned an unreadable response envelope."); }
  if (!isVisionOutput(parsed)) throw new SpotlightError("invalid_provider_response", "Vision returned an invalid response envelope.");
  if (parsed.candidate !== "apple-vision" || parsed.profile !== PINNED_VISION_PROFILE.profileId || parsed.rasterWidth !== raster.width || parsed.rasterHeight !== raster.height) throw new SpotlightError("invalid_provider_response", "Vision response does not match the accepted local profile or raster.");
  const convert = (element: VisionOutputElement, granularity: OcrGranularity): FrozenOcrElement => ({
    granularity, rawOrdinal: element.rawOrdinal, text: element.text.normalize("NFC"), ...(element.lineRawOrdinal === undefined ? {} : { lineRawOrdinal: element.lineRawOrdinal }),
    confidenceMillionths: element.confidenceMillionths ?? null,
    rect: { leftMicros: element.rect.x * MILLION, topMicros: element.rect.y * MILLION, rightMicros: (element.rect.x + element.rect.width) * MILLION, bottomMicros: (element.rect.y + element.rect.height) * MILLION },
  });
  return { rawResponseBytes, elements: [...parsed.lines.map((element) => convert(element, "line")), ...parsed.words.map((element) => convert(element, "word"))] };
}

export interface OcrElement {
  readonly elementId: string;
  readonly granularity: OcrGranularity;
  readonly rawOrdinal: number;
  readonly readingOrder: number;
  readonly text: string;
  readonly sourcePixelRect: CapturePixelRect;
  readonly normalizedRectPpm: { readonly left: number; readonly top: number; readonly right: number; readonly bottom: number };
  readonly confidence: { readonly kind: "provider_reported"; readonly millionths: number } | { readonly kind: "unavailable"; readonly reason: string };
  readonly parentLineId?: string;
  readonly childWordIds?: readonly string[];
  readonly context: { readonly before: readonly string[]; readonly after: readonly string[]; readonly atStart: boolean; readonly atEnd: boolean };
}

export interface OcrBatch {
  readonly recordId: string;
  readonly recordType: "ocr_evidence_batch";
  readonly schemaVersion: typeof SCHEMA_VERSION;
  readonly projectId: string;
  readonly createdAt: string;
  readonly payloadDigest: string;
  readonly attemptId: string;
  readonly raster: RasterRef;
  readonly profile: OcrExecutionProfile;
  readonly rawResponseDigest: string;
  readonly evidenceSeedDigest: string;
  readonly evidenceDigest: string;
  readonly elements: readonly OcrElement[];
}

interface RecordBase {
  readonly recordId: string;
  readonly schemaVersion: typeof SCHEMA_VERSION;
  readonly projectId: string;
  readonly createdAt: string;
  readonly payloadDigest: string;
}

export interface OcrAttempt extends RecordBase {
  readonly recordType: "ocr_attempt_evidence";
  readonly raster: RasterRef;
  readonly profile: OcrExecutionProfile;
  readonly authorizationDigest: string;
  readonly requestDigest: string;
  readonly outcome: "succeeded" | "failed";
  readonly terminalCode: string | null;
  readonly batchId: string | null;
}

export interface AutomatedProposal extends RecordBase {
  readonly recordType: "automated_target_proposal";
  readonly raster: RasterRef;
  readonly batchId: string;
  readonly granularity: OcrGranularity;
  readonly elementIds: readonly string[];
  readonly methodVersion: string;
}

export interface ManualProposal extends RecordBase {
  readonly recordType: "manual_geometry_proposal";
  readonly raster: RasterRef;
  readonly region: CapturePixelRect;
}

export type Proposal = AutomatedProposal | ManualProposal;

export interface Confirmation extends RecordBase {
  readonly recordType: "author_confirmation";
  readonly proposalId: string;
  readonly raster: RasterRef;
  readonly source: "ocr_proposal" | "manual_geometry";
  readonly actorId: string;
  readonly authorizationDigest: string;
  readonly expectedBindingSequence: number;
  readonly geometry: readonly ({ readonly id: string; readonly granularity: OcrGranularity } & CapturePixelRect)[] | CapturePixelRect;
  readonly geometryDigest: string;
  readonly selectedText: readonly string[];
  readonly context: { readonly before: readonly string[]; readonly after: readonly string[]; readonly atStart: boolean; readonly atEnd: boolean } | null;
  readonly batchId: string | null;
  readonly remapProposalId: string | null;
  readonly remapDecisionId: string | null;
}

export interface RemapProposal extends RecordBase {
  readonly recordType: "remap_proposal";
  readonly oldConfirmationId: string;
  readonly newRaster: RasterRef;
  readonly newBatchId: string | null;
  readonly outcome: RemapOutcome;
  readonly candidateElementIds: readonly (readonly string[])[];
}

export interface RemapDecision extends RecordBase {
  readonly recordType: "remap_decision";
  readonly remapProposalId: string;
  readonly decision: "keep_old" | "accept_remap" | "redraw";
  readonly actorId: string;
  readonly expectedBindingSequence: number;
  readonly newConfirmationId: string | null;
}

export interface DerivationRecord extends RecordBase {
  readonly recordType: "spotlight_derivation_record";
  readonly confirmationId: string;
  readonly projectedInputDigest: string;
  readonly matteDigest: string;
  readonly matteReceiptDigest: string;
  readonly wrapperDigest: string;
  readonly matteBytes: Buffer;
  readonly matteReceiptBytes: Buffer;
}

export type SpotlightRecord = OcrAttempt | OcrBatch | Proposal | Confirmation | RemapProposal | RemapDecision | DerivationRecord;

export interface SpotlightRepository {
  append(record: SpotlightRecord): void;
  get<T extends SpotlightRecord["recordType"]>(type: T, id: string): Extract<SpotlightRecord, { readonly recordType: T }> | undefined;
  records(): readonly SpotlightRecord[];
}

export class MemorySpotlightRepository implements SpotlightRepository {
  private readonly values = new Map<string, SpotlightRecord>();

  append(record: SpotlightRecord): void {
    if (this.values.has(record.recordId)) throw new SpotlightError("duplicate_record", "An immutable record already exists.");
    this.values.set(record.recordId, structuredClone(record));
  }

  get<T extends SpotlightRecord["recordType"]>(type: T, id: string): Extract<SpotlightRecord, { readonly recordType: T }> | undefined {
    const record = this.values.get(id);
    return record?.recordType === type ? structuredClone(record) as Extract<SpotlightRecord, { readonly recordType: T }> : undefined;
  }

  records(): readonly SpotlightRecord[] { return [...this.values.values()].map((record) => structuredClone(record)); }
}

export class SpotlightError extends Error {
  override readonly name = "SpotlightError";
  constructor(readonly code: string, message: string) { super(message); }
}

function canonical(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  return `{${Object.entries(value as Record<string, unknown>).sort(([a], [b]) => a.localeCompare(b)).map(([key, child]) => `${JSON.stringify(key)}:${canonical(child)}`).join(",")}}`;
}

function digest(value: unknown): string {
  return `sha256:${createHash("sha256").update(`${canonical(value)}\n`, "utf8").digest("hex")}`;
}

function safeDigest(value: string, field: string): void {
  if (!DIGEST.test(value)) throw new SpotlightError("invalid_evidence", `${field} must be a lowercase SHA-256 digest.`);
}

function integer(value: number, field: string): void {
  if (!Number.isSafeInteger(value)) throw new SpotlightError("invalid_provider_geometry", `${field} must be a safe integer.`);
}

function sameRaster(left: RasterRef, right: RasterRef): boolean {
  return left.projectId === right.projectId && left.captureRevisionId === right.captureRevisionId && left.rasterArtifactId === right.rasterArtifactId && left.rasterDigest === right.rasterDigest && left.width === right.width && left.height === right.height;
}

function rectFromMicros(rect: ProviderRect, raster: RasterRef): CapturePixelRect {
  for (const [name, value] of [["leftMicros", rect.leftMicros], ["topMicros", rect.topMicros], ["rightMicros", rect.rightMicros], ["bottomMicros", rect.bottomMicros]] as const) integer(value, name);
  if (rect.leftMicros < 0 || rect.topMicros < 0 || rect.rightMicros <= rect.leftMicros || rect.bottomMicros <= rect.topMicros) throw new SpotlightError("invalid_provider_geometry", "Provider geometry is inverted.");
  const x = Math.floor(rect.leftMicros / MILLION);
  const y = Math.floor(rect.topMicros / MILLION);
  const right = Math.ceil(rect.rightMicros / MILLION);
  const bottom = Math.ceil(rect.bottomMicros / MILLION);
  if (right > raster.width || bottom > raster.height || x < 0 || y < 0 || right <= x || bottom <= y) throw new SpotlightError("invalid_provider_geometry", "Provider geometry is outside the immutable raster.");
  return { x, y, width: right - x, height: bottom - y };
}

function normalized(rect: CapturePixelRect, raster: RasterRef) {
  return { left: Math.floor(rect.x * MILLION / raster.width), top: Math.floor(rect.y * MILLION / raster.height), right: Math.ceil((rect.x + rect.width) * MILLION / raster.width), bottom: Math.ceil((rect.y + rect.height) * MILLION / raster.height) };
}

function ensureRaster(raster: RasterRef): void {
  safeDigest(raster.rasterDigest, "rasterDigest");
  if (!Number.isSafeInteger(raster.width) || !Number.isSafeInteger(raster.height) || raster.width < 1 || raster.height < 1 || raster.width * raster.height > 16_777_216) throw new SpotlightError("invalid_evidence", "Raster dimensions are invalid.");
}

function recordBase(projectId: string, recordId: string, createdAt: string, payload: object) {
  return { recordId, schemaVersion: SCHEMA_VERSION, projectId, createdAt, payloadDigest: digest(payload) } as const;
}

function ordered(elements: readonly OcrElement[], granularity: OcrGranularity): OcrElement[] {
  return elements.filter((element) => element.granularity === granularity).sort((left, right) => left.readingOrder - right.readingOrder || left.elementId.localeCompare(right.elementId));
}

function exactContext(elements: readonly OcrElement[], index: number, spanLength: number, width: number) {
  return {
    before: elements.slice(Math.max(0, index - width), index).map(({ text }) => text),
    after: elements.slice(index + spanLength, index + spanLength + width).map(({ text }) => text),
    atStart: index === 0,
    atEnd: index + spanLength === elements.length,
  } as const;
}

function matchingContext(left: NonNullable<Confirmation["context"]>, right: ReturnType<typeof exactContext>): boolean {
  return left.atStart === right.atStart && left.atEnd === right.atEnd && canonical(left.before) === canonical(right.before) && canonical(left.after) === canonical(right.after);
}

export interface SpotlightServiceOptions {
  readonly repository?: SpotlightRepository;
  readonly now?: () => Date;
  readonly id?: () => string;
}

export class SpotlightEvidenceService {
  readonly repository: SpotlightRepository;
  private readonly now: () => Date;
  private readonly id: () => string;
  private bindingSequence = 0;

  constructor(options: SpotlightServiceOptions = {}) {
    this.repository = options.repository ?? new MemorySpotlightRepository();
    this.now = options.now ?? (() => new Date());
    this.id = options.id ?? randomUUID;
  }

  recordFrozenOcr(input: {
    readonly raster: RasterRef;
    readonly authorizationDigest: string;
    readonly requestDigest: string;
    readonly profile: OcrExecutionProfile;
    readonly response: FrozenOcrResponse;
  }): { readonly attempt: OcrAttempt; readonly batch: OcrBatch } {
    ensureRaster(input.raster);
    safeDigest(input.authorizationDigest, "authorizationDigest");
    safeDigest(input.requestDigest, "requestDigest");
    if (canonical(input.profile) !== canonical(PINNED_VISION_PROFILE)) throw new SpotlightError("engine_profile_unavailable", "Only the accepted local Vision profile may execute.");
    const timestamp = this.now().toISOString();
    const attemptId = this.id();
    const rawResponseDigest = `sha256:${createHash("sha256").update(input.response.rawResponseBytes).digest("hex")}`;
    const seen = new Set<string>();
    const rawElements = input.response.elements.map((element) => {
      if (element.text.normalize("NFC") !== element.text || element.text.length === 0 || !Number.isSafeInteger(element.rawOrdinal) || element.rawOrdinal < 0) throw new SpotlightError("invalid_provider_response", "OCR text and ordinal must be canonical.");
      const unique = `${element.granularity}:${element.rawOrdinal}`;
      if (seen.has(unique)) throw new SpotlightError("invalid_provider_response", "OCR raw ordinals must be unique by granularity.");
      seen.add(unique);
      if (element.confidenceMillionths !== null && (!Number.isSafeInteger(element.confidenceMillionths) || element.confidenceMillionths < 0 || element.confidenceMillionths > MILLION)) throw new SpotlightError("invalid_provider_response", "OCR confidence must be an integer in millionths.");
      return { ...element, sourcePixelRect: rectFromMicros(element.rect, input.raster) };
    });
    const evidenceSeedDigest = digest({ raster: input.raster, profile: input.profile, rawResponseDigest, canonicalization: CANONICALIZATION_VERSION });
    const lines = rawElements.filter(({ granularity }) => granularity === "line").sort((a, b) => a.sourcePixelRect.y - b.sourcePixelRect.y || a.sourcePixelRect.x - b.sourcePixelRect.x || a.rawOrdinal - b.rawOrdinal);
    const words = rawElements.filter(({ granularity }) => granularity === "word").sort((a, b) => a.sourcePixelRect.y - b.sourcePixelRect.y || a.sourcePixelRect.x - b.sourcePixelRect.x || a.rawOrdinal - b.rawOrdinal);
    const elementId = (element: typeof rawElements[number], readingOrder: number) => digest({ identityVersion: "vera.spotlight.ocr-element-id.v1", evidenceSeedDigest, granularity: element.granularity, rawOrdinal: element.rawOrdinal, canonicalText: element.text, providerRectMicros: element.rect, sourcePixelRect: element.sourcePixelRect, readingOrder });
    const lineIds = new Map(lines.map((line, index) => [line.rawOrdinal, elementId(line, index)]));
    const makeElement = (element: typeof rawElements[number], readingOrder: number): OcrElement => {
      const parentLineId = element.granularity === "word" && element.lineRawOrdinal !== undefined ? lineIds.get(element.lineRawOrdinal) : undefined;
      if (element.granularity === "word" && !parentLineId) throw new SpotlightError("invalid_provider_response", "Every word must reference a retained line.");
      return {
      elementId: elementId(element, readingOrder), granularity: element.granularity, rawOrdinal: element.rawOrdinal, readingOrder, text: element.text,
      sourcePixelRect: element.sourcePixelRect, normalizedRectPpm: normalized(element.sourcePixelRect, input.raster),
      confidence: element.confidenceMillionths === null ? { kind: "unavailable", reason: "vision_no_word_confidence" } : { kind: "provider_reported", millionths: element.confidenceMillionths },
      ...(parentLineId ? { parentLineId } : {}),
      context: { before: [], after: [], atStart: false, atEnd: false },
      };
    };
    const elements = [...lines.map(makeElement), ...words.map(makeElement)].map((element, _index, all) => {
      const peers = ordered(all, element.granularity);
      const position = peers.findIndex(({ elementId }) => elementId === element.elementId);
      const children = element.granularity === "line" ? all.filter((word) => word.parentLineId === element.elementId).sort((a, b) => a.readingOrder - b.readingOrder).map(({ elementId }) => elementId) : undefined;
      return { ...element, ...(children ? { childWordIds: children } : {}), context: exactContext(peers, position, 1, element.granularity === "word" ? 2 : 1) };
    });
    const batchId = this.id();
    const evidenceDigest = digest({ evidenceSeedDigest, elements });
    const batch: OcrBatch = { ...recordBase(input.raster.projectId, batchId, timestamp, { attemptId, evidenceSeedDigest, evidenceDigest, elements }), recordType: "ocr_evidence_batch", attemptId, raster: input.raster, profile: input.profile, rawResponseDigest, evidenceSeedDigest, evidenceDigest, elements };
    const attempt: OcrAttempt = { ...recordBase(input.raster.projectId, attemptId, timestamp, { raster: input.raster, rawResponseDigest, batchId }), recordType: "ocr_attempt_evidence", raster: input.raster, profile: input.profile, authorizationDigest: input.authorizationDigest, requestDigest: input.requestDigest, outcome: "succeeded", terminalCode: null, batchId };
    this.repository.append(attempt);
    this.repository.append(batch);
    return { attempt, batch };
  }

  recordOcrFailure(input: { readonly raster: RasterRef; readonly authorizationDigest: string; readonly requestDigest: string; readonly profile: OcrExecutionProfile; readonly terminalCode: string }): OcrAttempt {
    ensureRaster(input.raster);
    safeDigest(input.authorizationDigest, "authorizationDigest");
    safeDigest(input.requestDigest, "requestDigest");
    if (!/^[a-z0-9_]+$/u.test(input.terminalCode)) throw new SpotlightError("invalid_evidence", "Terminal OCR codes must be stable safe identifiers.");
    const recordId = this.id();
    const attempt: OcrAttempt = { ...recordBase(input.raster.projectId, recordId, this.now().toISOString(), { raster: input.raster, profile: input.profile, terminalCode: input.terminalCode }), recordType: "ocr_attempt_evidence", raster: input.raster, profile: input.profile, authorizationDigest: input.authorizationDigest, requestDigest: input.requestDigest, outcome: "failed", terminalCode: input.terminalCode, batchId: null };
    this.repository.append(attempt);
    return attempt;
  }

  proposeOcr(batchId: string, granularity: OcrGranularity, elementIds: readonly string[]): AutomatedProposal {
    const batch = this.required("ocr_evidence_batch", batchId);
    if (elementIds.length === 0 || new Set(elementIds).size !== elementIds.length) throw new SpotlightError("proposal_invalid", "An OCR proposal needs one unique, nonempty selection.");
    const candidates = ordered(batch.elements, granularity);
    const positions = elementIds.map((id) => candidates.findIndex((element) => element.elementId === id));
    if (positions.some((index) => index < 0) || positions.some((index, offset) => index !== positions[0]! + offset)) throw new SpotlightError("proposal_invalid", "A v1 OCR proposal must select a contiguous ordered span.");
    const recordId = this.id();
    const proposal: AutomatedProposal = { ...recordBase(batch.projectId, recordId, this.now().toISOString(), { batchId, granularity, elementIds }), recordType: "automated_target_proposal", raster: batch.raster, batchId, granularity, elementIds: [...elementIds], methodVersion: "vera.spotlight.ocr-proposal.v1" };
    this.repository.append(proposal);
    return proposal;
  }

  proposeManual(raster: RasterRef, region: CapturePixelRect): ManualProposal {
    ensureRaster(raster);
    this.validateRect(region, raster);
    const recordId = this.id();
    const proposal: ManualProposal = { ...recordBase(raster.projectId, recordId, this.now().toISOString(), { raster, region }), recordType: "manual_geometry_proposal", raster, region: { ...region } };
    this.repository.append(proposal);
    return proposal;
  }

  confirm(input: { readonly proposalId: string; readonly actorId: string; readonly actorKind: PrincipalKind; readonly authorizationDigest: string; readonly expectedBindingSequence: number; readonly remapProposalId?: string; readonly remapDecisionId?: string }): Confirmation {
    if (input.actorKind === "service") throw new SpotlightError("confirmation_required", "Automation cannot create an author confirmation.");
    safeDigest(input.authorizationDigest, "authorizationDigest");
    if (input.expectedBindingSequence !== this.bindingSequence) throw new SpotlightError("binding_conflict", "The target binding changed; refresh before confirming.");
    const proposal = this.requiredProposal(input.proposalId);
    const automated = proposal.recordType === "automated_target_proposal";
    const batch = automated ? this.required("ocr_evidence_batch", proposal.batchId) : undefined;
    const selected = automated ? proposal.elementIds.map((id) => batch!.elements.find((element) => element.elementId === id)!).map((element) => ({ id: element.elementId, granularity: element.granularity, ...element.sourcePixelRect })) : null;
    const orderedSelection = automated ? ordered(batch!.elements, proposal.granularity).filter((element) => proposal.elementIds.includes(element.elementId)) : [];
    const position = automated ? ordered(batch!.elements, proposal.granularity).findIndex((element) => element.elementId === proposal.elementIds[0]) : -1;
    const context = automated ? exactContext(ordered(batch!.elements, proposal.granularity), position, proposal.elementIds.length, proposal.granularity === "word" ? 2 : 1) : null;
    const geometry = automated ? selected! : proposal.region;
    const recordId = this.id();
    const confirmation: Confirmation = { ...recordBase(proposal.projectId, recordId, this.now().toISOString(), { proposalId: proposal.recordId, geometry, actorId: input.actorId }), recordType: "author_confirmation", proposalId: proposal.recordId, raster: proposal.raster, source: automated ? "ocr_proposal" : "manual_geometry", actorId: input.actorId, authorizationDigest: input.authorizationDigest, expectedBindingSequence: input.expectedBindingSequence, geometry, geometryDigest: digest(geometry), selectedText: orderedSelection.map(({ text }) => text), context, batchId: automated ? batch!.recordId : null, remapProposalId: input.remapProposalId ?? null, remapDecisionId: input.remapDecisionId ?? null };
    this.repository.append(confirmation);
    this.bindingSequence += 1;
    return confirmation;
  }

  assessRemap(input: { readonly oldConfirmationId: string; readonly newBatchId: string; readonly newRaster: RasterRef }): RemapProposal {
    const old = this.required("author_confirmation", input.oldConfirmationId);
    ensureRaster(input.newRaster);
    if (sameRaster(old.raster, input.newRaster)) throw new SpotlightError("remap_invalid", "A remap requires a distinct capture revision.");
    let outcome: RemapOutcome;
    let candidates: readonly (readonly string[])[] = [];
    let newBatch: OcrBatch | undefined;
    try { newBatch = this.required("ocr_evidence_batch", input.newBatchId); } catch { newBatch = undefined; }
    if (!newBatch || !sameRaster(newBatch.raster, input.newRaster)) {
      outcome = "stale_invalid_evidence";
    } else if (old.source === "manual_geometry" || old.batchId === null || old.context === null) {
      outcome = "stale_manual_redraw_required";
    } else {
      const oldBatch = this.required("ocr_evidence_batch", old.batchId);
      const compatible = canonical({ provider: oldBatch.profile.providerId, adapter: oldBatch.profile.adapterVersion, model: oldBatch.profile.modelVersion, digest: oldBatch.profile.profileDigest, geometry: oldBatch.profile.geometryVersion, order: oldBatch.profile.readingOrderPolicy }) === canonical({ provider: newBatch.profile.providerId, adapter: newBatch.profile.adapterVersion, model: newBatch.profile.modelVersion, digest: newBatch.profile.profileDigest, geometry: newBatch.profile.geometryVersion, order: newBatch.profile.readingOrderPolicy });
      if (!compatible) {
        outcome = "stale_incompatible_profile";
      } else {
        const geometry = old.geometry as readonly ({ readonly id: string; readonly granularity: OcrGranularity } & CapturePixelRect)[];
        const granularity = geometry[0]?.granularity;
        if (!granularity || geometry.length !== old.selectedText.length) {
          outcome = "stale_invalid_evidence";
        } else {
          const target = ordered(newBatch.elements, granularity);
          const textCandidates: OcrElement[][] = [];
          const fullCandidates: OcrElement[][] = [];
          for (let index = 0; index + old.selectedText.length <= target.length; index += 1) {
            const window = target.slice(index, index + old.selectedText.length);
            if (canonical(window.map(({ text }) => text)) !== canonical(old.selectedText)) continue;
            textCandidates.push(window);
            if (matchingContext(old.context, exactContext(target, index, window.length, granularity === "word" ? 2 : 1))) fullCandidates.push(window);
          }
          candidates = fullCandidates.map((candidate) => candidate.map(({ elementId }) => elementId)).sort((left, right) => canonical(left).localeCompare(canonical(right)));
          outcome = textCandidates.length === 0 ? "stale_missing" : fullCandidates.length === 1 ? "unique_candidate" : fullCandidates.length > 1 ? "stale_ambiguous" : "stale_contradictory";
        }
      }
    }
    const recordId = this.id();
    const proposal: RemapProposal = { ...recordBase(old.projectId, recordId, this.now().toISOString(), { algorithmVersion: REMAP_VERSION, oldConfirmationId: old.recordId, newRaster: input.newRaster, newBatchId: newBatch?.recordId ?? null, outcome, candidates }), recordType: "remap_proposal", oldConfirmationId: old.recordId, newRaster: input.newRaster, newBatchId: newBatch?.recordId ?? null, outcome, candidateElementIds: candidates };
    this.repository.append(proposal);
    return proposal;
  }

  decideRemap(input: { readonly remapProposalId: string; readonly decision: "keep_old" | "accept_remap"; readonly actorId: string; readonly actorKind: PrincipalKind; readonly authorizationDigest: string; readonly expectedBindingSequence: number }): { readonly decision: RemapDecision; readonly confirmation: Confirmation | null } {
    if (input.actorKind === "service") throw new SpotlightError("confirmation_required", "Automation cannot decide a remap.");
    if (input.expectedBindingSequence !== this.bindingSequence) throw new SpotlightError("binding_conflict", "The target binding changed; refresh before deciding.");
    safeDigest(input.authorizationDigest, "authorizationDigest");
    const proposal = this.required("remap_proposal", input.remapProposalId);
    if (input.decision === "accept_remap" && proposal.outcome !== "unique_candidate") throw new SpotlightError("spotlight_stale", "Only one exact compatible remap candidate may be accepted.");
    const decisionId = this.id();
    let confirmation: Confirmation | null = null;
    if (input.decision === "accept_remap") {
      const batch = this.required("ocr_evidence_batch", proposal.newBatchId!);
      const automated = this.proposeOcr(batch.recordId, batch.elements.find((element) => element.elementId === proposal.candidateElementIds[0]![0])!.granularity, proposal.candidateElementIds[0]!);
      confirmation = this.confirm({ proposalId: automated.recordId, actorId: input.actorId, actorKind: input.actorKind, authorizationDigest: input.authorizationDigest, expectedBindingSequence: input.expectedBindingSequence, remapProposalId: proposal.recordId, remapDecisionId: decisionId });
    }
    const decision: RemapDecision = { ...recordBase(proposal.projectId, decisionId, this.now().toISOString(), { remapProposalId: proposal.recordId, decision: input.decision, confirmationId: confirmation?.recordId ?? null }), recordType: "remap_decision", remapProposalId: proposal.recordId, decision: input.decision, actorId: input.actorId, expectedBindingSequence: input.expectedBindingSequence, newConfirmationId: confirmation?.recordId ?? null };
    this.repository.append(decision);
    return { decision, confirmation };
  }

  derive(input: { readonly confirmationId: string; readonly parameters?: DerivationParameters }): DerivationRecord {
    const confirmation = this.required("author_confirmation", input.confirmationId);
    const evidence = confirmation.source === "ocr_proposal"
      ? { kind: "confirmed_ocr" as const, captureHash: confirmation.raster.rasterDigest, confirmation: "confirmed" as const, boxes: confirmation.geometry as readonly ({ readonly id: string; readonly granularity: OcrGranularity } & CapturePixelRect)[] }
      : { kind: "manual_geometry" as const, captureHash: confirmation.raster.rasterDigest, confirmation: "confirmed" as const, region: confirmation.geometry as CapturePixelRect };
    const projected = { capture: { hash: confirmation.raster.rasterDigest, width: confirmation.raster.width, height: confirmation.raster.height }, evidence, ...(input.parameters ? { parameters: input.parameters } : {}) };
    const result = deriveSpotlightMatte(projected);
    if (!result.ok) throw new SpotlightError("matte_derivation_failed", result.diagnostics.map(({ code }) => code).join(","));
    const matteReceiptBytes = Buffer.from(result.receiptJson, "utf8");
    const wrapper = { derivationVersion: "vera.spotlight.derivation-wrapper.v1", confirmationId: confirmation.recordId, raster: confirmation.raster, batchId: confirmation.batchId, remapProposalId: confirmation.remapProposalId, remapDecisionId: confirmation.remapDecisionId, projectedInputDigest: digest(projected), parameters: result.receipt.parameters, matteReceiptDigest: `sha256:${createHash("sha256").update(matteReceiptBytes).digest("hex")}`, matteDigest: result.matte.sha256 };
    const recordId = this.id();
    const record: DerivationRecord = { ...recordBase(confirmation.projectId, recordId, this.now().toISOString(), wrapper), recordType: "spotlight_derivation_record", confirmationId: confirmation.recordId, projectedInputDigest: wrapper.projectedInputDigest, matteDigest: result.matte.sha256, matteReceiptDigest: wrapper.matteReceiptDigest, wrapperDigest: digest(wrapper), matteBytes: Buffer.from(result.matte.alpha), matteReceiptBytes };
    this.repository.append(record);
    return record;
  }

  private required<T extends SpotlightRecord["recordType"]>(type: T, id: string): Extract<SpotlightRecord, { readonly recordType: T }> {
    const record = this.repository.get(type, id);
    if (!record) throw new SpotlightError("evidence_not_found", "The immutable evidence record was not found.");
    return record;
  }

  private requiredProposal(id: string): Proposal {
    return this.repository.get("automated_target_proposal", id) ?? this.repository.get("manual_geometry_proposal", id) ?? (() => { throw new SpotlightError("evidence_not_found", "The immutable target proposal was not found."); })();
  }

  private validateRect(rect: CapturePixelRect, raster: RasterRef): void {
    for (const [field, value] of [["x", rect.x], ["y", rect.y], ["width", rect.width], ["height", rect.height]] as const) integer(value, field);
    if (rect.x < 0 || rect.y < 0 || rect.width < 1 || rect.height < 1 || rect.x + rect.width > raster.width || rect.y + rect.height > raster.height) throw new SpotlightError("invalid_geometry", "Manual geometry must be a positive, wholly in-bounds rectangle.");
  }
}
