import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  REQUEST_ACCOUNTING,
  assertGraphqlBudget,
  parseGraphqlResponse,
  parseGraphqlRateLimitResponse,
  plannedGraphqlPoints,
} from "./roadmap-rate-limit.mjs";
import { acquireRoadmapLock } from "./roadmap-lock.mjs";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const RATE_LIMIT_QUERY = `query RoadmapRateLimit {
  rateLimit { limit remaining used resetAt cost }
}`;

function defaultRunGhResult(args, input) {
  return spawnSync("gh", args, {
    cwd: repositoryRoot,
    encoding: "utf8",
    input,
    env: process.env,
    maxBuffer: 10 * 1024 * 1024,
  });
}

function graphqlArguments(query, variables) {
  const args = ["api", "graphql", "-f", `query=${query}`];
  for (const [name, value] of Object.entries(variables)) {
    if (value === null || value === undefined) continue;
    args.push(Number.isInteger(value) || typeof value === "boolean" ? "-F" : "-f", `${name}=${value}`);
  }
  return args;
}

// Only the lock-owning factory below can construct a production gate.
class RoadmapGraphqlGate {
  #runGhResult;
  #reservations = [];
  #snapshot = null;
  #active = true;

  constructor({ runGhResult = defaultRunGhResult } = {}) {
    this.#runGhResult = runGhResult;
  }

  close() {
    this.#active = false;
    this.#reservations = [];
  }

  #assertActive() {
    if (!this.#active) throw new Error("This roadmap reader no longer holds the host lock");
  }

  #runGh(args, input) {
    this.#assertActive();
    const result = this.#runGhResult(args, input);
    if (result.status !== 0) {
      throw new Error((result.stderr || result.stdout || "GitHub command failed").trim());
    }
    return result.stdout.trim();
  }

  rateLimit() {
    this.#assertActive();
    try {
      const result = this.#runGhResult(["api", "graphql", "--include", "-f", `query=${RATE_LIMIT_QUERY}`]);
      const output = [result.stdout, result.stderr].filter(Boolean).join("\n");
      const snapshot = parseGraphqlRateLimitResponse(output);
      if (result.status !== 0) throw new Error(result.stderr || "Direct GraphQL preflight failed");
      this.#snapshot = snapshot;
      return snapshot;
    } catch (error) {
      this.#reservations = [];
      throw error;
    }
  }

  reserve(operationNames) {
    this.#assertActive();
    try {
      const planned = [...this.#reservations, ...operationNames];
      const points = plannedGraphqlPoints(planned);
      const snapshot = this.rateLimit();
      assertGraphqlBudget(snapshot, points);
      this.#reservations = planned;
      return snapshot;
    } catch (error) {
      this.#reservations = [];
      throw error;
    }
  }

  discard(operationName) {
    this.#reservations = this.#reservations.filter((name) => name !== operationName);
  }

  #consume(operationName, kind) {
    this.#assertActive();
    const index = this.#reservations.indexOf(operationName);
    const operation = REQUEST_ACCOUNTING[operationName];
    const count = kind === "query" ? operation?.graphqlQueries : operation?.graphqlMutations;
    if (index < 0 || count !== 1) {
      throw new Error(`GitHub operation ${operationName} has no reserved GraphQL ${kind}; preflight is required before the request`);
    }
    assertGraphqlBudget(this.#snapshot, plannedGraphqlPoints(this.#reservations));
    this.#reservations.splice(index, 1);
    this.#snapshot = { ...this.#snapshot, remaining: this.#snapshot.remaining - plannedGraphqlPoints([operationName]) };
  }

  #graphql(operationName, kind, query, variables) {
    try {
      if (!query.trimStart().startsWith(`${kind} `)) throw new Error(`Expected one explicit GraphQL ${kind}`);
      this.#consume(operationName, kind);
      const args = graphqlArguments(query, variables);
      args.push("--include");
      const result = this.#runGhResult(args);
      const output = [result.stdout, result.stderr].filter(Boolean).join("\n");
      if (kind === "query") {
        this.#snapshot = parseGraphqlRateLimitResponse(output, Date.now(), { allowExhausted: true });
      }
      const payload = parseGraphqlResponse(output, Date.now(), { allowExhausted: true });
      if (result.status !== 0) throw new Error(result.stderr || "GitHub GraphQL request failed");
      if (!payload.data) throw new Error("GitHub GraphQL response had no data");
      return payload.data;
    } catch (error) {
      this.#reservations = [];
      throw error;
    }
  }

  query(operationName, query, variables = {}) {
    return this.#graphql(operationName, "query", query, variables);
  }

  mutation(operationName, query, variables = {}) {
    return this.#graphql(operationName, "mutation", query, variables);
  }

  restCoreRateLimit() {
    const core = JSON.parse(this.#runGh(["api", "rate_limit", "--jq", ".resources.core"]));
    const values = [core.limit, core.remaining, core.used, core.reset].map(Number);
    if (!values.every((value) => Number.isSafeInteger(value) && value >= 0)) {
      throw new Error("GitHub REST core rate-limit response was incomplete");
    }
    return { limit: values[0], remaining: values[1], used: values[2], reset: values[3] };
  }

  restMutation(args, input) {
    if (args[0] !== "api" || args[1] !== "-X" || args[2] !== "POST" || !/^repos\/[^/]+\/[^/]+\/issues$/.test(args[3])) {
      throw new Error("The shared roadmap gate permits REST only for explicit mutations; live reads must use accounted GraphQL queries");
    }
    return this.#runGh(args, input);
  }
}

export function withRoadmapGraphqlGate(callback, options = {}) {
  const release = acquireRoadmapLock(options.lockOptions);
  const gate = new RoadmapGraphqlGate({ runGhResult: options.runGhResult });
  process.once("exit", release);
  const cleanup = () => {
    gate.close();
    process.removeListener("exit", release);
    release();
  };
  try {
    const result = callback(gate);
    if (result && typeof result.then === "function") return result.finally(cleanup);
    cleanup();
    return result;
  } catch (error) {
    cleanup();
    throw error;
  }
}
