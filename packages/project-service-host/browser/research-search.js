/** Filter an ALREADY authorized Research catalog. No search field grants authorization. */
export function filterLoggedResearchClips(clips, usage, filters) {
  return filterResearchLibraryItems(clips, [], usage, { ...filters, kind: "footage" })
    .map(({ item }) => item);
}

/** Search the already-authorized mixed Library list without widening clip search fields. */
export function filterResearchLibraryItems(clips, quotes, usage, filters = {}) {
  const projectId = String(filters.projectId ?? "").toLowerCase();
  const query = String(filters.query ?? "").trim().toLocaleLowerCase("en-US");
  const seed = String(filters.seed ?? "").trim().toLocaleLowerCase("en-US");
  const showUsed = filters.showUsed === true;
  const kind = ["all", "footage", "quotes"].includes(filters.kind) ? filters.kind : "all";
  const sort = ["newest", "oldest", "title"].includes(filters.sort) ? filters.sort : "newest";
  const logger = String(filters.logger ?? "").toLowerCase();
  const topic = String(filters.topic ?? "").toLocaleLowerCase("en-US");
  const key = (type, project, item) => JSON.stringify([type, String(project).toLowerCase(), String(item).toLowerCase()]);
  const useCounts = new Map(usage.map((entry) => [
    key(entry.kind ?? "footage", entry.researchProjectId, entry.itemId ?? entry.clipId ?? entry.quoteId),
    entry.scriptCount ?? entry.count ?? 0,
  ]));
  const clipsEnabled = kind !== "quotes";
  const quotesEnabled = kind !== "footage";
  const rows = [
    ...(clipsEnabled ? clips.map((item) => ({ kind: "footage", item })) : []),
    ...(quotesEnabled ? quotes.map((item) => ({ kind: "quote", item })) : []),
  ].map((entry) => {
    const item = entry.item;
    const project = entry.kind === "quote" ? item.researchProjectId : item.projectId;
    const id = entry.kind === "quote" ? item.itemId : item.id;
    const title = entry.kind === "quote" ? (item.sourceTitle || item.speakerName || "Research quote") : String(item.video?.title ?? "");
    // D130: clips remain searchable only by title and complete saved transcript.
    const search = entry.kind === "quote"
      ? [item.sourceTitle, item.text, item.displayText, item.speakerName, item.speakerTitle, item.citationText, item.credit]
      : [item.video?.title, item.englishText, item.selection?.text, item.originalText];
    const parts = search.map((part) => String(part ?? "").toLocaleLowerCase("en-US"));
    const loggerId = String(entry.kind === "quote" ? item.logger ?? "" : item.createdBy ?? item.logger ?? "").toLowerCase();
    const topics = (item.topics ?? []).map((value) => String(value).toLocaleLowerCase("en-US"));
    return { ...entry, project, id, title, parts, loggerId, topics,
      createdAt: Date.parse(item.createdAt ?? "") || 0,
      usage: useCounts.get(key(entry.kind, project, id)) ?? 0 };
  });
  const words = [...new Set(seed.match(/[\p{L}\p{N}]+/gu) ?? [])];
  const relevance = (row) => words.reduce((score, word) => score +
    (row.parts[0]?.includes(word) ? 2 : row.parts.some((part) => part.includes(word)) ? 1 : 0), 0);
  const tie = (a, b) => a.title.localeCompare(b.title, undefined, { sensitivity: "base" }) || a.id.localeCompare(b.id);
  return rows.filter((row) => {
    if (String(row.project).toLowerCase() !== projectId) return false;
    if (!showUsed && row.usage > 0) return false;
    if (logger && row.loggerId !== logger) return false;
    if (topic && !row.topics.includes(topic)) return false;
    return !query || row.parts.some((part) => part.includes(query));
  }).sort((a, b) => (words.length ? relevance(b) - relevance(a) : 0) ||
    (sort === "title"
      ? a.title.localeCompare(b.title, undefined, { sensitivity: "base" }) ||
        b.createdAt - a.createdAt || a.id.localeCompare(b.id)
      : (sort === "newest" ? b.createdAt - a.createdAt : a.createdAt - b.createdAt) || tie(a, b)));
}

export function libraryFilterOptions(clips, quotes) {
  const loggers = new Map();
  const topics = new Set();
  for (const item of [...clips, ...quotes]) {
    const logger = item.logger ?? item.createdBy;
    if (logger) loggers.set(String(logger).toLowerCase(), String(logger));
    for (const topic of item.topics ?? []) if (topic) topics.add(String(topic));
  }
  return {
    loggers: [...loggers].sort((a, b) => a[1].localeCompare(b[1])),
    topics: [...topics].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" })),
  };
}
