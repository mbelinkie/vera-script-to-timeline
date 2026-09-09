import { it } from "vitest";

import { runAcceptance } from "../src/acceptance-cli.js";

it("passes the issue 39 producer synthetic acceptance flow", async () => {
  await runAcceptance();
}, 120_000);
