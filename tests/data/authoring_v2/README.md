# Synthetic compiler v2 fixtures

These three closed JSON samples exercise the v2 dependency, timeline-manifest,
and build-report roots. Every identifier, digest, source record, and locator is
synthetic; the samples do not refer to production media or research data.
The [source/tool/profile descriptor](source-tool-profile.json) pins the exact
synthetic hashes used by the dependency sample and is not external verification.

The dependency sample includes token timing, an occurrence-specific frame map,
and a verified preparation binding. Its presenter-alignment array is empty;
schema tests cover the versioned slot/take identity, source frame, precision,
and expected/recognized word records. Word agreement remains semantic
validation. The manifest sample serializes source,
event, composition, duration, boundary, and unplaced-item evidence. The report
sample includes blocked readiness, typed recovery, source sufficiency,
migration diagnostics, and representable cross-record mismatch evidence.

The TypeScript test mutates copies to cover missing and unsafe bindings,
invalid preparation mode and report status. It also validates each occurrence
owner, event kind, duration basis, support-item disposition, migration issue,
diagnostic-evidence, recovery-action, and compiler-result variant. These checks
validate shape only. They do not detect stale references, mismatched hashes,
unreduced fractions, mapping disagreement, or occurrence-set mismatch; those
remain serialized runtime diagnostics for later compiler slices. The refused
compiler result is separate from the BuildReport root, and no migration
candidate, lineage, or activation record is represented.
