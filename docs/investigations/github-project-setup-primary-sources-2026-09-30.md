# GitHub Issues + Projects setup: primary-source notes

Reviewed 2026-09-30 against the current GitHub.com documentation. This is a
source note for a reusable, LLM-agnostic playbook, not a historical guarantee
of documentation contents. No GitHub state was changed. Scope: documented
API budgets, pagination, authentication, automation, and issue relationships.
No product contracts, fixtures, dependencies, or accepted tests are touched.

## Rate limits: keep three different measurements separate

| Budget | Ordinary authenticated user | What is counted |
| --- | --- | --- |
| REST primary | 5,000 requests/hour | Requests; some resource families, including search, have different limits |
| GraphQL primary | 5,000 points/hour | Query cost based on connections; minimum one point |
| Secondary | Endpoint, concurrency, CPU, and content controls | A separate request-point calculation and additional limits |

Sources: [REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
and [GraphQL rate and query limits](https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api).

GraphQL mutation requests cost **five secondary points**; requests without
mutations cost one. That does not mean every mutation costs five primary
points. Estimate primary cost by adding requests needed for each unique
connection, dividing by 100 and rounding; inspect `rateLimit.cost` for actual
query cost. Nested connections can multiply cost. Formula and limits can
change. GraphQL rate errors can arrive with HTTP 200, so inspect the error
payload, not status alone. [GraphQL limits](https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api)

Secondary controls currently include a shared REST/GraphQL ceiling of 100
concurrent requests; 900 REST endpoint points/minute versus 2,000 GraphQL
endpoint points/minute; 90 CPU seconds per 60 seconds, at most 60 for GraphQL;
and generally 80 content-generating requests/minute and 500/hour, including
web UI activity. Lower endpoint limits and undisclosed triggers exist.
These are ceilings, not promised safe throughput. [REST limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)

Use the response's `x-ratelimit-*` headers as authority; counts may vary by
region and need not decrease monotonically. `GET /rate_limit` is a periodic
overview, can disagree with response headers, and consumes secondary budget
despite exemption from primary budget. No secondary-status query exists.
[REST limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)

## Practical pacing and pagination

GitHub recommends serial requests and at least one second between mutations.
For rate-limit failures, obey `retry-after`; if primary remaining is zero,
wait until `x-ratelimit-reset`; otherwise wait at least a minute, then use
bounded exponential backoff if secondary failures persist. Prefer webhooks
over polling. Authenticated conditional REST GETs returning 304 avoid primary
charges; this is not a general GraphQL exemption. [API best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)

GraphQL connections require `first` or `last` from 1–100. Follow
`pageInfo.endCursor`/`hasNextPage` with `after`, or the corresponding backward
cursor. Smaller pages can prevent limits for complex queries. Pagination is
multiple requests; it does not make an arbitrarily large query free.
[GraphQL pagination](https://docs.github.com/en/graphql/guides/using-pagination-in-the-graphql-api)

`gh api graphql --paginate` requires an `$endCursor: String` variable and
`pageInfo { hasNextPage endCursor }`; it retrieves pages sequentially. Use
`--jq` for concise output, `--include` to inspect response headers, and
`--cache` only for reads whose staleness is acceptable. Output filtering does
not itself prove lower server query cost. [gh api](https://cli.github.com/manual/gh_api)

```sh
# A bounded repository inventory, including closed issues; not a complete
# inventory if more than 100 issues match. Fetch only fields you need.
gh issue list --repo OWNER/REPO --state all --limit 100 \
  --json number,title,state,url --jq '.[] | [.number,.state,.title,.url] | @tsv'

# An explicit GraphQL call, including rate headers and a tiny response.
gh api graphql --include \
  -f query='query { viewer { login } rateLimit { cost remaining resetAt } }'
```

The issue-list flags and default open-only behavior are documented in
[gh issue list](https://cli.github.com/manual/gh_issue_list). The query is a
small adaptation of GitHub's documented `rateLimit` examples, not a free
health probe. Treat pagination completeness and output size separately.

## Documented CLI transport versus implementation details

The manual explicitly documents `gh api graphql` as GraphQL and REST endpoint
paths as REST. It does not promise a permanent endpoint/call-count mapping
for every high-level command. Do not equate one `gh` invocation with one REST
request or one GraphQL point. To verify a particular installed CLI version,
`GH_DEBUG=api` logs HTTP traffic; sanitize logs before sharing.
[gh api](https://cli.github.com/manual/gh_api),
[CLI environment](https://cli.github.com/manual/gh_help_environment)

## Projects authentication and item identity

The GraphQL Projects guide documents classic PAT `read:project` for reads,
`project` for writes, and GitHub App installation tokens. App permissions
still matter: `createProjectV2` with `repositoryId` also requires repository
Contents permission. Read-only GraphQL can use `read:project`; the high-level
`gh project` manual specifies `project` as its minimum scope. Do not promise
identical authentication requirements across commands and API routes.
[Projects GraphQL guide](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects),
[gh project](https://cli.github.com/manual/gh_project)

Organization Projects REST list/get routes explicitly support fine-grained
PATs and App user/installation tokens with organization Projects read
permission. User Projects REST list/get routes explicitly exclude all three.
Thus neither “Projects always requires classic PATs” nor “fine-grained tokens
work for all Projects” is supported. Check the exact operation and owner type.
[Projects REST endpoints](https://docs.github.com/en/rest/projects/projects)

Organization REST item add/update/delete and field creation support those
fine-grained/App token types with organization Projects write permission.
These are separately documented operations, not capabilities of the
list/get page. The corresponding user routes exclude fine-grained/App tokens.
[Project items](https://docs.github.com/en/rest/projects/items?apiVersion=2026-03-10),
[Project fields](https://docs.github.com/en/rest/projects/fields?apiVersion=2026-03-10)

`gh auth refresh -s project` modifies stored credentials for the active
account; switch accounts first when needed. `GH_TOKEN`/`GITHUB_TOKEN` take
precedence over stored credentials. Inference: refreshing stored credentials
does not repair an overriding environment token's permissions.
[gh auth refresh](https://cli.github.com/manual/gh_auth_refresh),
[CLI environment](https://cli.github.com/manual/gh_help_environment)

For Actions, the built-in `GITHUB_TOKEN` cannot access Projects; use a
deliberately authorized PAT or App installation token rather than assuming
repository workflow permissions grant project access.
[Projects Actions guide](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/automating-projects-using-actions)

Project field writes need the project ID, project item ID, field ID, and
single-select option ID; issue IDs and project item IDs are different.
Adding and updating an item require separate calls. Adding an existing issue
returns its existing project item ID. Assignees, labels, milestone, and
repository belong to the issue/PR and cannot be changed through
`updateProjectV2ItemFieldValue`.
[Projects GraphQL guide](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects)

## Built-in workflows and issue relationships

New projects default to closed issue/PR → Done and merged PR → Done.
Item-added → Todo and project-status → issue closure are configurable
workflows. Inspect these settings before bulk setup: project status and issue
state can influence each other through enabled automation. The documentation
does not guarantee a reopen → status rollback or event ordering when multiple
workflows might apply. A pre-closed imported issue therefore needs explicit
verification, rather than assuming historical closure triggers a workflow.
[Built-in automations](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-built-in-automations)

Auto-add handles newly created or updated matching issues/PRs; it does not
backfill all pre-existing matches. `reason:reopened` is an available filter.
Seed existing work explicitly, then use auto-add for subsequent matching
events. [Auto-add workflows](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/adding-items-automatically)

Sub-issues express hierarchy; blocked-by/blocking dependencies express
prerequisites. These are separate relationships. Parent grouping/filtering
in Projects does not itself establish dependency readiness. Sub-issues allow
up to 100 children and eight nested levels; issue dependencies require triage
permission. [Sub-issues](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/adding-sub-issues),
[Dependencies](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-issue-dependencies)

Current CLI documentation includes `--parent`, `--blocked-by`, and
`--blocking` on issue creation. Use installed-version help before assuming
those flags exist on an older CLI. Issue creation supports `--body-file` for
literal multiline bodies and `--project` by title; explicit project numbers
and item IDs avoid ambiguity for later project field operations.
[gh issue create](https://cli.github.com/manual/gh_issue_create)

## Acceptance of this research note

- Check the linked official documentation before applying this guidance to a
  different host, credential type, or future CLI version.
- Confirm the final playbook keeps primary points, secondary points, and REST
  request counts distinct, and does not present ceilings as pacing targets.
- Actual board behavior and permissions require a bounded test on the chosen
  project; this note does not claim live producer acceptance.
