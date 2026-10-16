/** Pure transformation of an accepted edit; caller owns evidence/decision authority.
 * No public operator bypass, synthesis, dependency reuse or native action.
 */
import { createHash } from "node:crypto";
import { canonicalJson, sha256CanonicalJson } from "./compiler-core.js";
import type { HostVisibilitySpan, NarrationAnnotation, NarrationBlock, PerformanceBeat, ScriptDocumentV1, TextAnchorRange, VisualBlock, VisualEvent } from "./generated/contracts.js";
import { validateScriptDocument } from "./script-validator.js";

export interface AcceptedOmission {
  expectedDocumentHash: string;
  blockId: string;
  tokenIds: string[];
}
type Anchored = HostVisibilitySpan | VisualEvent | NarrationAnnotation | PerformanceBeat;
interface AnchorOwner { entity: Anchored; narrationId: string | null; wrapper: VisualBlock | null }
export interface OmissionRevision {
  document: ScriptDocumentV1;
  documentJson: string;
  regeneration: { policy: "replace_whole_row"; blockId: string; blockRevision: number; text: string; textHash: string };
}
function requireFact(condition: boolean, message: string): asserts condition {
  if (!condition) throw new Error(message);
}
function next(value: number): number {
  requireFact(Number.isSafeInteger(value) && Number.isSafeInteger(value+1), "version/sequence must remain exact safe integer");
  return value+1;
}
function anchors(document: ScriptDocumentV1): AnchorOwner[] {
  return document.activeDraft.blocks.flatMap((block): AnchorOwner[] => {
    if(block.type==="visual") return [{entity:block.event,narrationId:null,wrapper:block}];
    if(block.type!=="narration")return [];
    return [...block.hostVisibilitySpans,...block.visualEvents,...(block.annotations??[]),...(block.performanceBeats??[])].map(entity=>({entity,narrationId:block.id,wrapper:null}));
  });
}
function quote(range: TextAnchorRange, tokens: NarrationBlock): string {
  const start=tokens.tokens.findIndex(token=>token.id===range.startTokenId)+(range.startAffinity==="after"?1:0);
  const end=tokens.tokens.findIndex(token=>token.id===range.endTokenId)+(range.endAffinity==="after"?1:0);
  const first=tokens.tokens[start];const last=tokens.tokens[end-1];
  requireFact(start>=0&&end>start&&first!==undefined&&last!==undefined,"omission leaves an empty anchor");
  return tokens.text.slice(first.startOffset,last.endOffset);
}

export function applyAcceptedOmission(input: ScriptDocumentV1, edit: AcceptedOmission): OmissionRevision {
  // The proof caller must independently establish/accept the audible edit and
  // bind this exact current document. IDs/hash alone do not prove authorization.
  requireFact(validateScriptDocument(input).valid,"actual script validator refused input");
  requireFact(edit.expectedDocumentHash===sha256CanonicalJson(input),"stale current document hash");
  requireFact(canonicalJson(Object.keys(edit).sort())===canonicalJson(["blockId","expectedDocumentHash","tokenIds"]),"unexpected omission edit fields");
  const original=input.activeDraft.blocks.find(block=>block.id===edit.blockId);
  requireFact(original?.type==="narration"&&original.state==="active","active narration row required");
  requireFact(original.tokens.length<=64&&Array.isArray(edit.tokenIds)&&edit.tokenIds.length>0&&new Set(edit.tokenIds).size===edit.tokenIds.length,"unique bounded selected token IDs required");
  const positions=edit.tokenIds.map(identity=>original.tokens.findIndex(token=>token.id===identity));
  const first=positions[0]!;const last=positions.at(-1)!;
  requireFact(first>0&&last<original.tokens.length-1&&positions.every((value,index)=>value===first+index),"ordered contiguous interior token IDs required");
  const previous=original.tokens[first-1]!;const following=original.tokens[last+1]!;
  for(let index=first;index<=last+1;index+=1){
    requireFact(/^[ \t\r\n]*$/u.test(original.text.slice(original.tokens[index-1]!.endOffset,original.tokens[index]!.startOffset)),"unsupported joining-gap punctuation/whitespace");
  }
  requireFact(!/[.!?]$/u.test(previous.value)&&!/[.!?]/u.test(original.text.slice(original.tokens[first]!.startOffset,original.tokens[last]!.endOffset)),"sentence punctuation boundary is unsupported");
  const removed=new Set(edit.tokenIds);
  const document=structuredClone(input);
  const block=document.activeDraft.blocks.find(candidate=>candidate.id===original.id);
  requireFact(block?.type==="narration","missing cloned narration row");
  const refs=anchors(document).filter(owner=>owner.entity.range.blockId===block.id);
  for(const owner of refs){
    requireFact(owner.narrationId===null||owner.narrationId===block.id,"cross-narration anchor ownership is unsupported");
    requireFact(!removed.has(owner.entity.range.startTokenId)&&!removed.has(owner.entity.range.endTokenId),"removed anchor endpoint is unsupported");
  }
  // Native .length/.slice count UTF-16 units, including astral text in the cut.
  // Join only the accepted span; do not tokenize, reorder or repair grammar.
  const delta=1-(following.startOffset-previous.endOffset);
  block.text=original.text.slice(0,previous.endOffset)+" "+original.text.slice(following.startOffset);
  const kept=block.tokens.filter(token=>!removed.has(token.id)).map(token=>token.startOffset>=following.startOffset?{...token,startOffset:token.startOffset+delta,endOffset:token.endOffset+delta}:token);
  const head=kept[0];requireFact(head!==undefined,"empty narration after omission");
  block.tokens=[head,...kept.slice(1)];block.version=next(original.version);
  for(const owner of refs){
    const text=quote(owner.entity.range,block);
    if(text===owner.entity.range.quotedText)continue;
    owner.entity.range.quotedText=text;owner.entity.range.anchorVersion=next(owner.entity.range.anchorVersion);
    owner.entity.version=next(owner.entity.version);
    if(owner.wrapper)owner.wrapper.version=next(owner.wrapper.version);
  }
  document.liveHeadSequence=next(input.liveHeadSequence);document.liveStateVector="";
  document.liveContentHash=sha256CanonicalJson(Object.fromEntries(Object.entries(document).filter(([key])=>key!=="liveContentHash")));
  // A wording edit invalidates old narration deps. Validate the script now;
  // compile only after a whole-row service handoff supplies fresh audio/marks.
  const validation=validateScriptDocument(document);
  requireFact(validation.valid,`actual script validator refused omission: ${canonicalJson(validation.diagnostics)}`);
  return {document,documentJson:canonicalJson(document),regeneration:{policy:"replace_whole_row",blockId:block.id,blockRevision:block.version,text:block.text,textHash:`sha256:${createHash("sha256").update(block.text,"utf8").digest("hex")}`}};
}
