import { describe, expect, it } from "vitest";

import { assertCompleteCases, QaSmokeRefusal, requireEqual,
  requireStatus, requireTrue, REQUIRED_CASES } from "../src/qa-smoke-checks.js";

describe("real deployment smoke fail-closed checks", () => {
  it("rejects wrong HTTP statuses including unexpected permission grants", () => {
    expect(() => requireStatus(403, 403)).not.toThrow();
    expect(() => requireStatus(200, 403)).toThrow(QaSmokeRefusal);
    expect(() => requireStatus(503, 200)).toThrow(QaSmokeRefusal);
  });

  it("rejects changed persistence snapshots and failed integrity flags", () => {
    requireEqual({ revision: 2, roles: ["producer", "revoked"] },
      { revision: 2, roles: ["producer", "revoked"] });
    expect(() => requireEqual({ revision: 0 }, { revision: 2 })).toThrow(QaSmokeRefusal);
    expect(() => requireTrue(false)).toThrow(QaSmokeRefusal);
    expect(() => requireTrue("yes")).toThrow(QaSmokeRefusal);
  });

  it("cannot report acceptance with an omitted, duplicate or invented case", () => {
    assertCompleteCases([...REQUIRED_CASES]);
    expect(() => assertCompleteCases(REQUIRED_CASES.slice(1))).toThrow(QaSmokeRefusal);
    expect(() => assertCompleteCases([...REQUIRED_CASES.slice(1), REQUIRED_CASES[1]])).toThrow(QaSmokeRefusal);
    expect(() => assertCompleteCases([...REQUIRED_CASES.slice(1), "made-up"])).toThrow(QaSmokeRefusal);
  });
});
