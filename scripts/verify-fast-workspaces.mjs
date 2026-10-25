import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const missingFastScript = readdirSync("packages", { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .map((entry) => join("packages", entry.name, "package.json"))
  .filter((path) => {
    try {
      const { scripts = {} } = JSON.parse(readFileSync(path, "utf8"));
      return scripts.test && !scripts["test:fast"];
    } catch {
      return false;
    }
  });

if (missingFastScript.length > 0) {
  throw new Error(
    `Workspace tests need an explicit test:fast script: ${missingFastScript.join(", ")}`,
  );
}
