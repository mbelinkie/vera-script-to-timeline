# Claude review dispositions — #166

Initial candidate `fd8e5e65f97fd252549b591d81f43b3c0feff530`.
Read-only separate CLI review: exit 0, usable NO-GO, 147.9 seconds.
[Prompt](claude-prompt.md), [candidate diff](candidate.patch),
[result](claude-result.json), [command/exit](claude-exit.json).
Only public accepted/main source and synthetic examples were in the isolated
packet; tools were Read/Grep/Glob, no shell/network/MCP/private inputs.

| Finding | Disposition |
| --- | --- |
| B1 v2 missing content can silently become legacy | Fixed proposal: mandatory `graphicContentClass` on each graphic-source media resolution, no default; missing class/content blocks. Only positively identified legacy storage may resolve as `legacy_unclassified`; manual/derived require exact matching content. Compiler checks class/content/pointer. Resolver trust is explicit. Added migration/default effects and acceptance tests; v1 writer-omission residual is named for Producer judgment. |
| B2 revision ID type rejects #20 IDs | Fixed to exact accepted #7 `^[A-Za-z0-9_-]+$` pattern. `projectId` remains the document UUID; internal #20 handles are not substituted. |
| M1 unused/contradictory records | Added `GRAPHIC_PROVENANCE_UNEXPECTED`; unused/duplicate snapshot/content records refuse; manual forbids snapshot pointer. |
| M2 byte versus canonical hash ambiguity | Source `contentHash` explicitly hashes retained exact bytes. Synthetic canonical JSON file is an extract; equality to canonical-object hash only follows from writing those exact bytes. |
| M3 diagnostic schema scope | Applied to v1 only: existing code pattern accepts vocabulary. Checked main v2 `DiagnosticCodeV2` at lines 393–420: it is an enum, so retained explicit proposed enum additions there. The review's generalization to v2 was not supported by the actual main schema. |
| M4 owner placeholder | Created #218 in Inbox after open/closed duplicate audit; exact reference and retained body added. No dispatch/claim. |
| M5 policy wording | Cross-referenced the every-ticket rule in the older risk-proportionate-review paragraph. Qualified cloud section unchanged. |

The fix delta receives a separate read-only Claude review before final checks.
No runtime, shared contract, generated output, fixture, golden or accepted test
changed to resolve these findings.
