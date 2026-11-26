export interface ResearchQuoteUsage {
  kind: "quote";
  researchProjectId: string;
  itemId: string;
  scriptCount: number;
  scriptUses: Array<{ rowId: string; useId: string }>;
}

export function researchQuoteUsage(model: unknown, fallbackProjectId?: string): ResearchQuoteUsage[];
