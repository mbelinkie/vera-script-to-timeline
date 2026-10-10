# Word-timing v2 — notes for the take stage (#53, #45)

These notes come out of the word-timing v2 study (`docs/plans/word-timing-v2-test-plan.md`).
They record interface points the take stage depends on. They are not take
rules: the take logic itself is owned by #53/#45.

## 1. Script-reconciled transcripts carry two texts per word

`scripts/word-timing-v2/reconcile.py` aligns recognised words to the prompter
script and writes, per word:

- `text`: the spelling for **matching and timing**. For a heard word that
  sounds like a script *name*, this is the script's spelling (`kai` becomes
  `KAJ`). Otherwise it is the heard word.
- `heard`: the recogniser's own word. This is the **presenter-fidelity
  evidence**.

The take stage must read `heard`, not `text`, when judging whether a read was
accurate. Otherwise a mispronounced name would look correct after the
spelling fix.

## 2. Misreadings are a reason to reject a take

A misread word, **including a mispronounced name**, should count against a
take's usability, in the same way as an omission or a flub. That evidence comes
from `heard` and its disagreement with the script word at `scriptIndex`. Only
the presenter's words matter here. Reconciliation must never hide them.

## 3. Local and cloud options (D-P007 softened, 2026-10-10)

The Producer softened D-P007 to "local is better": VERA must ship a local
pipeline, and may also offer a cloud pipeline if it is clearly superior. The
transcript contract (#45) should therefore stay provider-neutral across local
and hosted recognisers. The no-hosted-fallback rule stays: a cloud option is
an explicit choice, never a silent fallback.
