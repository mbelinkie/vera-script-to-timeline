# Producer correction 2 — S04 validation-state cleanup

Work only in the existing Claude Design artifact:

`Script to Timeline - Prompter Runtime and Suite Navigation S04-S06.dc.html`

This is a bounded correction to S04. Preserve the Producer's current S04
layout and content, including the complete Harbor Lights prompter script,
left-aligned composition, app-level footer action, product-only app window,
and clearly external prototype harness. Do not change S05, S06, or the accepted
S01–S03 artifact.

Use your own product-design and interaction-design judgment. These notes define
the product meaning, not a required visual solution. If an unresolved decision
would materially change the experience, ask Matthew one or more concise,
decision-bearing questions in this Claude chat and wait for his answer before
editing. Do not ask about matters you can resolve confidently with the existing
design system and requirements.

## Product conclusions

### Production note whose target was removed

A script-originated production note can be anchored to a word or passage so it
later becomes a Resolve timeline marker. If that text is deleted or its mapping
becomes ambiguous, the note is retained as unplaced until the writer reattaches
or dismisses it.

That condition is real, but it has no effect on a prompter export:

- it is not spoken;
- it never appears in prompter text;
- it has zero duration;
- it does not change the prompter sidecar; and
- it must not block prompter creation.

Remove `Marker target removed` from the S04 scenario selector and remove its
notice/actions from the S04 prompter experience. Do not delete or redefine the
underlying behavior. It belongs in authoring issue review and, if still
unresolved, timeline-build preparation. Its eventual user-facing wording there
should be closer to `Production note lost its place` than `Marker target
removed`, but do not design that separate surface in this correction.

### Spoken text with no camera state

This state is also real. Draft editing, deletion, import, anchor repair, or
concurrent changes can temporarily leave spoken words without exactly one OC or
VO assignment. VERA must not invent the missing state, and a prompter export
cannot be created until it is repaired.

However, do not make the Prompter destination itself inaccessible or use an
unexplained disabled navigation button in authoring. A user should still be
able to open the Prompter page to understand what is wrong. In the missing-state
scenario:

- keep the page recognizably the same Prompter experience rather than replacing
  it with a dead end;
- clearly identify the exact affected phrase;
- make clear that VERA needs the user to choose OC or VO and will not guess;
- provide an obvious route back to that phrase in the script;
- prevent the final creation action until the issue is fixed; and
- use accessible text and state, not color alone, to communicate the block.

Choose the best interaction and visual treatment using your own design skills.
For example, the blocked creation state could be expressed as a focused
preflight issue within the Prompter page, but that example is not a mandated
layout.

## Boundaries

- Preserve every current S04 prompter option and its behavior.
- Preserve the complete current prompter text and square-bracket export rules.
- Preserve the current simplified-camera default and deterministic identity
  behavior.
- Preserve the app footer and the separation between prototype controls and the
  VERA app window unless a direct consequence of the required missing-camera
  solution needs a small adjustment.
- Do not add implementation claims, real downloads, real clipboard writes,
  Resolve actions, background jobs, or navigation.
- Do not modify S05, S06, shared tokens, contracts, fixtures, or the accepted
  S01–S03 artifact.

After editing, summarize the design judgment you made, the missing-camera user
journey, and confirmation that the production-note scenario is absent from S04
without implying that the underlying authoring behavior was removed. This is
not Producer acceptance and must not mark issue #58 Done.
