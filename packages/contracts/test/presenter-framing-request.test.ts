import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { canonicalJson, sha256CanonicalJson } from "../src/compiler-core.js";
import type { ShootRegistrationProjectV1 } from "../src/generated/contracts.js";
import { presenterFramingProfileHash, type PresenterFramingProfileSnapshot } from "../src/presenter-framing.js";
import { createPresenterFramingRequest, type PresenterFramingRequestInput } from "../src/presenter-framing-request.js";
import { addShootSession, createShootRegistrationProject } from "../src/shoot-registration.js";
import { validShootRegistration } from "./samples.js";

function request(): PresenterFramingRequestInput {
  const profile = JSON.parse(readFileSync(new URL("./fixtures/presenter-framing/profile.json", import.meta.url), "utf8")) as PresenterFramingProfileSnapshot;
  const sample = structuredClone(validShootRegistration);
  const sampleSession = sample.sessions[0]!;
  const sampleSource = sampleSession.sources[0]!;
  const registration: ShootRegistrationProjectV1 = addShootSession(
    createShootRegistrationProject(sample.projectId, { kind: "project_local", libraryId: sample.mediaLibrary.libraryId }),
    sampleSession,
  );
  registration.sessions[0]!.sources.push({ ...sampleSource, authorization: "authorized_local", status: "ready",
    inspection: { ...sampleSource.inspection, videoStreams: [sampleSource.inspection.videoStreams[0]!] } });
  const session = registration.sessions[0]!;
  const source = session.sources[0]!;
  source.inspection.durationMs = 60000;
  source.inspection.videoStreams[0] = { ...source.inspection.videoStreams[0],
    width: profile.context.sourceRaster.width, height: profile.context.sourceRaster.height,
    frameRate: `${profile.context.sourceRaster.frameRate.numerator}/${profile.context.sourceRaster.frameRate.denominator}`,
  };
  const hash = `sha256:${"d".repeat(64)}`;
  const rate = profile.context.timelineRaster.frameRate;
  const sampleRate = 48000;
  const intervals = [
      { eventId: "first", framingKey: "wide", recordStart: 0, recordEnd: 75, sourceStart: 1000, sourceEnd: 1075, visible: true },
      { eventId: "covered", framingKey: "wide", recordStart: 75, recordEnd: 150, sourceStart: 1075, sourceEnd: 1150, visible: false },
      { eventId: "return", framingKey: "tight", recordStart: 150, recordEnd: 250, sourceStart: 1150, sourceEnd: 1250, visible: true },
  ] satisfies PresenterFramingRequestInput["intervals"];
  return { registration, sessionId: session.id, sourceId: source.id, profile, observedContext: structuredClone(profile.context),
    mappingEvidence: intervals.map((interval) => mappingFor(registration.projectId, source.id, source.mediaHash, rate, interval.sourceStart, interval.sourceEnd)),
    reviewedColor: { profileHash: hash, reviewEvidenceHash: hash }, intervals,
    dialogue: { eventId: "dialogue", mediaHash: hash, processingProfileHash: hash, synchronizationEvidenceHash: hash,
      recordStart: 0, recordEnd: 250, sourceStartSample: 96000, sourceEndSample: 96000 + 250 * sampleRate * rate.denominator / rate.numerator, sampleRate },
  };
}

function mappingFor(projectId: string, sourceId: string, sourceContentHash: string, sourceRate: unknown, start: number, end: number) {
  return { method: "frame-index-identity/v1", projectId, sourceId, sourceContentHash, sourceRate,
    generationIdentity: "e".repeat(64), sourceProbeHash: `sha256:${"f".repeat(64)}`,
    videoSource: "master", mappingHash: null,
    frameRange: { startInclusive: start, endExclusive: end },
    startBoundary: { sourceFrameIndex: start, reviewFrameIndex: start },
    endBoundary: { sourceFrameIndex: end, reviewFrameIndex: end } };
}

describe("registered synthetic presenter framing requests", () => {
  it("retains covered source time, independent unchanged dialogue and exact grouping labels", () => {
    const input = request();
    const before = canonicalJson(input);
    const built = createPresenterFramingRequest(input);
    expect(built.status).toBe("requested");
    expect(built.masterPolicy).toBe("create_new_protected_master");
    expect(built.intervals.map(({ name, color }) => [name, color])).toEqual([
      ["OC WIDE first", "Blue"], ["OC WIDE covered", "Blue"], ["OC TIGHT return", "Orange"],
    ]);
    expect(built.intervals[2]!.sourceStart).toBe(1150);
    expect(built.dialogue).toEqual(input.dialogue);
    expect(built.requestHash).toBe(sha256CanonicalJson(JSON.parse(built.requestContentJson)));
    expect(canonicalJson(input)).toBe(before);
  });

  it("accepts an exact direct Wide to Tight boundary without restarting the master", () => {
    const input = request();
    input.intervals.splice(1, 1);
    input.mappingEvidence.splice(1, 1);
    input.intervals[0]!.recordEnd = 150;
    input.intervals[0]!.sourceEnd = 1150;
    input.mappingEvidence[0] = mappingFor(input.registration.projectId, input.sourceId, input.registration.sessions[0]!.sources[0]!.mediaHash, (input.profile as PresenterFramingProfileSnapshot).context.sourceRaster.frameRate, 1000, 1150);
    expect(createPresenterFramingRequest(input).intervals[1]!.sourceStart).toBe(1150);
  });

  it("requires the actual mapping handoff for each registered source interval", () => {
    const input = request();
    input.mappingEvidence[1] = { ...(input.mappingEvidence[1] as object), sourceContentHash: `sha256:${"0".repeat(64)}` };
    expect(() => createPresenterFramingRequest(input)).toThrow(/mapping/u);
    const missing = request();
    missing.mappingEvidence = [];
    expect(() => createPresenterFramingRequest(missing)).toThrow(/mapping/u);
    const stale = request();
    stale.mappingEvidence[1] = { ...(stale.mappingEvidence[1] as object), generationIdentity: "a".repeat(64) };
    expect(() => createPresenterFramingRequest(stale)).toThrow(/generation/u);
  });

  it.each(["recordStart", "sourceStart"] as const)("rejects a skipped/repeated %s frame", (key) => {
    const input = request();
    input.intervals[1]![key] += 1;
    expect(() => createPresenterFramingRequest(input)).toThrow();
  });

  it("requires registered matching picture and exact captured context", () => {
    const input = request();
    input.sourceId = "unregistered";
    expect(() => createPresenterFramingRequest(input)).toThrow(/registered/u);
    const mismatched = request();
    mismatched.observedContext = {};
    expect(() => createPresenterFramingRequest(mismatched)).toThrow(/context/u);
  });

  it("refuses absent upstream reviewed-color or synchronization evidence", () => {
    const input = request();
    input.reviewedColor.reviewEvidenceHash = "";
    expect(() => createPresenterFramingRequest(input)).toThrow(/evidence/u);
    const noSync = request();
    noSync.dialogue.synchronizationEvidenceHash = "";
    expect(() => createPresenterFramingRequest(noSync)).toThrow(/evidence/u);
    const embedded = request();
    embedded.dialogue.mediaHash = embedded.registration.sessions[0]!.sources[0]!.mediaHash;
    expect(() => createPresenterFramingRequest(embedded)).toThrow(/independent/u);
  });

  it("refuses retiming and incomplete or duration-shifted dialogue", () => {
    const input = request();
    input.intervals[0]!.sourceEnd += 1;
    expect(() => createPresenterFramingRequest(input)).toThrow(/1:1/u);
    const audio = request();
    audio.dialogue.recordEnd -= 1;
    expect(() => createPresenterFramingRequest(audio)).toThrow(/dialogue/u);
    const shifted = request();
    shifted.dialogue.sourceEndSample += 1;
    expect(() => createPresenterFramingRequest(shifted)).toThrow(/duration/u);
  });

  it("freezes a distinct new request after calibration edits without changing the prior request", () => {
    const input = request();
    const first = createPresenterFramingRequest(input);
    const oldBytes = canonicalJson(first);
    const profile = input.profile as PresenterFramingProfileSnapshot;
    input.profile = { ...profile, version: profile.version + 1,
      tight: { ...profile.tight, Pan: profile.tight.Pan + 1 } };
    const changed = input.profile as PresenterFramingProfileSnapshot;
    input.profile = { ...changed, profileHash: presenterFramingProfileHash(changed) };
    const second = createPresenterFramingRequest(input);
    expect(second.requestHash).not.toBe(first.requestHash);
    expect(canonicalJson(first)).toBe(oldBytes);
    input.dialogue.sourceStartSample += 10;
    expect(canonicalJson(first)).toBe(oldBytes);
  });
});
