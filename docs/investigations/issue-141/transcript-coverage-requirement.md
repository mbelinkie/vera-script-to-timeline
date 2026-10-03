# Task ID: Issue 141 — conditional transcript coverage requirement

## Adopted requirement

If VERA uses Resolve transcript data for reconciliation or word/cut analysis,
Resolve transcription coverage for every clip in the analyzed scope is a
prerequisite. VERA must enforce that prerequisite. Missing or incomplete
coverage visibly blocks transcript-based conclusions; it never becomes evidence
of word removal, inaudibility, deletion, or absent source material.

This is a future product/design requirement. The Issue 141 getter observation
does not implement or accept the gate.

## Retained Inbox design placeholder #146

Define and Producer-accept the smallest coverage gate and evidence record for a
Resolve-transcript-based reconciliation path. The design must cover:

- enumeration of every source clip and timeline occurrence in scope, with the
  project/timeline/content identity bound to the check;
- per-clip transcript states that distinguish usable value, valid no-speech or
  no-audio, empty, missing, getter error, unsupported access, and stale or
  mismatched provenance;
- a fail-closed result when any required clip is uncovered, unreadable,
  unstable, stale, or otherwise unknown;
- transcript freshness/version binding to the observed source identity and
  content revision, including what invalidates a prior coverage result;
- explicit local/cloud provider consent, retention, and automatic-transcription
  policy before any missing transcript can be generated; and
- evidence that keeps source-item and timeline-proxy/occurrence results
  separate. Ordinary and nested getter values are observations, not proof that
  edited output retained or removed audible speech.

## Acceptance authority and routing

- Acceptance: Producer.
- Tentative model: `model:sol`.
- Tentative effort: `effort:high`.

## Dependencies

- Blocked by #141

## Exclusions

No production implementation, schema or contract change, provider selection,
automatic transcription, Resolve mutation, source-media export, or claim about
program routing belongs in this design placeholder.

## Unresolved decisions

1. What observable evidence distinguishes valid no-speech/no-audio from a missing
   or unsupported transcript getter?
2. Which source hash, transcript version, timeline occurrence, and edit/content
   revision fields define freshness, and how are stale results invalidated?
3. What consent and retention record is required before automatic transcription,
   and is the operation local-only by default?
4. Is coverage required per source item, per timeline occurrence, or both when
   nested media and timeline proxies are involved?

## Duplicate audit (2026-10-01)

No exact open or closed issue was found for this all-clips Resolve coverage
gate. Existing issues are partial or adjacent:

- [#141](https://github.com/mbelinkie/vera-script-to-timeline/issues/141) is
  the external Resolve observation and now records this conditional requirement,
  but it does not implement the future enforcement gate.
- [#45](https://github.com/mbelinkie/vera-script-to-timeline/issues/45) owns
  VERA's provider-neutral word-timed transcription/alignment implementation and
  explicit missing-timing behavior, but does not require complete Resolve
  transcript coverage for reconciliation.
- [#123](https://github.com/mbelinkie/vera-script-to-timeline/issues/123)
  designs reconciliation and `Words cut`, while excluding production
  reconciliation implementation and leaving transcript coverage unspecified.
- [#124](https://github.com/mbelinkie/vera-script-to-timeline/issues/124) and
  [#49](https://github.com/mbelinkie/vera-script-to-timeline/issues/49) cover
  review design and real-media validation downstream of the transcription
  engine; neither defines this Resolve coverage gate.

The adopted conditional requirement is retained in [#146](https://github.com/mbelinkie/vera-script-to-timeline/issues/146) in Inbox, blocked by #141, with tentative Sol/high routing and Producer acceptance. It does not authorize implementation or dispatch.


## Producer test interpretation

The two producer timelines successfully demonstrate source-word/range reconstruction of the intended phrase omission. Kai is accepted as the spoken form of KAJ; Specifically is correct, replacing the mistakenly supplied Namely. The sole minor wording error is out versus up. This makes the tested approach workable and reinforces the coverage prerequisite. It does not itself implement the gate or establish final mixed-output audibility.
