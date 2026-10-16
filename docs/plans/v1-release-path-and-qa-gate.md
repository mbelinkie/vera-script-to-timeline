# V1 release path and QA gate

> **Planning guide, not live workflow authority.** The GitHub Project remains
> authoritative for issue status, dependencies, priority, ownership, and
> routing. The Product Spec remains authoritative for product behavior. This
> document records the Producer's V1 framing: get a coherent, useful build in
> front of QA testers before full presenter-footage syncing or reverse timeline
> reconciliation.

## V1 promise

An individual author can move between rebuilt VERA Research discovery and
Script-to-Timeline authoring, then turn a prepared script into a reviewable,
portable Resolve draft without losing evidence behind its visual choices:

1. Discover or reopen authorized Research material through the rebuilt web
   experience, then bring the selected evidence into authoring through its
   approved boundary.
2. Create or open a script project and author its narration and visual
   structure.
3. Capture an authorized public page and select confirmed text for a Spotlight
   highlight.
4. Preview choices and request a controlled build.
5. Receive a deterministic Resolve-compatible draft package or Studio build,
   with retained evidence, readable failures, and an unmodified source.

V1 is a **single-author, local-first QA candidate** spanning both VERA web
experiences. It does not promise cloud collaboration, autonomous editorial
judgment, or full production delivery.

## What belongs in the first tester build

### Core authoring and build route

- A rebuilt, usable Research web experience and its approved handoff into the
  authoring web experience; this is a prerequisite, not a later add-on.
- A durable project document and two-column script editor.
- The minimum required OC/VO ranges, visual events, local media,
  markers/citations, and deterministic prompter export.
- The established local public-page capture and confirmed-text Spotlight path.
- A controlled build request with understandable status and failure states.
- A verified Free import package and, where available, the bounded Studio
  assembly path.
- One representative real script exercised end-to-end through each supported
  delivery mode, with known limitations plainly documented.

### Required engineering route

The production Studio assembly (#34), durable resumable build jobs (#35), and
first real-script conversion/build (#36) make this promise credible. The
accepted capture/OCR/Spotlight work (#39, #41) supplies the visual-evidence
route. The Phase 2 authoring placeholders (#64–#71) must be refined into
bounded slices with accepted design handoffs before they are dispatchable.

Curated Fusion templates are not a release prerequisite unless the board shows
a proven, supported template path. V1 may use the verified fallback/pinned
graphics route, but must not pretend an unverified Fusion template is editable
or portable.

## Designed now; deferred from V1 implementation

| Capability | Design/planning now | Deferred because |
| --- | --- | --- |
| Presenter shoot analysis and take review | #124 designs the transcript-first review/approval flow; #45 and #46 define evidence and approval semantics. | Real speech matching, candidate segmentation, manual approval, and safe trims need more validation than the draft-build loop. |
| Recorded-performance conform to Resolve | #47/#48 retain the later snapshot/build path. | It depends on explicit human take choices and must not turn suggestions into edits. |
| Presenter audio treatment | #52/#121 set the local treatment boundary; #92 implements it later. | It belongs to the deferred shoot/performance path. |
| Timeline-to-script reconciliation | #123 designs the reverse-S05 review experience. | Observation, three-way classification, and preservation of manual Resolve work need a separate technical proof. |
| Transition update/reconciliation | #88 retains transition policy. | Defaults and overrides are protected editorial state; they cannot be silently adopted, dropped, or rebuilt. |
| Collaboration, external sharing, research integration, broad media acquisition, subtitles, music, and regeneration review | Phase 3–10 items remain on the board. | They widen identity, permission, external-service, and review risk beyond local single-author QA. |

## V1 presentation rule for deferred capabilities

Do not expose a control that looks functional but fails later. Until a deferred
workflow exists, either omit it or show a disabled, non-interactive affordance
only when it helps explain the future product; label it plainly, for example:
“Presenter take review arrives after the initial release.” It must never show
false progress or a false status.

An automatically detected take is never a keeper. A timeline-side change is
never silently made canonical in the script. These are product safety rules,
not temporary UI limitations.

## QA-candidate gate

Package for external QA testers only when all of these are true:

1. The live board identifies a bounded V1 set whose dependencies are Done,
   with no unresolved design or contract blocker hidden in prose.
2. A fresh local checkout installs dependencies and passes the documented full
   validation gate.
3. The representative-script route creates the expected package/build twice
   from identical inputs, with retained manifests, hashes, and readable reports.
4. At least one supported Resolve path has real-application evidence: import or
   open, timeline inspection, expected placement, save/reopen, and documented
   edition-specific limitations.
5. The authoring UI has retained 1280x800 and 1024x768 evidence for normal,
   empty, validation-error, unavailable-local-agent, build-progress/failure,
   keyboard-focus, non-color, and overflow states.
6. Capture and Spotlight preserve source provenance and fail closed on an
   unavailable browser/local agent, changed source, unresolved text, or failed
   OCR evidence.
7. No V1 control can start a deferred presenter, timeline-sync, sharing,
   upload, or destructive workflow.
8. A producer-run smoke script succeeds from a clean test project and every
   observed limitation appears in the tester brief.

## Tester brief: first useful feedback loop

Ask a tester to perform only the supported loop:

1. Open a supplied test project and inspect its script/visual structure.
2. Capture or reopen the supplied public-page revision through the authorized
   local flow.
3. Confirm a highlighted text selection and its evidence state.
4. Generate the supported draft package/build.
5. Open it in the documented Resolve edition and compare it with the retained
   build report.
6. Report the first place the application was unclear, lost context, produced
   a wrong result, or failed without a useful recovery instruction.

Do not ask testers to test presenter take approval, external uploads,
collaboration, reverse synchronization, or unverified Fusion-template editing.

## Exit decision

After the first QA round, either harden reproducible V1
authoring/capture/build/Resolve failures and repeat this smoke path, or begin
the presenter-performance path in order: accept #124, then #45, #46,
approved-performance preview, conform snapshot, and recorded timeline build.
Do not treat QA feedback as authorization to broaden the release into a
presenter-sync or reconciliation system without its own accepted design,
contract, and safety evidence.
