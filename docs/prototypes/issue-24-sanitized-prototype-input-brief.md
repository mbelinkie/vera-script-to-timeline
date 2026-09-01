# Sanitized Script-to-Timeline prototype input brief

- Source: fictional content created for issue #24
- Intended consumer: a later authorized Claude Design prototype task
- Authority: the Producer-accepted issue #24 coverage decisions
- Token boundary: issue #21 remains the sole visual-token authority

## 1. Purpose

Build one realistic authoring scenario that proves the Script-to-Timeline
interface can represent the accepted content language of a production script
without reproducing private production material or treating two-column rows as
edit boundaries.

This brief is design input, not a `ScriptDocument` fixture, parser fixture,
contract proposal, or authorization to build the prototype.

## 2. Privacy and sanitization rules

- Use only the fictional names, prose, data, and `.invalid` links in this file.
- Do not use the private source title, URL, document identifier, production
  names, factual claims, quotations, participants, or source-specific links.
- Do not place the private source in Claude, screenshots, comments, test data,
  issue text, or design-artifact attachments.
- General layout may resemble a familiar two-column script, but no distinctive
  source wording or ordering may be recreated.
- Absolute local paths are prohibited. A local reference appears only as a
  redacted unresolved label.

## 3. Fictional project frame

Project title: **Harbor Lights Explainer**

Section under review: **Why the Signal Changes**

The section explains a fictional coastal monitoring demonstration. All people,
places, measurements, quotations, and sources are invented.

## 4. Required authoring content

The layout below is a readable presentation sketch. The `Anchor / role` column
is explicit metadata for the prototype; physical row position has no semantic
authority.

| Spoken / performed | Shown / heard / built | Anchor / role |
| --- | --- | --- |
| **Section: Why the Signal Changes** |  | Section block; no duration by itself |
| `[OC] A quiet harbor can still hide a moving pattern.` | Citation: “Coastal Sensor Primer,” `https://source-a.example.invalid/primer` | Citation card; no visual duration |
| `Keep this calm; pause after “harbor.”` |  | Direction plus typed pause/performance annotation; not spoken |
| `[OC] Watch the marker behind me [VO] as the tide turns and the reading begins to drift.` | Visual request: wide harbor footage with source audio muted, then a sensor close-up | One intact narration paragraph; two successive full-frame visual ranges begin inside it |
|  | Candidate A: `https://media-a.example.invalid/harbor`, `00:12–00:19`; Candidate B: `https://media-b.example.invalid/sensor`, `01:03–01:10` | Right-only multiple-candidate visual request; no candidate selected initially |
| `[VO] The instrument calls this the Lunara effect.` | Pronunciation: `Lunara` → `loo-NAH-rah` | Exact text annotation; not a visual and not spoken as an instruction |
| `[VO] The public dashboard shows the same change from another angle.` | Webpage capture: `https://page.example.invalid/dashboard`; capture only the fictional trend panel | Web Capture card with requested region and unresolved immutable-artifact state |
| `[OC] Here is the sensor before the trial began.` | Imported still `asset-demo-still-01`; contain without crop | Durable Local Still card with verified fictional identity separate from its locator |
| `[VO] In one trial, the blue series rises while the amber series holds steady.` | Two-series chart: blue `12, 18, 27`; amber `14, 15, 15`; cite data snapshot `demo-v1` | Derived Graphic card with semantic inputs, source/version, and pinned-template placeholder |
| `[VO] The operator described the change as “slow, then sudden.”` | Logged source clip, selected range `00:24–00:32`; transcript excerpt shown; source audio on | Source Clip card with immutable evidence and occurrence range |
| `[VO] A short chime marks the second reading.` | Music/SFX cue `demo-chime-v1`; start at the anchored phrase; license note fictional | Music/SFX card with pinned fictional revision and explicit cue intent |
| `[OC] That distinction matters because the next step depends on timing.` | Full-screen text: `MEASURE FIRST / ADJUST SECOND` | Long-text Graphic card; overlay/full-frame choice visible |
| `Variant A: [OC] We adjust only after the second reading.` |  | Variant group `closing-line`; selected choice |
| `Variant B: [OC] The second reading tells us when to adjust.` |  | Same variant group; inactive but readable |
| `Variant C: [OC] Timing decides the adjustment.` |  | Same variant group; inactive but readable |
| `[VO] A final comparison confirms the pattern.` | `[possible superseded] Earlier map treatment` plus highlight-review signal | Formatting/superseded review; no automatic exclusion or semantic mapping |
|  | `Add a map somewhere near the comparison.` | Right-only Unplaced Graphic request; original proximity visible, no invented anchor/duration |
|  | Local audio reference: `[unresolved local reference]` | Reference card; requires import/relink before any build use; no absolute path |
|  | Production note: `Check the on-screen units in Resolve.` | Point-anchored Production marker; zero duration |
| `[OC] The result is simple: observe, compare, then act.` |  | Narration-only row; no missing-visual warning because host remains on camera |

## 5. Ideas, Extras, and excluded material

Show these beside the Draft without letting them enter validation, prompter,
voice generation, duration, or build preview:

- Idea: “Explain why the first reading can be misleading.”
- Extra: an unused alternative paragraph with one stale visual reference.
- Excluded draft note: “Verify the fictional units before publication.”
- Superseded fragment awaiting confirmation from the formatting-review state.

## 6. Required interactions and visible states

### 6.1 Anchoring and asymmetry

1. Hovering or focusing a Visual card highlights its exact narration words.
2. Hovering or focusing highlighted words emphasizes the attached card.
3. The continuous OC→VO paragraph remains one paragraph while two picture
   events attach to successive ranges.
4. The right-only candidate row displays an explicit attachment control; its
   legacy vertical position does not create an anchor.
5. The Unplaced map request stays in an Unplaced state until the user chooses a
   range, a point, Extras, or dismissal.

### 6.2 Typed right-lane roles

Citation, Visual request, Source Clip, Graphic, Production marker, Draft note,
and Reference must be distinguishable by visible label, icon, accessible name,
and inspector fields—not color alone. Changing a role must show which fields
and build behavior will change before confirmation.

### 6.3 Variants and candidates

- The `closing-line` group shows exactly one active choice.
- Only the active choice appears in prompter/build preview.
- Inactive choices remain readable and lossless beside the group.
- The source-candidate request may have zero or one selected candidate.
- A release attempt with no selected candidate follows the explicit unresolved
  placeholder/block policy; it never chooses the first URL.

### 6.4 Formatting review

- Highlight, color, bold, italic, underline, and strikethrough appear as
  preserved source formatting plus review signals.
- No formatting cue silently assigns OC/VO, role, status, ownership, active
  Draft membership, build eligibility, or timeline action.
- Confirming `superseded` may move content to Extras; rejecting it restores
  ordinary active/inactive classification without deleting text.

### 6.5 Graphics and asset durability

- The chart card shows semantic values, fictional data snapshot/version,
  citation relationship, template placeholder, and unresolved/render state.
- The long-text card keeps editable text as data rather than baking it into an
  image.
- The local audio reference shows `Reference not durable`, Import, Relink, and
  Replace actions without displaying an absolute path.
- A missing locator never erases the asset intent or substitutes unrelated
  media.

### 6.6 Status and accessibility

Exercise these states: ready, unresolved, unplaced, needs classification,
candidate selection required, possible superseded, stale reference, failed,
and excluded. Each state needs text/icon/non-color distinction, keyboard
access, an accessible name, and one relevant remediation action.

## 7. Required scenario views

1. **Coverage overview** — the entire section with exact-range card links and
   mixed left-only, right-only, paired, and blank presentation.
2. **Classify right-lane item** — role picker and role-specific inspector.
3. **Attach Unplaced item** — range/point/Extras/dismiss choices with no default
   nearest-row binding.
4. **Choose source candidate** — compare candidates, select one, clear the
   selection, and see deterministic build impact.
5. **Choose narration variant** — switch active choice without deleting other
   variants.
6. **Review imported formatting** — accept/reject possible-superseded state and
   prove other formatting remains nonsemantic.
7. **Inspect derived graphic provenance** — semantic inputs, data version,
   citation, template version, and build readiness.
8. **Resolve local reference** — unresolved, imported, relinked, and failed
   states using fictional locator labels only.

Every view must be testable at `1280 × 800` and `1024 × 768` as a real reflow,
with pointer and keyboard operation. Exact visual tokens come only from the
Producer-accepted output of issue #21.

## 8. Coverage checklist

The later prototype is incomplete unless it visibly exercises all of these:

- [ ] section heading;
- [ ] ordinary narration;
- [ ] inline OC/VO transition;
- [ ] performance direction, pause, and pronunciation;
- [ ] narration spanning multiple visual changes;
- [ ] generic unresolved visual request;
- [ ] logged clip with range, transcript excerpt, and source-audio policy;
- [ ] webpage capture and durable local still;
- [ ] Music/SFX cue with pinned identity and explicit intent;
- [ ] Citation that is not a visual;
- [ ] full-screen text graphic;
- [ ] data-derived graphic with provenance;
- [ ] multiple candidate sources/ranges;
- [ ] mutually exclusive narration variants;
- [ ] right-only anchored and right-only Unplaced items;
- [ ] formatting and possible-superseded review;
- [ ] local/non-durable asset reference;
- [ ] production point marker;
- [ ] Ideas, Extras, excluded note, and stale reference;
- [ ] left-only, right-only, paired, and blank presentation;
- [ ] deterministic active Draft/build inclusion; and
- [ ] issue #21 token authority and both required viewports.

## 9. Explicit non-goals

- No Google Docs importer or parser behavior.
- No contract, fixture, schema, generated type, or validator change.
- No media download, upload, local-path access, graphic rendering, or Resolve
  action.
- No Research Video Clips redesign.
- No visual-token decision or wiring.
- No representation of private source facts or wording.
