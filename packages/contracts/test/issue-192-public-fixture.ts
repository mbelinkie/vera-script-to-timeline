// Test-only numeric specimen producer; never an execution or qualification flag.
import { registerHooks } from "node:module";
const contracts = new URL("../", import.meta.url).href;
const hooks = registerHooks({ resolve(specifier, context, nextResolve) {
  return nextResolve(context.parentURL?.startsWith(contracts) && specifier.startsWith(".") && specifier.endsWith(".js")
    ? specifier.slice(0, -3) + ".ts" : specifier, context);
} });
const { specimen } = await import("./issue-192-case.ts");
hooks.deregister();
process.stdout.write(JSON.stringify(specimen()));
