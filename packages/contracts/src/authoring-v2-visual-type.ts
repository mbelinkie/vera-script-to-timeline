import type { ContentSlot, NarratedVisualPayloadV2 } from "./generated/contracts-v2.js";
import { sameAuthoringJsonV2 } from "./authoring-v2-json.js";
import type { DroppedVisualDetailV2, VisualTypeChangeV2 } from "./authoring-v2.js";

/**
 * Change type (S03 D93, D100): turn one placed or waiting visual into another
 * type from the + Visual list. The payload keeps its identity, so the slot's
 * words and the comments on it are untouched. Only what the new type cannot
 * hold is dropped, and each loss is returned in plain words.
 *
 * A source is carried over only when the type stays the same. Footage, Still
 * Image, Web Capture and Graphic chosen without a source become an unresolved
 * visual that remembers the chosen type, so the card can keep its label until
 * media is picked.
 */

type VisualPayload = NarratedVisualPayloadV2;
type RetypablePayload = Extract<ContentSlot["payload"], { kind: "visual" | "undefined" }>;
type MediaKind = "clip" | "image" | "capture" | "graphic";
type RetypeTarget = Exclude<VisualTypeChangeV2, { type: "on_camera" }>;

export type RetypeResultV2 =
  | { ok: true; payload: RetypablePayload; dropped: DroppedVisualDetailV2[] }
  | { ok: false; code: string; message: string };

const MEDIA_KIND: Record<"footage" | "still_image" | "web_capture" | "graphic", MediaKind> = {
  footage: "clip", still_image: "image", web_capture: "capture", graphic: "graphic",
};

const TYPE_LABEL: Record<VisualTypeChangeV2["type"], string> = {
  footage: "Footage", on_camera: "On Camera", still_image: "Still Image", web_capture: "Web Capture",
  graphic: "Graphic", onscreen_placeholder: "Onscreen Placeholder", need_to_find: "Need to Find",
  visual_undefined: "Visual Undefined",
};

export function visualTypeLabelV2(type: VisualTypeChangeV2["type"]): string {
  return TYPE_LABEL[type];
}

/** The words a text-only visual carries: placeholder text or a Need to Find note. */
function carriedText(payload: RetypablePayload): string | null {
  if (payload.kind !== "visual") return null;
  if (payload.source.kind === "intentional_placeholder") return payload.source.text;
  if (payload.source.kind === "unresolved_visual") return payload.source.description;
  return null;
}

function describeSource(source: VisualPayload["source"]): string {
  switch (source.kind) {
    case "media_reference": return "The media file was dropped";
    case "capture_revision": return "The web capture was dropped";
    case "graphic_revision": return "The graphic was dropped";
    case "url": return `The link ${source.url} was dropped`;
    case "intentional_placeholder": return `The placeholder text "${source.text}" was dropped`;
    case "unresolved_visual": return `The note "${source.description}" was dropped`;
  }
}

export function retypeVisualPayloadV2(old: RetypablePayload, to: RetypeTarget): RetypeResultV2 {
  const label = TYPE_LABEL[to.type];
  const dropped: DroppedVisualDetailV2[] = [];
  const previous = old.kind === "visual" ? old : null;
  const framingPolicy = previous?.framingPolicy ?? "contain";
  let sourceKept = false;
  let textKept = false;
  let trimKept = false;
  let payload: RetypablePayload;

  if (to.type === "visual_undefined") {
    if (old.kind === "undefined") return unchanged(label);
    payload = { kind: "undefined", payloadId: old.payloadId, description: "No visual has been chosen for these words." };
  } else if (to.type === "onscreen_placeholder" || to.type === "need_to_find") {
    const given = to.type === "onscreen_placeholder" ? to.text : to.description;
    if (given !== undefined && given.trim().length === 0) {
      return { ok: false, code: "CHANGE_TYPE_TEXT_EMPTY", message: `Type some words for the ${label}, or leave them out to keep the current ones.` };
    }
    const carried = carriedText(old);
    const text = given ?? carried ?? label;
    textKept = given === undefined && carried !== null;
    payload = to.type === "onscreen_placeholder"
      ? {
          kind: "visual", payloadId: old.payloadId, pictureKind: "intentional_placeholder",
          source: { kind: "intentional_placeholder", text }, sourceUsage: null, audioPolicy: "mute", framingPolicy,
        }
      : {
          kind: "visual", payloadId: old.payloadId, pictureKind: "unresolved_visual",
          source: { kind: "unresolved_visual", description: text }, sourceUsage: null, audioPolicy: "mute", framingPolicy,
        };
  } else {
    const kind = MEDIA_KIND[to.type];
    const sameKind = previous?.pictureKind === kind;
    if (!to.source && sameKind) return unchanged(label);
    if (!to.source) {
      // Chosen, but nothing picked yet: keep the choice so the card can say what it is waiting for.
      const carried = carriedText(old);
      textKept = carried !== null;
      payload = {
        kind: "visual", payloadId: old.payloadId, pictureKind: "unresolved_visual",
        source: { kind: "unresolved_visual", description: carried ?? `${label} to choose`, wantedPictureKind: kind },
        sourceUsage: null, audioPolicy: "mute", framingPolicy,
      };
    } else if (to.type === "footage") {
      sourceKept = sameKind && sameAuthoringJsonV2(previous.source, to.source);
      const inFrame = to.sourceInFrame ?? (sourceKept ? previous!.sourceUsage?.sourceInFrame : undefined) ?? 0;
      if (!Number.isSafeInteger(inFrame) || inFrame < 0) {
        return { ok: false, code: "CHANGE_TYPE_SOURCE_INVALID", message: "The footage in-point must be a whole frame number, zero or later." };
      }
      // A different in-point on the same file is a new trim, so the old chosen length no longer applies.
      trimKept = sourceKept && inFrame === previous!.sourceUsage?.sourceInFrame;
      payload = {
        kind: "visual", payloadId: old.payloadId, pictureKind: "clip", source: to.source,
        sourceUsage: { sourceInFrame: inFrame }, audioPolicy: previous?.audioPolicy ?? "mute", framingPolicy,
        ...(trimKept && previous!.researchClip ? { researchClip: previous!.researchClip } : {}),
        ...(trimKept && previous!.frameBinding ? { frameBinding: previous!.frameBinding } : {}),
        ...(trimKept && previous!.selectedSourceRange ? { selectedSourceRange: previous!.selectedSourceRange } : {}),
      };
    } else {
      sourceKept = sameKind && sameAuthoringJsonV2(previous.source, to.source);
      payload = {
        kind: "visual", payloadId: old.payloadId, pictureKind: kind, source: to.source,
        sourceUsage: null, audioPolicy: "mute",
        ...(kind !== "image" || previous?.framingPolicy !== undefined ? { framingPolicy } : {}),
        ...(kind === "image" && sourceKept && previous?.researchStill
          ? { researchStill: previous.researchStill } : {}),
        ...(kind === "image" && sourceKept && previous?.researchQuotePicture
          ? { researchQuotePicture: previous.researchQuotePicture } : {}),
      };
    }
  }

  if (previous) {
    const next = payload.kind === "visual" ? payload : null;
    // Still Image, Web Capture and Graphic all support a slow move across the picture; keep it between them.
    const holdsMotion = next !== null && ["image", "capture", "graphic"].includes(next.pictureKind);
    if (previous.imageMotion && holdsMotion) next.imageMotion = previous.imageMotion;
    if (!sourceKept && !textKept) {
      const why = "source" in to && to.source ? "replaced by the new one" : `because ${label} does not use it`;
      dropped.push({ what: "source", message: `${describeSource(previous.source)}, ${why}.` });
    }
    const hadTrim = previous.selectedSourceRange !== undefined || (previous.sourceUsage?.sourceInFrame ?? 0) > 0;
    if (hadTrim && !trimKept) {
      dropped.push({ what: "trim", message: "The trim (in and out points) was dropped with the footage it belonged to." });
    }
    if (previous.researchClip && !next?.researchClip) {
      dropped.push({ what: "research_clip", message: `The link to the logged Research clip "${previous.researchClip.video.title}" was dropped.` });
    }
    if (previous.imageMotion && !next?.imageMotion) {
      dropped.push({ what: "image_motion", message: `The picture's zoom move was dropped, because a ${label} cannot hold one.` });
    }
    if (previous.audioPolicy === "quiet" && next?.audioPolicy !== "quiet") {
      dropped.push({ what: "source_audio", message: "The quiet source sound was dropped, because only footage carries sound." });
    }
  }
  // A name describes this placement of a particular source, not an arbitrary
  // future choice. Keep it through source-preserving retypes (including trims).
  if (sourceKept && previous?.displayName && payload.kind === "visual" &&
    (payload.pictureKind === "clip" || payload.pictureKind === "image")) {
    payload.displayName = previous.displayName;
  }
  if (sameAuthoringJsonV2(payload, old)) return unchanged(label);
  return { ok: true, payload, dropped };
}

function unchanged(label: string): RetypeResultV2 {
  return { ok: false, code: "CHANGE_TYPE_UNCHANGED", message: `This visual is already ${label}; choose a different type or new media.` };
}
