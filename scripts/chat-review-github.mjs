import { REPOS, verifyProducerReview } from "./chat-review-current.mjs";

const PAGE_SIZE = 100;
const MAX_COMMENTS = 2000;

function parseIssue(text) {
  const issue = JSON.parse(text);
  if (!issue || typeof issue !== "object" || Array.isArray(issue)) {
    throw new Error("Invalid issue response");
  }
  return issue;
}

function labelNames(issue) {
  if (!Array.isArray(issue.labels)) throw new Error("Review labels unavailable");
  const names = issue.labels.map(label => {
    const name = typeof label === "string" ? label : label?.name;
    if (typeof name !== "string" || !name) throw new Error("Review labels unavailable");
    return name;
  });
  return names.sort();
}

function validateIssue(issue, repo, number) {
  if (issue.number !== number || issue.repository_url !== "https://api.github.com/repos/" + repo ||
      issue.html_url !== "https://github.com/" + repo + "/issues/" + number ||
      issue.pull_request || typeof issue.title !== "string" || typeof issue.body !== "string" ||
      typeof issue.state !== "string" || issue.state.toLowerCase() !== "open") {
    throw new Error("Review issue identity mismatch");
  }
  const labels = labelNames(issue);
  if (!Number.isSafeInteger(issue.comments) || issue.comments < 0 || issue.comments > MAX_COMMENTS) {
    throw new Error("Review comment count unavailable or exceeds safe bound");
  }
  return labels;
}

function readComments(readGh, path, expectedCount) {
  const pages = JSON.parse(readGh(["api", "--paginate", "--slurp", path + "/comments?per_page=" + PAGE_SIZE]));
  const pageCount = Math.max(1, Math.ceil(expectedCount / PAGE_SIZE));
  if (!Array.isArray(pages) || pages.length !== pageCount || !pages.every(Array.isArray)) {
    throw new Error("Review comment pagination was incomplete");
  }

  const comments = [];
  for (let pageIndex = 0; pageIndex < pages.length; pageIndex++) {
    const expectedPageLength = pageIndex === pageCount - 1
      ? expectedCount - PAGE_SIZE * pageIndex
      : PAGE_SIZE;
    const page = pages[pageIndex];
    if (page.length !== expectedPageLength) throw new Error("Review comment pagination was incomplete");
    for (const comment of page) {
      if (!comment || typeof comment !== "object" || Array.isArray(comment) ||
          !Number.isSafeInteger(comment.id) || comment.id < 1 || typeof comment.body !== "string" ||
          !comment.user || typeof comment.user.login !== "string") {
        throw new Error("Review comment response invalid");
      }
      comments.push(comment);
    }
  }

  return comments;
}

function sameHistory(left, right) {
  return left.length === right.length && left.every((comment, index) => {
    const other = right[index];
    return comment.id === other.id && comment.user.login === other.user.login && comment.body === other.body;
  });
}

function checkSnapshot(snapshot, issue, labels) {
  if (!snapshot) return;
  if (snapshot.title !== issue.title || snapshot.body !== issue.body) {
    throw new Error("Review issue changed since roadmap snapshot");
  }
  if (snapshot.labels !== undefined) {
    const snapshotIssue = { labels: snapshot.labels };
    if (JSON.stringify(labelNames(snapshotIssue)) !== JSON.stringify(labels)) {
      throw new Error("Review issue changed since roadmap snapshot");
    }
  }
}

// Read-only GitHub CLI wrapper supplied by caller. Two bounded history reads
// catch comment edits/deletions with stable counts; REST offers no transaction,
// so a final concurrent edit after the second read cannot be eliminated.
export function verifyReviewFromGh(readGh, repo, number, snapshot = null) {
  if (!REPOS.has(repo) || !Number.isSafeInteger(number) || number < 1) {
    throw new Error("Unrecognized review issue/repository");
  }
  const path = "repos/" + repo + "/issues/" + number;
  const before = parseIssue(readGh(["api", path]));
  const beforeLabels = validateIssue(before, repo, number);
  const comments = readComments(readGh, path, before.comments);
  const after = parseIssue(readGh(["api", path]));
  const afterLabels = validateIssue(after, repo, number);

  if (before.title !== after.title || before.body !== after.body ||
      before.comments !== after.comments || JSON.stringify(beforeLabels) !== JSON.stringify(afterLabels)) {
    throw new Error("Review issue changed during verification");
  }
  checkSnapshot(snapshot, after, afterLabels);

  const confirmedComments = readComments(readGh, path, after.comments);
  if (!sameHistory(comments, confirmedComments)) {
    throw new Error("Review comments changed during verification");
  }
  return verifyProducerReview(after, confirmedComments, repo, number);
}
