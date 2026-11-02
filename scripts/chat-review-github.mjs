import { REPOS, verifyProducerReview } from "./chat-review-current.mjs";

// Read-only GitHub CLI wrapper supplied by caller. Verify all pages and re-fetch
// the current issue after the comment history before allowing any claim.
export function verifyReviewFromGh(readGh, repo, number, snapshot = null) {
  if (!REPOS.has(repo) || !Number.isSafeInteger(number) || number < 1) {
    throw new Error("Unrecognized review issue/repository");
  }
  const path = "repos/" + repo + "/issues/" + number;
  const parseIssue = text => {
    const value = JSON.parse(text);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid issue response");
    return value;
  };
  const before = parseIssue(readGh(["api", path]));
  if (!Number.isSafeInteger(before.comments) || before.comments < 0 || before.comments > 2000) {
    throw new Error("Review comment count unavailable or exceeds safe bound");
  }
  const pages = JSON.parse(readGh(["api", "--paginate", "--slurp", path + "/comments?per_page=100"]));
  if (!Array.isArray(pages) || !pages.every(Array.isArray)) {
    throw new Error("Review comment pagination was incomplete");
  }
  const comments = pages.flat();
  const after = parseIssue(readGh(["api", path]));
  const labels = issue => JSON.stringify((issue.labels || []).map(l => typeof l === "string" ? l : l.name).sort());
  if (before.title !== after.title || before.body !== after.body ||
      before.comments !== after.comments || labels(before) !== labels(after)) {
    throw new Error("Review issue changed during verification");
  }
  if (snapshot && (snapshot.title !== after.title || snapshot.body !== after.body)) {
    throw new Error("Review issue changed since roadmap snapshot");
  }
  return verifyProducerReview(after, comments, repo, number);
}
