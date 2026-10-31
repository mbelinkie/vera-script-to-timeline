# VERA master roadmap — GitHub setup checklist

**Dashboard status:** The local dashboard is ready. GitHub Projects and issues still need the data below; the dashboard **does not edit GitHub**.

## Required GitHub changes

1. **Keep the two existing Projects:** VERA Research Roadmap (#1) and VERA Script-to-Timeline Roadmap (#2). Issues remain in their own repositories. An issue can be added to both Projects if useful; the dashboard shows it only once in the shared queue.
2. **Add custom Project fields** (exact names) where you will queue issues:
   - `Queue Order` — **Number**, positive, unique **across both Projects** (e.g. 10, 20, 30).
   - `Program Milestone` — **Text**, exact same name for all issues in the milestone (e.g. `01 Research validated`).
   - `Milestone Order` — **Number**, optional, to explicitly sequence milestones (e.g. 1, 2, 3).
3. **Size each queued issue** using the existing Project `Size` field. The dashboard displays `XS` (Extra small), `S` (Small), `M` (Medium), `L` (Large), `XL` (Extra large), or `XXL` (Huge), and allows filtering by size. Unknown/custom sizes display verbatim; blanks say *Unassigned*. The sizes are estimates of relative scope, not predicted durations.
4. **Link real dependencies:** In each dependent GitHub issue, use **Relationships → Mark as blocked by**. This works for Research-to-Implementation dependencies too. Every prerequisite must have a **strictly smaller Queue Order** than its dependent ticket.
5. **Define milestone exit criteria:** Use a tracked goal issue or description. Assign every committed delivery issue to a `Program Milestone`. Leave uncommitted research discoveries and backlog issues without `Queue Order` until they are scheduled.
6. **Preserve current issue metadata:** Existing Project statuses including `Done`, and the required `type:`, `model:`, and `effort:` labels. The current parser expects these.

## Example queue

| Queue Order | Repository | Work | Size | Program Milestone | Blocked by |
|---|---|---|---|---|---|
| 10 | Research | Validate method | M | 01 Research validated | — |
| 20 | Research | Approve results | S | 01 Research validated | #10 |
| 30 | Script-to-Timeline | Implement validated method | XL | 02 Implementation | #20 |

## Activate and verify

- Check `gh auth status` on your Mac; the GitHub CLI must be authorized to **read both Projects and both repositories**.
- In the local repository, run `npm run test:progress` and double-click `Open VERA Progress.command`, or run `npm run progress -- --serve --open`.
- The live view checks GitHub about every **15 minutes** while open. Use **Refresh now** to request a fresh snapshot immediately.
- Confirm the master queue shows issue sizes, milestones, and dependency status. Investigate warnings for missing/duplicate ranks or bad dependencies.

**Not implemented yet:** Changing queue order, inserting surprise detours, auto-renumbering, and enforcing dependency-safe writes **on GitHub**. The dashboard detects invalid ordering, but it does not fix it. Those write operations need to be added to the existing `scripts/roadmap.mjs` automation or a GitHub Action before the queue is self-maintaining.

For implementation details, see [VERA-GITHUB-SETUP.md](./VERA-GITHUB-SETUP.md).
