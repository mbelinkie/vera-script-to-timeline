import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { Ajv2020, type AnySchemaObject } from "ajv/dist/2020.js";
import * as formatsModule from "ajv-formats";
import { describe, expect, it } from "vitest";

const repositoryRoot = fileURLToPath(new URL("../../../", import.meta.url));
const documentSchema = JSON.parse(
  readFileSync(`${repositoryRoot}contracts/script-document-v2.schema.json`, "utf8"),
) as AnySchemaObject;
const projectSettingsSchema = JSON.parse(
  readFileSync(
    `${repositoryRoot}contracts/authoring-project-settings-v1.schema.json`,
    "utf8",
  ),
) as AnySchemaObject;

const ajv = new Ajv2020({ allErrors: true, strict: true });
formatsModule.default.default(ajv);
ajv.addSchema(documentSchema);
ajv.addSchema(projectSettingsSchema);

const validateDocument = ajv.getSchema(
  "https://schemas.vera.video/contracts/script-document-v2.schema.json",
)!;
const validateProjectSettings = ajv.getSchema(
  "https://schemas.vera.video/contracts/authoring-project-settings-v1.schema.json",
)!;

const ids = {
  document: "00000000-0000-4000-8000-000000000001",
  project: "00000000-0000-4000-8000-000000000002",
  narration: "00000000-0000-4000-8000-000000000003",
  tokenOne: "00000000-0000-4000-8000-000000000004",
  tokenTwo: "00000000-0000-4000-8000-000000000005",
  sequence: "00000000-0000-4000-8000-000000000006",
  slot: "00000000-0000-4000-8000-000000000007",
  payload: "00000000-0000-4000-8000-000000000008",
  media: "00000000-0000-4000-8000-000000000009",
  artifact: "00000000-0000-4000-8000-000000000010",
  capture: "00000000-0000-4000-8000-000000000011",
  revision: "00000000-0000-4000-8000-000000000012",
  graphic: "00000000-0000-4000-8000-000000000013",
  event: "00000000-0000-4000-8000-000000000014",
  support: "00000000-0000-4000-8000-000000000015",
  secondSupport: "00000000-0000-4000-8000-000000000016",
  settings: "00000000-0000-4000-8000-000000000017",
  annotation: "00000000-0000-4000-8000-000000000018",
  performanceBeat: "00000000-0000-4000-8000-000000000019",
};

const contentHash = `sha256:${"a".repeat(64)}`;
const maxSafeInteger = Number.MAX_SAFE_INTEGER;

function wordAnchor() {
  return {
    blockId: ids.narration,
    tokenId: ids.tokenOne,
    affinity: "before",
    quotedWord: "hello",
    anchorVersion: 1,
  };
}

function textRange() {
  return {
    blockId: ids.narration,
    startTokenId: ids.tokenOne,
    endTokenId: ids.tokenTwo,
    startAffinity: "before",
    endAffinity: "after",
    quotedText: "hello world",
    anchorVersion: 1,
  };
}

function pointAnchor(kind: "word" | "between_blocks" | "event_edge" = "word") {
  if (kind === "word") {
    return { kind, anchor: wordAnchor() };
  }
  if (kind === "between_blocks") {
    return {
      kind,
      beforeBlockId: ids.narration,
      afterBlockId: ids.document,
    };
  }
  return { kind, eventId: ids.event, edge: "start" };
}

function mediaSource() {
  return { kind: "media_reference", mediaReferenceId: ids.media };
}

function narratedVisualPayload(
  pictureKind:
    | "unresolved_visual"
    | "clip"
    | "image"
    | "capture"
    | "graphic"
    | "intentional_placeholder" = "clip",
  audioPolicy: "mute" | "quiet" = "mute",
) {
  const sources = {
    unresolved_visual: { kind: "unresolved_visual", description: "Choose a source" },
    clip: mediaSource(),
    image: mediaSource(),
    capture: {
      kind: "capture_revision",
      captureId: ids.capture,
      revisionId: ids.revision,
    },
    graphic: {
      kind: "graphic_revision",
      graphicId: ids.graphic,
      revisionId: ids.revision,
    },
    intentional_placeholder: {
      kind: "intentional_placeholder",
      text: "Leave this visual blank",
    },
  };
  return {
    kind: "visual",
    payloadId: ids.payload,
    pictureKind,
    source: sources[pictureKind],
    sourceUsage: pictureKind === "clip" ? { sourceInFrame: 0 } : null,
    audioPolicy: pictureKind === "clip" ? audioPolicy : "mute",
    framingPolicy: "contain",
  };
}

function standaloneVisualPayload(
  pictureKind: "clip" | "image" | "capture" | "graphic" | "intentional_placeholder" = "clip",
  audioPolicy: "mute" | "quiet" | "full" = "full",
) {
  const sources = {
    clip: mediaSource(),
    image: mediaSource(),
    capture: {
      kind: "capture_revision",
      captureId: ids.capture,
      revisionId: ids.revision,
    },
    graphic: {
      kind: "graphic_revision",
      graphicId: ids.graphic,
      revisionId: ids.revision,
    },
    intentional_placeholder: {
      kind: "intentional_placeholder",
      text: "Leave this visual blank",
    },
  };
  return {
    kind: "visual",
    payloadId: ids.payload,
    pictureKind,
    source: sources[pictureKind],
    audioPolicy,
    framingPolicy: "contain",
  };
}

function contentSlot(options: {
  relation?: "base" | "sequential" | "cutaway";
  boundaryBefore?: unknown;
  payload?: unknown;
  id?: string;
} = {}) {
  const relationKind = options.relation ?? "base";
  const relation =
    relationKind === "cutaway"
      ? { kind: relationKind, parentSlotId: ids.slot }
      : { kind: relationKind };
  return {
    id: options.id ?? ids.slot,
    kind: "content",
    relation,
    boundaryBefore: options.boundaryBefore ?? { kind: "row_start" },
    payload:
      options.payload ?? { kind: "on_camera", presenterChoiceId: null },
    playoutPolicy: "match_structural_interval",
    version: 1,
  };
}

function primaryVisualSequence(slots: unknown[] = [contentSlot()]) {
  return { id: ids.sequence, slots, version: 1 };
}

function narrationBlock(options: {
  state?: "active" | "excluded";
  omitSequence?: boolean;
  sequence?: unknown;
  overlays?: unknown[];
} = {}) {
  const block: Record<string, unknown> = {
    type: "narration",
    id: ids.narration,
    orderKey: "a0",
    text: "hello world",
    tokens: [
      { id: ids.tokenOne, value: "hello", startOffset: 0, endOffset: 5 },
      { id: ids.tokenTwo, value: "world", startOffset: 6, endOffset: 11 },
    ],
    overlayEvents: options.overlays ?? [],
    timingPolicy: "narration_spine",
    state: options.state ?? "active",
    notes: [],
    version: 1,
  };
  if (options.sequence !== undefined) {
    block.primaryVisualSequence = options.sequence;
  } else if (!options.omitSequence) {
    block.primaryVisualSequence = primaryVisualSequence();
  }
  return block;
}

function documentWithBlock(
  block: unknown = narrationBlock(),
  supportingItems: unknown[] = [],
) {
  return {
    schemaVersion: "script-document/v2",
    id: ids.document,
    projectId: ids.project,
    title: "Synthetic schema sample",
    activeDraft: { blocks: [block], supportingItems },
    ideaOutline: [],
    extras: [],
    liveHeadSequence: 0,
    liveStateVector: "",
    liveContentHash: contentHash,
  };
}

function projectSettings(presenterStill?: unknown) {
  const value: Record<string, unknown> = {
    schemaVersion: "authoring-project-settings/v1",
    id: ids.settings,
    projectId: ids.project,
    version: 1,
    settingsHash: contentHash,
    visualOnlyStillDurationMs: 3000,
  };
  if (presenterStill !== undefined) {
    value.presenterStill = presenterStill;
  }
  return value;
}

function presenterStillReference(
  provenance:
    | { origin: "local_import"; originalFilename: string }
    | {
        origin: "captured_frame";
        sourceMediaReferenceId: string;
        sourceFrame: number;
      } = { origin: "local_import", originalFilename: "presenter.png" },
) {
  return {
    mediaReferenceId: ids.media,
    artifactId: ids.artifact,
    artifactVersion: 1,
    contentHash,
    projectRelativeLocator: "assets/presenter torso.png",
    width: 1920,
    height: 1080,
    provenance,
  };
}

function supportingItem(options: {
  role?:
    | "picture"
    | "audio_cue"
    | "citation"
    | "editor_note"
    | "draft_note"
    | "reference";
  placement?: unknown;
  pictureKind?:
    | "unresolved_visual"
    | "clip"
    | "image"
    | "capture"
    | "graphic"
    | "intentional_placeholder";
  source?: unknown;
  extra?: Record<string, unknown>;
} = {}) {
  const role = options.role ?? "citation";
  const value: Record<string, unknown> = {
    id: ids.support,
    version: 1,
    orderKey: "s0",
    role,
    content: "A retained source note",
    placement: options.placement ?? { kind: "unplaced", reason: "Needs a location" },
  };
  if (role === "picture") {
    value.pictureKind = options.pictureKind ?? "clip";
    value.source = options.source ?? mediaSource();
  } else if (options.source !== undefined) {
    value.source = options.source;
  }
  if (options.extra !== undefined) {
    Object.assign(value, options.extra);
  }
  return value;
}

function visualOnlyBlock(
  pictureKind: "clip" | "image" | "capture" | "graphic" | "intentional_placeholder" = "image",
  timing: Record<string, unknown> = { kind: "visual_only" },
  audioPolicy: "mute" | "quiet" | "full" = "mute",
) {
  return {
    type: "visual_only",
    id: ids.event,
    orderKey: "b0",
    payload: standaloneVisualPayload(pictureKind, audioPolicy),
    visualOnlyTiming: timing,
    version: 1,
  };
}

function setAt(root: unknown, path: (string | number)[], value: unknown): void {
  let current = root;
  for (const segment of path.slice(0, -1)) {
    if (current === null || typeof current !== "object") {
      throw new TypeError("Cannot reach nested schema sample path");
    }
    current = Reflect.get(current, segment);
  }
  const last = path.at(-1);
  if (last === undefined || current === null || typeof current !== "object") {
    throw new TypeError("Cannot set nested schema sample path");
  }
  Reflect.set(current, last, value);
}

function expectDocumentValid(value: unknown): void {
  expect(validateDocument(value), JSON.stringify(validateDocument.errors, null, 2)).toBe(
    true,
  );
}

function expectSettingsValid(value: unknown): void {
  expect(
    validateProjectSettings(value),
    JSON.stringify(validateProjectSettings.errors, null, 2),
  ).toBe(true);
}

function expectDocumentInvalid(value: unknown): void {
  expect(validateDocument(value)).toBe(false);
}

function expectSettingsInvalid(value: unknown): void {
  expect(validateProjectSettings(value)).toBe(false);
}

describe("authoring v2 document and project-settings schemas", () => {
  it("compiles as Draft 2020-12 and accepts representative independent roots", () => {
    expectDocumentValid(documentWithBlock());
    expectSettingsValid(projectSettings(presenterStillReference()));
  });

  it("accepts each structural content-slot, relation, boundary, payload, and return variant", () => {
    const slots = [
      contentSlot({ relation: "base", boundaryBefore: { kind: "row_start" } }),
      contentSlot({
        id: ids.event,
        relation: "sequential",
        boundaryBefore: { kind: "spoken_word", anchor: wordAnchor() },
        payload: { kind: "undefined", payloadId: ids.payload, description: "Unresolved" },
      }),
      contentSlot({
        id: ids.secondSupport,
        relation: "cutaway",
        boundaryBefore: {
          kind: "previous_media_end",
          controllingSlotId: ids.slot,
        },
        payload: {
          kind: "on_camera",
          presenterChoiceId: ids.artifact,
        },
      }),
      {
        id: ids.capture,
        kind: "return",
        parentSlotId: ids.slot,
        inpoint: null,
        version: 1,
      },
    ];
    const block = narrationBlock({ sequence: primaryVisualSequence(slots) });
    expectDocumentValid(documentWithBlock(block));

    const staleAnchor = contentSlot({
      id: ids.capture,
      boundaryBefore: {
        kind: "spoken_word",
        anchor: { ...wordAnchor(), blockId: ids.secondSupport, tokenId: ids.artifact },
      },
    });
    const draftWithStaleAnchor = narrationBlock({
      sequence: primaryVisualSequence([staleAnchor]),
    });
    expectDocumentValid(documentWithBlock(draftWithStaleAnchor));
  });

  it("accepts each narrated pictureKind only with its matching source and audio shape", () => {
    const variants = [
      narratedVisualPayload("clip", "quiet"),
      narratedVisualPayload("image"),
      narratedVisualPayload("capture"),
      narratedVisualPayload("graphic"),
      narratedVisualPayload("unresolved_visual"),
      narratedVisualPayload("intentional_placeholder"),
    ];
    const slotIds = [
      ids.slot,
      ids.event,
      ids.secondSupport,
      ids.capture,
      ids.graphic,
      ids.revision,
    ] as const;
    const slots = variants.map((payload, index) =>
      contentSlot({ id: slotIds[index] ?? ids.slot, payload }),
    );
    expectDocumentValid(
      documentWithBlock(
        narrationBlock({ sequence: primaryVisualSequence(slots) }),
      ),
    );

    const mismatchedImage = structuredClone(narratedVisualPayload("image"));
    Reflect.set(mismatchedImage, "source", {
      kind: "capture_revision",
      captureId: ids.capture,
      revisionId: ids.revision,
    });
    const invalid = documentWithBlock(
      narrationBlock({
        sequence: primaryVisualSequence([contentSlot({ payload: mismatchedImage })]),
      }),
    );
    expectDocumentInvalid(invalid);

    const invalidAudio = documentWithBlock(
      narrationBlock({
        sequence: primaryVisualSequence([
          contentSlot({ payload: narratedVisualPayload("clip", "quiet") }),
        ]),
      }),
    );
    setAt(invalidAudio, ["activeDraft", "blocks", 0, "primaryVisualSequence", "slots", 0, "payload", "audioPolicy"], "full");
    expectDocumentInvalid(invalidAudio);
  });

  it("requires a primary sequence only for active narration and rejects v1 visual surfaces", () => {
    expectDocumentValid(documentWithBlock(narrationBlock({ state: "excluded", omitSequence: true })));
    expectDocumentInvalid(documentWithBlock(narrationBlock({ omitSequence: true })));
    expectDocumentInvalid(documentWithBlock(narrationBlock({ sequence: null })));

    const v1Surfaces = documentWithBlock();
    setAt(v1Surfaces, ["activeDraft", "blocks", 0, "visualEvents"], []);
    setAt(v1Surfaces, ["activeDraft", "blocks", 0, "hostVisibilitySpans"], []);
    expectDocumentInvalid(v1Surfaces);

    const wrongVersion = documentWithBlock();
    setAt(wrongVersion, ["schemaVersion"], "script-document/v1");
    expectDocumentInvalid(wrongVersion);
  });

  it("preserves optional v1 narration annotations and performance beats without accepting null or unknown fields", () => {
    const compatible = documentWithBlock();
    setAt(compatible, ["activeDraft", "blocks", 0, "annotations"], [
      {
        id: ids.annotation,
        kind: "pronunciation_alias",
        range: textRange(),
        value: "Vera",
        includeInPrompter: true,
        version: 1,
      },
      {
        id: ids.secondSupport,
        kind: "pronunciation_phoneme",
        range: textRange(),
        value: "/ˈvɪərə/",
        includeInPrompter: false,
        version: 1,
      },
      {
        id: ids.revision,
        kind: "performance_note",
        range: textRange(),
        value: "Hold the final word",
        includeInPrompter: false,
        version: 1,
      },
    ]);
    setAt(compatible, ["activeDraft", "blocks", 0, "performanceBeats"], [
      { id: ids.performanceBeat, range: textRange(), version: 1 },
    ]);
    expectDocumentValid(compatible);

    const nullAnnotations = structuredClone(compatible);
    setAt(nullAnnotations, ["activeDraft", "blocks", 0, "annotations"], null);
    expectDocumentInvalid(nullAnnotations);
    const nullPerformanceBeats = structuredClone(compatible);
    setAt(nullPerformanceBeats, ["activeDraft", "blocks", 0, "performanceBeats"], null);
    expectDocumentInvalid(nullPerformanceBeats);

    const unknownAnnotation = structuredClone(compatible);
    setAt(
      unknownAnnotation,
      ["activeDraft", "blocks", 0, "annotations", 0, "providerSyntax"],
      "must remain typed metadata",
    );
    expectDocumentInvalid(unknownAnnotation);
    const unknownBeatField = structuredClone(compatible);
    setAt(
      unknownBeatField,
      ["activeDraft", "blocks", 0, "performanceBeats", 0, "takeOrdinal"],
      1,
    );
    expectDocumentInvalid(unknownBeatField);
  });

  it("keeps overlays independent and validates their timing without parent, layer, or ordinal authority", () => {
    const point = pointAnchor();
    const overlay = {
      id: ids.event,
      payload: narratedVisualPayload("clip", "quiet"),
      timing: { kind: "timed", start: point, end: point, durationMs: 20 },
      version: 1,
    };
    expectDocumentValid(documentWithBlock(narrationBlock({ overlays: [overlay] })));

    for (const ownerField of ["parentSlotId", "layer", "ordinal"]) {
      const invalid = documentWithBlock(narrationBlock({ overlays: [overlay] }));
      setAt(invalid, ["activeDraft", "blocks", 0, "overlayEvents", 0, ownerField], 1);
      expectDocumentInvalid(invalid);
    }

    const fullAudioOverlay = documentWithBlock(
      narrationBlock({ overlays: [{ ...overlay, payload: narratedVisualPayload("clip", "quiet") }] }),
    );
    setAt(fullAudioOverlay, ["activeDraft", "blocks", 0, "overlayEvents", 0, "payload", "audioPolicy"], "full");
    expectDocumentInvalid(fullAudioOverlay);
  });

  it("accepts the structural two-of-three timing forms but does not resolve anchor agreement", () => {
    const placements = [
      { kind: "timed", start: pointAnchor(), end: pointAnchor() },
      { kind: "timed", start: pointAnchor("between_blocks"), durationMs: 10 },
      { kind: "timed", end: pointAnchor("event_edge"), durationMs: 20 },
      {
        kind: "timed",
        start: pointAnchor(),
        end: pointAnchor("event_edge"),
        durationMs: 999,
      },
    ];
    for (const placement of placements) {
      expectDocumentValid(
        documentWithBlock(
          narrationBlock(),
          [supportingItem({ role: "audio_cue", placement })],
        ),
      );
    }

    for (const placement of [
      { kind: "timed", start: pointAnchor() },
      { kind: "timed", durationMs: 10 },
      { kind: "timed", start: pointAnchor(), durationMs: 0 },
    ]) {
      expectDocumentInvalid(
        documentWithBlock(
          narrationBlock(),
          [supportingItem({ role: "audio_cue", placement })],
        ),
      );
    }
  });

  it("accepts all typed supporting-item placements and enforces role-specific placement limits", () => {
    const rangePlacement = { kind: "range", range: textRange() };
    const pointPlacement = { kind: "point", anchor: pointAnchor("event_edge") };
    const unplacedWithEvidence = {
      kind: "unplaced",
      reason: "Its old paragraph was removed",
      priorAnchor: textRange(),
      sourceOrderKey: "s-previous",
      neighboringBlockIds: [ids.narration, ids.event],
    };
    const allRoles = [
      supportingItem({ role: "picture", placement: unplacedWithEvidence }),
      supportingItem({ role: "audio_cue", placement: { kind: "timed", start: pointAnchor(), durationMs: 10 } }),
      supportingItem({ role: "citation", placement: rangePlacement }),
      supportingItem({ role: "editor_note", placement: pointPlacement }),
      supportingItem({ role: "draft_note", placement: unplacedWithEvidence }),
      supportingItem({ role: "reference", placement: pointPlacement }),
    ];
    expectDocumentValid(documentWithBlock(narrationBlock(), allRoles));

    const editorRange = documentWithBlock(
      narrationBlock(),
      [supportingItem({ role: "editor_note", placement: rangePlacement })],
    );
    expectDocumentInvalid(editorRange);

    const citationTimed = documentWithBlock(
      narrationBlock(),
      [
        supportingItem({
          role: "citation",
          placement: { kind: "timed", start: pointAnchor(), durationMs: 10 },
        }),
      ],
    );
    expectDocumentInvalid(citationTimed);

    for (const reason of ["", " \t\n "]) {
      const blankReason = documentWithBlock(
        narrationBlock(),
        [supportingItem({ placement: { kind: "unplaced", reason } })],
      );
      expectDocumentInvalid(blankReason);
    }
  });

  it("accepts each picture support subtype only with its matching source identity", () => {
    const pairs = [
      ["clip", mediaSource()],
      ["image", mediaSource()],
      ["capture", { kind: "capture_revision", captureId: ids.capture, revisionId: ids.revision }],
      ["graphic", { kind: "graphic_revision", graphicId: ids.graphic, revisionId: ids.revision }],
      ["unresolved_visual", { kind: "unresolved_visual", description: "Not selected" }],
      ["intentional_placeholder", { kind: "intentional_placeholder", text: "Intentionally empty" }],
    ] as const;
    for (const [pictureKind, source] of pairs) {
      expectDocumentValid(
        documentWithBlock(
          narrationBlock(),
          [supportingItem({ role: "picture", pictureKind, source })],
        ),
      );
    }
    for (const [pictureKind, source] of pairs) {
      const wrongSource =
        source.kind === "media_reference"
          ? {
              kind: "capture_revision",
              captureId: ids.capture,
              revisionId: ids.revision,
            }
          : mediaSource();
      const mismatched = documentWithBlock(
        narrationBlock(),
        [supportingItem({ role: "picture", pictureKind, source: wrongSource })],
      );
      expectDocumentInvalid(mismatched);
    }
    expectDocumentInvalid(
      documentWithBlock(
        narrationBlock(),
        [supportingItem({ role: "citation", extra: { pictureKind: "image" } })],
      ),
    );
  });

  it("applies the distinct visual-only still and clip timing and audio rules", () => {
    for (const pictureKind of ["image", "capture", "graphic", "intentional_placeholder"] as const) {
      expectDocumentValid(
        documentWithBlock(
          visualOnlyBlock(pictureKind, { kind: "visual_only", durationOverrideMs: 3000 }),
        ),
      );
      expectDocumentValid(documentWithBlock(visualOnlyBlock(pictureKind)));
      const rangeOnStill = documentWithBlock(
        visualOnlyBlock(pictureKind, {
          kind: "visual_only",
          selectedSourceRange: { startFrame: 0, durationFrames: 10 },
        }),
      );
      expectDocumentInvalid(rangeOnStill);
    }

    const selectedClip = {
      kind: "visual_only",
      selectedSourceRange: { startFrame: 0, durationFrames: 120 },
    };
    for (const audioPolicy of ["mute", "quiet", "full"] as const) {
      expectDocumentValid(
        documentWithBlock(visualOnlyBlock("clip", selectedClip, audioPolicy)),
      );
    }
    expectDocumentInvalid(
      documentWithBlock(
        visualOnlyBlock("clip", { kind: "visual_only" }, "full"),
      ),
    );
    expectDocumentInvalid(
      documentWithBlock(
        visualOnlyBlock("clip", {
          kind: "visual_only",
          selectedSourceRange: { startFrame: 0, durationFrames: 120 },
          durationOverrideMs: 3000,
        }),
      ),
    );
    expectDocumentInvalid(
      documentWithBlock(
        visualOnlyBlock("clip", {
          kind: "visual_only",
          selectedSourceRange: { startFrame: 0, durationFrames: 0 },
        }),
      ),
    );
    for (const pictureKind of ["image", "capture", "graphic", "intentional_placeholder"] as const) {
      const fullAudioStill = documentWithBlock(
        visualOnlyBlock(pictureKind, { kind: "visual_only" }, "full"),
      );
      expectDocumentInvalid(fullAudioStill);
    }
  });

  it("allows optional project and document settings while rejecting null and unknown settings", () => {
    expectDocumentValid(documentWithBlock());
    expectSettingsValid(projectSettings());
    for (const presenterStill of [
      presenterStillReference(),
      presenterStillReference({
        origin: "captured_frame",
        sourceMediaReferenceId: ids.media,
        sourceFrame: 0,
      }),
    ]) {
      const validOverride = documentWithBlock();
      setAt(validOverride, ["scriptSettings"], {
        presenterStillOverride: presenterStill,
      });
      expectDocumentValid(validOverride);
    }

    const emptyOverrides = documentWithBlock();
    setAt(emptyOverrides, ["scriptSettings"], {});
    expectDocumentValid(emptyOverrides);

    const nullProjectDefault = projectSettings();
    setAt(nullProjectDefault, ["presenterStill"], null);
    expectSettingsInvalid(nullProjectDefault);
    const nullScriptOverride = documentWithBlock();
    setAt(nullScriptOverride, ["scriptSettings"], { presenterStillOverride: null });
    expectDocumentInvalid(nullScriptOverride);
    const nullSettings = documentWithBlock();
    setAt(nullSettings, ["scriptSettings"], null);
    expectDocumentInvalid(nullSettings);

    const unknownOverride = documentWithBlock();
    setAt(unknownOverride, ["scriptSettings"], { futureDefault: "no" });
    expectDocumentInvalid(unknownOverride);
  });

  it("accepts only the two immutable presenter-still provenance variants and project-relative locators", () => {
    expectSettingsValid(projectSettings(presenterStillReference()));
    expectSettingsValid(
      projectSettings(
        presenterStillReference({
          origin: "captured_frame",
          sourceMediaReferenceId: ids.media,
          sourceFrame: 0,
        }),
      ),
    );

    for (const locator of ["/tmp/presenter.png", "../outside.png", "assets/../outside.png", "C:/outside.png", "assets\\presenter.png", "https://example.test/presenter.png"]) {
      const invalid = projectSettings(presenterStillReference());
      setAt(invalid, ["presenterStill", "projectRelativeLocator"], locator);
      expectSettingsInvalid(invalid);
    }

    const inventedProvenance = projectSettings(presenterStillReference());
    setAt(inventedProvenance, ["presenterStill", "provenance"], {
      origin: "remote_upload",
      remoteId: ids.media,
    });
    expectSettingsInvalid(inventedProvenance);

    const extraProvenance = projectSettings(presenterStillReference());
    setAt(extraProvenance, ["presenterStill", "provenance", "downloadUrl"], "https://example.test/p.png");
    expectSettingsInvalid(extraProvenance);
  });

  it("bounds every exercised version, frame, offset, and duration to safe integers", () => {
    const maxedDocument = documentWithBlock(
      narrationBlock({
        sequence: primaryVisualSequence([
          contentSlot({ payload: narratedVisualPayload("clip") }),
        ]),
      }),
    );
    setAt(maxedDocument, ["liveHeadSequence"], maxSafeInteger);
    setAt(maxedDocument, ["activeDraft", "blocks", 0, "version"], maxSafeInteger);
    setAt(maxedDocument, ["activeDraft", "blocks", 0, "tokens", 0, "startOffset"], maxSafeInteger);
    setAt(maxedDocument, ["activeDraft", "blocks", 0, "tokens", 0, "endOffset"], maxSafeInteger);
    expectDocumentValid(maxedDocument);

    for (const [path, tooLarge] of [
      [["liveHeadSequence"], maxSafeInteger + 1],
      [["activeDraft", "blocks", 0, "tokens", 0, "startOffset"], maxSafeInteger + 1],
    ] as const) {
      const invalid = documentWithBlock();
      setAt(invalid, [...path], tooLarge);
      expectDocumentInvalid(invalid);
    }
    const overLimitSourceFrame = documentWithBlock(
      narrationBlock({
        sequence: primaryVisualSequence([
          contentSlot({ payload: narratedVisualPayload("clip") }),
        ]),
      }),
    );
    setAt(
      overLimitSourceFrame,
      ["activeDraft", "blocks", 0, "primaryVisualSequence", "slots", 0, "payload", "sourceUsage", "sourceInFrame"],
      maxSafeInteger + 1,
    );
    expectDocumentInvalid(overLimitSourceFrame);

    const maxedSettings = projectSettings(
      presenterStillReference({
        origin: "captured_frame",
        sourceMediaReferenceId: ids.media,
        sourceFrame: 0,
      }),
    );
    setAt(maxedSettings, ["version"], maxSafeInteger);
    setAt(maxedSettings, ["visualOnlyStillDurationMs"], maxSafeInteger);
    setAt(maxedSettings, ["presenterStill", "artifactVersion"], maxSafeInteger);
    setAt(maxedSettings, ["presenterStill", "width"], maxSafeInteger);
    setAt(maxedSettings, ["presenterStill", "provenance", "sourceFrame"], maxSafeInteger);
    expectSettingsValid(maxedSettings);
    const overLimitSettings = projectSettings();
    setAt(overLimitSettings, ["visualOnlyStillDurationMs"], maxSafeInteger + 1);
    expectSettingsInvalid(overLimitSettings);
  });

  it("rejects unknown fields and schema-version tags at both roots and nested closed objects", () => {
    const unknownDocumentField = documentWithBlock();
    setAt(unknownDocumentField, ["parentId"], ids.project);
    expectDocumentInvalid(unknownDocumentField);
    const unknownSlotField = documentWithBlock();
    setAt(unknownSlotField, ["activeDraft", "blocks", 0, "primaryVisualSequence", "slots", 0, "ordinal"], 1);
    expectDocumentInvalid(unknownSlotField);
    const unknownSettingsField = projectSettings();
    setAt(unknownSettingsField, ["schemaVersion"], "authoring-project-settings/v2");
    expectSettingsInvalid(unknownSettingsField);
  });

  it("keeps both new schema roots outside frozen v1 generated outputs", { timeout: 120_000 }, () => {
    const output = execFileSync(
      process.execPath,
      ["packages/contracts/scripts/generate-contracts.mjs", "--check"],
      { cwd: repositoryRoot, encoding: "utf8" },
    );
    expect(output).toContain("Generated contract types are current.");
  });
});
