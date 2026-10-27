import type { NarrationBlockV2, NarrationToken } from "./generated/contracts-v2.js";

export interface StageDirectionRunV2 {
  startTokenIndex: number;
  endTokenIndexExclusive: number;
  openOffset: number;
  closeOffset: number;
}

export interface StageDirectionIssueV2 {
  tokenIndex: number;
  message: string;
}

export interface SpokenNarrationViewV2 {
  text: string;
  tokens: NarrationToken[];
}

/** Find only bracket pairs explicitly marked by nonspoken tokens. */
export function inspectStageDirectionsV2(row: NarrationBlockV2): {
  runs: StageDirectionRunV2[];
  issues: StageDirectionIssueV2[];
} {
  const runs: StageDirectionRunV2[] = [];
  const issues: StageDirectionIssueV2[] = [];
  let index = 0;
  while (index < row.tokens.length) {
    if (row.tokens[index]!.spoken !== false) {
      index += 1;
      continue;
    }
    const startTokenIndex = index;
    index += 1;
    while (
      index < row.tokens.length &&
      row.tokens[index]!.spoken === false &&
      !/[[\]]/u.test(row.text.slice(row.tokens[index - 1]!.endOffset, row.tokens[index]!.startOffset))
    ) index += 1;
    const endTokenIndexExclusive = index;
    const first = row.tokens[startTokenIndex]!;
    const last = row.tokens[endTokenIndexExclusive - 1]!;
    const openOffset = first.startOffset - 1;
    const closeOffset = last.endOffset;
    if (row.text[openOffset] !== "[" || row.text[closeOffset] !== "]") {
      issues.push({ tokenIndex: startTokenIndex, message: "Direction tokens must have one complete square-bracket pair." });
      continue;
    }
    if (
      /[[\]]/u.test(row.text.slice(first.startOffset, last.endOffset)) ||
      row.text[openOffset - 1] === "[" ||
      row.text[closeOffset + 1] === "]"
    ) {
      issues.push({ tokenIndex: startTokenIndex, message: "Nested or literal brackets inside a direction pair are unsupported." });
      continue;
    }
    runs.push({ startTokenIndex, endTokenIndexExclusive, openOffset, closeOffset });
  }
  return { runs, issues };
}

export function spokenTokensV2(row: NarrationBlockV2): NarrationToken[] {
  return row.tokens.filter((token) => token.spoken !== false);
}

/** A clean prompter view with the stage-direction pair and its words removed. */
export function spokenNarrationViewV2(row: NarrationBlockV2): SpokenNarrationViewV2 {
  const { runs, issues } = inspectStageDirectionsV2(row);
  if (issues.length > 0) throw new Error(issues[0]!.message);

  const removals = runs.map(({ openOffset, closeOffset }) => {
    let start = openOffset;
    let end = closeOffset + 1;
    while (/[ \t]/u.test(row.text[end] ?? "")) end += 1;
    if (/^[ \t]*$/u.test(row.text.slice(0, start))) start = 0;
    else if (end === row.text.length || /[,.!?;:)\]}"'”’]/u.test(row.text[end] ?? "")) {
      while (/[ \t]/u.test(row.text[start - 1] ?? "")) start -= 1;
    } else if (!/[ \t\r\n"'“‘]/u.test(row.text[start - 1] ?? "")) end = closeOffset + 1;
    return { start, end };
  }).reduce<{ start: number; end: number }[]>((merged, range) => {
    const prior = merged.at(-1);
    if (prior && range.start <= prior.end) prior.end = Math.max(prior.end, range.end);
    else merged.push(range);
    return merged;
  }, []);
  for (const range of removals) {
    if (range.end === row.text.length || /[,.!?;:)\]}"'”’]/u.test(row.text[range.end] ?? "")) {
      while (/[ \t]/u.test(row.text[range.start - 1] ?? "")) range.start -= 1;
    }
  }
  let text = "";
  let cursor = 0;
  for (const removal of removals) {
    text += row.text.slice(cursor, removal.start);
    cursor = removal.end;
  }
  text += row.text.slice(cursor);
  const offsetAfterRemoval = (offset: number): number => offset - removals.reduce(
    (removed, range) => removed + (range.end <= offset ? range.end - range.start : 0),
    0,
  );
  const tokens = spokenTokensV2(row).map((token) => ({
    ...token,
    startOffset: offsetAfterRemoval(token.startOffset),
    endOffset: offsetAfterRemoval(token.endOffset),
  }));
  return { text, tokens };
}

/** Mask directions with equal-width spaces so provider timing offsets stay in authored-text UTF-16 coordinates. */
export function maskStageDirectionsV2(row: NarrationBlockV2): string {
  const { runs, issues } = inspectStageDirectionsV2(row);
  if (issues.length > 0) throw new Error(issues[0]!.message);
  let text = row.text;
  for (const run of [...runs].reverse()) {
    const end = run.closeOffset + 1;
    text = `${text.slice(0, run.openOffset)}${" ".repeat(end - run.openOffset)}${text.slice(end)}`;
  }
  return text;
}

/** Comment quotes ignore only the recognized delimiters; literal bracket text remains untouched. */
export function commentQuoteV2(row: NarrationBlockV2, start: number, end: number): string {
  const { runs } = inspectStageDirectionsV2(row);
  const markers = new Set(runs.flatMap(({ openOffset, closeOffset }) => [openOffset, closeOffset]));
  let result = "";
  for (let offset = start; offset < end; offset += 1) {
    if (!markers.has(offset)) result += row.text[offset] ?? "";
  }
  return result;
}
