import test from "node:test";
import assert from "node:assert/strict";
import { issueRevision, verifyProducerReview } from "./chat-review-current.mjs";
import { verifyReviewFromGh } from "./chat-review-github.mjs";
import { parseReviewUrl } from "./chat-review-dispatch-gate.mjs";

const repo = "mbelinkie/vera-script-to-timeline";
const number = 378;
function issue() {
  return {
    number, title: "Review test", body: "## Outcome\\nBounded work",
    state: "open", labels: [{ name: "chat-reviewed" }], comments: 1,
    repository_url: "https://api.github.com/repos/" + repo,
    html_url: "https://github.com/" + repo + "/issues/" + number
  };
}
function approval(i, id = 12, overrides = {}) {
  return { id, user: { login: "mbelinkie" }, html_url: "https://github.com/example#review",
    body: '<!-- VERA_CHAT_REVIEW_V1 ' + JSON.stringify({
      revision: issueRevision(i.title, i.body), producer: "mbelinkie",
      promptVersion: "1", reviewedAt: "2026-11-02T02:59:16.691Z", ...overrides
    }) + ' -->' };
}
test("accept current Producer comment and ignore ordinary later comments", () => {
  const i = issue();
  const a = approval(i);
  assert.equal(verifyProducerReview(i, [a], repo, number).approved, true);
  i.comments = 2;
  assert.equal(verifyProducerReview(i, [a, { id: 13, body: "ordinary follow-up", user: { login: "mbelinkie" } }], repo, number).approved, true);
});
test("reject label-only, pending review, missing and wrong-author records", () => {
  const i = issue(); const a = approval(i);
  assert.throws(() => verifyProducerReview(i, [{ id: 12, body: "no record" }], repo, number));
  a.user.login = "automation-bot";
  assert.throws(() => verifyProducerReview(i, [a], repo, number));
  i.labels = [];
  assert.throws(() => verifyProducerReview(i, [approval(i)], repo, number));
  i.labels = [{ name: "chat-reviewed" }, { name: "chat-review-pending" }];
  assert.throws(() => verifyProducerReview(i, [approval(i)], repo, number));
});
test("reject stale body/title and a newer malformed or stale review", () => {
  const i = issue(); const a = approval(i);
  i.body = "Changed after approval";
  assert.throws(() => verifyProducerReview(i, [a], repo, number), /stale/);
  const j = issue(); j.comments = 2;
  assert.throws(() => verifyProducerReview(j, [approval(j), {
    id: 13, user: { login: "mbelinkie" }, body: "<!-- VERA_CHAT_REVIEW_V1 malformed -->"
  }], repo, number), /valid current/i);
  assert.throws(() => verifyProducerReview(j, [approval(j), approval(j, 13, {
    revision: "a".repeat(64)
  })], repo, number), /stale/);
});
test("reject malformed record, incomplete history, bad identity, unexpected repo", () => {
  const i = issue();
  assert.throws(() => verifyProducerReview(i, [approval(i, 12, { promptVersion: "0" })], repo, number));
  assert.throws(() => verifyProducerReview(i, [], repo, number), /incomplete/);
  assert.throws(() => verifyProducerReview({ ...i, repository_url: "https://api.github.com/repos/evil/repo" }, [approval(i)], repo, number));
  assert.throws(() => verifyProducerReview(i, [approval(i)], "evil/repo", number));
  const two = { ...i, comments: 2 };
  assert.throws(() => verifyProducerReview(two, [approval(two), approval(two)], repo, number), /out of order/);
});
test("fail closed on incomplete pagination, changed issue, or missing API", () => {
  const i = issue(); const a = approval(i);
  function provider(options = {}) {
    let reads = 0;
    return args => {
      if (args.includes("--paginate")) return JSON.stringify(options.pages ?? [[a]]);
      reads++;
      if (options.fail) throw new Error("GitHub failed");
      return JSON.stringify(reads === 2 && options.changed ? { ...i, title: "Modified" } : i);
    };
  }
  assert.equal(verifyReviewFromGh(provider(), repo, number).approved, true);
  assert.throws(() => verifyReviewFromGh(provider({ pages: [] }), repo, number), /incomplete/);
  assert.throws(() => verifyReviewFromGh(provider({ changed: true }), repo, number), /changed/);
  assert.throws(() => verifyReviewFromGh(provider({ fail: true }), repo, number), /GitHub failed/);
  assert.throws(() => verifyReviewFromGh(provider(), repo, number, { title: "old", body: i.body }), /changed/);
});
test("standalone gate accepts only exact allowed issue URLs", () => {
  assert.deepEqual(parseReviewUrl("https://github.com/mbelinkie/vera-script-to-timeline/issues/378"), { repo, number });
  for (const url of ["https://github.com/evil/repo/issues/378", "https://github.com/mbelinkie/vera-script-to-timeline/pull/378", "https://github.com/mbelinkie/vera-script-to-timeline/issues/0"]) {
    assert.throws(() => parseReviewUrl(url));
  }
});
