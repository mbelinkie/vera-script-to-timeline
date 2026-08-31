const RESOURCE_NAMES = ["core", "graphql", "search"];

function finiteInteger(value) {
  const number = Number(value);
  return Number.isSafeInteger(number) && number >= 0 ? number : null;
}

function resourceSummary(resource) {
  if (!resource || typeof resource !== "object") return null;
  const limit = finiteInteger(resource.limit);
  const used = finiteInteger(resource.used);
  const remaining = finiteInteger(resource.remaining);
  const reset = finiteInteger(resource.reset);
  if ([limit, used, remaining, reset].some((value) => value === null)) return null;
  return { limit, used, remaining, reset };
}

function retryAfterSeconds(value, now) {
  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds >= 0) return Math.ceil(seconds);
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? null : Math.max(0, Math.ceil((timestamp - now) / 1000));
}

export function parseRateLimitResponse(output, now = Date.now()) {
  const bodyStart = output.lastIndexOf("\n{");
  const jsonText = (bodyStart >= 0 ? output.slice(bodyStart + 1) : output).trim();
  let payload;
  try {
    payload = JSON.parse(jsonText);
  } catch {
    throw new Error("GitHub rate-limit response was not valid JSON");
  }
  const resources = Object.fromEntries(
    RESOURCE_NAMES.map((name) => [name, resourceSummary(payload.resources?.[name])]).filter(([, value]) => value),
  );
  const headerValues = new Map();
  let retryAfter;
  for (const line of output.split(/\r?\n/)) {
    const match = line.match(/^x-ratelimit-(limit|remaining|used|reset):\s*(\d+)\s*$/i);
    if (match) headerValues.set(match[1].toLowerCase(), Number(match[2]));
    const retryMatch = line.match(/^retry-after:\s*(.+?)\s*$/i);
    if (retryMatch) retryAfter = retryAfterSeconds(retryMatch[1], now);
  }
  const headers = resourceSummary({
    limit: headerValues.get("limit"),
    used: headerValues.get("used"),
    remaining: headerValues.get("remaining"),
    reset: headerValues.get("reset"),
  });
  if (Object.keys(resources).length === 0 && !headers) {
    throw new Error("GitHub rate-limit response had no usable rate-limit data");
  }
  return { resources, headers, retryAfter };
}

export function rateLimitSnapshot(parsed) {
  const core = parsed.resources.core ?? parsed.headers;
  if (!core) throw new Error("GitHub response did not report the REST core limit");
  return {
    core,
    graphql: parsed.resources.graphql ?? null,
    search: parsed.resources.search ?? null,
  };
}

export function formatRateLimitReport(parsed, now = Date.now()) {
  const snapshot = rateLimitSnapshot(parsed);
  const format = (name, resource) => {
    if (!resource) return `${name}: unavailable`;
    const resetInSeconds = Math.max(0, Math.ceil((resource.reset * 1000 - now) / 1000));
    return `${name}: ${resource.remaining}/${resource.limit} remaining; reset in ${resetInSeconds}s`;
  };
  const lines = [format("REST core", snapshot.core), format("GraphQL", snapshot.graphql), format("REST search", snapshot.search)];
  if (parsed.retryAfter > 0) lines.push(`Secondary throttle: defer mutations for at least ${parsed.retryAfter}s`);
  return lines.join("\n");
}

export function assertMutationBudget(parsed, requiredRequests, graphqlRequests = 0, now = Date.now()) {
  const snapshot = rateLimitSnapshot(parsed);
  if (
    parsed.retryAfter > 0 ||
    snapshot.core.remaining < requiredRequests ||
    (graphqlRequests > 0 && (!snapshot.graphql || snapshot.graphql.remaining < graphqlRequests))
  ) {
    throw new Error(`Insufficient GitHub API budget for planned mutations (REST core: ${requiredRequests}, GraphQL: ${graphqlRequests}).\n${formatRateLimitReport(parsed, now)}\nNo mutation was attempted.`);
  }
  return snapshot;
}

export function classifyGitHubFailure(message) {
  const value = String(message).toLowerCase();
  if (value.includes("secondary rate limit") || value.includes("abuse detection") || value.includes("retry-after")) return "secondary-rate-limit";
  if (value.includes("graphql") || value.includes("query cost")) return "graphql-rate-limit";
  if (value.includes("rate limit") || value.includes("api rate limit")) return "rest-rate-limit";
  return "client-or-tooling-failure";
}
