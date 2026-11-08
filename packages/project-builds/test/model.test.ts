import { randomUUID } from "node:crypto";

import { describe, expect, it } from "vitest";

import { buildIntentFingerprint, BuildInputRefusal, parseBuildIntent } from "../src/model.js";

const DIGEST = "sha256:" + "a".repeat(64);
function good() {
  return {
    buildClass: "preview",
    mode: "free",
    expectedRevision: 0,
    expectedDigest: DIGEST,
    idempotencyKey: randomUUID(),
    selectedSources: [],
    render: false,
    delivery: false,
  };
}

describe("strict frozen build intent (input only; never authority)", () => {
  it("accepts bounded Free Preview and Studio Release without requesting effects", () => {
    expect(parseBuildIntent(good())).toMatchObject({
      buildClass: "preview", mode: "free", selectedSources: [],
      render: false, delivery: false,
    });
    expect(parseBuildIntent({ ...good(), mode: "studio", buildClass: "release" }))
      .toMatchObject({ buildClass: "release", mode: "studio" });
  });

  it("refuses extra/missing fields, caller roles, commands, paths and delivery", () => {
    const base = good();
    const invalid: unknown[] = [
      {}, null, [], "preview", 3, { ...base, role: "Producer" },
      { ...base, path: "/Users/someone/Media" },
      { ...base, command: "build" },
      { ...base, render: true }, { ...base, delivery: true },
      { ...base, render: undefined }, { ...base, mode: "cloud" },
      { ...base, buildClass: "publish" },
      { ...base, selectedSources: {}, },
      { ...base, selectedSources: Array.from({ length: 257 }, () => ({})) },
      Object.assign(Object.create({ role: "admin" }) as object, base),
      { ...base, [Symbol("secret")]: true },
    ];
    for (const input of invalid) expect(() => parseBuildIntent(input)).toThrow(BuildInputRefusal);
  });

  it("requires exact lowercase storage digests, safe revision and UUID request identity", () => {
    const base = good();
    for (const expectedDigest of ["a".repeat(64), "sha256:" + "A".repeat(64), DIGEST + "0", ""]) {
      expect(() => parseBuildIntent({ ...base, expectedDigest })).toThrow(BuildInputRefusal);
    }
    for (const expectedRevision of [-1, 0.5, Number.NaN, Number.POSITIVE_INFINITY,
      Number.MAX_SAFE_INTEGER + 1, "0"]) {
      expect(() => parseBuildIntent({ ...base, expectedRevision })).toThrow(BuildInputRefusal);
    }
    for (const idempotencyKey of ["", "not-uuid", "/tmp/build", 7]) {
      expect(() => parseBuildIntent({ ...base, idempotencyKey })).toThrow(BuildInputRefusal);
    }
  });

  it("refuses duplicate source identities, unbounded/unverified pin structures and path injection", () => {
    const base = good();
    const sourceId = randomUUID();
    const pin = { sourceId, revision: "accepted-3", sha256: DIGEST };
    expect(parseBuildIntent({ ...base, selectedSources: [pin] }).selectedSources).toEqual([pin]);
    const invalid: unknown[] = [
      [{ ...pin, path: "/tmp/secret" }],
      [{ ...pin, sha256: "a".repeat(64) }],
      [{ ...pin, revision: "" }],
      [{ ...pin, revision: " bad " }],
      [{ ...pin, revision: "a".repeat(257) }],
      [{ ...pin, revision: "a\nb" }],
      [{ ...pin, revision: "../etc/passwd" }],
      [{ ...pin, sourceId: "source:fake" }],
      [{ ...pin, sourceId: randomUUID(), sha256: "sha256:" + "A".repeat(64) }],
      [pin, { ...pin, sourceId: sourceId.toUpperCase() }],
    ];
    for (const selectedSources of invalid) {
      expect(() => parseBuildIntent({ ...base, selectedSources })).toThrow(BuildInputRefusal);
    }
  });

  it("normalizes source-set ordering and UUID case for stable request fingerprints", () => {
    const base = good();
    const one = { sourceId: randomUUID(), revision: "1", sha256: DIGEST };
    const two = { sourceId: randomUUID(), revision: "2", sha256: DIGEST };
    const first = parseBuildIntent({ ...base, selectedSources: [one, two] });
    const reordered = parseBuildIntent({
      ...base,
      idempotencyKey: base.idempotencyKey.toUpperCase(),
      selectedSources: [{ ...two, sourceId: two.sourceId.toUpperCase() }, one],
    });
    expect(buildIntentFingerprint(first)).toBe(buildIntentFingerprint(reordered));
    expect(first.selectedSources).toEqual(reordered.selectedSources);
    expect(() => { (first.selectedSources as unknown[]).push(one); }).toThrow();
    expect(() => buildIntentFingerprint({ ...first, selectedSources: [one, one] })).toThrow();
    expect(buildIntentFingerprint(first)).not.toBe(
      buildIntentFingerprint(parseBuildIntent({ ...base, selectedSources: [one] })),
    );
  });
});
