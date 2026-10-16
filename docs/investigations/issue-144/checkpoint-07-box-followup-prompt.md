# Checkpoint 7 follow-up: row boxes and preservation boundary

Read-only review; no edits, commands, comments or native actions. The previous
review is retained. Please examine only these follow-up concerns and the
updated policy document/current plan, using the accepted compiler if needed.

Producer clarification after the initial prompt: each row is a self-contained
box; VO changes regenerate and retime only that row, visuals affect only that
row, and music may span rows. Validate boxes individually and string them
together. Conceptual per-row pre-comps placed in a master timeline are a useful
model, but actual nested timelines would be awkward for the human editor. VERA
should distinguish altered, rearranged and untouched boxes. Untouched boxes'
contents stay intact; new duration or order can translate their placement.

1. Is this compatible with the accepted compiler's block-local timing and
   sequential assembly? Flag any specific contrary assumption in #144.
2. Current #144 creates a fresh timeline. We must distinguish unchanged
   logical row content from reusing native objects or preserving all untouched
   human Resolve refinements. Is that limitation clearly surfaced, and what
   minimal tests establish content preservation without claiming #104's
   production selective-regeneration capability?
3. Your prior recommendation to limit regeneration to pre-approval rows is
   not adopted. The Producer already specified that an explicit post-prompter
   override creates whole-row TEMP VO and signals reshoot. This never
   resynthesizes/overwrites the human recording, and an ordinary rebuild does
   not unlock it. Confirm that historical locked recordings can remain intact
   while a current edited version is stale and has fresh temporary VO.
4. Keep changed-row export/lock details in Inbox design #153 and implementation
   in their owning future slices, rather than widening #144.

Return concrete discrepancies or a concise confirmation, plus only unresolved
product decisions that the Producer has not already settled.
