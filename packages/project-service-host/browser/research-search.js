/** Filter an ALREADY authorized Research catalog. No search field grants authorization. */
export function filterLoggedResearchClips(clips, usage, filters) {
  const projectId = String(filters.projectId ?? "").toLowerCase();
  const query = String(filters.query ?? "").trim().toLocaleLowerCase("en-US");
  const seed = String(filters.seed ?? "").trim().toLocaleLowerCase("en-US");
  const showUsed = filters.showUsed === true;
  const sort = ["newest", "oldest", "title"].includes(filters.sort) ? filters.sort : "newest";
  const key = (project, clip) => JSON.stringify([String(project).toLowerCase(), String(clip).toLowerCase()]);
  const useCounts = new Map(usage.map((entry) =>
    [key(entry.researchProjectId, entry.clipId), entry.scriptCount]));
  const title = (clip) => String(clip.video.title);
  // D130: ONLY title and full saved transcript, not ID, createdBy, labels,
  // dates, channel or displayed shortened excerpts.
  const searchable = (clip) => [clip.video.title, clip.englishText, clip.selection.text, clip.originalText ?? ""]
    .map((part) => String(part).toLocaleLowerCase("en-US"));
  const loggedDate = (clip) => {
    const time = Date.parse(clip.createdAt ?? "");
    return Number.isFinite(time) ? time : 0;
  };
  const tie = (a, b) => title(a).localeCompare(title(b), undefined, { sensitivity: "base" }) ||
    a.id.localeCompare(b.id);
  const words = [...new Set(seed.match(/[\p{L}\p{N}]+/gu) ?? [])];
  const relevance = (clip) => {
    const parts = searchable(clip);
    return words.reduce((score, word) => score + (parts[0].includes(word) ? 2 : parts.some((part) => part.includes(word)) ? 1 : 0), 0);
  };
  return clips.filter((clip) => {
    if (String(clip.projectId).toLowerCase() !== projectId) return false;
    if (!showUsed && (useCounts.get(key(clip.projectId, clip.id)) ?? 0) > 0) return false;
    return !query || searchable(clip).some((part) => part.includes(query));
  }).sort((a, b) => (words.length ? relevance(b) - relevance(a) : 0) ||
    (sort === "title"
      ? title(a).localeCompare(title(b), undefined, { sensitivity: "base" }) ||
        loggedDate(b) - loggedDate(a) || a.id.localeCompare(b.id)
      : (sort === "newest" ? loggedDate(b) - loggedDate(a) : loggedDate(a) - loggedDate(b)) || tie(a, b)));
}
