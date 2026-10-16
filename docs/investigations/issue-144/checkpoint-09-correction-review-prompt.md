Review only the checkpoint9 corrections in roundtrip_narration.py and the new
refusal tests in test_issue144_row_narration.py. No edits/commands/provider/native
actions; read-only as before.

1. The entry now rejects isinstance(provider, PollyProvider), including
subclasses, despite synthetic profile labels. A spy subclass test demonstrated
the provider was reached before correction; it must now refuse before any call.
This guards the accepted real provider; explicitly injected test Python code is
trusted, not claimed sandboxed against arbitrary malicious custom providers.
2. Provenance is verified in the accepted synthesis cache, not inferred from
asset fallback profile fields: actual provider/region plus request IDs and
raw audio/input/timing hashes matching the asset record. The empty-provenance
test retains nonempty request IDs and was red before this correction; request
IDs alone would not resolve the missing-provenance bug.
3. The original cache check already included ALL cache_root.parents, including
intermediate components. The new cache-ancestor symlink test passed before any
correction, so the stated cache-path defect was not reproduced. The check is
consolidated to explicitly walk owner/prior/cache roots and every ancestor;
the prior path was also protected by _assert_current before synthesis. Confirm
this disposition; do not claim the review discovered a demonstrated escape.
4. Validator messages now distinguish exit1 refusal from abnormal exit faults.
Fresh-process import check ensures the handoff imports no boto3; Polly import
remains lazy for its SDK. Accepted narration/compiler/fixtures remain unchanged.

Confirm the concrete corrections or name remaining issues. This still proves
only the synthetic handoff; canonical omission/fresh-native integration remains
outstanding. Full validation is running independently on fixed source bytes.
