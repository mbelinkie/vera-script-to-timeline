import type { ScriptDocumentV2 } from "./generated/contracts-v2.js";
import type { createResearchClient } from "./research-clip-client.js";
import { activeResearchQuoteUses, editResearchQuoteUseCitation, refreshResearchQuoteCitations, researchQuoteCitation } from "./research-quote-citations.js";
import { formatResearchSourceList, usedResearchLibraryItems } from "./research-source-list.js";

type Client = Pick<ReturnType<typeof createResearchClient>, "item" | "source">;

export async function refreshScriptCitations(document: ScriptDocumentV2, projectId: string, client: Client) {
  const uses = new Map<string, { projectId: string; quoteId: string; sourceId?: string }>();
  for (const { quoteBox } of activeResearchQuoteUses(document)) {
    if (quoteBox.citationOverridden) continue;
    const useProjectId = quoteBox.researchProjectId ?? projectId;
    const quoteId = quoteBox.researchQuoteId.toLowerCase();
    uses.set(`${useProjectId.toLowerCase()}\u0000${quoteId}`, {
      projectId: useProjectId, quoteId, ...(quoteBox.researchSourceId ? { sourceId: quoteBox.researchSourceId } : {}),
    });
  }
  const citations = new Map<string, ReturnType<typeof researchQuoteCitation>>();
  const sources = new Map<string, Awaited<ReturnType<Client["source"]>>>();
  for (const [key, use] of uses) {
    const item = await client.item(use.projectId, use.quoteId, "quote");
    const sourceId = use.sourceId ?? item.sourceId;
    const sourceKey = `${use.projectId.toLowerCase()}\u0000${sourceId.toLowerCase()}`;
    const source = sources.get(sourceKey) ?? await client.source(use.projectId, sourceId);
    sources.set(sourceKey, source);
    citations.set(key, researchQuoteCitation(source, item.content));
  }
  return refreshResearchQuoteCitations(document, citations, projectId);
}

export async function editScriptCitation(
  document: ScriptDocumentV2, projectId: string, client: Client, overlayId: string, text: string,
) {
  if (text !== "--reset") return editResearchQuoteUseCitation(document, overlayId, { text });
  const use = activeResearchQuoteUses(document).find(({ id }) => id === overlayId);
  if (!use) throw new Error("Research quote box ID must name a use in an active script row.");
  const useProjectId = use.quoteBox.researchProjectId ?? projectId;
  const quote = await client.item(useProjectId, use.quoteBox.researchQuoteId, "quote");
  const source = await client.source(useProjectId, use.quoteBox.researchSourceId ?? quote.sourceId);
  return editResearchQuoteUseCitation(document, overlayId, { reset: researchQuoteCitation(source, quote.content) });
}

export async function exportScriptSources(document: ScriptDocumentV2, projectId: string, client: Client) {
  const sources = new Map<string, Awaited<ReturnType<Client["source"]>>>();
  for (const use of usedResearchLibraryItems(document, projectId)) {
    const sourceId = use.sourceId ?? (await client.item(use.projectId, use.itemId, use.kind)).sourceId;
    const key = `${use.projectId.toLowerCase()}/${sourceId.toLowerCase()}`;
    if (!sources.has(key)) sources.set(key, await client.source(use.projectId, sourceId));
  }
  return formatResearchSourceList([...sources.values()]);
}
