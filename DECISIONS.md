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

## Pending producer decisions

| ID | Status | Decision needed | Known constraint / evidence required |
| --- | --- | --- | --- |
| D-P001 | Pending producer | Primary local-agent OS | Local inspection detected macOS 15.1 build 24B83 on x86_64, but detection is not producer approval of the supported primary environment. |
| D-P002 | Pending producer | Exact Resolve Studio installation to test; retain or refine the tested Free baseline | The producer accepted Slice 0.3 after testing Resolve Free 21 from the Blackmagic download on the detected default-path bundle (21.0.4, build 21.0.40005). No Studio installation is currently available, so the Studio target, connected executable identity, and successful external connection remain unresolved. |

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
