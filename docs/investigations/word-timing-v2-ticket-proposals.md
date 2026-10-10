# Word-timing v2 — proposed ticket changes across both boards (draft)

Status: **draft, not posted.** Nothing here is filed until the Producer
approves. Evidence is in `word-timing-v2-results.md` (in progress) and
`word-timing-v2-status.md`.

Principle (Producer, 2026-10-10): VERA ships as one package. Script to
Timeline (STT) and Research Video Clips (RVC) share one word-timing engine
behind thin per-app adapters, and the tickets cross-reference each other.
Earlier Research choices were made with weaker models and are open for review.

## What Research does today (origin/main, read-only check)

| Source | What RVC keeps | Word timing? |
|---|---|---|
| YouTube captions (`yt-dlp --sub-format vtt`) | cue start/end; `timingPrecision: "cue"` | **No.** Auto-caption VTT carries an inline start time per word (`<00:00:11.840><c> word</c>`); RVC drops it. |
| No captions → whisper.cpp (`ggml-large-v3-turbo`, `-ojf`) | segment `offsets` only | **No.** Segment-level; word times interpolated or absent. |

So RVC #16's "incumbent word-timing behaviour" is cue/segment timing. Every
MFA pipeline in this study is a strict timing improvement over it.

## Existing tickets this study unblocks or changes

- **STT #51** (closed, negative): superseded by this study's positive result.
  Proposal: add a comment linking `word-timing-v2-results.md` as the selection
  evidence. No reopen needed.
- **STT #168** (shared RecognizerPort/AlignerPort contract): now has
  measured profiles to design against. Proposals to add to its scope:
  - an optional **AudioPrep** stage (e.g. DeepFilterNet) whose output may feed
    the aligner and/or the recogniser independently (see cleanup finding);
  - **caption text as a RecognizerPort source** (YouTube auto/manual captions
    are "recognised text with coarse anchors");
  - a `timingPrecision` value for **start-only** word timing (auto-captions),
    distinct from `word` and `estimated`.
- **STT #45**: implementation per the results' STT profile (recogniser →
  script reconcile → MFA + guides → agreement flags). Still blocked by #168's
  approved schema.
- **RVC #16**: incumbent is cue/segment timing (above); the "demonstrably
  better" bar is met for timing. Text accuracy vs whisper large-v3-turbo is
  measured in the results. Add cross-refs to the new RVC tickets below.
- **RVC #19 (M7-04)**: the caption/ASR path it wires end to end should call
  the shared ports, not the retired whisper segment path. Cross-ref only.
- **RVC #38 (M9-04 hosted capacity)**: the cloud profile (ElevenLabs Scribe /
  AssemblyAI → MFA) is a candidate hosted provider. Cross-ref only.

## Proposed new tickets

### RVC-new-1 — Keep auto-caption word start times (small, Research only)

Parse the inline `<timestamp><c>` word starts that YouTube auto-caption VTT
already carries, instead of collapsing to cue timing. Ends remain derived and
labelled as such. A cheap interim win before the shared aligner lands.
Depends on #168 only for the precision label; could ship as
`estimated` with exact starts in the meantime.

### RVC-new-2 — Caption text → shared aligner path

When a source has captions, use the caption text as the recognised text and
the shared AlignerPort (MFA profile) for acoustic word bounds; fall back to the
shared local recogniser when there are none. Blocked by STT #168 and RVC #16.
Cross-ref STT #45. Evidence needed first: YouTube captions → MFA scored
against a keyed recording (see "open evidence" below).

### STT/RVC-new-3 — Audio preparation stage policy

Decide where DeepFilterNet sits: before recognition, before alignment only, or
not at all, per source type (scripted presenter vs arbitrary YouTube).
Evidence in the results' cleanup section. Belongs in the #168 contract as an
optional stage, so this may fold into #168 rather than be a separate ticket.

## Open evidence (needs the Producer)

- **Keyed YouTube test:** upload recordings A and B to YouTube as *unlisted*,
  let auto-captions generate, and the study scores "YouTube captions → (DFN) →
  MFA" against the frozen answer keys. This is the only way to measure the
  likely default Research path with real ground truth.
