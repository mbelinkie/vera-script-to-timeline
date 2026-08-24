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

## Pending producer decisions

| ID | Status | Decision needed | Known constraint / evidence required |
| --- | --- | --- | --- |
| D-P001 | Pending producer | Primary local-agent OS | Must be named before dependent Phase 0 work closes; this tooling scaffold does not infer it from the machine used to develop the repository. |
| D-P002 | Pending producer | Exact Resolve Free and Resolve Studio versions/installations to test | Must be recorded from the actual supported desktop installations. |
| D-P004 | Pending producer | Track naming convention | Specification section 9.2 is the stated default, but adoption remains to be confirmed rather than guessed here. |
| D-P005 | Pending producer | Maintain FCPXML as a fallback or park it | Slice 0.3 must decide from recorded OTIO-versus-FCPXML import evidence. |

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
