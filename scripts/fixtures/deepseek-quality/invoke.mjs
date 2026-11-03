import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const fail = (code) => {
  process.stdout.write(JSON.stringify({ error: code }) + "\n");
  process.exitCode = 2;
};

const strictJsonValue = (value, seen = new Set()) => {
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "boolean"
  ) {
    return true;
  }
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value !== "object" || seen.has(value)) return false;
  seen.add(value);
  if (Array.isArray(value)) {
    const valid = value.every((item) => strictJsonValue(item, seen));
    seen.delete(value);
    return valid;
  }
  if (
    Object.getPrototypeOf(value) !== Object.prototype &&
    Object.getPrototypeOf(value) !== null
  ) {
    seen.delete(value);
    return false;
  }
  if (Object.getOwnPropertySymbols(value).length !== 0) {
    seen.delete(value);
    return false;
  }
  const valid = Object.keys(value).every((key) =>
    strictJsonValue(value[key], seen),
  );
  seen.delete(value);
  return valid;
};

const args = process.argv.slice(2);
if (args.length !== 2) {
  fail("invalid_arguments");
} else {
  let inputs;
  try {
    inputs = JSON.parse(readFileSync(args[0], "utf8"));
  } catch {
    fail("invalid_input_json");
  }
  if (process.exitCode !== 2) {
    if (!Array.isArray(inputs)) {
      fail("inputs_must_be_array");
    } else {
      let solve;
      try {
        ({ solve } = await import(pathToFileURL(args[1]).href));
      } catch {
        fail("target_load_failed");
      }
      if (process.exitCode !== 2) {
        const suppressed = () => true;
        const original = {
          stdout: process.stdout.write,
          stderr: process.stderr.write,
          log: console.log,
          error: console.error,
          warn: console.warn,
        };
        process.stdout.write = suppressed;
        process.stderr.write = suppressed;
        console.log = suppressed;
        console.error = suppressed;
        console.warn = suppressed;
        let outputs;
        let solveFailed = false;
        try {
          outputs = inputs.map((payload) => solve(payload));
        } catch {
          solveFailed = true;
        } finally {
          process.stdout.write = original.stdout;
          process.stderr.write = original.stderr;
          console.log = original.log;
          console.error = original.error;
          console.warn = original.warn;
        }
        if (solveFailed) {
          fail("solve_failed");
        } else {
          try {
            if (!strictJsonValue(outputs)) {
              fail("output_not_json");
            } else {
              process.stdout.write(JSON.stringify(outputs) + "\n");
            }
          } catch {
            fail("output_not_json");
          }
        }
      }
    }
  }
}
