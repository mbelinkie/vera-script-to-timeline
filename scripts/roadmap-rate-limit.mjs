export const REQUEST_ACCOUNTING = Object.freeze({
  rateLimitPreflight: Object.freeze({ graphqlQueries: 1, graphqlMutations: 0, restMutations: 0 }),
  issueProjectSnapshot: Object.freeze({ graphqlQueries: 1, graphqlMutations: 0, restMutations: 0 }),
  issueCommentPage: Object.freeze({ graphqlQueries: 1, graphqlMutations: 0, restMutations: 0 }),
  issueComment: Object.freeze({ graphqlQueries: 0, graphqlMutations: 1, restMutations: 0 }),
  dependencyBatch: Object.freeze({ graphqlQueries: 1, graphqlMutations: 0, restMutations: 0 }),
  parentIssueSnapshot: Object.freeze({ graphqlQueries: 1, graphqlMutations: 0, restMutations: 0 }),
  projectMetadata: Object.freeze({ graphqlQueries: 1, graphqlMutations: 0, restMutations: 0 }),
  // 1 item connection + up to 100 labels and 100 field-value connections: 201 / 100, rounded.
  projectItemsPage: Object.freeze({ graphqlQueries: 1, graphqlMutations: 0, restMutations: 0, graphqlPoints: 2 }),
  projectStatus: Object.freeze({ graphqlQueries: 0, graphqlMutations: 1, restMutations: 0 }),
  lifecycleMutation: Object.freeze({ graphqlQueries: 0, graphqlMutations: 1, restMutations: 0 }),
  projectAdd: Object.freeze({ graphqlQueries: 0, graphqlMutations: 1, restMutations: 0 }),
  subIssueLink: Object.freeze({ graphqlQueries: 0, graphqlMutations: 1, restMutations: 0 }),
  issueCreate: Object.freeze({ graphqlQueries: 0, graphqlMutations: 0, restMutations: 1 }),
  issueEdit: Object.freeze({ graphqlQueries: 0, graphqlMutations: 1, restMutations: 0 }),
  issueClose: Object.freeze({ graphqlQueries: 0, graphqlMutations: 1, restMutations: 0 }),
});

function finiteInteger(value) {
  if (value === null || value === undefined || value === "" || typeof value === "boolean") return null;
  const number = Number(value);
  return Number.isSafeInteger(number) && number >= 0 ? number : null;
}

export function parseGraphqlPayload(output) {
  const lines = String(output).split(/\r?\n/);
  // Start at the outer JSON document, never a nested node in pretty-printed output.
  const start = lines.findIndex((line) => line.trimStart().startsWith("{"));
  if (start >= 0) {
    for (let end = lines.length; end > start; end -= 1) {
      try {
        return JSON.parse(lines.slice(start, end).join("\n").trim());
      } catch {
        // Try the next candidate boundary. `gh` can put a diagnostic after JSON.
      }
    }
  }
  throw new Error("GitHub direct GraphQL rate-limit response was not valid JSON");
}

function retryAfterSeconds(value, now) {
  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds >= 0) return Math.ceil(seconds);
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? null : Math.max(0, Math.ceil((timestamp - now) / 1000));
}

function directGraphqlHeaders(output, now) {
  const values = new Map();
  let retryAfter = null;
  for (const line of String(output).split(/\r?\n/)) {
    const match = line.match(/^x-ratelimit-(limit|remaining|used|reset):\s*(\d+)\s*$/i);
    if (match) values.set(match[1].toLowerCase(), Number(match[2]));
    const retryMatch = line.match(/^retry-after:\s*(.+?)\s*$/i);
    if (retryMatch) retryAfter = retryAfterSeconds(retryMatch[1], now);
  }
  const limit = finiteInteger(values.get("limit"));
  const remaining = finiteInteger(values.get("remaining"));
  const used = finiteInteger(values.get("used"));
  const reset = finiteInteger(values.get("reset"));
  return { limit, remaining, used, resetAt: reset === null ? null : new Date(reset * 1000).toISOString(), retryAfter };
}

function resetGuidance(resetAt, now = Date.now()) {
  if (!resetAt) return "Do not retry until GitHub reports that the GraphQL budget has reset.";
  const seconds = Math.max(0, Math.ceil((Date.parse(resetAt) - now) / 1000));
  return `Do not retry before that reset (${resetAt}; in ${seconds}s).`;
}

export class GraphqlRateLimitError extends Error {
  constructor(message, snapshot = null) {
    super(message);
    this.name = "GraphqlRateLimitError";
    this.snapshot = snapshot;
  }
}

function exhaustedError(snapshot, now) {
  const remaining = snapshot ? `${snapshot.remaining}/${snapshot.limit} remaining. ` : "";
  return new GraphqlRateLimitError(`GitHub GraphQL budget is exhausted. ${remaining}${resetGuidance(snapshot?.resetAt, now)}`, snapshot);
}

export function parseGraphqlResponse(output, now = Date.now(), { allowExhausted = false } = {}) {
  const headers = directGraphqlHeaders(output, now);
  const secondaryError = () => {
    const guidance = headers.retryAfter > 0
      ? `Do not retry for at least ${headers.retryAfter}s`
      : "Wait at least 60s and revalidate the direct budget before retrying";
    return new GraphqlRateLimitError(
      `GitHub secondary rate limit is active. ${guidance}; ${allowExhausted ? "no further roadmap request was attempted" : "no roadmap operation was attempted"}.`,
      headers,
    );
  };
  if (headers.retryAfter > 0) throw secondaryError();
  let payload;
  try {
    payload = parseGraphqlPayload(output);
  } catch (error) {
    if (/secondary rate limit|abuse detection/i.test(output)) throw secondaryError();
    throw error;
  }
  const errors = Array.isArray(payload.errors) ? payload.errors : [];
  // Issue/comment bodies may discuss throttling; only API errors are throttle evidence.
  if (errors.some((error) => /secondary rate limit|abuse detection/i.test(error?.message ?? ""))) {
    throw secondaryError();
  }
  const exhausted = errors.some((error) => {
    const evidence = `${error?.type ?? ""} ${error?.message ?? ""}`.toLowerCase();
    return evidence.includes("rate_limited") || evidence.includes("graphql_rate_limit") || evidence.includes("rate limit");
  });
  if (exhausted || (!allowExhausted && headers.remaining === 0)) throw exhaustedError(headers, now);
  if (errors.length > 0) throw new Error(errors.map((error) => error.message ?? String(error)).join("; "));
  return payload;
}

export function parseGraphqlRateLimitResponse(output, now = Date.now(), options = {}) {
  const payload = parseGraphqlResponse(output, now, options);
  const rateLimit = payload.data?.rateLimit;
  if (!rateLimit || typeof rateLimit !== "object") {
    throw new Error("GitHub response did not contain a direct GraphQL rateLimit object; REST rate data is not accepted as GraphQL authority");
  }
  const limit = finiteInteger(rateLimit.limit);
  const remaining = finiteInteger(rateLimit.remaining);
  const used = finiteInteger(rateLimit.used);
  const cost = finiteInteger(rateLimit.cost);
  const resetTimestamp = Date.parse(rateLimit.resetAt);
  if ([limit, remaining, used, cost].some((value) => value === null) || Number.isNaN(resetTimestamp)) {
    throw new Error("GitHub direct GraphQL rateLimit object was incomplete");
  }
  const snapshot = { limit, remaining, used, resetAt: new Date(resetTimestamp).toISOString(), cost };
  if (!options.allowExhausted && snapshot.remaining === 0) throw exhaustedError(snapshot, now);
  return snapshot;
}

export function formatGraphqlRateLimitReport(snapshot, now = Date.now()) {
  const resetInSeconds = Math.max(0, Math.ceil((Date.parse(snapshot.resetAt) - now) / 1000));
  return `GraphQL: ${snapshot.remaining}/${snapshot.limit} remaining; ${snapshot.used} used; query cost ${snapshot.cost}; reset at ${snapshot.resetAt} (in ${resetInSeconds}s)`;
}

export function assertGraphqlBudget(snapshot, requiredPoints, now = Date.now()) {
  if (!Number.isSafeInteger(requiredPoints) || requiredPoints < 0) throw new Error("Planned GraphQL points must be a non-negative integer");
  if (snapshot.remaining < requiredPoints) {
    const resetInSeconds = Math.max(0, Math.ceil((Date.parse(snapshot.resetAt) - now) / 1000));
    throw new GraphqlRateLimitError(
      `Insufficient GitHub GraphQL budget: planned work needs ${requiredPoints} point(s), but ${snapshot.remaining} remain. ` +
        `Safe retry: at or after ${snapshot.resetAt} (in ${resetInSeconds}s). No additional roadmap request was attempted.`,
      snapshot,
    );
  }
  return snapshot;
}

export function plannedGraphqlPoints(operationNames) {
  return operationNames.reduce((total, name) => {
    const operation = REQUEST_ACCOUNTING[name];
    if (!operation) throw new Error(`Unknown GitHub operation accounting key: ${name}`);
    return total + (operation.graphqlPoints ?? operation.graphqlQueries + operation.graphqlMutations);
  }, 0);
}

export function classifyGitHubFailure(message) {
  const value = String(message).toLowerCase();
  if (value.includes("secondary rate limit") || value.includes("abuse detection") || value.includes("retry-after")) return "secondary-rate-limit";
  if (value.includes("graphql") || value.includes("query cost") || value.includes("rate_limited")) return "graphql-rate-limit";
  if (value.includes("rate limit") || value.includes("api rate limit")) return "rest-rate-limit";
  return "client-or-tooling-failure";
}
