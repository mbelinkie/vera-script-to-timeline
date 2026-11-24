# Issue filing and bug classification

File confirmed product defects under `type:bug`. The legacy `bug` label still
identifies a defect. Add the canonical label before moving the issue to Ready
or claiming new work. Incomplete issues can stay in Inbox. Leave existing active
claims in place.

- Confirm the defect before filing and look for an existing remediation issue
  for the same root cause. Record expected and observed behavior and one focused
  regression check. Explain the impact, urgency and effect on the release.
- Set one severity. `severity:high` covers serious data-integrity or
  essential-workflow failure. `severity:medium` covers material bounded impact
  or a workaround. `severity:low` covers minor impact.
- Set one priority. `priority:P0` is immediate, `priority:P1` is before the
  affected release, `priority:P2` is planned, and `priority:P3` is low urgency.
  When the Project Priority field is set, use the same P0–P3 value.
- For audit remediation, apply `source:audit` and record independently verified
  finding IDs, links to the original issue or report, and historical discovery
  severity. Select **audit** in Timeline’s **Issue origin** field. In a plain
  GitHub issue, put this exact field at the top of the body:

  ```markdown
  ### Issue origin

  audit
  ```

  Retain the remediation’s existing owner, routing, dependencies and defensive
  security-review boundaries. Audit origin does not authorize a Zodex, Codex or
  paid-service run.

Both repositories reconcile one bot warning against the current issue labels
and the structured audit origin. The workflow leaves label choices to the
filer and clears its warning after correction. Timeline's `npm run roadmap --
ready <issue>` and `npm run roadmap -- claim <issue> --branch <branch>` also
check the Project Priority when it is set.

### Manual Ready and claim in GitHub

Research issues use the Research GitHub Issues page for filing and its Project
for manual Ready and claim. Apply the labels on the issue, add it to the Project
as Inbox, and record the evidence and rationale above. Before moving to Ready
or claiming from the Project, open the issue and check the canonical label,
the single valid severity and priority, the audit label and evidence where
applicable, and any Project Priority against the priority label. Correct any
classification warnings. Apply the existing routing, acceptance, dependency
and ownership checks before changing Status or recording a claim. Use the same
manual checks for direct GitHub Project operations in Timeline.
