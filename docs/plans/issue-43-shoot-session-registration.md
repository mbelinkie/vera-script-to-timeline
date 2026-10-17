# Issue 43 plan — immutable shoot-session and master registration

## Status and approval gate

The Producer approved the paired contract-change note on 2026-09-09, including
the `unconfigured` media-library state. The shared boundary is new: the
existing contracts do not serialize a shoot session, source master,
media-library strategy, or handoff inventory.

## Scope

Implement a small local registration library that:

1. creates a named shoot session bound to an already frozen prompter-export
   identity and its beat-map identity;
2. registers one or more explicitly authorized local master files by SHA-256,
   running a read-only ffprobe inspection before a usable source is published;
3. records either an authorized project-local library identifier or an explicit
   no-library state, while keeping absolute library paths in a local-only
   configuration surface;
4. returns only root-relative locators and safe display names in shared project
   records, verifies candidate bytes before append-only relink evidence is
   added, and creates a non-media handoff inventory; and
5. lets a future local worker request a resolved master only through a
   project-and-source-scoped job capability.

## Exclusions

No proxy, waveform, transcription, take, review UI, cloud storage/sharing,
automatic copying or moving, multi-camera switching, conform, Resolve relink,
or source-media mutation. Tests create their own synthetic byte files in
temporary directories and only read, rename, or move them as their test setup.

## Contract and fixture boundary

The proposed additive `shoot-registration/v1` schema is documented in
`issue-43-shoot-registration-contract-change-note.md`. It would be added to
the contract generator and regenerate TypeScript and Python types. Existing
contracts, fixtures, and accepted goldens stay byte-identical. New tests own
their temporary synthetic masters; no committed media fixture is necessary.

## Dependency justification

No new runtime dependency is proposed. Node built-ins provide hashing, path
validation, and file reads; an injected read-only probe runner permits real
ffprobe use while making tests deterministic.

## Automated acceptance

Before implementation, add focused tests proving multi-source frozen binding,
idempotency, pre-publication failure, absolute-path exclusion, handoff
inventory sanitization, verified rename/move/second-library relink, wrong-byte
refusal, and job scope. Then run the focused suite and `npm run validate`.

## Producer review after automated completion

Use only dedicated test media: register a multi-file shoot; inspect hash and
probe facts; confirm project and handoff records contain no absolute paths;
rename/move a master; scan a byte-identical copy in a second authorized local
library; and verify that a different-byte candidate is rejected. This does not
close the Automated issue; it is a retained safety check requested by #43.
