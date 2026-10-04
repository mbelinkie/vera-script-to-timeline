# Claude checkpoint 7: Producer row-audio policy and corrected plan

Read-only plan review. Do not edit files, execute commands, post comments or
perform native actions. The Producer's clarification is authoritative product
intent; identify conflicts in our implementation plan rather than arguing it
away. This is an additional plan checkpoint before the omission work. The new
uncommitted visual file controller will receive a separate finished-work review
after its currently failing identity safety test is fixed; do not count this
request as that review.

Read `docs/investigations/issue-144/producer-row-audio-policy.md`, the current
`docs/plans/issue-144-roundtrip-harness.md`, and relevant authoritative spec
sections 6.5, 6.15, 8.3 and Slice 7.5. Inspect the accepted narration boundary if
needed. Earlier reviews endorsed a lossless splice, but the Producer has now
explicitly rejected that route. The active plan has been corrected.

Producer intent: every row is one piece of temporary audio. Any VO wording
change, even a simple accepted cut, replaces the entire recording; no fragment
splicing. Obtain new timings and recalculate all cuts in that row. Prompter
generation starts an authoring lock/warning checkpoint. Explicit warning
override regenerates row temp VO and indicates reshoot. Later, export prompter
only for rows changed since the last prompter export.

Additional Producer framing during this checkpoint: each row is a self-contained
box; narration and visuals are row-local, while music may span rows. Regenerate
and internally retime only the changed VO row. Later rows may move together to
new absolute starts, preserving audio and relative cuts. Whole-timeline building
validates rows individually and strings them together, with separate spanning
music checks. Assess this against the current plan and accepted compiler. Do not
invent new authoring features or imply that global package/identity verification
itself violates row-local product behavior.

Please review:

1. Any remaining splice, old-timing reuse, exact-removed-duration or old-frame
   equivalence assumptions that contradict whole-row generation.
2. Whether the corrected semantic approach preserves accepted token/visual
   anchor intent while safely recompiling against new pacing, duration and
   source-handle/coverage limits.
3. The smallest executable generation/preparation handoff compatible with
   #144's no paid/cloud calls, real-script #145 authorization, accepted narration
   implementation and frozen contracts. A manually rewritten input or merely
   relabeled old recording cannot substitute for integrated regeneration.
4. Other product mismatches worth telling the Producer concisely: visual-only
   versus VO edits, lock beginning at export rather than audio import, retained
   unchanged recorded beats versus whole-row reshoot, and failure behavior.
5. Any hidden reduction of #144's named positive omission coverage. Detection
   still needs verified audible absence and explicit acceptance; successful
   rebuild needs new full-row audio/timing and actual compiler/package/jobs.

Return concrete findings with file references, distinction between settled
rules and unresolved decisions, and a short plain-language logic summary.
Review is advisory; it cannot change Producer policy or count as acceptance.
