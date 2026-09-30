// Disposable representation experiment, NOT a Resolve detector or production reconciler.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

const bytes = readFileSync(new URL("./synthetic.json", import.meta.url));
assert.equal(createHash("sha256").update(bytes).digest("hex"), "98fede0b93d26d1f19632250208a111671bd3650b7d18b8930fca86262643dbf", "Frozen investigation input changed");
const corpus = JSON.parse(bytes);
const digest = value => createHash("sha256").update(JSON.stringify(value)).digest("hex");
const original = JSON.stringify(corpus);
const passed = [];
function check(id, action) {
  action();
  assert.equal(JSON.stringify(corpus), original, `${id}: source snapshots changed`);
  passed.push(id);
}
const tokenIds = rows => rows.flatMap(row => row.tokens.map(token => token.id));
function locate(rows, tokenId) {
  const matches = rows.flatMap(row => row.tokens.filter(token => token.id === tokenId).map(() => row.id));
  assert.equal(matches.length, 1, `Missing or non-unique token: ${tokenId}`);
  return matches[0];
}

check("P01 stable identities, repeated words, reordered rows", () => {
  const rows = corpus.baseline.rows;
  assert.equal(rows.flatMap(row => row.tokens).filter(token => token.word === "same").length, 2);
  assert.equal(locate(rows, "t3"), "r1");
  assert.equal(locate([...rows].reverse(), "t3"), "r1");
  assert.throws(() => locate(rows, "unknown"));
  assert.throws(() => locate([...rows, rows[0]], "t3"));
  const movedEndpoint = { ...corpus.baseline.anchor, endTokenId: "t2" };
  assert.notEqual(digest(movedEndpoint), digest(corpus.baseline.anchor));
  assert.equal(movedEndpoint.logicalId, corpus.baseline.anchor.logicalId);
});

check("P02 merge/split many-to-many lineage without word loss", () => {
  const oldRows = corpus.baseline.rows.slice(0, 2);
  const merged = [{ id: "merged", headingId: "h1", tokens: oldRows.flatMap(row => row.tokens) }];
  const split = [
    { id: "split-a", headingId: "h1", tokens: merged[0].tokens.slice(0, 2) },
    { id: "split-b", headingId: "h1", tokens: merged[0].tokens.slice(2) },
  ];
  assert.deepEqual(tokenIds(split), tokenIds(oldRows));
  const edges = oldRows.map(row => ({ from: row.id, to: [...new Set(row.tokens.map(token => locate(split, token.id)))] }));
  assert.deepEqual(edges, [{ from: "r1", to: ["split-a", "split-b"] }, { from: "r2", to: ["split-b"] }]);
  assert.equal(new Set(edges.flatMap(edge => edge.to)).size, 2);
  const regrouped = { rows: split, audioEdit: structuredClone(corpus.baseline.audioEdit) };
  assert.deepEqual(regrouped.audioEdit, corpus.baseline.audioEdit);
  assert.equal(locate(split, "t1"), "split-a");
  assert.equal(locate(split, "t3"), "split-b"); // The old anchor now spans two rows; v1 cannot encode it as one range.
  // The sidecar can preserve audio independently. The actual compiler check rejects stale dependencies.
});

check("P03 linked appearances and duplicate signatures are not 1:1 identities", () => {
  const items = corpus.baseline.occurrences;
  assert.equal(items.filter(item => item.logicalId === "v1").length, 2);
  assert.equal(items.reduce((total, item) => total + item.recordRange[1] - item.recordRange[0], 0), 96);
  assert.equal(items[1].recordRange[1] - items[0].recordRange[0], 120); // Do not fill the interruption with invented active coverage.
  assert.equal(new Set(items.map(item => item.occurrenceId)).size, items.length);
  const duplicate = { ...items[0], occurrenceId: "copied-item" };
  const signature = item => digest([item.assetId, item.track, item.sourceRange, item.recordRange]);
  const candidates = [...items, duplicate].filter(item => signature(item) === signature(items[0]));
  assert.equal(candidates.length, 2); // A signature-only matcher must report ambiguity, never pick index 0.
  assert.notEqual(items[0].occurrenceId, duplicate.occurrenceId);
  assert.equal(items[0].logicalId, duplicate.logicalId);
  const rows = corpus.baseline.rows;
  const heads = [locate(rows, "t1"), locate(rows, "t6")].map(id => rows.find(row => row.id === id).headingId);
  assert.notEqual(heads[0], heads[1]); // Linked appearance evidence does NOT authorize I01 adoption.
});

// Half-open, sample-exact coverage of the entire PROGRAM audio, not just a named narration track.
function audioCut(observation) {
  if (!observation.available || !observation.complete || observation.precision !== "verified_samples") return "ambiguous";
  const [start, end] = corpus.baseline.wordAudio;
  return observation.program.some(([a, b]) => a < end && start < b) ? "unsupported" : "supported";
}
check("P04 verified omission versus picture/subword/precision ambiguity", () => {
  for (const example of corpus.audioObservations) assert.equal(audioCut(example), example.expected, example.id);
  assert.equal(audioCut(corpus.audioObservations[0]), "supported"); // Offline PICTURE is irrelevant to verified audio omission.
  assert.equal(corpus.audioObservations[0].pictureAvailable, false);
});

check("P05 dormant hide/reveal retains former range but not active coverage", () => {
  const saved = structuredClone(corpus.baseline.dormant);
  const hidden = { ...saved, state: "dormant", activeRanges: [] };
  assert.deepEqual(hidden.formerRange, saved.formerRange);
  assert.equal(hidden.activeRanges.length, 0);
  const restored = { ...hidden, state: "active", activeRanges: [hidden.formerRange] };
  assert.equal(restored.logicalId, saved.logicalId);
  assert.equal(restored.assetId, saved.assetId);
  assert.deepEqual(restored.activeRanges, [saved.formerRange]);
  // Restoration is representable; safe placement and available media still require a fresh review.
});

const overlaps = ([a, b], [c, d]) => a < d && c < b;
function placement(proposal) {
  const item = corpus.baseline.preserved;
  if (!proposal.verifiedAnchor) return { status: "ambiguous", item };
  const end = proposal.start + item.durationFrames;
  if (proposal.start < proposal.bounds[0] || end > proposal.bounds[1] ||
      proposal.occupied.some(range => overlaps([proposal.start, end], range))) return { status: "unsupported", item };
  return { status: proposal.start === item.recordStart ? "supported" : "review", item: { ...item, recordStart: proposal.start } };
}
check("P06 fixed-source 6.4s preserved placement: fit/review/unknown/collision", () => {
  for (const example of corpus.placements) {
    const result = placement(example);
    assert.equal(result.status, example.expected, example.id);
    assert.equal(result.item.durationFrames, 160);
    assert.equal(result.item.sourceStart, 800);
    assert.deepEqual(result.item.opaque, corpus.baseline.preserved.opaque);
    if (["unsupported", "ambiguous"].includes(result.status)) assert.deepEqual(result.item, corpus.baseline.preserved);
  }
  assert.equal(corpus.baseline.preserved.durationFrames / corpus.frameRate, 6.4);
});

function razor(boundary) {
  if (!boundary.sectionBoundary) return "unsupported";
  if (!boundary.completeProgramAudio || !boundary.completeProgramVideo || !boundary.tokenBoundary) return "ambiguous";
  if (boundary.crossingItems.length) return "unsupported";
  return "supported";
}
check("P07 structural razors require explicit section, A/V and word boundaries", () => {
  for (const example of corpus.razors) assert.equal(razor(example), example.expected, example.id);
});

function threeWay(base, script, timeline) {
  if (script === timeline) return "equal";
  if (script === base) return "timeline_only";
  if (timeline === base) return "script_only";
  return "conflict";
}
check("P08 common ancestor: compatible edits versus competing endpoint rewrites", () => {
  const fields = corpus.threeWay;
  const classifications = Object.fromEntries(Object.entries(fields).map(([field, values]) => [field, threeWay(...values)]));
  assert.deepEqual(classifications, { text: "script_only", endpoint: "timeline_only", competingEndpoint: "conflict", convergent: "equal" });
  // Independent fields can combine only after dependency/anchor validation, not by blanket "no conflict".
  assert.equal(locate(corpus.baseline.rows, fields.endpoint[2]), "r1");
  assert.throws(() => locate(corpus.baseline.rows, "deleted-anchor"));
});

function outboundGate(review, fresh) {
  if (digest(fresh) !== review.observedHash) return "stale";
  if (review.groups.some(group => ["unreviewed", "defer", "blocked"].includes(group.decision))) return "inbound_required";
  return "eligible_for_separate_outbound_review";
}
check("P09 one group decision, Defer roundtrip, stale/new changes gate outbound", () => {
  const review = {
    baselineHash: digest(corpus.baseline), scriptHash: digest(corpus.currentScript), observedHash: digest(corpus.currentTimeline),
    groups: [
      { id: "C07", axes: ["rowMove", "endpoint"], decision: "keep_script", pendingCorrection: true },
      { id: "C17", axes: ["competingEndpoint"], decision: "defer", evidence: corpus.threeWay.competingEndpoint },
    ],
  };
  const reopened = JSON.parse(JSON.stringify(review));
  assert.deepEqual(reopened, review);
  assert.equal(reopened.groups[0].decision, "keep_script"); // No per-axis decisions.
  assert.equal(outboundGate(reopened, corpus.currentTimeline), "inbound_required");
  assert.equal(reopened.groups[1].decision, "defer");
  const later = { ...corpus.currentTimeline, version: 3 };
  assert.equal(outboundGate(reopened, later), "stale");
  assert.equal(reopened.groups[1].decision, "defer"); // Retain deferred evidence; never silently reset/resolve it.
  const resolved = { ...reopened, groups: [{ ...reopened.groups[0] }] };
  assert.equal(outboundGate(resolved, corpus.currentTimeline), "eligible_for_separate_outbound_review");
  assert.equal(resolved.groups[0].pendingCorrection, true); // Eligibility is not execution or baseline advancement.
  for (const decision of ["unreviewed", "blocked"]) {
    assert.equal(outboundGate({ ...resolved, groups: [{ decision }] }, corpus.currentTimeline), "inbound_required");
  }
  assert.notEqual(digest(corpus.baseline), digest(corpus.currentScript));
  assert.notEqual(digest(corpus.baseline), digest(corpus.currentTimeline));
});

check("P10 paths are locators; unavailable or mismatched bytes never mean deletion", () => {
  const expected = createHash("sha256").update("asset-A").digest("hex");
  const verify = bytes => bytes === null ? "offline" : createHash("sha256").update(bytes).digest("hex") === expected ? "verified" : "mismatch";
  assert.equal(verify("asset-A"), "verified");
  assert.equal(verify("asset-B"), "mismatch");
  assert.equal(verify(null), "offline");
  assert.equal(corpus.media[0].locator, corpus.media[1].locator);
  assert.notEqual(corpus.media[0].assetId, corpus.media[1].assetId);
  const requests = [{ id: "affected", assetId: "asset-A" }, { id: "unaffected", assetId: "asset-C" }];
  const access = { "asset-A": "offline", "asset-C": "verified" };
  assert.deepEqual(requests.map(item => [item.id, access[item.assetId] === "verified" ? "available" : "blocked"]), [
    ["affected", "blocked"], ["unaffected", "available"],
  ]);
  assert.equal(requests.length, 2); // Scoped blocking; no missing-media deletion or global equivalence claim.
});

check("P11 swap assignments and replace assets without moving words or conflating slots", () => {
  const assignments = [{ slotId: "slot-a", rowId: "r1", assetId: "asset-A" }, { slotId: "slot-b", rowId: "r2", assetId: "asset-B" }];
  const swapped = assignments.map((item, index) => ({ ...item, assetId: assignments[1 - index].assetId }));
  assert.deepEqual(swapped.map(item => [item.slotId, item.rowId]), assignments.map(item => [item.slotId, item.rowId]));
  assert.notEqual(swapped[0].assetId, assignments[0].assetId);
  const replacement = { ...assignments[0], assetId: "asset-C" };
  assert.equal(replacement.slotId, assignments[0].slotId);
  assert.notEqual(replacement.assetId, assignments[0].assetId);
});

check("P12 document bed identity and duration end without an invented out-word", () => {
  const bed = { logicalId: "bed-1", assetId: "music-A", startTokenId: "t4", durationFrames: 160, endTokenId: null };
  const rows = corpus.baseline.rows;
  const appearances = [{ logicalId: bed.logicalId, rowId: "r2" }, { logicalId: bed.logicalId, rowId: "r3" }];
  assert.equal(new Set(appearances.map(item => item.logicalId)).size, 1);
  assert.equal(locate(rows, bed.startTokenId), "r2");
  assert.notEqual(rows[1].headingId, rows[2].headingId);
  assert.equal(bed.endTokenId, null);
  assert.equal(bed.durationFrames / corpus.frameRate, 6.4);
  // A representable document-level bed does not make cross-heading VisualEvent adoption safe.
});

assert.deepEqual(readFileSync(new URL("./synthetic.json", import.meta.url)), bytes);
console.log(`${passed.length} representation experiments passed; corpus SHA-256 ${createHash("sha256").update(bytes).digest("hex")}`);
for (const id of passed) console.log(id);
console.log("No Resolve connection, production mapping, source mutation or contract changes.");
