import type { ScriptDocumentV2 } from "./generated/contracts-v2.js";
import type { createResearchClient } from "./research-clip-client.js";
import { activeResearchQuoteUses, editResearchQuoteUseCitation, refreshResearchQuoteCitations, researchQuoteCitation } from "./research-quote-citations.js";
import { formatResearchSourceList, usedResearchLibraryItems } from "./research-source-list.js";

type Client = Pick<ReturnType<typeof createResearchClient>, "item" | "source">;

export async function refreshScriptCitations(document: ScriptDocumentV2, projectId: string, client: Client) {
  const ids = new Set(activeResearchQuoteUses(document).filter(({ quoteBox }) => !quoteBox.citationOverridden)
    .map(({ quoteBox }) => quoteBox.researchQuoteId.toLowerCase()));
  const citations = new Map<string, ReturnType<typeof researchQuoteCitation>>();
  const sources = new Map<string, Awaited<ReturnType<Client["source"]>>>();
  for (const id of ids) {
    const item = await client.item(projectId, id, "quote");
    const source = sources.get(item.sourceId) ?? await client.source(projectId, item.sourceId);
    sources.set(item.sourceId, source);
    citations.set(id, researchQuoteCitation(source, item.content));
  }
  return refreshResearchQuoteCitations(document, citations);
}

export async function editScriptCitation(
  document: ScriptDocumentV2, projectId: string, client: Client, overlayId: string, text: string,
) {
  if (text !== "--reset") return editResearchQuoteUseCitation(document, overlayId, { text });
  const use = activeResearchQuoteUses(document).find(({ id }) => id === overlayId);
  if (!use) throw new Error("Research quote box ID must name a use in an active script row.");
  const quote = await client.item(projectId, use.quoteBox.researchQuoteId, "quote");
  const source = await client.source(projectId, quote.sourceId);
  return editResearchQuoteUseCitation(document, overlayId, { reset: researchQuoteCitation(source, quote.content) });
}

export async function exportScriptSources(document: ScriptDocumentV2, projectId: string, client: Client) {
  const sources = new Map<string, Awaited<ReturnType<Client["source"]>>>();
  for (const use of usedResearchLibraryItems(document, projectId)) {
    const item = await client.item(use.projectId, use.itemId, use.kind);
    const key = `${use.projectId}/${item.sourceId}`;
    if (!sources.has(key)) sources.set(key, await client.source(use.projectId, item.sourceId));
  }
  return formatResearchSourceList([...sources.values()]);
}
