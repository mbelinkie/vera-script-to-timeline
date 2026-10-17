# Initial Claude review disposition

Separate read-only Claude CLI review completed exit 0 on candidate `4bf02e0`,
2026-10-15T22:31:51Z–22:37:33Z. Raw prompt, report and result are retained here.
The report is usable and **NO-GO**; no waiver was requested or inferred.

- **B1, migration recovery:** reproduced with new failing tests for missing,
  incompatible and corrupt old template packages. Split private revision
  history verification (address, closed content, advertised hash, snapshot
  binding/semantic equality) from public full evidence resolution. Refresh and
  migration verify the history and fully verify the proposed revision. A
  migration preserves source/badge/derivation identities, so candidate checks
  still require their bytes and the exact compatible target package. Repeat
  and ordinary resolution retain all old evidence requirements. Tests also
  refuse missing target/source evidence and a corrupt prior content hash.
- **Related refresh recovery:** reproduced loss of old source bytes. Explicit
  refresh can now verify replacement source evidence while retaining exact
  prior content/P identities in its receipt. Missing new evidence still blocks.
- **S1, unsafe integer parameters:** reproduced acceptance in deterministic
  content and v1 compilation. Both the core JSON validator and compiler
  inventory preflight now reject unsafe integers before hashing; restored the
  unchanged global v1 unsafe-integer check. No schema or canonicalizer changed.
  Core tests preserve safe-integer/fraction support; both compiler versions
  refuse positive/negative unsafe integer parameters.
- **N3, v2 direct coverage:** added missing/unused snapshot and snapshot/content
  template/semantic mismatch cases to the owned v2 refusal matrix.
- **N1:** unknown nested-format wrappers remain outside the closed injected
  record type and refuse resolution. Durable ID allocation remains #64's
  responsibility; no new format or runtime support is inferred.
- **N2:** historical pre-#218 package dependencies remain readable. New manual/
  derived provenance formats are explicitly refused by the package adapter
  until its separately owned evidence inventory/hash adapter exists.
- **N4:** retain the exact approved mediaType wire contract. Tightening it is
  outside this approved contract change; no new contract decision is needed
  to implement the accepted behavior.

The corrected regression tests first failed in six cases (35 unchanged cases
passed). Focused tests passed after the fixes. Fresh fast validation, a Claude
delta review and final full acceptance remain required; this is not a GO.
