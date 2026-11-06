import { randomUUID } from "node:crypto";

import type { ScriptDocumentV2 } from "@vera/contracts/v2";
import { describe, expect, it } from "vitest";

import {
  checkedDocument,
  checkedSettings,
  fingerprint,
  requireRevision,
  requireUuid,
  sha256,
} from "../src/model.js";

function draft(projectId: string): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2",
    id: randomUUID(), projectId, title: "Draft",
    activeDraft: { blocks: [], supportingItems: [] },
    ideaOutline: [], extras: [], liveHeadSequence: 3,
    liveStateVector: "", liveContentHash: "sha256:" + "a".repeat(64),
  };
}

describe("project storage typed boundary", () => {
  it("roundtrips exact accepted authoring fields without advancing collaboration state", () => {
    const projectId = randomUUID();
    const input = draft(projectId);
    const saved = checkedDocument(input, projectId);
    expect(saved.document).toEqual(input);
    expect(saved.digest).toBe(sha256(saved.documentJson));
    expect(saved.document.liveHeadSequence).toBe(3);
    expect(saved.document.liveContentHash).toBe(input.liveContentHash);
    expect(checkedDocument(JSON.parse(saved.documentJson), projectId).digest).toBe(saved.digest);
  });

  it("refuses different identity, schema damage, invalid revision or request key", () => {
    const projectId = randomUUID();
    const input = draft(projectId);
    expect(() => checkedDocument(input, randomUUID())).toThrow();
    expect(() => checkedDocument(input, projectId, randomUUID())).toThrow();
    expect(() => checkedDocument({ ...input, extras: [{}] }, projectId)).toThrow();
    expect(() => checkedDocument({ ...input, unknown: "secret" }, projectId)).toThrow();
    expect(() => requireRevision(Number.MAX_SAFE_INTEGER + 1)).toThrow();
    expect(() => requireUuid("not-an-actor")).toThrow();
  });

  it("validates typed settings while keeping the supplied settingsHash opaque", () => {
    const projectId = randomUUID();
    const settings = {
      schemaVersion: "authoring-project-settings/v1", id: randomUUID(), projectId,
      version: 1, settingsHash: "sha256:" + "b".repeat(64),
    };
    const saved = checkedSettings(settings, projectId);
    expect(saved.settings.settingsHash).toBe(settings.settingsHash);
    expect(saved.digest).toBe(sha256(saved.settingsJson));
    expect(saved.digest).not.toBe(settings.settingsHash);
    expect(() => checkedSettings(settings, randomUUID())).toThrow();
    expect(() => checkedSettings({ ...settings, extra: 1 }, projectId)).toThrow();
    expect(() => checkedSettings({ ...settings, settingsHash: "invalid" }, projectId)).toThrow();
  });

  it("keeps idempotency fingerprint insensitive to field insertion order", () => {
    expect(fingerprint({ a: 2, z: { b: 1, a: 2 } }))
      .toBe(fingerprint({ z: { a: 2, b: 1 }, a: 2 }));
    expect(fingerprint({ a: 1 })).not.toBe(fingerprint({ a: 2 }));
  });
});
