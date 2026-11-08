/** Assertion helpers used by the opt-in, actual-HTTP development-QA smoke. */
export class QaSmokeRefusal extends Error {
  override readonly name = "QaSmokeRefusal";
  constructor() { super("development-QA smoke verification failed"); }
}

export function requireStatus(actual: number, expected: number): void {
  if (actual !== expected) throw new QaSmokeRefusal();
}

export function requireEqual(actual: unknown, expected: unknown): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new QaSmokeRefusal();
}

export function requireTrue(condition: unknown): asserts condition {
  if (condition !== true) throw new QaSmokeRefusal();
}

/** Restrict the printed evidence to explicitly named checked scenarios. */
export const REQUIRED_CASES = [
  "loopback-auth", "create-replay", "document-cas-replay", "viewer-read-refusal",
  "editor-write-producer-refusal", "producer-settings-title", "editor-revocation",
  "build-freeze-and-replay", "agent-lease-partial",
  "source-restart", "populated-migration", "tampered-archive-refusal",
  "fresh-restore", "existing-restore-refusal", "restored-restart",
] as const;

export function assertCompleteCases(cases: readonly string[]): void {
  if (cases.length !== REQUIRED_CASES.length ||
      new Set(cases).size !== REQUIRED_CASES.length ||
      REQUIRED_CASES.some((name) => !cases.includes(name))) throw new QaSmokeRefusal();
}
