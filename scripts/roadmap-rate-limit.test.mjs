import assert from "node:assert/strict";
import test from "node:test";

import {
  REQUEST_ACCOUNTING,
  assertGraphqlBudget,
  classifyGitHubFailure,
  formatGraphqlRateLimitReport,
  parseGraphqlRateLimitResponse,
  plannedGraphqlPoints,
} from "./roadmap-rate-limit.mjs";

const directResponse = `HTTP/2 200 OK
X-RateLimit-Limit: 5000
X-RateLimit-Remaining: 41
X-RateLimit-Used: 4959
X-RateLimit-Reset: 1788215569
X-RateLimit-Resource: graphql

{"data":{"rateLimit":{"limit":5000,"remaining":41,"used":4959,"resetAt":"2026-08-31T22:32:49Z","cost":1}}}`;

test("parses authoritative direct GraphQL rateLimit fields and omits response metadata", () => {
  const parsed = parseGraphqlRateLimitResponse(
    directResponse.replace("\n\n{", "\nX-OAuth-Scopes: repo\nX-GitHub-Request-Id: secret-looking-id\n\n{"),
  );
  assert.deepEqual(parsed, {
    limit: 5000,
    remaining: 41,
    used: 4959,
    resetAt: "2026-08-31T22:32:49.000Z",
    cost: 1,
  });
  assert.equal(JSON.stringify(parsed).includes("secret-looking"), false);
  assert.match(formatGraphqlRateLimitReport(parsed, Date.parse("2026-08-31T22:31:49Z")), /41\/5000 remaining; 4959 used; query cost 1/);
  assert.match(formatGraphqlRateLimitReport(parsed, Date.parse("2026-08-31T22:31:49Z")), /reset at 2026-08-31T22:32:49.000Z \(in 60s\)/);
});

test("fails closed on GitHub's graphql_rate_limit exhaustion response with reset guidance", () => {
  const exhausted = `HTTP/2 200 OK
X-RateLimit-Limit: 5000
X-RateLimit-Remaining: 0
X-RateLimit-Used: 5000
X-RateLimit-Reset: 1788215569
X-RateLimit-Resource: graphql

{"data":null,"errors":[{"type":"RATE_LIMITED","message":"Something went wrong while executing your query. This may be the result of a timeout, or it could be a GitHub bug. Please include \`graphql_rate_limit\` in your report."}]}`;
  assert.throws(
    () => parseGraphqlRateLimitResponse(exhausted, Date.parse("2026-08-31T22:31:49Z")),
    /GitHub GraphQL budget is exhausted.*Do not retry before that reset.*2026-08-31T22:32:49\.000Z/s,
  );
});

test("never accepts a false REST-green payload as GraphQL authority", () => {
  const restGreen = JSON.stringify({
    resources: { graphql: { limit: 5000, remaining: 5000, used: 0, reset: 1788215569 } },
  });
  assert.throws(() => parseGraphqlRateLimitResponse(restGreen), /direct GraphQL rateLimit/);
});

test("preflight reserves points for the planned GraphQL work", () => {
  const parsed = parseGraphqlRateLimitResponse(directResponse);
  assert.doesNotThrow(() => assertGraphqlBudget(parsed, 41));
  assert.throws(
    () => assertGraphqlBudget(parsed, 42, Date.parse("2026-08-31T22:31:49Z")),
    /needs 42 point\(s\).*41 remain.*Safe retry: at or after 2026-08-31T22:32:49\.000Z/s,
  );
});

test("honors direct Retry-After evidence during a secondary throttle", () => {
  const throttled = directResponse.replace("\n\n{", "\nRetry-After: 60\n\n{");
  assert.throws(
    () => parseGraphqlRateLimitResponse(throttled, Date.parse("2026-08-31T22:31:49Z")),
    /secondary rate limit is active.*Do not retry for at least 60s.*no roadmap operation was attempted/s,
  );
});

test("accounts for issue, comment, dependency, and Project V2 operations by actual transport", () => {
  assert.deepEqual(REQUEST_ACCOUNTING.issueProjectSnapshot, { graphqlQueries: 1, graphqlMutations: 0, restMutations: 0 });
  assert.deepEqual(REQUEST_ACCOUNTING.issueComment, { graphqlQueries: 0, graphqlMutations: 1, restMutations: 0 });
  assert.deepEqual(REQUEST_ACCOUNTING.dependencyBatch, { graphqlQueries: 1, graphqlMutations: 0, restMutations: 0 });
  assert.deepEqual(REQUEST_ACCOUNTING.projectStatus, { graphqlQueries: 0, graphqlMutations: 1, restMutations: 0 });
  assert.equal(plannedGraphqlPoints(["issueProjectSnapshot", "dependencyBatch"]), 2);
  assert.equal(plannedGraphqlPoints(["issueComment", "projectStatus"]), 2);
  assert.equal(plannedGraphqlPoints(["lifecycleMutation"]), 1);
});

test("distinguishes REST, GraphQL, secondary, and client/tooling failures", () => {
  assert.equal(classifyGitHubFailure("API rate limit exceeded"), "rest-rate-limit");
  assert.equal(classifyGitHubFailure("graphql_rate_limit"), "graphql-rate-limit");
  assert.equal(classifyGitHubFailure("You have exceeded a secondary rate limit; Retry-After: 60"), "secondary-rate-limit");
  assert.equal(classifyGitHubFailure("gh: command not found"), "client-or-tooling-failure");
});
