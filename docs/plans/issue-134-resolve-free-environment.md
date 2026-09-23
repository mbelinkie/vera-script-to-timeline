# Issue 134 — provision the isolated Resolve Free environment

## Bounded scope

Provision one Producer-approved, separately booted macOS environment on one
dedicated external SSD, install a compatible Resolve Free release only in that
environment, place every test working location under one external test root,
prove that a disposable project/library reopens, and then prove that the
internal Studio system still opens with its prior projects available.

## Explicit exclusions

- No deletion to create capacity and no use of the internal startup disk as a
  target.
- No erase, format, repartition, macOS installation, Resolve installation, or
  Startup Security Utility change without the Producer present and explicitly
  confirming that exact device or machine-wide action immediately beforehand.
- No same-macOS Free/Studio installation and no VM baseline.
- No Studio data migration, import, opening, relinking, preference reuse, or
  cleanup.
- No #10 baked-graphics test, #36 real-script test, or acceptance claim for
  either issue.

## Contracts, fixtures, and dependencies

No VERA source, contract, generated type, fixture, golden, accepted test, or
product data changes are authorized. The only canonical dependency is #133,
which is closed and Done. Its accepted external-boot recommendation is the
operating basis for this slice.

## Implementation sequence and stop gates

1. Record the current-day, read-only hardware, software, storage, and vendor
   compatibility preflight without retaining serials, personal paths, project
   names, source media, or private screenshots.
2. Stop until the Producer identifies one exact external physical SSD,
   confirms it is disposable, and confirms that erasing that whole device is
   acceptable. Re-identify the device in Disk Utility immediately before any
   erase. A prior general approval is not sufficient.
3. In macOS Recovery, record the current T2 Secure Boot and Allowed Boot Media
   values. If external boot is disallowed, stop until the Producer explicitly
   approves the exact policy change. Preserve the original values for rollback.
4. Prepare only the confirmed external physical device as GUID/APFS and verify
   at least 180 GiB usable after formatting. Stop on any identity or capacity
   discrepancy.
5. Install the Producer-selected compatible macOS only on that external disk,
   create a test-only local user, and decline migration of all existing data.
6. Create one external test root and install the Producer-selected compatible
   Resolve Free release only in the externally booted system.
7. Configure the project/library, media storage, cache/proxy, gallery, render,
   and VERA test locations under that external root. Create and reopen one
   disposable project/library without selecting any Studio location.
8. Shut down, boot the internal system, and have the Producer verify Studio and
   its prior projects. Stop and file a separate Inbox issue on any discrepancy.
9. Retain only the public-safe evidence named in the verification worksheet and
   move #134 to In review. External evidence, not this plan, is the acceptance
   authority.

## Verification

- Review the retained worksheet against every #134 acceptance criterion.
- Verify the worksheet contains no serial, UUID, personal path, project name,
  source-media identity, or private screenshot.
- Verify the final external capacity is at least 180 GiB usable and every
  Resolve working location is inside the one external test root.
- Verify the exact installed macOS and Resolve Free versions are recorded from
  the separately booted environment.
- Verify the internal Studio return check is recorded after the external Free
  baseline succeeds.

## Producer-operated acceptance

The ordered action/check/expected-result script is maintained in
`docs/verification/issue-134-resolve-free-environment.md`. The issue remains in
progress until setup is complete, then remains In review until the required
real-environment evidence is retained. It is never closed by an agent report
alone. After #134 is accepted and Done, issues that must execute in this
environment follow `docs/external-resolve-free-codex-handoff.md`; that procedure
does not authorize #10, #36, or any other issue to start early.
