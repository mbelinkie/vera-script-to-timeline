# CN-218-A1 — bounded #144 compatibility guard (approval requested)

The exact accepted foundation integration `f4df73e` fails TypeScript checking
in isolation, before any #218 feature code. Its accepted #7 source union adds
`FusionTemplateSource`, which deliberately has no media `path`/`contentHash`.
The current-main #144 observation proof and synthetic test helper assume
every non-placeholder source has both fields. Retained proof:
`docs/verification/issue-218/integration-typecheck-blocker.txt` and `.json`.

CN-166-P1 only permits the named `compiler-v2.test.ts` graphic branch to change.
#218 explicitly says any additional frozen test adjustment requires revised
approval. Therefore implementation stops before changing these #144 files.

## Exact proposed exception

In `packages/contracts/src/issue-144-semantics.ts`, immediately after finding
the manifest source in `validateObservation`, add:

```ts
requireFact(source.kind !== "fusion_template", "Fusion graphic observations require a verified adapter");
```

In the accepted synthetic helper
`packages/contracts/test/issue-144-test-inputs.ts`, immediately after finding
the manifest source inside `inputs`'s `manifest.events.map`, add:

```ts
if (source.kind === "fusion_template") throw new Error("Fusion graphic observations require a verified adapter");
```

These two guards narrow the type and refuse unsupported Fusion observations;
they do not synthesize a media path/hash or claim native proof. Existing
accepted test assertions and fixtures/goldens remain unchanged. No new schema,
identifier/hash meaning, renderer, runtime placement or product behavior is
authorized. Do not import #8 code. All original CN-166-P1 constraints remain.

After approval, verify isolated integration typechecking and the existing
#144 observation tests, then continue #218's focused/fast → Claude review/fix →
final full verification flow. Any further frozen exception still stops.

Approval requested: `Approve CN-218-A1 at <commit>`.
