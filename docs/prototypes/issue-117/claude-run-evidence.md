# Issue #117 — Claude run and regression evidence

## Submitted request

- Producer authorization: [issue comment 5628742071](https://github.com/mbelinkie/vera-script-to-timeline/issues/117#issuecomment-5628742071).
- Destination: Claude Design project `VERA design feedback`, clean successor
  chat while the accepted v2 artifact was selected.
- Submitted: 2026-09-10 at 22:57 EDT, once, as a 135-line pasted-text block.
- Exact body: `claude-s01-s03-wide-tight-amendment-prompt.md`, from the first
  line after its divider through EOF (including the final newline), 7,532
  characters, SHA-256
  `f15a0565ddac991fb844ba634bb6e80ed7f041ef2681d8fa3320e02ad8581f66`.
- Claude visibly entered active work after submission. No follow-up request was
  sent while the bounded amendment ran.

## Immutable comparison evidence

- #14 accepted artifact: `Script to Timeline - Two-Column Authoring S01-S03
  v2.dc.html` in `VERA design feedback`; accepted evidence commit
  `11cef62fad9800bdca2934343515dd9a0c3d5172`.
- #55 accepted contract-design evidence: commit `a561735`.
- #56 accepted ordered-visual contract-design evidence: commit
  `9e2b8817ffe97fbc9d6fcf31099aca578c5022bb`.

This slice does not edit or import any file from those accepted evidence sets.
The external v2 artifact remains the selected comparison baseline until Claude
creates the separately named v3 successor.

## Claude result

Claude created the separately named artifact
`Script to Timeline - Two-Column Authoring S01-S03 v3.dc.html` in the
`VERA design feedback` project and left the accepted v2 artifact available as a
separate comparison file. The retained artifact URL is:

<https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=Script+to+Timeline+-+Two-Column+Authoring+S01-S03+v3.dc.html>

The completed artifact exposes eight accessible two-option radio groups, one
for each ordinary or returning On Camera appearance in rows 2, 6, 7, 18, and
19. The retained explicit states are row 2 Wide/Wide, row 6 Wide/Tight, row 7
Tight/Tight, row 18 Wide, and row 19 Tight. Each group identifies the row,
appearance, continuous presenter recording, and picture-only meaning in its
accessible name. Row 6 now says `When we return to me`; the contradictory
`When we return to the wider view` phrase is absent.

Claude's retained run log records pointer and keyboard selection, Undo/Redo,
carry-forward creation, configured-still and no-still preview checks, hidden
thumbnail behavior, appearance/control mapping, overflow inspection, and both
requested viewports. The run was resumed after an execution interruption and
completed without a second user-authored prompt. A later Producer question
about an intermittent divider in the segmented control led Claude to remove
that decorative divider from v3; Claude explicitly reported that v2 remained
untouched.

Producer observation after completion: the temporary Wide fallback visual is
not suitable production artwork. The Producer treats that as a non-blocking
prototype-quality note to address when the real UI is created in ChatGPT, not
as a failure of this bounded interaction amendment.

## Independent regression

Repository gate passed under the pinned Node 24.19.0/npm 11.17.0 runtime:

```text
rtk npx -y -p node@24.19.0 -p npm@11.17.0 npm run validate
```

Generated contracts were current; TypeScript lint and typecheck passed; 141
contract tests, one tooling test, six progress tests, and 23 roadmap tests
passed; Python Ruff/format and strict mypy passed; and all 175 pytest tests
passed. The fresh worktree required `npm ci` from the existing lockfile before
the gate; package manifests and the lockfile did not change.

An independent accessibility inspection of the completed v3 confirmed eight
radio groups, 16 total Wide/Tight options, exactly one selected option per
group, the required eight explicit states, continuous-presenter and
picture-only accessible naming, and no framing group on any non-presenter
visual. The live artifact also retains the 22-row document, the 13 placeholder
cards, range controls, readiness, Undo/history, reorder controls, thumbnail
sizing, configured-still and no-still harness states, and the 1280×800 and
1024×768 harness states. Producer execution of the checked-in presence
checklist remains the closing authority.
