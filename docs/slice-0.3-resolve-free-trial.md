# Slice 0.3 producer runbook and evidence worksheet

This is a manual trial against actual Resolve Free. The generated files are
locally verified inputs; they are not evidence of Resolve import fidelity.
Do not launch Resolve through an agent, automate its UI, or write observations
that the producer did not make.

## Prepare inputs

From a locked repository install, run the Slice 0.3 command in `README.md`.
Keep each interchange file beside its own `media/` directory. In Resolve Free,
create two fresh empty projects/timelines under the same project settings. Use
**File > Import > Timeline** to import OTIO first and FCPXML second. Do not fix
or relink either result until the initial state and evidence are recorded.

## Environment (record before import)

- Date/time and observer: Matt, 2026-08-24 11:10
- OS product/version/build and architecture: macOS 15.1 build 24B83, Intel
  x86_64
- Resolve edition: Free
- Resolve version/build shown inside the application: 21 (producer-observed);
  the installed bundle separately reports version 21.0.4, build 21.0.40005
- Install source (Blackmagic download, App Store, other): Blackmagic download
- Package/receipt evidence locator: installed package receipt
  `com.blackmagic-design.ManifestLite` version 21.0.4; application bundle at
  `/Applications/DaVinci Resolve/DaVinci Resolve.app`
- Trial package path or retained archive:
  `/Users/matthewbelinkie/Documents/ChatGPT/VERA Script to Timeline/out/slice-0.3-free-trial`
- Manifest SHA-256:
  `173e4b4cba80b89ab1f7192d35bd16358ee18b9167bb1e936861a29843c4fff0`
- OTIO SHA-256:
  `13a7c6cfd481c7863d9d0f6d63b9ba959d82acc7acb4e5ea50a5458f2df63a40`
- FCPXML SHA-256:
  `e5821f678eb71c9d9919ed11c526a3f1d1d5623b01f848a238fe4033c4d7f3a2`

Repository-side detection on 2026-08-24 found, but has **not tested**:

- macOS 15.1 build 24B83, x86_64;
- default-path `/Applications/DaVinci Resolve/DaVinci Resolve.app` reporting
  version 21.0.4 and build 21.0.40005;
- matching installed package receipt `com.blackmagic-design.ManifestLite`
  version 21.0.4; and
- no `_MASReceipt` in the application bundle.

Confirm the edition/version/build in Resolve itself before treating these as
the trial environment. Detection is not a capability observation.

## Expected manifest facts

- Timeline: 72 frames at 24000/1001 fps, 1920×1080, 48 kHz.
- Events: 4 picture events on `V3 B-roll / stills` (18 frames each, starting
  at 0/18/36/54) and 1 audio event on `A1 Narration 1` (72 frames at 0).
- Picture source starts: 2, 4, 6, then 0 frames for the still.
- Tracks, in manifest order: V1, V2, V3, V4, V5, A1, A2, A3, A4, A5, S1,
  with their full names in `timeline-manifest.json`.
- One blue `Producer review` marker at frame 33.
- Three zero-duration hard cuts at frames 18, 36, and 54; no transition effect.

## OTIO observation

- Import outcome/error text: imported successfully; no warning or error was
  reported
- Timeline item count and per-item duration/start/source-in: all five expected
  items were present (four picture items and one audio item); no timing
  discrepancy was noticed
- Timeline total duration/rate/resolution/audio rate: no discrepancy was
  noticed
- Track names and top-to-bottom order (include missing/extra tracks): no
  discrepancy was noticed
- Media link status for each of five sources: all five sources were linked; no
  relink issue was reported
- Marker name/frame/note/color: the expected `Producer review` marker was
  present; no marker discrepancy was noticed
- Cuts/transitions at frames 18/36/54: no discrepancy was noticed
- Discrepancies from the expected manifest facts: none observed
- Evidence locators (screenshots, exported timeline, notes/logs): producer
  observation recorded in this worksheet

## FCPXML observation

- Import outcome/error text: Resolve required the producer to redirect the
  import to the packaged media; no other warning or error was reported
- Timeline item count and per-item duration/start/source-in: after redirecting
  the media, all five expected items were present (four picture items and one
  audio item); no timing discrepancy was noticed
- Timeline total duration/rate/resolution/audio rate: no discrepancy was
  noticed
- Track names and top-to-bottom order (include missing/extra tracks): no
  discrepancy was noticed
- Media link status for each of five sources: all five sources were linked
  after the producer manually redirected Resolve to the packaged media
- Marker name/frame/note/color: the expected `Producer review` marker was
  missing
- Cuts/transitions at frames 18/36/54: no discrepancy was noticed
- Discrepancies from the expected manifest facts: the marker was missing and
  initial media linking required a manual redirect
- Evidence locators (screenshots, exported timeline, notes/logs): producer
  observation recorded in this worksheet

## Comparison and exit decision

- Gaps common to both: none observed
- OTIO-only gaps: none observed
- FCPXML-only gaps: expected marker missing; initial media linking required a
  manual redirect to the packaged media
- Does FCPXML close a material OTIO gap? State exact evidence: no. The producer
  observed no advantage over OTIO; FCPXML instead introduced two additional
  import discrepancies.
- Proposed D-P005 outcome: **park FCPXML** (pending explicit producer approval)
- Rationale and compatibility/acceptance impact: OTIO preserved the expected
  marker and linked all five sources without a reported relink issue. FCPXML
  preserved the five timeline items after manual relinking but omitted the
  marker. Parking FCPXML avoids maintaining a second interchange writer that
  did not close an observed OTIO gap. The deterministic spike remains available
  as contingency evidence rather than a supported product path.

After both observations are complete, transfer only objective results and
evidence locators into `CAPABILITIES.md`; resolve D-P001, D-P002, and D-P005 in
`DECISIONS.md`. The producer—not the generated package or agent report—accepts
the slice.
