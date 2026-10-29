import { mkdir, open, readFile, rename, rmdir } from "node:fs/promises";
import { dirname } from "node:path";
import { loadOutbound } from "./selective-outbound.ts";
import type { OutboundAttempt, OutboundStore } from "./selective-outbound.ts";

/** One journal owns one target. An abandoned lock requires inspection, never automatic replay. */
export function outboundFileStore(path: string): OutboundStore {
  let held = false;
  return {
    async exclusive<T>(work: () => Promise<T>): Promise<T> {
      const lock = `${path}.lock`;
      await mkdir(lock);
      held = true;
      try { return await work(); }
      finally { held = false; await rmdir(lock); }
    },
    async load(): Promise<OutboundAttempt> {
      return loadOutbound(await readFile(path, "utf8"));
    },
    async save(attempt: OutboundAttempt): Promise<void> {
      if (!held) throw new Error("Attempt write requires exclusive target ownership");
      const bytes = JSON.stringify(loadOutbound(JSON.stringify(attempt)));
      let prior: OutboundAttempt | null = null;
      try { prior = loadOutbound(await readFile(path, "utf8")); }
      catch (error) {
        if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error;
      }
      if (prior) {
        if (prior.plan.hash !== attempt.plan.hash || prior.outcomes.some((outcome, index) =>
          (outcome.status === "verified" && JSON.stringify(outcome) !== JSON.stringify(attempt.outcomes[index])) ||
          (["uncertain", "failed"].includes(outcome.status) && attempt.outcomes[index]?.status === "unattempted"))) {
          throw new Error("Cannot replace a frozen plan or verified receipt");
        }
        if (prior.completed) {
          if (JSON.stringify(prior) !== bytes) throw new Error("Cannot replace a completed attempt");
          return;
        }
      } else if (attempt.outcomes.some((outcome) => !["unattempted", "skipped", "blocked"].includes(outcome.status))) {
        throw new Error("A new journal must start before native work");
      }
      const temporary = `${path}.next`;
      const file = await open(temporary, "wx", 0o600);
      try { await file.writeFile(bytes); await file.sync(); }
      finally { await file.close(); }
      await rename(temporary, path);
      const directory = await open(dirname(path), "r");
      try { await directory.sync(); }
      finally { await directory.close(); }
    },
  };
}
