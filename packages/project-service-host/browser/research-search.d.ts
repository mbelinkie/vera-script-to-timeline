export interface LoggedResearchSearchClip {
  id: string;
  projectId: string;
  createdAt?: string;
  video: { title: string; youtubeVideoId?: string };
  englishText: string;
  originalText?: string;
  selection: { text: string };
  createdBy?: string;
  logger?: string;
  topics?: string[];
}

export interface LoggedResearchSearchQuote {
  itemId: string;
  researchProjectId: string;
  text?: string;
  displayText?: string;
  speakerName?: string;
  speakerTitle?: string;
  sourceTitle?: string;
  citationText?: string;
  credit?: string;
  logger?: string;
  topics?: string[];
  createdAt?: string;
}

export interface LoggedResearchSearchStill {
  itemId: string;
  researchProjectId: string;
  title: string;
  sourceTitle?: string;
  credit?: string;
  logger?: string;
  topics?: string[];
  createdAt?: string;
}

export interface LoggedResearchSearchUsage {
  kind?: "footage" | "quote" | "still";
  researchProjectId: string;
  clipId?: string;
  itemId?: string;
  quoteId?: string;
  scriptCount: number;
  stashCount?: number;
}

export interface LoggedResearchSearchFilters {
  projectId: string;
  query?: string;
  seed?: string;
  kind?: "all" | "footage" | "quotes" | "stills";
  logger?: string;
  topic?: string;
  showUsed?: boolean;
  sort?: "newest" | "oldest" | "title";
}

export type LoggedResearchLibraryResult<TClip, TQuote, TStill = never> =
  | { kind: "footage"; item: TClip & { itemId?: string } }
  | { kind: "quote"; item: TQuote & { id?: string } }
  | { kind: "still"; item: TStill & { id?: string } };

export function filterLoggedResearchClips<T extends LoggedResearchSearchClip>(
  clips: readonly T[], usage: readonly LoggedResearchSearchUsage[], filters: LoggedResearchSearchFilters,
): T[];

export function filterResearchLibraryItems<TClip extends LoggedResearchSearchClip,
  TQuote extends LoggedResearchSearchQuote, TStill extends LoggedResearchSearchStill = never>(
  clips: readonly TClip[], quotes: readonly TQuote[], usage: readonly LoggedResearchSearchUsage[],
  filters?: LoggedResearchSearchFilters, stills?: readonly TStill[],
): Array<LoggedResearchLibraryResult<TClip, TQuote, TStill>>;

export function libraryFilterOptions(
  clips: readonly LoggedResearchSearchClip[], quotes: readonly LoggedResearchSearchQuote[], stills?: readonly LoggedResearchSearchStill[],
): { loggers: Array<[string, string]>; topics: string[] };
