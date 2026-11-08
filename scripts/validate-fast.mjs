import { spawnSync } from "node:child_process";
import { constants } from "node:os";
import { performance } from "node:perf_hooks";

import { runFastPhases } from "./validate-fast-lib.mjs";

const report = runFastPhases({
  run(script) {
    const result = spawnSync("npm", ["run", script], {
      cwd: process.cwd(),
      env: process.env,
      stdio: "inherit",
    });
    if (result.error) {
      console.error(`[validate:fast] npm run ${script}: ${result.error.message}`);
    }
    if (result.status !== null) {
      return result.status;
    }
    if (result.signal && constants.signals[result.signal]) {
      return 128 + constants.signals[result.signal];
    }
    return 1;
  },
  now: () => performance.now(),
  write: (line) => console.log(line),
});

process.exitCode = report.exitCode;
