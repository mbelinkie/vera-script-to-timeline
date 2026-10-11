### Outcome

An independent second opinion on the Issue #141 Resolve observation handoff. For each limitation Codex reported, either reproduce it, resolve it by a different supported method (with a controlled counterexample), explain it as a harness issue, or leave it explicitly ambiguous. This issue is the home for the plan, scripts, results and verdicts; #141 points here.

### Current evidence and context

- Parent: #141 (open). Input: Codex's `second-opinion-handoff.md`.
- Plan: [VERA Resolve Second-Opinion Test Plan](https://claude.ai/code/artifact/d76c8659-5038-4d17-83c5-00dafa26e273)
- Phase 0 started 2026-10-02. A Console-launched runner works inside Resolve Studio 21.1.1.10 with External Scripting None.
- The installed README hash matches #141's record. The `DaVinciResolveScript.pyi` hash differs (`2755259e…` now vs `00078fa1…` in #141), so this is a different setup from #141's 21.1.0 build 14.
- Untested leads include timeline transcription (`CreateSubtitlesFromAudio`, nested `TranscribeAudio`), `Timeline.Export` (OTIO/FCPXML/DRT/AAF/EDL/CSV), `GetMarkInOut`, audio track Mute vs `GetIsTrackEnabled`, stamped lineage, and render-based audibility.

### Scope and non-goals

In scope: Phases 0–10 of the plan in a new disposable synthetic project. External Scripting stays None; Local is only a documented later workaround.

Non-goals: no edits to the retained #141 project or `semi1b.mp4`; no reconciler implementation, contract, fixture or golden changes; no deletions; this does not close or replace #141.

### Failure states

- A guard refusal or harness error is recorded as a harness failure, never as a Resolve limitation.
- A finding obtained only with External Scripting = Local is labeled as such and does not count for VERA until re-run under None.
- Missing data never becomes evidence of absence.

### Acceptance criteria

- [ ] Every #141 handoff limitation has one outcome: reproduced, resolved by a different method, harness explanation, or still ambiguous, naming the exact API, object or export used.
- [ ] Each "resolved" claim includes a controlled counterexample that the method correctly distinguishes.
- [ ] Every finding VERA will rely on is re-confirmed with External Scripting = None through Workspace → Scripts or the Workflow Integration path.
- [ ] Scripts, result JSON and new-result template records are retained and linked from this issue.
- [ ] A verdict table (limitation → stands or lifted → VERA design consequence) is posted here and linked from #141.

### Verification and producer acceptance

External: retained evidence from Resolve Studio on the producer's Mac. The producer reviews the verdict table before any #141 conclusion changes.

### Dependencies

None

Routing note: executed by Claude (Opus 5.5) at the producer's direction. The roadmap's model classes (luna/terra/sol) don't include Claude, so the model/effort labels mirror #141's profile for record-keeping only.
