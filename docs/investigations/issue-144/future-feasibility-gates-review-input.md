# Future feasibility gates — advice during #144

The producer asked whether later tests could reveal that planned capabilities
are impossible, and therefore should run before frontend work. This is an
assessment of retained evidence, not a roadmap reprioritization, implementation,
new Ready promotion or permission to touch Resolve.

## Current evidence and recommendation

#144 supplies a bounded automated harness; #145 still owns the real three-edit
round trip. Passing this subset cannot prove every future VERA workflow. Real
spikes should test exact operations and save/reopen on the intended supported
Resolve build. A failure may show an unsupported automation path or require a
bounded operator step/workflow change; it cannot by itself prove the editorial
result impossible in all implementations.

1. **Highest uncertainty: untouched human-finishing preservation (#104).**
   Our current rebuild creates a fresh target and tests unchanged canonical
   content/source/local geometry. This does not prove carrying arbitrary grades,
   effects, Fusion changes, Fairlight/mix settings or manual editorial changes
   into the new target when an earlier row changes duration or rows reorder.
   Before promising this in frontend work, test a finished untouched row after a
   neighboring duration change and reorder; compare actual retained native
   identity/settings and rendered result after save/reopen. Determine the
   supported preservation mechanism and exclusions before implementing UI.
2. **High uncertainty: exact transition automation and inbound observability
   (#88).** Design tickets #125/#137/#128/#138/#139 define meaning and review
   states, not a passing installed-Resolve automation proof. Test creating,
   reading/changing/reconciling supported boundary type/duration/effective intent,
   source handles and picture/audio separation after move/trim/reopen. A type
   supported for outbound may still be unobservable for inbound; preserve the
   explicit unsupported/unknown result rather than guess a default.
3. **Moderate uncertainty: music spanning boxes (#100).** Test one actual cue
   across at least two rows while the first duration changes and row order is
   changed, then verify explicit intended cue placement/extent, source identity
   and audible mix after reopen. Basic music is not asserted impossible; its
   complete VERA automation/regeneration behavior remains unproven. More complex
   mix/ducking/effect observability requires its own bounded supported envelope.
4. **Lower uncertainty for the exact accepted graphics subset.** Closed #3
   already owns the registered EV24 template's real set/read/save/reopen and
   visual capability proof. #8 still owns product placement/materialization and
   regression/visual acceptance. Arbitrary templates, Free fallback and human
   Fusion-finishing preservation are not covered by that bounded success.
5. **Post-prompter guard and changed-row export (#153) are mostly application
   state/policy work.** They still need state/failure tests, but the lock,
   explicit override and export comparison are not themselves unproven Resolve
   SDK operations. Real presenter timing/conform is separate: #51 retained no
   adequate local word-timing selection and #63 owns follow-up. Do not describe
   presenter timing as definitively solved merely because the guard is feasible.

Recommend small, headless, externally evidenced capability proofs for the first
three areas and retain the presenter-timing gate before frontend work promises
those behaviors. Their proposed tests should be explicit bounded evidence work,
not early implementation of #88/#100/#104 placeholders. Existing owner/dependency
and exact model/effort claim rules continue to apply. #145 remains the already
planned first real feasibility gate. Proven bounded mechanisms can wait for
implementation; cost, reliability, supported subset and failure UX still require
acceptance testing when implemented.

Primary sources: issue bodies/status in the full open/closed roadmap audit,
#3/#8/#51/#63/#88/#100/#104/#125/#137/#138/#139/#144/#145/#153,
`seam-matrix-draft.md`, and `POSSIBLE_ISSUES_FOR_ASTRA.md`. No live native
probe, new roadmap issue, reprioritization or contract amendment occurred here.
