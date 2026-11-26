export interface ResearchQuoteUsage {
  kind: "quote";
  researchProjectId: string;
  itemId: string;
  scriptCount: number;
  scriptUses: Array<{ rowId: string; useId: string }>;
}

export function researchQuoteUsage(model: unknown, fallbackProjectId?: string): ResearchQuoteUsage[];

export interface ResearchStillUsage {
  kind: "still";
  researchProjectId: string;
  itemId: string;
  scriptCount: number;
  scriptUses: Array<{ rowId: string; placementId: string }>;
}

export function researchStillUsage(model: unknown): ResearchStillUsage[];
