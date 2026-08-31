import assert from "node:assert/strict";
import test from "node:test";

import { assertMutationBudget, classifyGitHubFailure, formatRateLimitReport, parseRateLimitResponse } from "./roadmap-rate-limit.mjs";

const response = `HTTP/2 200 OK\nX-RateLimit-Limit: 5000\nX-RateLimit-Remaining: 4998\nX-RateLimit-Used: 2\nX-RateLimit-Reset: 1700000060\n\n{"resources":{"core":{"limit":5000,"used":2,"remaining":4998,"reset":1700000060},"graphql":{"limit":5000,"used":4,"remaining":4996,"reset":1700000060},"search":{"limit":30,"used":1,"remaining":29,"reset":1700000060}}}`;

test("parses only safe rate-limit fields and omits response headers such as scopes or request IDs", () => {
  const parsed = parseRateLimitResponse(response.replace("\n\n{", "\nX-OAuth-Scopes: repo\nX-GitHub-Request-Id: secret-looking-id\n\n{"));
  assert.deepEqual(parsed.resources.core, { limit: 5000, used: 2, remaining: 4998, reset: 1700000060 });
  assert.equal(JSON.stringify(parsed).includes("secret-looking"), false);
  assert.match(formatRateLimitReport(parsed, 1700000000000), /REST core: 4998\/5000 remaining; reset in 60s/);
});

test("fails closed before mutation when the planned REST budget is unavailable", () => {
  const parsed = parseRateLimitResponse(response);
  assert.throws(() => assertMutationBudget(parsed, 4999), /No mutation was attempted/);
  assert.doesNotThrow(() => assertMutationBudget(parsed, 2));
  assert.throws(() => assertMutationBudget(parsed, 2, 4997), /No mutation was attempted/);
});

test("honors Retry-After evidence and refuses mutation during a secondary throttle", () => {
  const throttled = `${response.replace("\n\n{", "\nRetry-After: 60\n\n{")}\n`;
  const parsed = parseRateLimitResponse(throttled, 1700000000000);
  assert.equal(parsed.retryAfter, 60);
  assert.match(formatRateLimitReport(parsed, 1700000000000), /Secondary throttle: defer mutations for at least 60s/);
  assert.throws(() => assertMutationBudget(parsed, 1, 0, 1700000000000), /No mutation was attempted/);
});

test("distinguishes REST, GraphQL, secondary, and client/tooling failures", () => {
  assert.equal(classifyGitHubFailure("API rate limit exceeded"), "rest-rate-limit");
  assert.equal(classifyGitHubFailure("GraphQL query cost exceeded"), "graphql-rate-limit");
  assert.equal(classifyGitHubFailure("You have exceeded a secondary rate limit; Retry-After: 60"), "secondary-rate-limit");
  assert.equal(classifyGitHubFailure("gh: command not found"), "client-or-tooling-failure");
});
