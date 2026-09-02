import { createHash } from "node:crypto";

export const DERIVATION_VERSION = "vera.spotlight-matte.alpha8.v1";
export const MAX_PADDING_PX = 64;
export const MIN_DIM_ALPHA = 1;
export const MAX_DIM_ALPHA = 255;

const MAX_PIXELS = 16_777_216;

export interface CaptureRaster {
  hash: string;
  width: number;
  height: number;
}

export interface CapturePixelRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ConfirmedOcrBox extends CapturePixelRect {
  id: string;
  granularity: "word" | "line";
}

export interface ConfirmedOcrEvidence {
  kind: "confirmed_ocr";
  captureHash: string;
  confirmation: string;
  boxes: readonly ConfirmedOcrBox[];
}

export interface ManualGeometryEvidence {
  kind: "manual_geometry";
  captureHash: string;
  confirmation: string;
  region: CapturePixelRect;
}

export interface DerivationParameters {
  dimAlpha?: number;
  paddingPx?: number;
}

export interface DerivationInput {
  capture: CaptureRaster;
  evidence: ConfirmedOcrEvidence | ManualGeometryEvidence;
  parameters?: DerivationParameters;
}

export interface DerivationDiagnostic {
  code:
    | "CAPTURE_DIMENSIONS_INVALID"
    | "CAPTURE_HASH_INVALID"
    | "CAPTURE_HASH_MISMATCH"
    | "EVIDENCE_EMPTY"
    | "EVIDENCE_NOT_CONFIRMED"
    | "GEOMETRY_INVALID"
    | "GEOMETRY_OUT_OF_BOUNDS"
    | "OCR_BOX_ID_INVALID"
    | "OCR_BOX_KIND_INVALID"
    | "PARAMETER_INVALID";
  message: string;
}

export interface InverseAlphaMatte {
  format: "alpha8-inverse-v1";
  width: number;
  height: number;
  alpha: Uint8Array;
  sha256: string;
}

export interface DerivationReceipt {
  derivationVersion: typeof DERIVATION_VERSION;
  captureHash: string;
  dimensions: { width: number; height: number };
  source:
    | { kind: "confirmed_ocr"; boxIds: string[] }
    | { kind: "manual_geometry"; region: CapturePixelRect };
  geometry:
    | { kind: "confirmed_ocr"; boxes: ConfirmedOcrBox[] }
    | { kind: "manual_geometry"; region: CapturePixelRect };
  parameters: { dimAlpha: number; paddingPx: number };
  matte: { format: InverseAlphaMatte["format"]; width: number; height: number };
  matteSha256: string;
}

export type DerivationResult =
  | { ok: true; matte: InverseAlphaMatte; receipt: DerivationReceipt; receiptJson: string }
  | { ok: false; diagnostics: DerivationDiagnostic[] };

type ValidatedEvidence =
  | { kind: "confirmed_ocr"; boxes: ConfirmedOcrBox[] }
  | { kind: "manual_geometry"; region: CapturePixelRect };

function compareText(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => compareText(left, right))
        .map(([key, nested]) => [key, canonicalize(nested)]),
    );
  }
  if (typeof value === "number" && !Number.isFinite(value)) {
    throw new TypeError("canonical JSON does not allow non-finite numbers");
  }
  return value;
}

function canonicalJson(value: unknown): string {
  return `${JSON.stringify(canonicalize(value), null, 2)}\n`;
}

function failure(code: DerivationDiagnostic["code"], message: string): DerivationResult {
  return { ok: false, diagnostics: [{ code, message }] };
}

function isSafePositiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}

function isSha256(value: unknown): value is string {
  return typeof value === "string" && /^sha256:[a-f0-9]{64}$/.test(value);
}

function validateCapture(capture: CaptureRaster): DerivationResult | undefined {
  if (!isSha256(capture.hash)) {
    return failure("CAPTURE_HASH_INVALID", "capture.hash must be a lowercase sha256 digest");
  }
  if (!isSafePositiveInteger(capture.width) || !isSafePositiveInteger(capture.height) || capture.width * capture.height > MAX_PIXELS) {
    return failure(
      "CAPTURE_DIMENSIONS_INVALID",
      `capture dimensions must be positive safe integers totaling at most ${MAX_PIXELS} pixels`,
    );
  }
  return undefined;
}

function validateRect(rect: CapturePixelRect, capture: CaptureRaster): DerivationDiagnostic | undefined {
  const values = [rect.x, rect.y, rect.width, rect.height];
  if (!values.every((value) => Number.isSafeInteger(value)) || rect.x < 0 || rect.y < 0 || rect.width <= 0 || rect.height <= 0) {
    return {
      code: "GEOMETRY_INVALID",
      message: "geometry must use nonnegative safe-integer origins and positive safe-integer extents",
    };
  }
  if (rect.x + rect.width > capture.width || rect.y + rect.height > capture.height) {
    return {
      code: "GEOMETRY_OUT_OF_BOUNDS",
      message: "geometry must be wholly inside the exact capture dimensions",
    };
  }
  return undefined;
}

function normalizedRect(rect: CapturePixelRect): CapturePixelRect {
  return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
}

function validateEvidence(input: DerivationInput): ValidatedEvidence | DerivationResult {
  const { capture, evidence } = input;
  if (evidence.confirmation !== "confirmed") {
    return failure("EVIDENCE_NOT_CONFIRMED", "evidence must be explicitly confirmed for the exact capture");
  }
  if (!isSha256(evidence.captureHash) || evidence.captureHash !== capture.hash) {
    return failure("CAPTURE_HASH_MISMATCH", "confirmed evidence is stale or belongs to another capture hash");
  }
  if (evidence.kind === "manual_geometry") {
    const diagnostic = validateRect(evidence.region, capture);
    return diagnostic === undefined
      ? { kind: "manual_geometry", region: normalizedRect(evidence.region) }
      : { ok: false, diagnostics: [diagnostic] };
  }
  if (evidence.boxes.length === 0) {
    return failure("EVIDENCE_EMPTY", "confirmed OCR evidence must contain at least one box");
  }
  const ids = new Set<string>();
  const boxes: ConfirmedOcrBox[] = [];
  for (const box of evidence.boxes) {
    if (typeof box.id !== "string" || box.id.length === 0 || ids.has(box.id)) {
      return failure("OCR_BOX_ID_INVALID", "each confirmed OCR box needs one unique nonempty id");
    }
    if (box.granularity !== "word" && box.granularity !== "line") {
      return failure("OCR_BOX_KIND_INVALID", "OCR box granularity must be word or line");
    }
    const diagnostic = validateRect(box, capture);
    if (diagnostic !== undefined) return { ok: false, diagnostics: [diagnostic] };
    ids.add(box.id);
    boxes.push({ ...normalizedRect(box), id: box.id, granularity: box.granularity });
  }
  boxes.sort((left, right) => compareText(left.id, right.id));
  return { kind: "confirmed_ocr", boxes };
}

function validatedParameter(
  value: number | undefined,
  defaultValue: number,
  minimum: number,
  maximum: number,
  label: string,
): number | DerivationResult {
  const effective = value ?? defaultValue;
  if (typeof effective !== "number" || !Number.isSafeInteger(effective)) {
    return failure("PARAMETER_INVALID", `${label} must be a safe integer`);
  }
  return Math.min(maximum, Math.max(minimum, effective));
}

function fillOpening(alpha: Uint8Array, capture: CaptureRaster, rect: CapturePixelRect, paddingPx: number): void {
  const left = Math.max(0, rect.x - paddingPx);
  const top = Math.max(0, rect.y - paddingPx);
  const right = Math.min(capture.width, rect.x + rect.width + paddingPx);
  const bottom = Math.min(capture.height, rect.y + rect.height + paddingPx);
  for (let y = top; y < bottom; y += 1) {
    alpha.fill(0, y * capture.width + left, y * capture.width + right);
  }
}

export function deriveSpotlightMatte(input: DerivationInput): DerivationResult {
  const invalidCapture = validateCapture(input.capture);
  if (invalidCapture !== undefined) return invalidCapture;

  const dimAlpha = validatedParameter(input.parameters?.dimAlpha, 191, MIN_DIM_ALPHA, MAX_DIM_ALPHA, "dimAlpha");
  const paddingPx = validatedParameter(input.parameters?.paddingPx, 0, 0, MAX_PADDING_PX, "paddingPx");
  if (typeof dimAlpha !== "number") return dimAlpha;
  if (typeof paddingPx !== "number") return paddingPx;

  const evidence = validateEvidence(input);
  if ("ok" in evidence) return evidence;
  const alpha = new Uint8Array(input.capture.width * input.capture.height).fill(dimAlpha);
  if (evidence.kind === "confirmed_ocr") {
    for (const box of evidence.boxes) fillOpening(alpha, input.capture, box, paddingPx);
  } else {
    fillOpening(alpha, input.capture, evidence.region, paddingPx);
  }
  const sha256 = `sha256:${createHash("sha256").update(alpha).digest("hex")}`;
  const receipt: DerivationReceipt = {
    derivationVersion: DERIVATION_VERSION,
    captureHash: input.capture.hash,
    dimensions: { width: input.capture.width, height: input.capture.height },
    source: evidence.kind === "confirmed_ocr"
      ? { kind: evidence.kind, boxIds: evidence.boxes.map((box) => box.id) }
      : { kind: evidence.kind, region: evidence.region },
    geometry: evidence.kind === "confirmed_ocr"
      ? { kind: evidence.kind, boxes: evidence.boxes }
      : { kind: evidence.kind, region: evidence.region },
    parameters: { dimAlpha, paddingPx },
    matte: { format: "alpha8-inverse-v1", width: input.capture.width, height: input.capture.height },
    matteSha256: sha256,
  };
  return {
    ok: true,
    matte: { format: "alpha8-inverse-v1", width: input.capture.width, height: input.capture.height, alpha, sha256 },
    receipt,
    receiptJson: canonicalJson(receipt),
  };
}
