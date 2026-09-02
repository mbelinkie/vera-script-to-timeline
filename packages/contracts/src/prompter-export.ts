import { createHash } from "node:crypto";

import { Ajv2020 } from "ajv/dist/2020.js";
import * as formatsModule from "ajv-formats";

import prompterExportSchema from "../../../contracts/prompter-export-v1.schema.json" with {
  type: "json",
};
import scriptDocumentSchema from "../../../contracts/script-document-v1.schema.json" with {
  type: "json",
};
import type {
  HostVisibilitySpan,
  NarrationAnnotation,
  NarrationBlock,
  PerformanceBeat,
  PrompterExportV1,
  ScriptDocumentV1,
  TextAnchorRange,
} from "./generated/contracts.js";
import {
  type ValidationDiagnostic,
  validateScriptDocument,
} from "./script-validator.ts";

export type PrompterExportSettings = PrompterExportV1["settings"];

export type PrompterExportResult =
  | { ok: false; diagnostics: ValidationDiagnostic[] }
  | {
      ok: true;
      text: string;
      sidecar: PrompterExportV1;
      sidecarJson: string;
      sidecarSha256: string;
    };

interface ResolvedRange {
  start: number;
  end: number;
}

interface ResolvedAnnotation extends ResolvedRange {
  annotation: NarrationAnnotation;
}

interface ResolvedBeat extends ResolvedRange {
  id: string;
}

interface BlockPlan {
  block: NarrationBlock;
  states: Array<HostVisibilitySpan["state"]>;
  annotations: ResolvedAnnotation[];
  beats: ResolvedBeat[];
  navigationCues: string[];
}

const DERIVED_BEAT_NAMESPACE = "a540f252-f01d-5f07-b6a4-88d6f8a02a58";

const ajv = new Ajv2020({ allErrors: true, strict: true });
formatsModule.default.default(ajv);
ajv.addSchema(scriptDocumentSchema);
const validatePrompterSidecar = ajv.compile<PrompterExportV1>(
  prompterExportSchema,
);

/**
 * Create deterministic prompter text and its canonical sidecar without I/O or
 * source-document mutation.
 */
export function exportPrompter(
  input: unknown,
  settings: PrompterExportSettings,
): PrompterExportResult {
  if (
    typeof settings?.includeSectionNavigation !== "boolean" ||
    typeof settings?.includeBeatNumbers !== "boolean" ||
    Object.keys(settings).some((key) => key !== "includeSectionNavigation" && key !== "includeBeatNumbers")
  ) {
    return {
      ok: false,
      diagnostics: [
        {
          code: "PROMPTER_SETTINGS_INVALID",
          message: "Prompter settings require boolean includeSectionNavigation and includeBeatNumbers values.",
          jsonPath: "/settings",
        },
      ],
    };
  }

  const validation = validateScriptDocument(input);
  if (!validation.valid) {
    return { ok: false, diagnostics: validation.diagnostics };
  }
  const document = input as ScriptDocumentV1;
  if (!Number.isSafeInteger(document.liveHeadSequence)) {
    return { ok: false, diagnostics: [{
      code: "PROMPTER_REVISION_INVALID",
      message: "The frozen live-head sequence must be an exactly representable integer.",
      jsonPath: "/liveHeadSequence",
    }] };
  }
  const plans = planBlocks(document, settings);
  const identityDiagnostics: ValidationDiagnostic[] = [];
  const seenIds = new Set<string>();
  for (const plan of plans) {
    for (const [index, beat] of plan.beats.entries()) {
      const id = beat.id.toLowerCase();
      if (seenIds.has(id)) identityDiagnostics.push({
        code: "PERFORMANCE_BEAT_ID_DUPLICATE",
        message: "Explicit and derived performance beats must have distinct UUID identities.",
        jsonPath: `/activeDraft/blocks/${document.activeDraft.blocks.indexOf(plan.block)}/performanceBeats/${index}`,
        blockId: plan.block.id, entityId: beat.id, entityKind: "performance_beat",
      });
      seenIds.add(id);
    }
  }
  if (identityDiagnostics.length > 0) return { ok: false, diagnostics: identityDiagnostics };
  const text = renderText(plans, settings.includeBeatNumbers);
  const sidecar: PrompterExportV1 = {
    schemaVersion: "prompter-export/v1",
    sourceDocument: {
      documentId: document.id,
      projectId: document.projectId,
      liveHeadSequence: document.liveHeadSequence,
      contentHash: document.liveContentHash,
    },
    settings: { ...settings },
    textSha256: sha256(text),
    beats: plans.flatMap((plan) => sidecarBeats(plan)),
  };
  if (!validatePrompterSidecar(sidecar)) {
    throw new Error(
      `Generated prompter sidecar failed its contract: ${JSON.stringify(validatePrompterSidecar.errors ?? [])}`,
    );
  }
  const sidecarJson = canonicalJson(sidecar);
  return {
    ok: true,
    text,
    sidecar,
    sidecarJson,
    sidecarSha256: sha256(sidecarJson),
  };
}

function planBlocks(
  document: ScriptDocumentV1,
  settings: PrompterExportSettings,
): BlockPlan[] {
  const plans: BlockPlan[] = [];
  let pendingSections: string[] = [];
  for (const block of document.activeDraft.blocks) {
    if (block.type === "section") {
      pendingSections.push(block.title);
      continue;
    }
    if (block.type !== "narration" || block.state !== "active") continue;

    const beats =
      (block.performanceBeats?.length ?? 0) > 0
        ? resolveExplicitBeats(block, block.performanceBeats!)
        : deriveSentenceBeats(document, block);
    plans.push({
      block,
      states: resolveVisibility(block),
      annotations: (block.annotations ?? []).map((annotation) => ({
        annotation,
        ...resolveRange(block, annotation.range),
      })),
      beats,
      navigationCues: settings.includeSectionNavigation
        ? pendingSections
        : [],
    });
    pendingSections = [];
  }
  return plans;
}

function resolveExplicitBeats(
  block: NarrationBlock,
  beats: PerformanceBeat[],
): ResolvedBeat[] {
  return beats.map((beat) => ({ id: beat.id, ...resolveRange(block, beat.range) }));
}

function deriveSentenceBeats(
  document: ScriptDocumentV1,
  block: NarrationBlock,
): ResolvedBeat[] {
  const beats: ResolvedBeat[] = [];
  let start = 0;
  for (const [index, token] of block.tokens.entries()) {
    const next = block.tokens[index + 1];
    const endsSentence = next === undefined || isSentenceEnd(block, index);
    if (!endsSentence) continue;

    const first = block.tokens[start]!;
    beats.push({
      id: uuidV5(
        [
          document.id,
          String(document.liveHeadSequence),
          block.id,
          first.id,
          token.id,
        ].join("\u0000"),
      ),
      start,
      end: index + 1,
    });
    start = index + 1;
  }
  return beats;
}

// Frozen, token-aligned sentence rule: no locale/ICU/provider dependency.
// Punctuation may be inside or outside the spoken token. Tokens are atomic;
// explicit authored beats override this default segmentation.
function isSentenceEnd(block: NarrationBlock, index: number): boolean {
  const next = block.tokens[index + 1]!;
  const end = textStart(block, index + 1);
  const prefix = block.text.slice(0, end).trimEnd();
  if (!/[.!?。！？]["'”’\])}]*$/u.test(prefix)) return false;
  // A decimal point inside a number does not end a sentence even when a
  // tokenizer supplied its digits as separate spoken tokens.
  if (/\d\.$/u.test(prefix) && /^\d/u.test(next.value) && !/\s$/u.test(block.text.slice(0, end))) return false;
  if (/(?:\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc)|\b[A-Z]|\be\.g|\bi\.e)\.$/u.test(prefix)) return false;
  return true;
}

function textStart(block: NarrationBlock, tokenIndex: number): number {
  if (tokenIndex === 0) return 0;
  const offset = block.tokens[tokenIndex]!.startOffset;
  const gap = block.text.slice(block.tokens[tokenIndex - 1]!.endOffset, offset);
  const opening = /(?:^|\s)([“‘"([{]+)$/u.exec(gap)?.[1];
  return offset - (opening?.length ?? 0);
}

function resolveRange(
  block: NarrationBlock,
  range: TextAnchorRange,
): ResolvedRange {
  const tokenIndex = new Map(
    block.tokens.map((token, index) => [token.id, index]),
  );
  const startToken = tokenIndex.get(range.startTokenId);
  const endToken = tokenIndex.get(range.endTokenId);
  if (startToken === undefined || endToken === undefined) {
    throw new Error("Validated prompter anchor lost a narration token.");
  }
  return {
    start: startToken + (range.startAffinity === "after" ? 1 : 0),
    end: endToken + (range.endAffinity === "after" ? 1 : 0),
  };
}

function resolveVisibility(
  block: NarrationBlock,
): Array<HostVisibilitySpan["state"]> {
  const states: Array<HostVisibilitySpan["state"] | undefined> = Array.from(
    { length: block.tokens.length },
  );
  for (const span of block.hostVisibilitySpans) {
    const range = resolveRange(block, span.range);
    for (let index = range.start; index < range.end; index += 1) {
      states[index] = span.state;
    }
  }
  if (states.some((state) => state === undefined)) {
    throw new Error("Validated prompter narration lost host visibility.");
  }
  return states as Array<HostVisibilitySpan["state"]>;
}

function sidecarBeats(plan: BlockPlan): PrompterExportV1["beats"] {
  return plan.beats.map((beat, index) => {
    const nextBeat = plan.beats[index + 1];
    const expectedEnd =
      nextBeat === undefined
        ? plan.block.text.length
        : textStart(plan.block, nextBeat.start);
    const beatAnnotations = plan.annotations.filter(
      (annotation) => annotation.start < beat.end && annotation.end > beat.start,
    );
    return {
      id: beat.id,
      expectedText: plan.block.text
        .slice(textStart(plan.block, beat.start), expectedEnd)
        .trim(),
      hostVisibility: plan.states
        .slice(beat.start, beat.end)
        .includes("on_camera")
        ? "on_camera"
        : "voiceover",
      navigationCues: index === 0 ? [...plan.navigationCues] : [],
      annotations: beatAnnotations.map(({ annotation }) => ({
        id: annotation.id,
        kind: annotation.kind,
        value: annotation.value,
        visibleInPrompter: annotation.includeInPrompter,
      })),
    };
  });
}

function renderText(
  plans: readonly BlockPlan[],
  includeBeatNumbers: boolean,
): string {
  let priorState: HostVisibilitySpan["state"] | undefined;
  let beatNumber = 1;
  const renderedBlocks: string[] = [];
  for (const plan of plans) {
    const prefixes = new Map<number, string[]>();
    const initialState = plan.states[0]!;
    const isFirstSpokenBlock = priorState === undefined;

    if (isFirstSpokenBlock) {
      addPrefix(prefixes, 0, stateMarker(initialState));
    }
    for (const navigation of plan.navigationCues) {
      addPrefix(prefixes, 0, `[SECTION: ${escapeCueText(navigation)}]`);
    }

    for (const [index, state] of plan.states.entries()) {
      const previous = index === 0 ? priorState : plan.states[index - 1];
      if (!isFirstSpokenBlock || index > 0) {
        if (state !== previous) addPrefix(prefixes, index, stateMarker(state));
      }
    }
    for (const beat of plan.beats) {
      if (includeBeatNumbers) {
        addPrefix(prefixes, beat.start, `[BEAT ${beatNumber}]`);
      }
      beatNumber += 1;
    }
    for (const { annotation, start } of plan.annotations) {
      if (annotation.includeInPrompter) {
        addPrefix(prefixes, start, annotationCue(annotation));
      }
    }

    let cursor = 0;
    let rendered = "";
    for (const tokenIndex of plan.block.tokens.keys()) {
      const cues = prefixes.get(tokenIndex);
      if (cues === undefined) continue;
      const offset = textStart(plan.block, tokenIndex);
      rendered += plan.block.text.slice(cursor, offset);
      rendered = rendered.replace(/[\t ]+$/u, "");
      if (rendered.length > 0 && !rendered.endsWith("\n")) rendered += "\n";
      rendered += `${cues.join("\n")}\n`;
      cursor = offset;
    }
    rendered += plan.block.text.slice(cursor);
    renderedBlocks.push(rendered.trimEnd());
    priorState = plan.states.at(-1)!;
  }
  return renderedBlocks.length === 0
    ? ""
    : `${renderedBlocks.join("\n\n")}\n`;
}

function addPrefix(
  prefixes: Map<number, string[]>,
  tokenIndex: number,
  value: string,
): void {
  const values = prefixes.get(tokenIndex) ?? [];
  values.push(value);
  prefixes.set(tokenIndex, values);
}

function stateMarker(state: HostVisibilitySpan["state"]): string {
  return state === "on_camera" ? "(OC)" : "(VO)";
}

function annotationCue(annotation: NarrationAnnotation): string {
  if (annotation.kind === "performance_note") {
    return `[PERFORMANCE: ${escapeCueText(annotation.value)}]`;
  }
  const label =
    annotation.kind === "pronunciation_alias"
      ? "PRONUNCIATION"
      : "PHONEME";
  return `[${label}: ${escapeCueText(annotation.range.quotedText)} = ${escapeCueText(annotation.value)}]`;
}

function escapeCueText(value: string): string {
  return value
    .replaceAll("\\", "\\\\")
    .replace(/[\p{Cc}\p{Cf}\u2028\u2029]/gu, (character) => {
      if (character === "\n") return "\\n";
      if (character === "\r") return "\\r";
      if (character === "\t") return "\\t";
      return `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`;
    })
    .replaceAll("]", "\\]");
}

function sha256(value: string): string {
  return `sha256:${createHash("sha256").update(value, "utf8").digest("hex")}`;
}

function canonicalJson(value: unknown): string {
  return `${JSON.stringify(canonicalize(value), null, 2)}\n`;
}

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .toSorted(([left], [right]) => compareText(left, right))
        .map(([key, nested]) => [key, canonicalize(nested)]),
    );
  }
  if (typeof value === "number" && !Number.isFinite(value)) {
    throw new TypeError("canonical JSON does not allow non-finite numbers");
  }
  return value;
}

function compareText(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

function uuidV5(name: string): string {
  const namespace = Buffer.from(DERIVED_BEAT_NAMESPACE.replaceAll("-", ""), "hex");
  const bytes = createHash("sha1")
    .update(namespace)
    .update(name, "utf8")
    .digest()
    .subarray(0, 16);
  bytes[6] = (bytes[6]! & 0x0f) | 0x50;
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;
  const hex = bytes.toString("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
