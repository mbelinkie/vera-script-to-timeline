export interface LoggedResearchSearchClip {
  id: string;
  projectId: string;
  createdAt?: string;
  video: { title: string };
  englishText: string;
  originalText?: string;
  selection: { text: string };
}

export interface LoggedResearchSearchUsage {
  researchProjectId: string;
  clipId: string;
  scriptCount: number;
  stashCount?: number;
}

export interface LoggedResearchSearchFilters {
  projectId: string;
  query?: string;
  seed?: string;
  showUsed?: boolean;
  sort?: "newest" | "oldest" | "title";
}

export function filterLoggedResearchClips<T extends LoggedResearchSearchClip>(
  clips: readonly T[], usage: readonly LoggedResearchSearchUsage[], filters: LoggedResearchSearchFilters,
): T[];
