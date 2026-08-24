import { describe, expect, it } from "vitest";

import { toolingPackageName } from "../src/index.js";

describe("tooling package", () => {
  it("can be imported by the TypeScript test runner", () => {
    expect(toolingPackageName()).toBe("@vera/tooling-smoke");
  });
});
