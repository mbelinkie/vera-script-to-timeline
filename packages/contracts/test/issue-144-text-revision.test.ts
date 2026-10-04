import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";
import { canonicalJson, sha256CanonicalJson } from "../src/compiler-core.js";
import type { NarrationBlock, ScriptDocumentV1, TextAnchorRange, VisualBlock } from "../src/generated/contracts.js";
import { applyAcceptedOmission } from "../src/issue-144-text-revision.js";
import { validateScriptDocument } from "../src/script-validator.js";
import { id, inputs } from "./issue-144-test-inputs.js";

function row(document: ScriptDocumentV1): NarrationBlock {
  const block = document.activeDraft.blocks[1];
  if (block?.type !== "narration") throw new Error("missing narration");
  return block;
}
function sample(): ScriptDocumentV1 {
  const document = inputs().currentDocument;
  row(document).visualEvents[0]!.range.endTokenId = id(4);
  row(document).visualEvents[0]!.range.quotedText = "Bravo Charlie Delta";
  return document;
}
function range(document: ScriptDocumentV1, first = 1, last = 5): TextAnchorRange {
  const block = row(document);
  const a = block.tokens[first-1]!; const b = block.tokens[last-1]!;
  return { blockId: block.id, startTokenId: a.id, endTokenId: b.id,
    startAffinity: "before", endAffinity: "after", quotedText: block.text.slice(a.startOffset,b.endOffset), anchorVersion: 1 };
}
function rewriteInput(document: ScriptDocumentV1, text: string): void {
  const block = row(document);
  const tokens = [...text.matchAll(/\S+/gu)].map((match,index) => ({ id: id(index+1), value: match[0], startOffset: match.index, endOffset: match.index+match[0].length }));
  const first = tokens[0]; if (!first) throw new Error("empty test row");
  block.text = text; block.tokens = [first,...tokens.slice(1)];
  block.hostVisibilitySpans[0]!.range = range(document);
  block.visualEvents[0]!.range = range(document,2,4);
}
function omit(document: ScriptDocumentV1, tokenIds = [id(3)]) {
  return applyAcceptedOmission(document,{ expectedDocumentHash: sha256CanonicalJson(document), blockId: row(document).id, tokenIds });
}
function standalone(document: ScriptDocumentV1, first: number, last: number, suffix: number): VisualBlock {
  const event = structuredClone(row(document).visualEvents[0]!);
  event.id = id(suffix+1); event.range = range(document,first,last); event.layer = suffix;
  const block: VisualBlock = { type: "visual", id: id(suffix), orderKey: `b${suffix}`, event, version: 1 };
  document.activeDraft.blocks.push(block); return block;
}

describe("Issue144 accepted omission canonical transformation (no acceptance/proof authority)",()=>{
  it("removes Charlie, preserves identities, reanchors and requests complete fresh VO",()=>{
    const document = sample(); const original = canonicalJson(document); const before = row(document);
    const result = omit(document); const after = row(result.document);
    expect(after.text).toBe("Alpha Bravo Delta Echo");
    expect(after.tokens.map(t=>t.id)).toEqual([id(1),id(2),id(4),id(5)]);
    expect(after.tokens.map(t=>[t.startOffset,t.endOffset])).toEqual([[0,5],[6,11],[12,17],[18,22]]);
    expect(after.version).toBe(before.version+1);
    expect(after.visualEvents[0]!.range.quotedText).toBe("Bravo Delta");
    expect(after.visualEvents[0]!.range.anchorVersion).toBe(before.visualEvents[0]!.range.anchorVersion+1);
    expect(after.visualEvents[0]!.version).toBe(before.visualEvents[0]!.version+1);
    expect(after.hostVisibilitySpans[0]!.range.quotedText).toBe(after.text);
    expect(result.document.liveHeadSequence).toBe(document.liveHeadSequence+1);
    expect(result.document.liveStateVector).toBe("");
    expect(result.document.liveContentHash).toBe(sha256CanonicalJson(Object.fromEntries(Object.entries(result.document).filter(([k])=>k!=="liveContentHash"))));
    expect(result.regeneration).toEqual({ policy: "replace_whole_row", blockId: after.id, blockRevision: after.version, text: after.text, textHash: `sha256:${createHash("sha256").update(after.text).digest("hex")}` });
    expect(result.documentJson).toBe(canonicalJson(result.document));
    expect(validateScriptDocument(result.document).valid).toBe(true);
    expect(omit(document)).toEqual(result);
    expect(canonicalJson(document)).toBe(original);
    expect(result).not.toHaveProperty("dependencies");
  });
  it("removes multiple interior tokens with the exact single-space join",()=>{
    const document = sample(); row(document).visualEvents[0]!.range = range(document);
    expect(row(omit(document,[id(2),id(3)]).document).text).toBe("Alpha Delta Echo");
  });
  it.each([" ","\t","\r\n"," \t\n"])("normalizes only the joining gaps (%j)",(separator)=>{
    const document=sample();rewriteInput(document,`Alpha Bravo${separator}Charlie${separator}Delta Echo`);
    expect(row(omit(document).document).text).toBe("Alpha Bravo Delta Echo");
  });
  it.each(["😀Alpha Bravo Charlie Delta Echo","Alpha Bravo 😀Charlie Delta Echo","Alpha Bravo Charlie 😀Delta Echo"])("uses actual UTF-16 delta for %s",text=>{
    const document=sample();rewriteInput(document,text);
    const result=omit(document); const block=row(result.document);
    const expected=text.replace(/[^ ]+ (?=[^ ]+ [^ ]+$)/u, "");
    expect(block.text).toBe(expected);
    expect(block.tokens[2]!.startOffset).toBe(text.startsWith("😀")?14:12);
    expect(block.tokens[2]!.endOffset-block.tokens[2]!.startOffset).toBe(block.tokens[2]!.value.length);
    expect(validateScriptDocument(result.document).valid).toBe(true);
  });
  it("preserves another narration row byte-for-byte",()=>{
    const document=sample();const second=structuredClone(row(document));
    second.id=id(60);second.orderKey="c0";
    second.tokens.forEach((t,i)=>{t.id=id(70+i);});
    second.hostVisibilitySpans[0]!.id=id(80);
    second.hostVisibilitySpans[0]!.range={...second.hostVisibilitySpans[0]!.range,blockId:second.id,startTokenId:id(70),endTokenId:id(74)};
    second.visualEvents=[];
    document.activeDraft.blocks.push(second);
    expect(validateScriptDocument(document).valid).toBe(true);
    const before=canonicalJson(second);const result=omit(document);
    expect(canonicalJson(result.document.activeDraft.blocks.at(-1))).toBe(before);
  });
  it("refuses anchors owned by another narration row rather than altering it",()=>{
    const document=sample();const second=structuredClone(row(document));
    second.id=id(200);second.orderKey="d0";
    second.tokens.forEach((t,i)=>{t.id=id(210+i);});
    second.hostVisibilitySpans[0]!.id=id(220);
    second.hostVisibilitySpans[0]!.range={...second.hostVisibilitySpans[0]!.range,blockId:second.id,startTokenId:id(210),endTokenId:id(214)};
    second.visualEvents[0]!.id=id(221);
    document.activeDraft.blocks.push(second);
    // The accepted validator already rejects a narration-owned visual anchored
    // to another row; this must refuse at that gate before any transformation.
    const validation=validateScriptDocument(document);
    expect(validation.valid).toBe(false);
    expect(validation.diagnostics.some(d=>d.code==="ANCHOR_BLOCK_MISMATCH")).toBe(true);
    const original=canonicalJson(document);
    expect(()=>omit(document)).toThrow(/validator/);
    expect(canonicalJson(document)).toBe(original);
  });
  it("honors before/after affinity, changes annotations/beats and keeps notes",()=>{
    const document=sample();const block=row(document);
    const anchored=range(document,1,5);anchored.startAffinity="after";anchored.endAffinity="before";anchored.quotedText="Bravo Charlie Delta";
    block.annotations=[{id:id(90),kind:"performance_note",range:anchored,value:"keep the note",includeInPrompter:true,version:1}];
    block.performanceBeats=[{id:id(91),range:range(document,1,4),version:1},{id:id(92),range:range(document,5,5),version:1}];
    block.notes=["Charlie is a note, not spoken token data."];
    const result=row(omit(document).document);
    expect(result.annotations![0]!.range.quotedText).toBe("Bravo Delta");
    expect(result.annotations![0]!.version).toBe(2);
    expect(result.performanceBeats![0]!.range.quotedText).toBe("Alpha Bravo Delta");
    expect(result.performanceBeats![0]!.version).toBe(2);
    expect(result.performanceBeats![1]).toEqual(block.performanceBeats[1]);
    expect(result.notes).toEqual(block.notes);
  });
  it("bumps an affected standalone event/wrapper once and leaves another wrapper intact",()=>{
    const document=sample();const changed=standalone(document,1,5,100);const unchanged=standalone(document,4,5,110);
    const original=canonicalJson(unchanged);const result=omit(document);
    const changedAfter=result.document.activeDraft.blocks.find(b=>b.id===changed.id);
    if(changedAfter?.type!=="visual")throw new Error("missing visual wrapper");
    expect(changedAfter.version).toBe(changed.version+1);
    expect(changedAfter.event.version).toBe(changed.event.version+1);
    expect(changedAfter.event.range.quotedText).toBe("Alpha Bravo Delta Echo");
    const unchangedAfter=result.document.activeDraft.blocks.find(b=>b.id===unchanged.id);
    expect(canonicalJson(unchangedAfter)).toBe(original);
  });
  it.each([[id(1)],[id(5)],[id(3),id(3)],[id(4),id(3)],[id(2),id(4)],[id(999)],[]].map(tokenIds=>({tokenIds})))("refuses invalid selected IDs $tokenIds",({tokenIds:selected})=>{
    const document=sample();const original=canonicalJson(document);
    expect(()=>omit(document,selected)).toThrow();expect(canonicalJson(document)).toBe(original);
  });
  it.each(["host","visual","annotation","beat","standalone"])("refuses removed %s endpoints",kind=>{
    const document=sample();const block=row(document);
    if(kind==="host")block.hostVisibilitySpans=[{...block.hostVisibilitySpans[0]!,range:range(document,1,3)},{...block.hostVisibilitySpans[0]!,id:id(150),range:range(document,4,5)}];
    if(kind==="visual")block.visualEvents[0]!.range=range(document,2,3);
    if(kind==="annotation")block.annotations=[{id:id(151),kind:"performance_note",range:range(document,3,3),value:"note",includeInPrompter:false,version:1}];
    if(kind==="beat")block.performanceBeats=[{id:id(152),range:range(document,1,3),version:1},{id:id(153),range:range(document,4,5),version:1}];
    if(kind==="standalone")standalone(document,2,3,160);
    expect(validateScriptDocument(document).valid).toBe(true);
    expect(()=>omit(document)).toThrow(/endpoint/);
  });
  it.each(["Alpha Bravo Charlie. Delta Echo","Alpha Bravo. Charlie Delta Echo","Alpha Bravo\u00a0Charlie Delta Echo"])("refuses unsupported punctuation/separators %s",text=>{
    const document=sample();rewriteInput(document,text);
    // A detached punctuation token increases token inventory, but all original
    // anchors still validate; the explicit requested interior omission refuses.
    expect(()=>omit(document)).toThrow();
  });
  it.each(["Alpha Bravo , Charlie Delta Echo","Alpha Bravo Charlie , Delta Echo"])("refuses punctuation outside selected tokens in a gap: %s",text=>{
    const document=sample();const block=row(document);const values=["Alpha","Bravo","Charlie","Delta","Echo"];
    block.text=text;
    block.tokens.forEach((token,index)=>{token.startOffset=text.indexOf(values[index]!);token.endOffset=token.startOffset+values[index]!.length;});
    block.hostVisibilitySpans[0]!.range=range(document);block.visualEvents[0]!.range=range(document,2,4);
    expect(validateScriptDocument(document).valid).toBe(true);
    expect(()=>omit(document)).toThrow(/joining-gap/);
    expect(()=>omit(document,[id(2),id(3)])).toThrow(/joining-gap/);
  });
  it("removes punctuation inside an explicitly removed token without editing surviving punctuation",()=>{
    const document=sample();rewriteInput(document,"Alpha Bravo Charlie, Delta Echo");
    expect(row(omit(document).document).text).toBe("Alpha Bravo Delta Echo");
  });
  it("refuses an empty affinity-selected surviving visual range",()=>{
    const document=sample();const visual=row(document).visualEvents[0]!;
    visual.range={...range(document,2,4),startAffinity:"after",endAffinity:"before",quotedText:"Charlie"};
    expect(validateScriptDocument(document).valid).toBe(true);
    expect(()=>omit(document)).toThrow(/empty/);
  });
  it.each(["sequence","row","entity","anchor","wrapper"])("refuses %s version overflow",kind=>{
    const document=sample();const block=row(document);
    if(kind==="sequence")document.liveHeadSequence=Number.MAX_SAFE_INTEGER;
    if(kind==="row")block.version=Number.MAX_SAFE_INTEGER;
    if(kind==="entity")block.visualEvents[0]!.version=Number.MAX_SAFE_INTEGER;
    if(kind==="anchor")block.visualEvents[0]!.range.anchorVersion=Number.MAX_SAFE_INTEGER;
    if(kind==="wrapper")standalone(document,1,5,230).version=Number.MAX_SAFE_INTEGER;
    expect(()=>omit(document)).toThrow(/integer/);
  });
  it("refuses excluded rows, invalid input and stale document hash",()=>{
    const document=sample();row(document).state="excluded";expect(()=>omit(document)).toThrow(/active/);
    const invalid=sample();row(invalid).tokens[2]!.startOffset+=1;expect(()=>omit(invalid)).toThrow(/validator/);
    const fresh=sample();expect(()=>applyAcceptedOmission(fresh,{expectedDocumentHash:`sha256:${"0".repeat(64)}`,blockId:row(fresh).id,tokenIds:[id(3)]})).toThrow(/hash/);
  });
});
