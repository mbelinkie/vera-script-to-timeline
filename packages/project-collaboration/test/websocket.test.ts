import { describe, expect, it } from "vitest";

import { runDemo } from "../src/demo.js";

describe("collaboration over a real WebSocket", () => {
  it("two scripted people type over each other, go offline, return, and end with the same saved text", async () => {
    const lines: string[] = [];
    const result = await runDemo((line) => { lines.push(line); });
    expect(result.identical).toBe(true);
    expect(result.matthew).toBe(result.writer);
    expect(result.saved).toBe(result.matthew);
    // Everything either person typed and did not undo is present.
    expect(result.saved).toContain("The old harbour is quiet at dawn, before the boats leave.");
    expect(result.saved).not.toContain("Nobody is awake yet.");
    expect(result.saved).not.toContain("and grey");
    expect(result.authors.find((run) => run.text.includes("old"))?.actor).toBe("Matthew");
    expect(result.authors.find((run) => run.text.includes("boats"))?.actor).toBe("Writer");
    expect(lines.at(-1)).toContain("exactly the same text");
  });
});
