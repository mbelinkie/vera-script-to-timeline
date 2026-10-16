# Approved #8 graph-persistence normalization

Producer approved this exact bounded proposal on 2026-10-15 with “I accept”
in the owning implementation chat. This authorizes the repair and its checks,
not native execution on a new target or final External acceptance of #8.

**Numeric-type amendment approved.** Producer said “yes correct” on 2026-10-15
to correcting only the badge exception to the exact captured float `0.0`,
while retaining rejection of integer `0`, booleans and every other change.
This supersedes the mistaken integer-only form, not the other guardrails.
New native execution and final External acceptance remain separate gates.

Replaying
the actual immutable witnesses after the first implementation revealed that
the captured BadgeImage Value is a Python/JSON floating-point `0.0`, not the
integer `0` described in this approved proposal. The original diagnostic's
dictionary equality accepted `0.0 == 0`, masking this distinction; its actual
reverse replay copied the original float and therefore still restored the
original hash. The three flag values really are integers. The approved
integer-only implementation passed its synthetic tests but FAILED the actual
native-witness replay. That failed candidate is not a verified repair.

The bounded exception, as corrected by the approved amendment, accepts
only the exact captured floating-point `0.0` form at that same BadgeImage path,
instead of integer `0`; keep integer `0`, booleans, nonzero values, different
flags/types, additional keys and every other graph change visible. Signed
negative zero remains distinct too. No native run or installation change
is authorized by this amendment; required local verification may proceed.

## Evidence and diagnosis

The first standard64 and explicitly authorized second overrides64 diagnostic
both failed exact raw SaveSettings fingerprint persistence on Studio21.1.1/10.
The second run captured the exact table at each original production hash call,
one native read per call, with the original helper unchanged. Its native result
remains verification_failed; neither target is accepted or to be repaired.

Private evidence index:
`out/issue8/native-evidence/overrides-64-diagnostic/diagnostic-index-afea48e7c67e43119f56cae84e1654f1.json`,
SHA256 `80a3a1a8078d02586cbe6b6687755a5ef9632036d1a55216231017f03f8e1100`.
Result SHA256 `35495b2327b3990305045bd46d2a63bf0fddf030a7cf38905712af080ad02733`.
Both witnesses independently match their retained SHA256 and actual production
hash. Before0a40e879... differs from reopened8a344048....

An exhaustive recursive diff found exactly four changes under
`Tools/EV24LowerThird/Tools`:

| Path | Before save | After reopen |
| --- | --- | --- |
| ControlHub/UserControls/Country/__flags | absent | integer256 |
| ControlHub/UserControls/__flags | absent | integer3145984 |
| Metrics/UserControls/__flags | absent | integer3145984 |
| RibbonUnit/Inputs | exact BadgeImage input described below | absent |

The removed input is exactly
`{"BadgeImage":{"Value":0.0,"__ctor":"Input","__flags":256}}`.
The original proposal incorrectly wrote integer0; the approved amendment
corrects that type without adding integer0 as another accepted form.
The pinned authored source has a nested BadgeImage InstanceInput declaration
pointing to BadgeOverride/ClipName; the immediate imported serialization has
already represented it as the zero-valued Input above. No other captured
field references BadgeImage. The actual exposed BadgeOverride control instead
points directly to BadgeOverride/Clip, and that mapping, underlying empty
Loader, group output, all expressions, connections, controls, values and every
other serialized setting are identical before/after. Custom badge placement
remains explicitly deferred/rejected by #8; this does not qualify that flow.

Offline replay reverses only these four exact changes and obtains complete
table equality plus the original production hash. Log
`out/issue8/graph-exact-diff-replay.log`, SHA256
`b6b69b5bd092a7e55c96757590b96319503dc110c28dcebc874aed0b8c4c09be`.
This proves the exact source of this hash mismatch, not visual/render parity
or general harmlessness of every future serialized field change.

## Approved bounded verification change

Normalize only the four exact known representations above for this pinned
EV24 graph. Treat absent flags and only those exact integer flag values as
equivalent at those exact paths. Treat the one exact float0.0 BadgeImage
input shape and absence as equivalent. Unexpected types/values, any additional
field/input/connection, or any other graph change remain detectable; do not
remove arbitrary __flags, UserControls, Inputs, ViewInfo or badge data.
Retain Lua-key collision rejection, missing/type-incompatible control refusal,
semantic/use/source/asset/track/range checks, actual stored fingerprint equality,
and the strict version, full-envelope, per-stage and current-target guards.
No authored template, asset, shared contract/generated type, accepted test,
fixture or golden changes. No new dependency. Do not relax #3's external
runtime qualification or imply this native result accepted21.1.1/10.

This is explicitly a graph-verification policy adjustment, not permission to
ignore a failed check. The approval above authorizes this narrow implementation.
The considered alternative was to retain byte-for-byte raw serialization
identity and investigate a native serialization-stabilization route, without
waiving any field; that would require new bounded runtime evidence.

## Impact and verification after approval

New fingerprint/runtime release identity invalidates reuse of the old installed
release/requests as the repaired candidate. Preserve all prior releases,
requests, results and both partial targets. Do not rerun or modify them.
New native qualification uses fresh unique explicitly authorized targets.

Test-first new issue-owned regressions must replay the captured pattern,
prove equality only for the exact four forms, and reject changed/noninteger
flag values, nonzero/boolean/integer/negative-zero BadgeImage values,
additional input fields,
source connections, different nodes/paths, expression changes, semantic drift,
and ambiguous Lua keys. Preserve all accepted assertions and frozen boundaries.
Then focused/fast checks, adversarial Claude delta review, fixes/review as
needed and a fresh durable full gate under the existing serial-test policy.
Actual new native64/120matrix, reopen persistence, assets/badge pixels,
renders/visual judgment and changed-build isolation remain mandatory.

Approved scope: the #8 narrow graph-persistence normalization in this note;
preserve every other graph and native verification check.
