# S05 guided redesign brief — create and update a Resolve timeline

This brief concerns only S05 in the existing Claude Design artifact:

`Script to Timeline - Prompter Runtime and Suite Navigation S04-S06.dc.html`

Do not edit S04, S06, or the accepted S01–S03 artifact. Do not begin redesigning
S05 immediately. First use your own product-design and interaction-design
skills to synthesize the requirements below, propose a plain-language page
concept and user-facing name, and ask Matthew only the questions whose answers
would materially change the design. Wait for his answers in this Claude chat.
Then design S05 from those answers rather than mechanically implementing this
brief as a wireframe specification.

## Why S05 needs rethinking

The current page feels like an internal capability diagnostic rather than a
producer workflow. Labels such as `Runtime boundary`, `Trusted local agent —
producer workstation`, `Capability facts`, and `acknowledged revision` are
accurate implementation language but confusing user-facing language.

The page needs a self-explanatory name and a clear answer to: what can the user
do with the current script and its linked DaVinci Resolve timeline right now?

## Product model already decided

There is no hard Preview-versus-Release cutoff in the normal workflow. The
script is continuously saved to the cloud. A producer may:

1. create a Resolve timeline from the current script;
2. edit that timeline in Resolve;
3. return to VERA and change or add script content;
4. update Resolve again; and
5. repeat until finishing in Resolve.

The two primary user jobs are therefore:

- **Create timeline** — make the first Resolve timeline from the current script.
- **Update timeline** — send selected later script changes to a timeline that
  may also have been edited in Resolve.

An update must create a new version beside the existing timeline rather than
overwrite it. Both the script and timeline may have diverged. The interface must
not imply that one side is automatically authoritative or that VERA can safely
reconstruct every Resolve edit.

The update review is row-based. Each proposed script-to-timeline change gets a
checkbox so the user can apply only a selected portion. The design should make
the scope and consequence of each selected change understandable before the
new timeline version is created.

Both Producer and Editor roles may create or update a timeline. The current
user's authorization, Resolve availability, and edition may still change which
actions are possible, but user-facing copy should describe the practical
result—not expose infrastructure jargon.

## Resolve editions and connection facts

The browser remains the authoring application. Some Resolve operations require
a small local VERA helper on the computer running Resolve, but `trusted local
agent` should not be the primary user-facing concept or page title.

- With a supported connected Resolve Studio installation, VERA may be able to
  create or inspect a linked timeline through Resolve's supported scripting
  surface.
- Resolve Free stops at a verified import/update package that the user imports
  manually in Resolve. Do not claim Free UI automation or automatic in-Resolve
  verification.
- If Resolve is closed, external scripting is unavailable, the helper is
  disconnected, or the version is unsupported, explain the concrete next step
  in ordinary language. Do not present a matrix of `capability facts` as the
  main experience.

## Critical open capability boundary

Do not assume that VERA can fully compare against an arbitrarily edited Resolve
timeline. There are at least three distinct evidence levels:

1. the last script revision and timeline snapshot VERA created;
2. the current linked Resolve timeline structure that a connected supported
   Studio integration can actually inspect; and
3. the producer's editorial intent, which cannot always be inferred from item
   positions, trims, deletions, replacements, effects, or track organization.

The design must state honestly which evidence is being compared. It must never
say `VERA compared your current script with the linked Resolve timeline` unless
the represented capability genuinely inspected the current timeline. Where
that capability is absent, describe comparison against VERA's last created
version and explain what the user must verify manually.

Treat a full current-timeline diff as an unresolved capability question, not a
guaranteed feature. Ask Matthew what degree of timeline inspection he wants the
prototype to assume, and help him understand the design consequences of the
available choices.

## Possible inbound editing workflow

There may be a useful editing-mode feature that reviews changes made in Resolve
and proposes corresponding script changes—for example, detecting that a spoken
section was cut in editing. Nothing should update the script automatically.
Every proposed inbound change requires human review and explicit approval.

Ask Matthew how accepted Resolve-originated cuts should be represented in the
script: deleted, moved to Extras, marked as an accepted cut, or handled another
way. Also distinguish exact, high-confidence relationships from ambiguous edits
that VERA must not guess about.

This inbound workflow may deserve a separate action such as `Review Resolve
changes` rather than being folded invisibly into `Update timeline`. Use your
design judgment and discuss the tradeoff with Matthew before choosing.

## Questions the design should resolve with Matthew

Do not recite these mechanically if you can combine or sharpen them. Ask only
questions that change the resulting experience, such as:

- What current-timeline inspection capability should this prototype assume for
  connected Resolve Studio?
- Which editor changes must VERA preserve when making the new timeline version?
- When script and Resolve changed the same section, what choices should the user
  see rather than a guessed merge?
- What should accepting a Resolve-originated narration cut do to the script?
- Should `Review Resolve changes` be a separate workflow or part of Update?
- Which exceptional connection/edition states need to appear in the main flow,
  and which belong in secondary troubleshooting?

## Design direction, not a prescribed layout

Use your own design skills to choose the information architecture, page name,
progressive disclosure, comparison presentation, selection controls, empty and
problem states, and responsive behavior. Optimize for a producer who understands
scripts and editing but does not need to understand VERA's architecture.

Prefer visible language such as `Create timeline`, `Update timeline`, `Resolve
connection`, `Changes in the script`, `Changes in Resolve`, `Keep`, `Apply`, and
`Needs your decision`. Avoid `runtime boundary`, `capability facts`, `trusted
local agent`, `live head`, `acknowledged revision`, `durable job`, and similar
system vocabulary unless it appears only under optional technical details.

Keep all actions simulated. Do not claim a production comparison, connection,
import, build, update, background job, or Resolve mutation. Validate the chosen
design at internal 1280 × 800 and 1024 × 768, including a long row list,
conflicting changes, partial selection, unavailable/Free/Studio routes,
keyboard focus, non-color state communication, and no horizontal overflow.

This guided redesign remains Producer review material. It does not constitute
acceptance and must not mark issue #58 Done.
