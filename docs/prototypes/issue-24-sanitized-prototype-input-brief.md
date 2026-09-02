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
| `Keep this calm.` |  | Ordinary Direction block; excluded from prompter by default |
|  | Comment: `@Editor Could we simplify “moving pattern”?` | Exact-range Comment anchored to the preceding narration, with optional stable-user mention, reply/resolve controls, and no build effect |
| `[OC] Watch the marker behind me [PAUSE] [VO] as the tide turns and the reading begins to drift.` | Typed pause annotation, `Include in prompter: On` | Non-spoken typed annotation visible in prompter and sidecar; setting defaults on |
|  | Sequence: wide harbor Clip (`Mute source audio`) followed by a sensor close-up Clip (`Use source audio`) | Timed Picture → Clip sequence; both play consecutively over successive exact ranges without splitting the paragraph |
|  | Option A: `https://media-a.example.invalid/harbor`, `00:12–00:19`; Option B: `https://media-b.example.invalid/sensor`, `01:03–01:10` | Right-only Option set; no option selected initially and Release blocked by default |
|  | Comparison stack: three fictional treatments on organized alternate Resolve tracks | Distinct comparison intent; explicit `Choose in Resolve` policy and choice marker |
| `[VO] The instrument calls this the Lunara effect.` | Pronunciation: `Lunara` → `loo-NAH-rah` | Exact text annotation; not a visual and not spoken as an instruction |
| `[VO] The public dashboard shows the same change from another angle.` | Webpage Capture: `https://page.example.invalid/dashboard`; fictional trend panel; policy `On build`; motion `Slow drift — top left v1` | Capture card with region/provenance, pre-build revision state, immutable-artifact history, and selected versioned motion preset |
| `[VO] The warning appears directly beneath the second reading.` | Spotlight the fictional sentence “Review required before adjustment”; `Zoom to spotlight` over this phrase | Timed inverse-dimming treatment plus slow-zoom segment bound to the confirmed Spotlight region |
| `[VO] The archive preserves one view each morning.` | Periodic Webpage Capture: `https://page.example.invalid/archive`; motion `Slow drift — top center v1` | Periodic policy with bounded configurable retention; pinned/checkpoint/build-referenced revisions protected |
| `[OC] Here is the sensor before the trial began.` | Uploaded Image `asset-demo-still-01`; slow zoom; manual focus `subject face` at fictional normalized point `(0.68, 0.32)` | Durable managed image plus custom source-relative zoom focus and start/end-frame preview |
| `[VO] A second still shows the repaired housing.` | Linked Image `https://images.example.invalid/housing.png`; motion `Slow zoom v1`; focus `Center` | Automatically acquire locally, then expose verifying/ready/failed status, hash, dimensions, and provenance |
| `[VO] This frozen screenshot came from an earlier review.` | User-uploaded screenshot `asset-demo-screenshot-01` | Image subtype, not recapturable Capture, because no authoritative live relationship is retained |
| `[VO] In one trial, the first bar reaches eighteen, then the second reaches twenty-seven.` | Bar chart: `reading-1 = 18`, `reading-2 = 27`; cue `bar:reading-1 → emphasis` over “first bar,” then `bar:reading-2 → emphasis` over “second”; cite snapshot `demo-v1` | One pinned Fusion Graphic with semantic inputs and two ordered exact-range highlight cues; completed target returns to base |
| `[VO] In the summary table, the west station needs attention.` | Table: fictional east/west/north rows; cue `row:west → emphasis` over “west station” | Fusion template publishes a stable row target and maps semantic emphasis to its own versioned color/control values |
| `[VO] The operator described the change as “slow, then sudden.”` | Logged source clip, selected range `00:24–00:32`; transcript excerpt shown; source audio on | Source Clip card with immutable evidence and occurrence range |
| `[VO] Viewers saw the demonstration in its original online context.` | YouTube page composite from fictional Clip `harbor-demo`, range `00:24–00:32`; description and two fictional comments visible; motion `Slow zoom v1`; focus `Center` | One-action compound Picture: moving clip inside a high-resolution fictional watch-page capture, pinned layout, source-audio policy, page revision, and whole-composite motion |
| `[VO] A short chime marks the second reading.` | Music/SFX cue `demo-chime-v1`; start at the anchored phrase; license note fictional | Music/SFX card with pinned fictional revision and explicit cue intent |
| `[OC] That distinction matters because the next step depends on timing.` | Full-screen text: `MEASURE FIRST / ADJUST SECOND` | Long-text Graphic card; overlay/full-frame choice visible |
| `Variant A: [OC] We adjust only after the second reading.` |  | Variant group `closing-line`; selected choice |
| `Variant B: [OC] The second reading tells us when to adjust.` |  | Same variant group; inactive but readable |
| `Variant C: [OC] Timing decides the adjustment.` |  | Same variant group; inactive but readable |
| `[VO] A final comparison confirms the pattern.` | `Propose cut` on “final”; attributed pending strikethrough | Explicit review action only; accept parks the cut text, reject restores it, and pending never silently changes build content |
|  | `Add a map somewhere near the comparison.` Duration `4s`, end anchored to “pattern.” | Right-only Graphic using duration+end three-point timing; interval is derivable without a start anchor |
|  | `Add an establishing still.` Duration `3s` only | Unplaced/incomplete timed Picture; no nearest-row attachment and Release cannot derive an interval |
|  | Local audio reference: `[unresolved local reference]` | Reference card; requires import/relink before any build use; no absolute path |
|  | Production note: `Check the on-screen units in Resolve.` | Point-anchored Production marker; zero duration |
| `[OC] The result is simple: observe, compare, then act.` |  | Narration-only row; no missing-visual warning because host remains on camera |

## 5. Ideas, Extras, and excluded material

Show these beside the Draft without letting them enter validation, prompter,
voice generation, duration, or build preview:

- Idea: “Explain why the first reading can be misleading.”
- Section-linked parked Extra: an unused paragraph with one stale visual
  reference, represented once and shown both collapsed under **Why the Signal
  Changes** and in global Extras.
- Excluded draft note: “Verify the fictional units before publication.”
- Content parked by an accepted `Propose cut`, with attribution and history.

## 6. Required interactions and visible states

### 6.1 Anchoring and asymmetry

1. Hovering or focusing a Picture card highlights its exact narration words.
2. Hovering or focusing highlighted words emphasizes the attached card.
3. The continuous OC→VO paragraph remains one paragraph while two picture
   events attach to successive ranges.
4. The right-only candidate row displays an explicit attachment control; its
   legacy vertical position does not create an anchor.
5. The duration-only establishing still stays Unplaced until the user adds a
   start or end, parks it in Extras, or dismisses it; nearest-row placement is
   never offered as an inferred default.
6. Timing accepts start+end, start+duration, or duration+end. If all three are
   present they must agree; contradictory values show a blocking conflict.

### 6.2 Typed right-lane roles

Timed Picture is a parent role with `Unresolved visual`, Clip, Image, Capture,
`YouTube page composite`, and Graphic subtypes. It must remain distinguishable
from Audio cue, Citation, Editor note/timeline marker, Draft note, Reference,
and Comment by visible label, icon, accessible name, and inspector fields—not
color alone. Clip shows `Mute`/`Use source audio`; Graphic shows semantic script
data plus pinned template. Changing a role previews changed fields and build
behavior.

### 6.3 Variants and candidates

- The `closing-line` group shows exactly one active choice.
- Only the active choice appears in prompter/build preview.
- Inactive choices remain readable and lossless beside the group.
- A Sequence schedules all members consecutively.
- An Option set may have zero or one selected candidate and never chooses the
  first URL. Release blocks while it is unresolved unless the Producer changes
  that set's resolution policy to `Choose in Resolve`.
- A Comparison stack intentionally shows every candidate on organized
  alternate Resolve tracks with a choice marker; it is not an unresolved
  Option set or a Sequence.

### 6.4 Formatting review

- Highlight, color, bold, italic, and underline may appear as preserved source
  formatting but remain nonsemantic.
- Strikethrough appears only after the attributed `Propose cut` action; there
  is no decorative strikethrough control.
- No formatting cue silently assigns OC/VO, role, status, ownership, active
  Draft membership, build eligibility, or timeline action.
- Accepting a proposed cut removes it from active Draft and preserves it as
  section-linked parked material/history. Rejecting restores normal text.

### 6.5 Graphics and asset durability

- The chart card shows semantic values, fictional data snapshot/version,
  citation relationship, template placeholder, and unresolved/render state.
- The pinned Fusion template publishes a human-readable target manifest. The
  prototype includes `bar:reading-1`, `bar:reading-2`, and `row:west`, with
  target kind, label, allowed semantic states, and verified template-control
  binding; authoring never exposes internal Fusion node names.
- A highlight cue selects one or more published targets, a template-defined
  state such as `emphasis` or `muted`, an exact narration range/interval, and an
  optional supported transition. The actual colors and Fusion parameters come
  from the pinned template revision, not from #24.
- Preview the two bar cues sequentially inside one chart and the row cue in the
  table. A start-only cue may explicitly last until the next cue or Graphic end;
  otherwise the two-of-three timing rule applies. Completed cues return to base
  unless the next cue continues the state.
- Disjoint targets may be active together. Contradictory overlapping states on
  the same target create a blocking cue conflict with direct remediation.
- Studio evidence shows the template controls/keyframes at compiled cue times.
  Free uses the package's declared live/baked/manual fallback and reports which
  representation it used. The build freezes template revision, inputs/data
  provenance, cue schedule, resolved control values, and render identity.
- The long-text card keeps editable text as data rather than baking it into an
  image.
- The local audio reference shows `Reference not durable`, Import, Relink, and
  Replace actions without displaying an absolute path.
- A missing locator never erases the asset intent or substitutes unrelated
  media.

### 6.6 Image, capture, and motion

- Upload Image creates a verified managed artifact using the authorized import
  policy. Link Image automatically acquires a local immutable artifact and
  exposes progress/failure without requiring a separate download command.
- A user-uploaded screenshot is an Image unless the user explicitly creates or
  preserves a live Capture relationship. A VERA-created webpage/screen Capture
  retains capture parameters, provenance, and recapture revisions.
- Capture policy choices are `Now`, `On build`, and `Periodic`. Preview them
  without contacting real URLs. Every build freezes the exact immutable
  revision it used.
- Periodic revision history displays configurable bounded retention. Pinned,
  checkpoint-referenced, and build-referenced captures are protected; only
  unreferenced periodic revisions may age out.
- Every Image/Capture occurrence selects a versioned motion preset. Show
  `None`, `Slow drift — top left`, `Slow drift — top center`, and `Slow zoom`,
  with room for future registered presets. `Slow zoom` then exposes a separate
  focus selector: `Center`, `Choose point`, or `Use spotlight` when eligible.
- `Choose point` lets the author click the immutable source preview—for example
  a fictional face—and stores normalized source coordinates plus an editable
  label. It requires no face-detection feature.
- `Use spotlight` binds focus to a confirmed Spotlight identity/revision and
  derives its centroid and padded region. `Zoom to spotlight` aligns a motion
  segment to the Spotlight interval by default, so the text brightens and the
  camera move begins together without duplicate coordinates.
- Start/end-frame preview shows the actual crop, scale, and target crosshair.
  The framing solver clamps or explains a requested move that would expose
  empty canvas; it never hides the adjustment.
- A Picture may contain ordered motion segments when focus changes. Overlapping
  contradictory transforms are a Release-blocking conflict.
- Replacing image bytes or selecting a new Capture revision marks a manual
  focus `Needs review`. An accepted Spotlight remap updates bound focus;
  `Spotlight stale` keeps its motion segment stale. Builds freeze focus evidence,
  resolved point/region, keyframes, timing, preset, source revision, and effect
  order.
- Capture and YouTube page composite occurrences may add a Spotlight.
  The simplest authoring flow is `Add spotlight`, then drag a rectangle over
  the critical text while the preview dims everything outside it.
- The primary assisted flow overlays selectable OCR words and lines on the
  immutable high-resolution capture. Selecting fictional text unions its source-
  pixel boxes; editable padding/rounding produces the previewed bright region.
  A manual rectangle remains available when OCR misses or joins text badly.
- Store capture hash, OCR word IDs/text/context and pixel boxes, OCR/profile
  version, capture-local normalized geometry, optional DOM evidence, union/
  padding/rounding parameters, dim opacity, feather, exact active interval, and
  treatment version.
- Confirmation generates a full-resolution immutable RGBA/alpha matte artifact
  whose transparent opening is the selected text region and whose outside area
  supplies the requested dimming. Preview uses that same derivation.
- After recapture, VERA may propose a repaired target using DOM/OCR evidence.
  If the page moved or the match is ambiguous, show `Spotlight stale` with
  `Keep previous capture`, `Accept remap`, and `Redraw`; never move the mask
  silently.
- Composition order is captured source (or completed YouTube page composite),
  then inverse matte, then whole-picture drift/zoom. The reliable Resolve
  baseline places the verified matte with the capture inside a generated nested
  sequence, then applies motion to the nest. A native editable Resolve/Fusion
  mask may be shown as a later adapter capability, not a baseline dependency.

### 6.7 Comments and prompter annotations

- A Comment can anchor to text, a card, an Idea, an Extra, or between blocks;
  it supports optional `@user`, replies, resolve/reopen, attribution, and an
  explicit stale/reattach state. It never enters narration, duration, prompter,
  or timeline output.
- Pronunciation, pause, pacing, and emphasis are typed exact-range annotations.
  `Include in prompter` defaults on. The visible prompter uses unmistakably
  non-spoken cues such as `[PRONUNCIATION: Lunara = loo-NAH-rah]`, `[PAUSE]`,
  and `[EMPHASIZE: second]`; ordinary Direction blocks remain excluded.

### 6.8 YouTube page composite

- Every compatible YouTube Clip card offers `Present on YouTube page`. One
  action captures the current public watch-page state and creates a nested
  composite in which the selected moving clip occupies the captured player
  area while the description and requested visible comments remain readable.
- The quick inspector exposes clip in/out and audio policy, page region,
  description/comments visibility, captured play count, page-capture revision,
  composite-template revision, and whole-composite motion preset. It does not
  require the author to create or align two separate cards.
- `Refresh page now` is an optional second action while authoring. It captures
  the current public page state—including a newer play count—as a new immutable
  revision and selects it for the active Draft; earlier revisions and builds
  remain unchanged. `On build` may instead be chosen when build-time freshness
  is desired.
- The Clip and page Capture retain separate identities. Refreshing page chrome
  never changes the selected video, in/out, source audio policy, or transcript
  evidence. The build snapshot pins both revisions, layout/template, motion,
  and resulting nested artifact.
- The prototype uses only fictional page text, channel identity, counts,
  description, and comments. Public anonymous capture is the baseline;
  authenticated or personalized page state is not silently accessed.

### 6.9 Status and accessibility

Exercise these states: ready, acquiring, unresolved, unplaced, incomplete
timing, timing conflict, needs classification, option selection required,
choose in Resolve, proposed cut, stale comment anchor, stale reference,
capture due, spotlight proposed, spotlight stale, motion focus needs review,
motion focus clamped, motion-segment conflict, graphic target missing, graphic
cue conflict, template update available, page refresh available, composite
generating, retention-protected, failed, and excluded. Each needs text/icon/
non-color distinction, keyboard access, an accessible name, and one relevant
remediation action.

## 7. Required scenario views

1. **Coverage overview** — the entire section with exact-range card links and
   mixed left-only, right-only, paired, and blank presentation.
2. **Classify right-lane item** — role picker and role-specific inspector.
3. **Attach Unplaced item** — range/point/Extras/dismiss choices with no default
   nearest-row binding.
4. **Choose collection behavior** — compare Sequence, Option set, and
   Comparison stack; select/clear an option and inspect deterministic Preview,
   Release, and Resolve impact.
5. **Choose narration variant** — switch active choice without deleting other
   variants.
6. **Review proposed cut** — propose, accept, and reject a cut while proving
   ordinary formatting remains nonsemantic and accepted content is parked.
7. **Inspect derived graphic provenance** — semantic inputs, data version,
   citation, template version, and build readiness.
8. **Cue infographic emphasis** — select stable semantic table/bar targets,
   add multiple narration-anchored cues to one chart, preview transitions and
   resets, expose a same-target conflict, and inspect Studio keyframes plus the
   declared Free fallback without choosing actual colors.
9. **Resolve local reference** — unresolved, imported, relinked, and failed
   states using fictional locator labels only.
10. **Acquire image and configure capture** — uploaded Image, automatically
    acquired linked Image, uploaded screenshot, Capture timing policy, revision
    history/retention, motion preset, manual face focus, and end-frame preview.
11. **Review section-linked Extras** — one parked identity visible under the
    section and in global Extras, with restore behavior.
12. **Comment and prompter review** — optional directed mention, stale-comment
    repair, annotation include toggle, and visibly non-spoken prompter output.
13. **Present Clip on YouTube page** — apply the one-action treatment, inspect
    separate Clip/page revisions, refresh the fictional play count, toggle
    description/comments visibility, and preview slow zoom on the composite.
14. **Spotlight critical webpage text** — select fictional OCR words/lines,
    inspect and adjust the generated inverse matte, compare the manual rectangle,
    set its active phrase, bind `Zoom to spotlight`, inspect focus/crop and the
    nested-sequence handoff, recapture the page, and resolve stale Spotlight and
    motion focus without silently moving either.

Every view must be testable at `1280 × 800` and `1024 × 768` as a real reflow,
with pointer and keyboard operation. Exact visual tokens come only from the
Producer-accepted output of issue #21.

## 8. Coverage checklist

The later prototype is incomplete unless it visibly exercises all of these:

- [ ] section heading;
- [ ] ordinary narration;
- [ ] inline OC/VO transition;
- [ ] ordinary Direction plus typed pause/pronunciation with default-on visible
      prompter cues;
- [ ] Comment with optional stable-user mention and no build behavior;
- [ ] narration spanning multiple visual changes;
- [ ] generic unresolved visual request;
- [ ] logged clip with range, transcript excerpt, and source-audio policy;
- [ ] uploaded Image, automatically acquired linked Image, and uploaded
      screenshot treated as Image;
- [ ] Webpage Capture with `Now`, `On build`, and `Periodic` policies,
      immutable revisions, bounded/protected retention, and motion presets;
- [ ] slow-zoom focus using center, a custom normalized point on a fictional
      face, and a Spotlight-bound region; start/end-frame crop, clamping,
      ordered segments/conflict, source-update review, and frozen transforms;
- [ ] one-action YouTube page composite with moving Clip, high-resolution page
      capture, visible fictional description/comments, refreshable play count,
      separate immutable revisions, pinned layout, and whole-composite motion;
- [ ] selectable high-resolution OCR text, manual fallback, immutable inverse
      matte artifact, exact Spotlight timing, generated nested-sequence handoff,
      deterministic effect order, and stale/remap review after recapture;
- [ ] Music/SFX cue with pinned identity and explicit intent;
- [ ] Citation that is not a visual;
- [ ] full-screen text graphic;
- [ ] data-derived graphic with provenance;
- [ ] pinned Fusion template with stable semantic row/bar targets, several
      exact-range highlight cues on one graphic, template-defined emphasis,
      transition/reset and conflict behavior, Studio keyframes, honest Free
      fallback, and no #24 color selection;
- [ ] Sequence, Option set, and Comparison stack, including Release policy;
- [ ] mutually exclusive narration variants;
- [ ] right-only anchored and right-only Unplaced items;
- [ ] nonsemantic formatting and explicit `Propose cut` review;
- [ ] local/non-durable asset reference;
- [ ] production point marker;
- [ ] Ideas, section-linked parked/global Extras, excluded note, stale comment,
      and stale reference;
- [ ] start+end, start+duration, duration+end, incomplete timing, and timing
      conflict states;
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
