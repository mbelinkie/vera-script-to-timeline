## Outcome

Define and obtain Producer acceptance for the post-prompter row editing guard,
whole-row temporary-VO replacement/reshoot states, and future prompter export
of rows changed since the last prompter export.

This is a bounded Inbox design placeholder adopted from Matthew Belinkie's
2026-10-03 clarification during #144. Tentative routing: model:sol / effort:high;
Size M; Acceptance Producer. It does not authorize implementation or dispatch.

## Scope

- Treat narration rows as self-contained boxes: row-local narration, visuals,
  word timings and cuts; later boxes translate when an earlier duration changes
  without regenerating their audio or changing relative cuts. Music may span
  rows and needs separate assembly checks.
- Any VO wording change, including an accepted cut, replaces the complete row
  temporary recording and obtains fresh timing. No splicing old fragments.
- Prompter generation begins the left-side authoring lock/warning checkpoint;
  an explicit warning override permits the edit, regenerates whole-row temp VO,
  and indicates reshoot. Preserve historical exports, recordings and builds.
- Define the future changed-row prompter export against the last prompter export,
  retaining exact spoken wording/order and needed OC/VO and non-spoken context.
- Identify bounded implementation ownership in #65, #68, #95 or a separately
  proposed successor without silently modifying accepted contracts/designs.

## Acceptance criteria

- [ ] Producer walks pre-prompter editing, prompter export, blocked ordinary
  editing, explicit override, regeneration pending/failure/success and reshoot
  indication; exact guarded controls and wording are accepted.
- [ ] A VO edit regenerates only its row; visual-only edits preserve VO. New
  duration moves later boxes intact, with explicit spanning-music treatment.
- [ ] The design distinguishes whole-row temp replacement from recorded-beat
  approval retention; changed wording never silently inherits an old take's
  approval, and the current-version fallback/reshoot behavior is explicit.
- [ ] Changed-row prompter export has accepted rules for added/deleted/moved,
  split/merged and reverted rows, output context, and when an export advances
  the last-prompter comparison baseline.
- [ ] Any required frozen-contract or accepted-prototype amendment has its own
  explicit change note and Producer approval before implementation.
- [ ] The accepted state/decision matrix and numbered Producer walkthrough
  identify implementation owners and remaining separately bounded work.

## Dependencies

- Blocked by #37
- Blocked by #127

## Exclusions

No #144 frontend expansion, production provider call, paid/cloud synthesis,
presenter ingest/conform implementation, native Resolve mutation, automatic
editing of recorded takes, frozen contract/generated type/fixture/golden change,
or dispatch. No new music engine.

## Unresolved decisions

Exact left-side controls covered by the guard; whether override is per edit or
per session; state persistence and recovery; reuse on exact-text reversion;
the current-version treatment of unchanged recorded beats in a changed row;
changed-row export comparison and context rules; any other explicitly approved
cross-row content beyond music. Settled Producer rules must not be reopened as
implementation preferences.

## Duplicate audit

Searched both open and closed issue titles/bodies on 2026-10-03. #37 owns the
accepted pure full-document export; #58 its accepted UI prototype; #65 the
editor implementation; #68 ordinary export integration; #95 post-shoot
staleness. None names the export-triggered lock plus warning override/reshoot
policy or changed-since-last-prompter export. This issue owns that missing
bounded design, preserving those existing implementation responsibilities.

## Source

#144 and `docs/investigations/issue-144/producer-row-audio-policy.md`.
