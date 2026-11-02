import { createHash } from "node:crypto";

export const REVIEW_MARKER = "VERA_CHAT_REVIEW_V1";
export const PRODUCER = "mbelinkie";
export const REPOS = new Set(["mbelinkie/vera-script-to-timeline", "mbelinkie/vera-research-video-clips"]);

export function issueRevision(title, body) {
  if (typeof title !== "string" || typeof body !== "string") throw new Error("Review issue title/body missing");
  return createHash("sha256").update(JSON.stringify([title, body]), "utf8").digest("hex");
}

function canonicalRestTimestamp(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value)) return false;
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return false;
  const canonical = new Date(timestamp).toISOString();
  return value === canonical || value === canonical.replace(".000Z", "Z");
}

export function verifyProducerReview(issue, comments, repo, number) {
  if (!REPOS.has(repo) || issue?.number !== number || issue.state?.toLowerCase() !== "open" ||
      issue.pull_request || issue.repository_url !== "https://api.github.com/repos/" + repo ||
      issue.html_url !== "https://github.com/" + repo + "/issues/" + number) {
    throw new Error("Review issue identity mismatch");
  }
  if (!Array.isArray(issue.labels)) throw new Error("Review labels unavailable");
  const labels = issue.labels.map(l => typeof l === "string" ? l : l.name);
  if (!labels.includes("chat-reviewed") || labels.includes("chat-review-pending")) {
    throw new Error("Current Producer Chat review label required");
  }
  if (!Number.isSafeInteger(issue.comments) || issue.comments < 0 || issue.comments > 2000 ||
      !Array.isArray(comments) || comments.length !== issue.comments) {
    throw new Error("Review comment history incomplete");
  }
  let previous = 0;
  let newest;
  for (const comment of comments) {
    if (!Number.isSafeInteger(comment?.id) || comment.id <= previous) throw new Error("Review comments out of order");
    if (typeof comment.body !== "string") throw new Error("Review comment body unavailable");
    previous = comment.id;
    // Discussion may name the format; only an attempted HTML record supersedes it.
    if (comment.user?.login !== PRODUCER || !/<!--\s*VERA_CHAT_REVIEW_V1\b/.test(comment.body)) continue;
    const matches = [...comment.body.matchAll(/<!-- VERA_CHAT_REVIEW_V1 (\{[^\r\n]*\}) -->/g)];
    newest = { invalid: true };
    if (matches.length !== 1 || comment.body.split(REVIEW_MARKER).length !== 2) continue;
    if (comment.performed_via_github_app !== null ||
        !canonicalRestTimestamp(comment.created_at) || comment.created_at !== comment.updated_at) continue;
    try {
      const r = JSON.parse(matches[0][1]);
      if (r.producer === PRODUCER && r.promptVersion === "1" &&
          typeof r.reviewedAt === "string" && Number.isFinite(Date.parse(r.reviewedAt)) &&
          new Date(r.reviewedAt).toISOString() === r.reviewedAt &&
          /^[a-f0-9]{64}$/.test(r.revision)) {
        newest = { revision: r.revision, commentId: comment.id, url: comment.html_url };
      }
    } catch { /* malformed latest Producer marker invalidates older review */ }
  }
  if (!newest || newest.invalid) throw new Error("Valid current Producer Chat review missing");
  if (newest.revision !== issueRevision(issue.title, issue.body)) throw new Error("Producer Chat review is stale");
  return { approved: true, ...newest };
}
