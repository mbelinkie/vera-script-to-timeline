# #123 accepted reconciliation design

## Acceptance and authority

Matthew Belinkie explicitly accepted this exact candidate with **“Accept #123”**
in Codex task `01a09d7d-49f0-7b12-b003-1163fb7d7959` on September 27, 2026.
This is Producer acceptance of the design artifact, not production behavior.

- Claude working page: **Script to Timeline - Compact Mixed-Change Reconciliation Pilot**.
- Authoritative retained artifact: [r2 standalone export](./Compact%20Mixed-Change%20Reconciliation%20Pilot%20-%20issue%20123%20export%20r2.dc.html).
- Size: **6,546,977 bytes**.
- SHA-256: **b4fae31553a72925315c213260e515f32bc97b289d244905daf815402289fa03**.
- Annotation authority: [reconciliation annotation guide](./reconciliation-annotation-guide.md).
- Evidence and qualifications: [final verification](./final-verification-2026-09-27.md).
- S03 authority remains Producer-accepted #135; this artifact uses a private
  older read-only renderer with local S03 v3 grammar alignment, not a direct
  import of the accepted S03 v3 renderer.

Use this handoff and the annotation guide when implementing #123 or adapting
its comparison grammar for #128. Earlier prompts, the original issue-body
checklist, old harness copy and the failed r1 export are historical evidence,
not competing specifications. Accepted S03/S05 artifacts remain unchanged.

## Superseded requirements

The accepted compact 22-change artifact replaces the original twelve-example
dual-source design. One surface is viewed at a time; Current script is literal
and neutral, Current Resolve shows classified inbound differences. Outcome
selection shows the matching source, or **Script after reconciling** only for
a result matching neither source. Source navigation preserves the outcome.

**Accept Resolve / Keep current script / Defer** replace Accept/Reject/Combine.
Special merge choices and the two independent questions in Change 10 remain.
Sources are not ghosted. One concise rail consequence replaces the old full
Outcome strips. All 22 changes begin Undecided; partial compound decisions
remain Undecided; Defer answers this review while preserving unresolved work.
The old fixed 8/1/2/1 tally and six-update demonstration are superseded by the
22-change interactive decision/count model. Outbound execution and partial
failures belong to #128 and the technical feasibility gate, not this pilot.

## Retained scenario inventory

| Change | Accepted scenario / essential distinction |
| --- | --- |
| 1 | On Camera framing changes Wide to Tight; only changed value emphasized. |
| 2 | Visual-only row added; literal Script has no equivalent row. |
| 3 | Three consecutive rows removed as one atomic change; red struck evidence is inert. |
| 4 | Visual crossing a heading; linked appearances and bounded structural handling. |
| 5 | Three rows moved; both locations and real adjacent context; interiors neutral. |
| 6 | Opaque visual covers B-roll and presenter; hidden alternatives are not deleted. |
| 7 | Music bed added, M1 Low Tide Bed; green new rail and anchors. |
| 8 | B-roll ends earlier; changed endpoint/length, existing revealed presenter neutral. |
| 9 | Bumper over independently rewritten narration; explicit merge outcomes and audio consequences. |
| 10 | Passage move plus B-roll trim; independent location and endpoint decisions, four combinations. |
| 11 | B-roll starts later; changed endpoint/length, unchanged words not green. |
| 12 | Footage replaced at identical anchors; card changes, range does not. |
| 13 | M2 Harbour Close Bed fade-only change; same out-word “coast”, only fade value changes. |
| 14 | Spoken phrase cut and displaced clip start; red cut words, green affected endpoint. |
| 15 | Opaque insert within B-roll; parent → cutaway → compact return, truthful visible intervals. |
| 16 | Transparent lower third over continuously visible On Camera base, partial/full range. |
| 17 | Footage fulfills ranged Need to Find slot; neutral identical anchors, optional open-request hybrid. |
| 18 | Two clips trade fixed narration rows; changed pairings/anchors, not new media or moved VO. |
| 19 | Whole rows swap; words and visuals travel together, neutral interiors. |
| 20 | Quote Graphic over captured image; base remains visible, spoken-word cue. |
| 21 | Graphic bridges two ordinary rows; acceptance combines them, preserving both clips and their cut. |
| 22 | Existing Graphic range changes; only changed endpoint/length green, existing dashed Graphic card. |

## Verification boundary

Producer reviewed the evolving design and accepted r2 after the focused final
checks. Retained checks cover compound outcomes, hybrids, action gating,
source/result navigation and representative music, Graphic, cutaway and swap
mechanisms. The r1 standalone-thumbnail failure is retained; r2 repairs the
image URL guard and was visually verified in independent Chrome at internal
1024 × 768 with actual thumbnails, merged result and keyboard inspection.

This is not a claim of an exhaustive 22-case × settings × outcomes sweep.
Earlier focused viewport checks covered 1280 × 800, 1024 × 768, small/default
text and 0%/default thumbnails. Rapid offscreen pointer activation had misses
of unestablished cause; explicit Enter activation and final counts agreed.

## Engineering and downstream handoff

- The prototype uses fixture-driven detection/mapping and simulated execution.
  Acceptance proves the design direction, not production reconciliation safety.
- The private renderer is patched by exact text substitution; some card-state
  detection still relies on colors. Production must derive annotations from
  classified operations, stable item/slot identities and row/word anchors.
- The r2 image URL guard accepts embedded blob/data URLs. Test actual rendered
  images in retained exports, not just image bytes or an empty console log.
- #131 already owns technical feasibility: identity/anchoring, merges, linked
  appearances, audio cuts, protected work, defer/persistence, missing media,
  safe structural operations and proposed contract impacts. Keep unsupported
  mappings visible and non-destructive; do not silently resolve them in UI.
- #128 owns the S05 successor. Carry over the accepted row/annotation grammar,
  while keeping outbound selection, skipped changes and execution failures
  distinct from inbound Defer and queued corrections.
- #129/#130 own wider project authority/index/naming; this handoff identifies
  #123 authority without renaming or deleting any Claude page.
- Do not copy prototype substitution/color heuristics into production, reopen
  #127/#135 decisions, or infer authorization to change frozen contracts.

No production API, schema, fixture, compiler, generated type, Resolve project
or accepted S01–S05 artifact changed in this closure pass.
