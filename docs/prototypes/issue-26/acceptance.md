# Producer acceptance and future prototype regression script

The dossier review below is executable now as a document walkthrough. Sections
2–5 define tests for a later authorized #14 artifact; **none is a claim of
completed browser, accessibility, capture, media, or Resolve testing in #26**.

## 1. Producer review of this dossier

Open `docs/prototypes/issue-26/README.md` on the committed review branch named
in issue #26. No application installation or private document is needed.

1. Read README §1 and follow the pinned A13, A24, K24 and A27 links plus their
   acceptance records. **Expected:** exact accepted revisions, not live or
   historical draft assumptions; S is pinned to baseline `163ecfa`.
2. Review README §2 R01–R24 and D24-01 through D24-19. **Expected:** every
   retained requirement has an exact section/decision, phase/slice, scenario
   and owner, including forbidden shortcuts. Check especially source-owned
   visual authority, no frozen-v1 change, and no implicit schedule revival.
3. Open `scenario-spine.md` §1 and walk S01→S06 with `content-kit.md` open.
   **Expected:** a writer can open/read/write without a workstation; F04
   stays one paragraph through OC→VO→OC; coverage and build boundaries are
   honest. No layout or token choice is embedded in these requirements.
4. Read S07→S11 and the role/runtime tables. **Expected:** Viewer changes
   nothing, Editor cannot Release, Producer needs an approved checkpoint,
   browser capability does not confer local execution, and separate Research
   authorization survives suite navigation.
5. Check S12→S19 and the K24 fourteen-view crosswalk. **Expected:** all accepted
   content families have a focused test; later-phase examples are explicit.
   S15 retains conceptual Periodic history while A27 keeps production
   execution deferred; S16 keeps independent capture/clip/treatment identities.
6. Review `content-kit.md` F01–F35 and E01–E14. **Expected:** K24-only fiction,
   neutral operational placeholders, `.invalid` story links, no private prose,
   title, source identifier or absolute local path. IDs are review aliases,
   not additions to contracts or fixtures. Resolve any inappropriate slot
   before supplying the packet to Claude.
7. Review this file §§2–5, README §3 and `claude-packets.md`.
   **Expected:** deterministic reset/action/result/evidence at both widths;
   keyboard/a11y/absence checks; O01–O03 gates before high-fidelity work;
   O04–O06 leave visual decisions and acceptance to Claude/Producer;
   O07–O09 do not silently decide new product semantics.
8. Reply on #26 with **`Accepted`** to accept this committed dossier as #14's
   semantic input, or **`Correction: <first authority/scenario/content ID> —
   <observed mismatch and intended meaning>`**. Producer judgment, including
   completeness and appropriateness of scope, remains authoritative.

Automated evidence obtained by the agent belongs in the #26 review comment
and its linked commit: source-byte checks, reference/coverage checks, privacy
and scope review, whitespace and `rtk npm run validate`. Those checks cannot
substitute for these eight Producer steps. #26 stays In review pending the
explicit response; its agent does not close it.

## 2. Deterministic test setup for #14

Required precondition: Producer-accepted dossier and all #14 prerequisites,
including #21 token output, accepted artifact/reference versions and runtime
names. Use only local design simulation; `.invalid` URLs must never initiate
capture, fetch, upload, media import or Resolve control.

For each S01–S19 in order:

1. Load the approved artifact's reset state from content-kit §3. Record artifact
   revision, suite-contract revision, accepted token revision, scenario, phase,
   role, runtime and content IDs. No preexisting cookies, personal projects,
   real files or history are test inputs.
2. Set the **actual content viewport** to `1280 × 800` CSS pixels at 100% zoom;
   record measured rendered width/height as well as the scenario label.
   Repeat the same reset and actions at `1024 × 768`. A width label alone is
   not proof of viewport size. Any embedding chrome must be accounted for.
3. Run the scenario actions in §3 once with pointer input. Reset and run them
   again using only keyboard navigation/activation and text selection.
4. Use Tab/Shift+Tab to traverse discoverable controls; Enter/Space activate
   their native equivalents; arrow keys operate the selected pattern. Use
   the artifact's documented text-selection method for exact ranges. The
   keyboard route must be independently discoverable; a hidden pointer click
   to focus the editor is not acceptable.
5. For every active state apply K01–K08 in §4; inspect accessible names/roles,
   DOM presence and reading order as well as pixels. Reset before an alternate
   role, runtime or failure branch so an earlier action cannot mask a bug.
6. Record expected vs observed for each numbered action. A missing branch is
   `Not demonstrated`, not Pass. Stop that branch at its first mismatch and
   retain the minimal reproducible sequence and authority/content ID.

No fixed Tab count or pixel coordinate is supplied because that would decide
navigation order or geometry. The reproducible selectors are scenario,
semantic control name/role, content ID, and exact narration phrase. #14 must
record its proposed names/keyboard route before execution; the Producer judges
whether that route is logical and discoverable.

## 3. Scenario actions and expected results

Every cell below is ordered: reset, perform each numbered action, compare the
stated result, then reset for the next branch. Unrelated incomplete content
is explicitly outside the branch's active test subset (content-kit §3).

| Test | Ordered actions and expected results |
| --- | --- |
| S01 | 1. As Phase 2 writer/no-agent choose F01 and open F02 → readable script, clear authorized context. 2. In empty E14 type F03 and F02 heading → normal authoring without install gate. 3. Acknowledge save then simulate reload → same acknowledged text/order/IDs. Loading/empty/unavailable entry states offer relevant explanation/retry. |
| S02 | 1. Select F04 and edit then undo/redo one word → ordinary prose edit, no row-induced split. 2. Mark `the reading begins to drift` OC, leaving earlier OC then VO ranges → exactly OC→VO→OC in one paragraph, state readable without weight/color. 3. Inspect F05/F32/F35 → Direction, excluded note, left-only/right-only/paired/blank retain distinct meaning; blank has no invented pause or missing-visual error. |
| S03 | 1. Reset F04 with its base VO interval but no coverage → explicit coverage error. 2. Add full-frame placeholder over selected VO words → coverage satisfied as explicit unresolved intent; no claim media is ready. 3. Attach F07's two ranges, navigate words→card→words → exact bidirectional relationship, paragraph intact. 4. Reset with only overlay over VO → error remains; overlay on OC is allowed. 5. Inspect E12 timing forms and contradiction → three valid derivations, then blocking conflict; no frame precision claimed without verification. |
| S04 | 1. Preview prompter from F03/F04/F10 with F34 included → only spoken wording plus initial/change OC/VO markers and visible non-spoken PAUSE/pronunciation cues. 2. Toggle annotation inclusion and optional section labels → controlled non-spoken differences; F05/F06/F28/F32 and source transcript never enter spoken text. 3. Repeat same revision/settings → identical simulated export content/sidecar identity; no real export performed. 4. Remove camera assignment → export blocked. 5. Remove F28 target → unplaced warning with reattach/dismiss, zero duration and no silent deletion. |
| S05 | 1. For this build branch set connected agent + Free, then make Revision B local-only → show local changes then syncing; Preview waits in this branch. 2. Acknowledge B → synced, simulated Preview freezes B. 3. Advance live head → source remains B with newer-live indicator. 4. No-agent branch → writing works, local execution controls absent, workstation explanation readable. 5. Simulate an authorized job already running, close/reopen browser view → same job/source/stage, not cancellation or duplicate. |
| S06 | 1. Activate Research product switch by pointer, then fresh-reset keyboard → new tab intent, source context intact, accessible destination disclosed. 2. Inspect simulated handoff payload → only allowed opaque context categories, no content/credentials/locators/permissions. 3. Exercise destination one/many/none linked projects → reauthorized target, authorized chooser, or normal home. 4. Repeat unauthorized/stale/archived/unlinked/unavailable and reciprocal Research→Script entry → safe fallback, no hidden names or automatic link; project switch remains a different action. |
| S07 | 1. As Viewer read complete F01, Ideas/Extras, history, comments, build results → content/status accessible. 2. Inspect DOM and keyboard routes for each matrix mutation family → editing, Insert/range mutation, comment compose/reply/resolve, checkpoint mutation, Preview/Release/settings/local execution absent. 3. Reset Editor, simulate role removal/demotion on next request → write session ends promptly, no accepted mutation or recovery-export invention. 4. No-membership reset → nonrevealing denial rather than cached protected content. |
| S08 | 1. As Editor inspect presence and local changes/syncing/synced/offline/sync failed → states distinct; presence never changes document identity. 2. In F03 simulate Editor removing `quiet` and Producer removing `moving`; Editor undo restores only `quiet`, so Producer's removal survives reconnect. Separately merge a change removing F04 VO coverage → preserve text and expose coverage conflict. 3. On F33 reply, mention Editor, resolve, reopen → attributed thread operations and stable mention identity. 4. Remove anchor text → stale; explicitly reattach → named new target, never nearest text. 5. Compare prompter/build before/after comment operations → no difference; included F34 remains visible non-spoken annotation only. Test anchor kinds text, card, Idea, Extra and between-block point. |
| S09 | Use connected agent + Free for submission branches. 1. Editor names Checkpoint A → all surfaces/source identity materialized, Release absent. 2. Producer attempts Release on unapproved A → rejected, no build created. 3. Approve A then simulate Release → frozen A source/dependencies/output identity. 4. Edit live head and inspect five version layers → checkpoint, dependency, build and delivery unchanged. 5. Restore A → new Revision C, intervening B and prior builds/comments/history retained. |
| S10 | 1. Start Ideas-only E14; add child/sibling, indent/outdent, reorder, collapse/expand F30 → outliner meaning distinct from section navigation. 2. Promote to chosen Draft position → backlink/incorporated state; only inserted Draft content becomes eligible. 3. Move a whole test block to Extras → same identity, atomic move, output excludes it. 4. Inspect F31 under F02 and in global Extras → one identity, no duplicate. 5. Restore at chosen point → stale visual reference explicit; explicit duplicate instead → new identity. Ordinary delete remains undoable deletion, not silent Extra creation. |
| S11 | 1. Producer + connected Free → Prepare Resolve timeline, verified package, ready_to_import and manual checklist; no Studio execution controls or automated placement claim. 2. Confirm import in simulation → user-confirmed label, never automated Free verification. 3. Supported Studio reset → Build in Resolve and requested stages; target busy waits serially. 4. Closed Resolve/scripting off/mismatch/disconnected resets → invalid execution absent, retained package/job waiting with remediation. 5. Render failure → verified timeline retained; retry render only. Upload failure → verified MP4 retained; retry upload only, sharing unchanged. Unrequested stages labeled skipped; cancellation reports boundary, not erased artifacts. 6. Editor + Studio → Preview only, Release absent; no-agent writer still edits. |
| S12 | 1. Authorized Editor searches allowed K24 phrase/Topic filter → result count/excerpt; clear/no-results/loading/error paths distinct. 2. Insert F19 twice → separate occurrence IDs, same Research evidence. 3. Refine one from logged 00:24–00:32 inward to simulated 00:26–00:30 → only its excerpt/use changes, explicit precision; other use stays 00:24–00:32. Reset returns full range; out-of-bounds rejected. 4. Show update available → keep snapshot/update reference/compare, never silent retarget. 5. Revoke Research access → restricted search/data access denied despite authoring membership. 6. Media plan branches verified reuse, missing locator, invalid located hash, incompatible package → accurate counts/estimated disk and verified locate/re-export/block policy; intent/evidence retained, no canonical package move. |
| S13 | 1. Inspect F35 and classify right-lane content → Picture parent with Unresolved visual/Clip/Image/Capture/YouTube page composite/Graphic versus Audio/Citation/Editor note/Draft note/Reference/Comment; text/icon/name distinguish them. 2. Preview a role change → fields and output meaning change explicitly, not by formatting. 3. F25 duration+end → derivable timing; F26 duration-only → Unplaced/incomplete and Release blocked. 4. Reset between attach exact start/end, park in Extras, and dismiss choices → explicit result, no default nearest-row binding. 5. E12 start+end, start+duration, duration+end each yield [0s,4s]; adding duration 3s to start 0s/end 4s → conflict, no silent correction. Citation/Reference/marker remain zero picture duration. |
| S14 | 1. F07 → both clips consecutive with separate audio policies. F08 → no implicit first choice; select B then clear → zero/one enforced. 2. Unresolved F08 Release → blocked; Producer Choose in Resolve policy → explicit choice handoff. Preview reports unresolved selection without pretending a candidate won; exact placeholder policy remains O07. 3. F09 → all organized alternate tracks plus choice marker, never sequence. 4. F23 choose B → only B in active Draft/prompter/build, A/C readable and retained. 5. F24 pending cut → `final` still active; accept → parked attributed content; fresh-reset reject → normal text. 6. Apply ordinary bold/italic/underline/highlight/color formatting → no OC/VO/role/selection/build change; no decorative strikethrough action. |
| S15 | Set connected agent for simulated acquisition branches; never acquire real bytes. 1. F14 upload vs F15 linked acquisition vs F16 screenshot → Image roles; linked acquisition automatic, no separate download command; progress/verification/failure/retry visible. 2. F27 import/relink/replace with simulated success/failure → durable evidence only after verification; intent retained, no path. Local move-removal failure reports effective copy and cleanup warning, never completed move. 3. F11 Now creates B candidate; explicit select changes Draft, prior builds stay A. Conditional capture-and-use with changed expected Draft leaves B unselected. 4. On build pins B only to new build; failed capture blocks or requires explicit named older revision, never silent fallback. 5. Safe-warning C → review_required; Editor preview acknowledgment permitted, release acceptance Producer-only; hard denial/integrity failure yields no revision. 6. F13 concept shows Periodic/protected bounded history, but no executable schedule/frequency/prune controls. Remove user pin from E08 → checkpoint/build/evidence protection remains; no policy means retain all. Stored-byte identity is not a promise of identical live-page recapture. |
| S16 | Set connected agent for simulated capture/composite branches. 1. From compatible F20 choose Present on YouTube page → one composite with moving-clip intent, description/two comment slots and separate clip/page/template identities. Refresh page now → new selected page revision if conditional selection remains valid; clip range/audio/transcript and old build unchanged. 2. F12 Add spotlight: choose OCR words/lines, adjust padding/rounding and compare manual rectangle → source-relative union and previewed inverse matte, exact interval, confirmed immutable matte evidence. 3. Set Slow zoom to Center, then F14 manual point, then confirmed Spotlight; Zoom to spotlight aligns segment interval → start/end crop and explicit clamp, no empty canvas. 4. Add ordered segments then contradictory overlap → Release conflict. 5. Source revision change → manual focus needs review; ambiguous remap → Spotlight/motion stale. Reset branches Keep previous capture / Accept remap / Redraw → explicit new evidence/selection; old revision remains valid. 6. Inspect output model → source/composite, matte, whole-picture motion; generated nest/verified matte baseline and honest simulated Studio/Free fallback, no native-mask dependency. |
| S17 | 1. F17/F18/F22 show editable semantic inputs, demo-v1, citation relationship, derivation note and pinned template A; no screenshot-only chart. 2. Target manifest exposes two bars and row:west, labels/kinds/states/binding evidence → no node-name authoring. 3. Preview bar 1 then bar 2, and separate row cue → base/active/transition/reset; start-only cue explicitly ends at next cue or Graphic end. 4. Disjoint targets overlap → allowed; same-target contradictory states → blocking conflict; missing target → actionable error. 5. B update available → A remains until explicit migration; invalid package/input → declared tested fallback or block, never latest substitution. 6. Inspect simulated Studio schedule/Free declared representation and frozen provenance; F21 missing audio → Release blocked, fictional license note does not imply rights clearance. |
| S18 | 1. Inspect independent presenter→B-roll/B-roll→presenter/B-roll→B-roll defaults; Apply to everything then edit one → other two remain independent. 2. Set explicit boundary override → resolved order override/event-type/project/hard-cut observable. 3. Insufficient handles → shorten/extend/use-cut choices, never moved narration. 4. Secondary timing adjustment is explicit and precision-labeled; paragraph/anchors unchanged; audio unchanged without explicit audio intent. |
| S19 | 1. Open the component-state inventory → every listed family/state has a scenario demonstration or an explicit scoped later-phase label; no silent omission. 2. Run K01–K08 against each instantiated primitive and the named failure states. 3. Compare adopted suite version and symbolic/accepted token references → no independently invented token value or renamed Research page. 4. Check role/capability absence for every action family at both widths; a screenshot alone is insufficient. |

## 4. Keyboard, accessibility and viewport checks

These are behavior assertions, not chosen visual implementations. #14 must
supply the exact accessible names, keyboard route and evidence for its proposal.

| Check | Actions | Required evidence |
| --- | --- | --- |
| K01 — Names, roles, state | Inspect each actionable control, Picture subtype, status, selected range and relationship. Read through a screen reader/accessibility tree. | Meaningful name/role/value/state; icons not sole names; focus/selection/current product and new-tab intent discoverable. Status, OC/VO, role and errors survive removal of color cues. |
| K02 — Keyboard reachability | Tab forward/backward from document entry; operate controls with native keys; select exact phrases and traverse linked card↔words. | Logical focus order, visible focus, no traps outside an intentional modal; all pointer actions have equivalent keyboard route, including OCR words, manual geometry/focus-point edits and drag/reorder operations. No coordinate or keyboard implementation is mandated here. |
| K03 — Dialogs and confirmation | Open a named dialog by keyboard; inspect initial focus; cycle forward/backward; exercise documented Escape/cancel/commit; reopen from a different trigger. | Correct modal/nonmodal semantics, contained focus only for modal, no inaccessible background, disclosed Escape policy, focus returns to relevant trigger or documented valid fallback after removal. Confirm/cancel never performs a real side effect in the prototype. |
| K04 — Status/error announcements | Trigger sync, validation error, acquisition progress/failure, stale anchor and build completion. | Readable cause and permitted remediation; relevant programmatic announcement without unexpected focus theft or repeated progress spam; terminal vs retryable/waiting distinct. |
| K05 — True viewport/reflow | Execute every S test at both measured widths; inspect long narration, cards, menus, dialogs, status, inspector and history. Repeat at browser text/zoom enlargement and record actual setting. | Readable untruncated meaning, operable controls, logical reading/focus order, no clipped critical content or inaccessible overflow. Compact is real reflow, not a scaled screenshot; precise composition remains Claude/Producer choice. |
| K06 — Contrast, motion, disclosure | Review with the accepted token set; enable reduced motion; inspect tooltip/help content using keyboard as well as pointer. | Contrast/focus evidence tied to accepted suite/token version; no essential information motion-only, reduced-motion behavior verified; help reachable without hover. No color/animation values chosen by #26. |
| K07 — Permission/capability absence | For S07/S11 and every matrix action family, search DOM/accessibility tree and keyboard traversal after role/runtime changes. | Unauthorized controls are absent, not disabled or hidden-but-focusable; context explanations remain. A stale event handler cannot accept a mutation after revocation in the simulated request model. This is UI evidence, not proof of server security. |
| K08 — Semantic output boundaries | Compare active content, status and simulated output identity before/after comments, formatting, variants, Extras, capture refresh and retries. | Excluded content stays excluded; intended edits only; frozen identities unchanged. Meaning matches R/D24 rows, not just visual resemblance. |

## 5. Evidence ledger for later #14 execution

Record one row per action/branch and viewport; link a screenshot plus keyboard
route and accessibility/DOM observation where relevant. A screenshot cannot
prove absent controls, focus behavior, data authorization, or immutable builds.

| Artifact revision | Test/action | Phase | Role | Runtime | Viewport measured | Content/reset | Pointer result | Keyboard + K checks | Evidence | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pending #14 | Sxx/action n | Owning slice | Named role | Named capability | CSS width × height | F/E IDs | Not run | Not run | None in #26 | Not demonstrated |

Pass requires every required action and K check at both widths, with any
source-owned exception explicitly accepted by the Producer. Later visual
approval must name the artifact/version, accepted scenarios and remaining
follow-up work. It never certifies production authentication, persistence,
compiler, capture engine, Fusion or Resolve behavior from a design simulation.
