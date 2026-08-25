# Decisions

This is the durable decision log for VERA Script to Timeline. Record settled
choices with evidence and impact. Do not convert an unresolved producer choice
into an implementation assumption.

## Status vocabulary

- **Accepted:** binding until a later decision explicitly supersedes it.
- **Pending producer:** intentionally unresolved; dependent work must not guess.
- **Superseded:** retained for history and linked to its replacement.

## Accepted repository defaults

| ID | Status | Decision | Rationale / impact |
| --- | --- | --- | --- |
| D-0001 | Accepted | Use npm workspaces for TypeScript and uv with a root Python package. Runtime, package-manager, and direct tool dependencies are pinned; npm and uv lockfiles are checked in. | Implements Slice 0.1's two-language monorepo and makes fresh-clone installs reproducible without choosing product architecture. |
| D-0002 | Accepted | `npm run validate` is the top-level automated validation entry point, and CI invokes the same command. | Gives later contract and fixture workstreams one regression ratchet to extend. |
| D-0003 | Accepted | CI runs on Ubuntu 24.04, while repository commands must also run on the producer's macOS-compatible local toolchain. | Slice 0.1 explicitly permits Ubuntu CI but requires macOS-compatible code. |
| D-0004 | Accepted | Default channel delivery settings are 23.976 fps, 1920×1080, and 48 kHz. They are configurable project/build settings, not hard-coded invariants. | Approved by the producer on 2026-08-24. Fixtures may use these defaults, while contracts and later compilation/delivery paths must permit explicit alternatives. |
| D-0005 | Accepted | Use the specification section 9.2 track map as the default: V1 presenter/A-roll, V2 research clips, V3 B-roll/stills, V4 graphics/titles, V5 debug/placeholders; A1–A2 narration, A3–A4 source audio, A5 music/SFX; S1 required English subtitles. Track names, IDs, and additional tracks remain adjustable rather than contract invariants. | Approved by the producer on 2026-08-24. Slice 0.2 may emit this default map, while the manifest contract continues to represent track identity, kind, index, and label structurally. |
| D-P005 | Accepted | Park FCPXML rather than maintain it as a product fallback. OTIO remains the maintained interchange path for the tested Resolve Free workflow; the deterministic FCPXML spike remains contingency evidence only. | Approved by the producer on 2026-08-24 after the Slice 0.3 comparison. OTIO imported all five expected linked items and retained the marker. FCPXML required a manual media redirect and omitted the marker, with no compensating advantage observed. |
| D-0006 | Accepted | Use the seven deterministic Slice 1.1 semantic interpretations recorded in `docs/plans/slice-1.1-script-validator.md`: authoritative supplied tokens with UTF-16 offsets; half-open affinity-resolved token intervals; exact quoted-text matching; unique real occurrences in both accepted visual-event storage forms; coverage checks only for active narration; ready full-frame local media or unresolved full-frame placeholders as qualifying VO coverage; and the documented ID-uniqueness scopes. | Approved by the producer on 2026-08-24. These are semantic validator rules, not authorization to change the accepted `ScriptDocument v1` schema. Any discovered structural delta still requires a separate contract-change note and approval. |
| D-0007 | Accepted | Permit provisional Slice 1.1 implementation while Slice 0.4 producer acceptance remains open. | Approved by the producer on 2026-08-24 because Slice 1.1's pure TypeScript validation work has no technical Resolve dependency. This is a bounded sequencing exception, not closure of the Phase 0 gate; Slice 0.4 remains agent-complete and still requires a real Studio run. |
| D-P002 | Accepted | Use the producer-selected default-path Blackmagic installation of DaVinci Resolve Studio 21.0.4 (bundle build 21.0.40005, connected API build 5) as the Slice 0.4 Studio test target; retain the accepted Resolve Free 21 baseline from Slice 0.3. | The producer explicitly authorized the open Studio installation for the one-time Slice 0.4 build on 2026-08-25. Connected identity matched the bundle and receipt, and the final uniquely named project saved, reopened, and passed public-API verification. This is a tested baseline, not evidence of a lower minimum version. |
| D-0008 | Accepted | The orchestrator may accept later slices without a separate producer message when the entire bounded done condition is objectively demonstrated by automated checks, frozen-boundary audits, the documented acceptance procedure, and independent review. It must stop at any done condition requiring manual listening or visual inspection, external authorization or credentials, or other irreducible human judgment. | Delegated explicitly by the producer on 2026-08-25 after accepting Slice 1.1. This changes who may record acceptance for automated-only slices, not the evidence standard, slice boundaries, contract-change controls, or genuinely manual producer gates. |
| D-0009 | Accepted | Use AWS Polly Neural as Slice 1.2's initial cloud `SpeechSynthesisProvider`, with profile `aws-polly-joanna-neural-en-us-v1` (`Joanna`, `neural`, `en-US`, default `us-east-1`). Preserve word/sentence speech marks, record `voiceVersion: provider_not_supplied`, and cache result bytes immutably rather than pretending the managed voice has a frozen vendor revision. | Current comparison on 2026-08-25 found Polly's native word marks, mature SSML/lexicon controls, and $16/M-character Neural rate (per audio or marks request) the best initial fit for later token-anchor compilation. Google requires inserted marks, Azure adds a heavier event SDK, and ElevenLabs' character timing costs materially more with weaker default data controls. The plan records official sources and limitations. |
| D-0010 | Accepted | Exact active narration text may leave the local machine only through the producer-run temporary-narration command; excluded narration never leaves. A live Polly call requires an explicit `opt_out_confirmed` or `provider_terms_accepted` data-policy attestation, prints a dated cost estimate, and stops above a default $1.00 run ceiling unless the producer explicitly raises it. | Applies the specification's recommended Phase 1 cloud-text and cost policy while making AWS's content-improvement terms visible. Agents may implement and test without cloud access but may not infer account opt-out state, authorize terms, or make the first billable call merely because credentials exist. |
| D-0011 | Accepted | Normalize temporary narration with profile `vera-temporary-narration-v1`: measured two-pass FFmpeg loudnorm at -16 LUFS / -1.5 dBTP / LRA 7, explicit mono 48 kHz resampling, and metadata-free 24-bit PCM WAV. Preserve exact sample duration and never proportionally scale timing marks to conceal drift. | The installed FFmpeg/FFprobe 8.1.2 pair exposes the required filters/codecs, and repeated full-filter probes were byte-identical under that fingerprint. The tool fingerprint is part of normalization identity; cross-build byte identity is not claimed. Final mixing and subjective loudness remain producer/editorial judgment. |

## Pending producer decisions

| ID | Status | Decision needed | Known constraint / evidence required |
| --- | --- | --- | --- |
| D-P001 | Pending producer | Primary local-agent OS | Local inspection detected macOS 15.1 build 24B83 on x86_64, but detection is not producer approval of the supported primary environment. |

## Decision record template

```markdown
### D-NNNN — Short title

- Status:
- Date:
- Owner:
- Context:
- Decision:
- Evidence:
- Compatibility / acceptance impact:
- Supersedes / superseded by:
```
