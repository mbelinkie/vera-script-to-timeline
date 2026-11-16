# S03 Integrated Authoring r29

This is the #125 design handoff from November 15, 2026. Unzip the [r29 prototype bundle](S03%20Integrated%20Authoring%20r29.zip). Open `S03 Integrated Authoring r29 - export.html` in a browser. The editable `.dc.html` and its companion `support.js` are in the same folder. The bundle preserves the exact Claude Design download. [Open the editable review revision](https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=S03+Integrated+Authoring+r29.dc.html).

## Production range editing

Decision 193 governs On Camera coverage. Uncovered narration uses On Camera with the chosen Wide or Tight framing. The first On Camera in a row uses the full card even when a still precedes it. A compact return requires an earlier appearance of the same shot and an intervening cutaway within the row. Keep recovery for deliberately placed visuals displaced from their words.

The r29 browser review observed these limitations:

- **Folded Letter.** Drag the first still's out bracket onto “next.” On Camera disappears, but Undo remains disabled. Shortening the still by one word also shifts the neighboring still's in bracket.
- **Amber Lantern and Paper Lanterns.** Confirming a highlighted Reselect creates a named Undo entry while the displayed brackets stay at their original words.
- **Chalk Crescent.** Splitting before “The shape simply marked…” produced one full On Camera card followed by the slate. One Undo restored the sequence. Use an additional regression case that removes the earlier appearance or intervening cutaway after a valid return exists.

Production acceptance covers one coherent sequence across the brackets, connectors, cards, and compiled edit, with one Undo restoring all affected ranges. The prototype's word timing, Research sources, and playback are fixtures. End-anchored audio is tracked separately in [#574](https://github.com/mbelinkie/vera-script-to-timeline/issues/574).
