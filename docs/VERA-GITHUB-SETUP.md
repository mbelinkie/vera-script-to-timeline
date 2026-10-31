# Make the VERA master queue and milestones live on GitHub

**Scope:** VERA Research + VERA Script-to-Timeline. **Status:** dashboard is ready to *read* these values; **nothing has been changed on GitHub** by this patch.

The new dashboard reads the existing **VERA Research Roadmap (Project #1)** and **VERA Script-to-Timeline Roadmap (Project #2)**, and combines their issues into one read-only execution queue. The underlying repositories and issue numbers remain separate.

## 1. Create the GitHub Project fields

In the Projects that will provide queue data, add the following custom fields **with these exact names**:

| Field name | GitHub field type | Required? | Example | Purpose |
|---|---|---|---|---|
| **Queue Order** | Number | For every committed/queued issue | `10`, `20`, `30` | Unique, **global** position across both Projects. Positive integers only. |
| **Program Milestone** | Text | For every queued issue | `01 Research validated` | Groups issues across repositories into a single milestone. Match the spelling exactly. |
| **Milestone Order** | Number | Optional | `1`, `2` | Explicit milestone sequence. Give every issue in the same milestone the same value, or leave it blank to order by earliest queued issue. |

**Size is already supported.** The dashboard uses the existing GitHub Project **Size** value (typically `XS`, `S`, `M`, `L`, or `XL`), shows it next to every queued issue, and provides a Size filter. `XXL` displays as **Huge**. Missing values display **Unassigned**, and any custom Size values are shown literally. This is a relative estimate, not a calendar duration. No new Size field is necessary if your existing boards already have it, but make sure queued issues have a size assigned before relying on the view for planning.

Suggested approach: retain the existing two boards as they are today, and apply these fields where issues actually live. As implementation approaches, **Project #2 can also hold selected Research issues** to serve as the shared planning view. The dashboard de-duplicates identical GitHub issue URLs appearing on both boards; if the same issue has conflicting queue/milestone values, it shows a warning rather than silently choosing an order.

**Do not use GitHub issue numbers as queue positions.** Issue #75 and Issue #75 in different repositories are different issues. Positions like 10 and 20 are **one global sequence** across both repos, not separate sequences per board. Leave exploratory/backlog items unnumbered until committed to the execution queue.

## 2. Link real issue dependencies

On the dependent issue in GitHub, use **Relationships → Mark as blocked by** to point at its prerequisite issue (including one in the other repository). Use **native GitHub issue dependencies**, not only text in the issue body. The dashboard reads GitHub's `blockedBy` GraphQL relationship.

**Hard invariant:** every prerequisite must itself have a `Queue Order`, and its value must be **strictly lower** than the dependent issue's order.

Example:

| Queue Order | Repository | Issue | Blocked by |
|---|---|---|---|
| 10 | Research | Validate input specification | — |
| 20 | Research | Approve research output | 10 |
| 30 | Script-to-Timeline | Implement verified input | 20 |
| 40 | Script-to-Timeline | Integration tests | 30 |

If the research issue is missing a queue position, or is ranked after the implementation issue, the dashboard will flag it. Duplicate ranks are also flagged. A circular dependency necessarily violates a valid ordering and will be reported as a conflict. **The dashboard does not change ranks for you.** A future queue-management command must implement stable topological reordering and atomic renumbering before GitHub changes can be guaranteed to obey the invariant.

## 3. Define meaningful program milestones

Start small: for example, `01 Research validated`, `02 Implementation foundation`, `03 Integrated end-to-end flow`, `04 Beta ready`. These are **illustrative names**, not pre-existing VERA commitments. Define clear exit/acceptance criteria in a tracked GitHub goal issue or milestone description, and assign each delivery issue the correct **Program Milestone** field.

Milestone progress currently means **Done issues / all assigned issues**, not weighted effort. Repo-specific GitHub Milestones are separate from the custom **Program Milestone** field and do not automatically populate it.

Keep the existing Project status vocabulary (especially `Done`) and the existing `type:`, `model:`, and `effort:` labels required by the current VERA progress parser. Research issues placed on the other board must meet that schema as well, or the existing fail-closed checks may reject them.

## 4. Permissions and verification

The dashboard runs with your Mac's GitHub CLI login (`gh`). It needs to read **both GitHub Projects** and the **issues/dependencies in both repositories**. For private repositories, ensure your CLI authentication grants the appropriate repository read access and GitHub Projects read permissions. Check with:

```sh
gh auth status
gh project item-list 1 --owner YOUR_GITHUB_USERNAME --limit 500 --format json
gh project item-list 2 --owner YOUR_GITHUB_USERNAME --limit 500 --format json
```

Your project owner and project numbers are read from `.github/vera-roadmap.json`, not hard-coded in the patch. If a field doesn't appear in the JSON, confirm its spelling and that your GitHub CLI is current.

Run the dashboard:

```sh
npm run test:progress
npm run progress -- --serve --open
```

Or double-click **Open VERA Progress.command**. It automatically checks for new data approximately every **15 minutes** while the browser tab is visible; **Refresh now** can force a check. Keep the Terminal window open for the local server.

## 5. What the dashboard will and will not do

**Now:** one ordered cross-repo queue; repository/status/size filters; a readable Size column (XS–XXL or custom values); milestone progress; links to Github issues; warnings for duplicate/missing/reversed ranks; verification of native `blockedBy` links; live refreshing; no invented milestones or queue positions. If dependency reads fail, it explicitly says the audit is incomplete, retaining the previous successful dashboard snapshot as appropriate.

**Not yet implemented on GitHub:** bulk issue edits, automatically moving dependencies, automatic number reindexing, milestone creation/management, or enforce-before-save queue edits. To *guarantee* the invariant for future GitHub edits, those operations need to be implemented in the existing `scripts/roadmap.mjs` workflow or a GitHub Action. Until then, the dashboard **detects** problems and a human or agent must correct them.

**Useful official documentation:** [Project number/text fields](https://docs.github.com/en/issues/planning-and-tracking-with-projects/understanding-fields/about-text-and-number-fields) · [Creating issue dependencies](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-issue-dependencies) · [GitHub CLI Project item listing](https://cli.github.com/manual/gh_project_item-list).
