## Outcome

Triage and resolve the three dependency advisories reported by the existing
locked npm toolchain during #131's clean bootstrap, without unrelated upgrades.

Tentative routing: Terra/high. Acceptance authority: Automated.

## Confirmed evidence

September 30, 2026: `npm ci --ignore-scripts` reported three high-severity
vulnerabilities; read-only `npm audit --json` exited 1. `npm ls` located:

- `brace-expansion@5.0.9` under ESLint/minimatch: recursion/expansion denial of
  service; GHSA-q2hr-2g5m-vwhr, GHSA-qhr7-859c-m2p7, GHSA-6j4f-fj2g-mc7p.
- `fast-uri@3.1.6` under AJV: URI authority/host parsing issues;
  GHSA-qw65-cvwx-89v3, GHSA-58mr-gqgx-xq4g, GHSA-hrr3-gc8f-f4qj.
- `js-yaml@4.3.1` under json-schema-to-typescript/ref-parser: merge CPU denial
  of service; GHSA-2883-xcg3-v3hh.

This is dependency-scanner evidence, not proof of an exploitable VERA runtime
path. #131's full validation passes; no dependency or lock changed there.

## Scope

Trace affected entry points, determine exposure, and make the smallest reviewed
lock/dependency change needed for patched transitive versions. Do not run an
unreviewed broad `npm audit fix` or alter frozen contracts/goldens to accommodate
a tooling change. Retain generated-type and compiler-byte compatibility checks.

## Acceptance criteria

- [ ] Each listed advisory has a confirmed affected path and a patched locked
  resolution or explicit evidence-backed non-applicability disposition.
- [ ] A clean pinned-runtime install and `npm audit --json` reproduce the final
  disposition; new advisories are reported separately rather than hidden.
- [ ] Full `npm run validate`, generated-type checks, frozen compiler goldens
  and `git diff --check` pass; lock changes are explained and bounded.
- [ ] No unrelated upgrade, frozen input amendment or production data change.

## Dependencies

None

## Exclusions

No reconciliation changes, major toolchain migration, general security audit,
external deployment or dispatch. Inbox proposal only.

## Unresolved decisions

Whether patched transitive resolutions suffice within existing direct package
constraints; whether any exposed URI/YAML/glob input needs a separately scoped
trust-boundary fix. Determine from actual callers, not scanner severity alone.

## Duplicate audit

Open/closed issue inventory and semantic advisory/vulnerability/dependency
search found no current issue covering these locked npm advisories.
