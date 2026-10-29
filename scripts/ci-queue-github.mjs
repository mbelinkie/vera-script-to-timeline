import { Buffer } from "node:buffer";
import { TextDecoder } from "node:util";
import { URL } from "node:url";

const API_BASE = "https://api.github.com";
const STATE_BRANCH = "vera-ci-queue-state";
const STATE_FILE = "queue.json";
const MAX_STATE_BYTES = 1024 * 1024;
const MAX_PAGES = 100;
const PAGE_SIZE = 100;
const SHA_PATTERN = /^[0-9a-f]{40}$/i;

function safeRepository(repository) {
  if (
    typeof repository !== "string" ||
    !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository) ||
    repository.split("/").some((part) => part === "." || part === "..")
  ) {
    throw new Error("GitHub repository must be an owner/repository pair");
  }
  return repository;
}

function safePath(path) {
  if (
    typeof path !== "string" ||
    !path.startsWith("/") ||
    path.startsWith("//") ||
    !/^\/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*(?:\?[A-Za-z0-9._~!$&'()*+,;=:@%/?-]*)?$/.test(path)
  ) {
    throw new Error("GitHub API path must be a safe absolute path");
  }
  const url = new URL(path, API_BASE);
  if (url.origin !== API_BASE) throw new Error("GitHub API path must stay on api.github.com");
  return url;
}

function safeSha(value, label) {
  if (typeof value !== "string" || !SHA_PATTERN.test(value)) throw new Error(`GitHub ${label} SHA was invalid`);
  return value;
}

function responseError(method, url, status, detail = "") {
  const error = new Error(`${method} ${url.pathname}${url.search} returned HTTP ${status}${detail}`);
  error.status = status;
  return error;
}

function decodeStateBlob(blob) {
  if (!blob || blob.encoding !== "base64" || typeof blob.content !== "string") {
    throw new Error("GitHub queue state blob had an invalid encoding or content");
  }
  const encoded = blob.content.replace(/\s/g, "");
  if (encoded.length > Math.ceil((MAX_STATE_BYTES * 4) / 3) + 4 || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(encoded)) {
    throw new Error("GitHub queue state blob exceeded 1 MiB or contained invalid base64");
  }
  const bytes = Buffer.from(encoded, "base64");
  if (bytes.length > MAX_STATE_BYTES || bytes.toString("base64") !== encoded) {
    throw new Error("GitHub queue state blob exceeded 1 MiB or contained invalid base64");
  }
  let content;
  try {
    content = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw new Error("GitHub queue state blob was not valid UTF-8");
  }
  try {
    return JSON.parse(content);
  } catch {
    throw new Error("GitHub queue state blob did not contain valid JSON");
  }
}

export class GitHub {
  constructor({ repository, token, fetchImpl = globalThis.fetch } = {}) {
    this.repository = safeRepository(repository);
    if (typeof token !== "string" || token.trim().length === 0 || /[\r\n]/.test(token)) {
      throw new Error("GitHub token is required");
    }
    if (typeof fetchImpl !== "function") throw new Error("GitHub fetch implementation is required");
    this.token = token;
    this.fetchImpl = fetchImpl;
  }

  async api(method, path, body) {
    const url = safePath(path);
    const verb = typeof method === "string" ? method.toUpperCase() : "";
    if (!["GET", "POST", "PATCH", "PUT", "DELETE"].includes(verb)) throw new Error("GitHub HTTP method was invalid");
    const headers = {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${this.token}`,
      "X-GitHub-Api-Version": "2022-11-28",
    };
    const options = { method: verb, headers, signal: globalThis.AbortSignal.timeout(30_000) };
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }

    let response;
    try {
      response = await this.fetchImpl(url, options);
    } catch {
      throw new Error(`${verb} ${url.pathname}${url.search} failed before receiving an HTTP response`);
    }
    if (response.status === 204) return null;
    if (!response.ok) throw responseError(verb, url, response.status);
    try {
      return await response.json();
    } catch {
      throw responseError(verb, url, response.status, " with invalid JSON");
    }
  }

  async pages(path) {
    const url = safePath(path);
    const items = [];
    for (let page = 1; page <= MAX_PAGES; page += 1) {
      url.searchParams.set("per_page", String(PAGE_SIZE));
      url.searchParams.set("page", String(page));
      const result = await this.api("GET", `${url.pathname}${url.search}`);
      if (!Array.isArray(result)) throw new Error(`GET ${url.pathname}${url.search} returned a non-array page`);
      items.push(...result);
      if (result.length < PAGE_SIZE) return items;
    }
    throw new Error(`GitHub pagination exceeded the ${MAX_PAGES}-page limit for ${url.pathname}`);
  }

  async loadState() {
    const root = `/repos/${this.repository}/git`;
    let reference;
    try {
      reference = await this.api("GET", `${root}/ref/heads/${STATE_BRANCH}`);
    } catch (error) {
      if (error.status === 404) return null;
      throw error;
    }
    const sha = safeSha(reference?.object?.sha, "state reference");
    const commit = await this.api("GET", `${root}/commits/${sha}`);
    const treeSha = safeSha(commit?.tree?.sha, "state tree");
    const tree = await this.api("GET", `${root}/trees/${treeSha}`);
    if (tree?.truncated === true || !Array.isArray(tree?.tree) || tree.tree.length !== 1) {
      throw new Error("GitHub queue state tree was incomplete or contained unexpected files");
    }
    const entry = tree.tree[0];
    if (entry?.path !== STATE_FILE || entry.type !== "blob" || entry.mode !== "100644") {
      throw new Error("GitHub queue state tree did not contain the expected queue.json blob");
    }
    const blobSha = safeSha(entry.sha, "state blob");
    const blob = await this.api("GET", `${root}/blobs/${blobSha}`);
    return { sha, state: decodeStateBlob(blob) };
  }

  async saveState(state, previousSha = null) {
    if (previousSha !== null) safeSha(previousSha, "previous state");
    let content;
    try {
      content = JSON.stringify(state);
    } catch {
      throw new Error("GitHub queue state must be JSON serializable");
    }
    if (typeof content !== "string") throw new Error("GitHub queue state must be JSON serializable");
    if (Buffer.byteLength(content, "utf8") > MAX_STATE_BYTES) throw new Error("GitHub queue state exceeded 1 MiB");

    const root = `/repos/${this.repository}/git`;
    const blob = await this.api("POST", `${root}/blobs`, { content, encoding: "utf-8" });
    const blobSha = safeSha(blob?.sha, "created state blob");
    const tree = await this.api("POST", `${root}/trees`, {
      tree: [{ path: STATE_FILE, mode: "100644", type: "blob", sha: blobSha }],
    });
    const treeSha = safeSha(tree?.sha, "created state tree");
    const commit = await this.api("POST", `${root}/commits`, {
      message: "Update CI queue state",
      tree: treeSha,
      parents: previousSha === null ? [] : [previousSha],
    });
    const sha = safeSha(commit?.sha, "created state commit");
    if (previousSha === null) {
      await this.api("POST", `${root}/refs`, { ref: `refs/heads/${STATE_BRANCH}`, sha });
    } else {
      await this.api("PATCH", `${root}/refs/heads/${STATE_BRANCH}`, { sha, force: false });
    }
    return { sha, state: JSON.parse(content) };
  }
}
