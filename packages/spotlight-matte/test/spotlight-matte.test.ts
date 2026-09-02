import { describe, expect, it } from "vitest";

import {
  deriveSpotlightMatte,
  type ConfirmedOcrEvidence,
  type DerivationInput,
} from "../src/spotlight-matte.js";

const CAPTURE_HASH = `sha256:${"a".repeat(64)}`;
const DIFFERENT_CAPTURE_HASH = `sha256:${"b".repeat(64)}`;

const OCR_INPUT: DerivationInput & { evidence: ConfirmedOcrEvidence } = {
  capture: { hash: CAPTURE_HASH, width: 8, height: 6 },
  evidence: {
    kind: "confirmed_ocr",
    captureHash: CAPTURE_HASH,
    confirmation: "confirmed",
    boxes: [
      { id: "word-second", granularity: "word", x: 4, y: 3, width: 2, height: 2 },
      { id: "line-first", granularity: "line", x: 1, y: 1, width: 2, height: 1 },
    ],
  },
  parameters: { dimAlpha: 191, paddingPx: 0 },
};

const OCR_ALPHA_GOLDEN = Uint8Array.from([
  191, 191, 191, 191, 191, 191, 191, 191,
  191, 0, 0, 191, 191, 191, 191, 191,
  191, 191, 191, 191, 191, 191, 191, 191,
  191, 191, 191, 191, 0, 0, 191, 191,
  191, 191, 191, 191, 0, 0, 191, 191,
  191, 191, 191, 191, 191, 191, 191, 191,
]);

const OCR_RECEIPT_GOLDEN = `{
  "captureHash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "derivationVersion": "vera.spotlight-matte.alpha8.v1",
  "dimensions": {
    "height": 6,
    "width": 8
  },
  "geometry": {
    "boxes": [
      {
        "granularity": "line",
        "height": 1,
        "id": "line-first",
        "width": 2,
        "x": 1,
        "y": 1
      },
      {
        "granularity": "word",
        "height": 2,
        "id": "word-second",
        "width": 2,
        "x": 4,
        "y": 3
      }
    ],
    "kind": "confirmed_ocr"
  },
  "matte": {
    "format": "alpha8-inverse-v1",
    "height": 6,
    "width": 8
  },
  "matteSha256": "sha256:517293353440e0b868ac119635a965456124cebec3ce300fe51a7765c8c278c0",
  "parameters": {
    "dimAlpha": 191,
    "paddingPx": 0
  },
  "source": {
    "boxIds": [
      "line-first",
      "word-second"
    ],
    "kind": "confirmed_ocr"
  }
}
`;

function expectSuccess(input: DerivationInput) {
  const result = deriveSpotlightMatte(input);
  expect(result.ok).toBe(true);
  if (!result.ok) throw new Error(result.diagnostics.map((item) => item.code).join(", "));
  return result;
}

describe("Issue 29 deterministic confirmed-text Spotlight matte", () => {
  it("produces byte-identical alpha and receipt goldens for confirmed OCR evidence", () => {
    const first = expectSuccess(OCR_INPUT);
    const second = expectSuccess({
      ...OCR_INPUT,
      evidence: { ...OCR_INPUT.evidence, boxes: [...OCR_INPUT.evidence.boxes].reverse() },
    });

    expect(first.matte.alpha).toEqual(OCR_ALPHA_GOLDEN);
    expect(first.matte.alpha).toEqual(second.matte.alpha);
    expect(first.receiptJson).toBe(OCR_RECEIPT_GOLDEN);
    expect(first.receiptJson).toBe(second.receiptJson);
    expect(first.receipt.matteSha256).toBe(first.matte.sha256);
  });

  it("keeps confirmed OCR text bright and dims outside pixels in the synthetic preview", () => {
    const result = expectSuccess(OCR_INPUT);
    const composite = (alpha: number): number => 255 - alpha;

    expect(composite(result.matte.alpha[1 + 1 * 8]!)).toBe(255);
    expect(composite(result.matte.alpha[0]!)).toBe(64);
    expect(result.receipt.source).toEqual({ kind: "confirmed_ocr", boxIds: ["line-first", "word-second"] });
  });

  it("uses confirmed manual geometry as the deterministic fallback", () => {
    const result = expectSuccess({
      capture: { hash: CAPTURE_HASH, width: 5, height: 4 },
      evidence: {
        kind: "manual_geometry",
        captureHash: CAPTURE_HASH,
        confirmation: "confirmed",
        region: { x: 1, y: 1, width: 2, height: 2 },
      },
      parameters: { dimAlpha: 191, paddingPx: 0 },
    });
    const composite = (alpha: number): number => 255 - alpha;

    expect([...result.matte.alpha]).toEqual([
      191, 191, 191, 191, 191,
      191, 0, 0, 191, 191,
      191, 0, 0, 191, 191,
      191, 191, 191, 191, 191,
    ]);
    expect(composite(result.matte.alpha[1 + 1 * 5]!)).toBe(255);
    expect(composite(result.matte.alpha[0]!)).toBe(64);
    expect(result.receipt.source).toEqual({
      kind: "manual_geometry",
      region: { height: 2, width: 2, x: 1, y: 1 },
    });
  });

  it("clamps bounded derivation parameters while recording the effective values", () => {
    const result = expectSuccess({
      ...OCR_INPUT,
      parameters: { dimAlpha: 999, paddingPx: 999 },
    });

    expect(result.receipt.parameters).toEqual({ dimAlpha: 255, paddingPx: 64 });
  });

  it("rejects malformed or out-of-bounds geometry without producing an artifact", () => {
    const malformed = deriveSpotlightMatte({
      ...OCR_INPUT,
      evidence: {
        ...OCR_INPUT.evidence,
        boxes: [{ id: "bad", granularity: "word", x: 1.5, y: 1, width: 2, height: 1 }],
      },
    });
    const outOfBounds = deriveSpotlightMatte({
      ...OCR_INPUT,
      evidence: {
        ...OCR_INPUT.evidence,
        boxes: [{ id: "outside", granularity: "word", x: 7, y: 1, width: 2, height: 1 }],
      },
    });

    expect(malformed).toEqual({ ok: false, diagnostics: [expect.objectContaining({ code: "GEOMETRY_INVALID" })] });
    expect(outOfBounds).toEqual({ ok: false, diagnostics: [expect.objectContaining({ code: "GEOMETRY_OUT_OF_BOUNDS" })] });
    expect("matte" in malformed).toBe(false);
    expect("receipt" in outOfBounds).toBe(false);
  });

  it("rejects stale or changed capture evidence without producing an artifact", () => {
    const stale = deriveSpotlightMatte({
      ...OCR_INPUT,
      evidence: { ...OCR_INPUT.evidence, confirmation: "stale" },
    });
    const mismatched = deriveSpotlightMatte({
      ...OCR_INPUT,
      capture: { ...OCR_INPUT.capture, hash: DIFFERENT_CAPTURE_HASH },
    });

    expect(stale).toEqual({ ok: false, diagnostics: [expect.objectContaining({ code: "EVIDENCE_NOT_CONFIRMED" })] });
    expect(mismatched).toEqual({ ok: false, diagnostics: [expect.objectContaining({ code: "CAPTURE_HASH_MISMATCH" })] });
    expect("matte" in stale).toBe(false);
    expect("receipt" in mismatched).toBe(false);
  });
});
