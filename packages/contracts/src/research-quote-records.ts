import { readResearchLibraryItem, type ResearchLibrarySource } from "./research-library-records.js";
import { researchQuoteCitation } from "./research-quote-citations.js";

export interface ResearchQuoteChoice {
  itemId: string;
  researchProjectId: string;
  sourceId: string;
  itemVersion: number;
  text: string;
  displayText: string;
  speakerName?: string;
  speakerTitle?: string;
  sourceTitle?: string;
  citationText: string;
  createdAt?: string;
  logger?: string;
  topics?: string[];
  credit?: string;
}

export type ResearchQuoteRecord = ResearchQuoteChoice & {
  italicSpan: ReturnType<typeof researchQuoteCitation>["italicSpan"];
  citationOverridden?: true;
  sourceKind?: ResearchLibrarySource["kind"];
};

const UUID = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/iu;

function optionalText(value: unknown, max = 20_000): string | undefined {
  if (value === undefined) return undefined;
  if (typeof value !== "string" || value.length > max || /[\0\p{Surrogate}]/u.test(value)) {
    throw new Error("Research returned invalid quote text.");
  }
  return value;
}

export function readResearchQuote(value: unknown, projectId: string, expectedItemId?: string) {
  const raw = value as Record<string, unknown> | null;
  const itemId = raw?.id;
  if (typeof itemId !== "string" || !UUID.test(itemId)) throw new Error("Research returned an invalid quote ID.");
  const item = readResearchLibraryItem(value, projectId, expectedItemId ?? itemId, "quote");
  const text = optionalText(item.content.text)?.trim();
  const displayText = optionalText(item.content.latestDisplayText)?.trim();
  const speakerName = optionalText(item.content.speaker, 500);
  const speakerTitle = optionalText(item.content.speakerTitle, 500);
  const location = optionalText(item.content.location);
  const citationOverride = optionalText(item.content.citationOverride);
  const createdAt = optionalText(raw?.createdAt, 64);
  const logger = optionalText(raw?.createdBy, 36);
  const topics = raw?.topics ?? [];
  if (!text || (logger !== undefined && !UUID.test(logger)) ||
      (createdAt !== undefined && !Number.isFinite(Date.parse(createdAt))) ||
      !Array.isArray(topics) || topics.length > 100 ||
      !topics.every((topic): topic is string => typeof topic === "string" && !!optionalText(topic, 200))) {
    throw new Error("Research returned invalid quote metadata.");
  }
  return {
    itemId: itemId.toLowerCase(), researchProjectId: projectId.toLowerCase(),
    sourceId: item.sourceId, itemVersion: item.version, text, displayText: displayText || text,
    ...(speakerName === undefined ? {} : { speakerName }),
    ...(speakerTitle === undefined ? {} : { speakerTitle }),
    ...(createdAt === undefined ? {} : { createdAt }),
    ...(logger === undefined ? {} : { logger }),
    topics, details: {
      ...(location === undefined ? {} : { location }),
      ...(citationOverride === undefined ? {} : { citationOverride }),
    },
  };
}

export function describeResearchQuote(
  quote: ReturnType<typeof readResearchQuote>, source: ResearchLibrarySource,
): ResearchQuoteRecord {
  const { details, ...choice } = quote;
  const { title, credit } = source.bibliography;
  return {
    ...choice, ...researchQuoteCitation(source, details), sourceKind: source.kind,
    ...(title === undefined ? {} : { sourceTitle: title.value }),
    ...(credit === undefined ? {} : { credit: credit.value }),
    ...(details.citationOverride === undefined ? {} : { citationOverridden: true }),
  };
}

export function publicResearchQuote(quote: ResearchQuoteRecord) {
  const { itemId, researchProjectId, sourceId, itemVersion, text, displayText, speakerName,
    speakerTitle, sourceTitle, citationText, createdAt, logger, topics, credit } = quote;
  return { itemId, researchProjectId, sourceId, itemVersion, text, displayText, speakerName,
    speakerTitle, sourceTitle, citationText, createdAt, logger, topics, credit };
}
