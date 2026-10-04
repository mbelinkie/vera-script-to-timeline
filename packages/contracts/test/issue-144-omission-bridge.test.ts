import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import { canonicalJson, compileTimeline, sha256CanonicalJson } from "../src/compiler-core.js";
import type { CompilerDependenciesV1 } from "../src/generated/contracts.js";
import { applyAcceptedOmission } from "../src/issue-144-text-revision.js";
import { hash, id, inputs } from "./issue-144-test-inputs.js";

const cli = fileURLToPath(new URL("../src/issue-144-proof-cli.ts", import.meta.url));
const roots: string[] = [];
const digest = (text: string): string => `sha256:${createHash("sha256").update(text).digest("hex")}`;
function files(values: unknown[]): string[] {
  const root = mkdtempSync(join(tmpdir(), "vera144-omission-bridge-")); roots.push(root);
  return values.map((value,index)=>{ const path=join(root,`${index}.json`);writeFileSync(path,canonicalJson(value));return path; });
}
function invoke(action: string, paths: string[]) { return spawnSync(process.execPath,[cli,action,...paths],{encoding:"utf8",timeout:300_000}); }
interface Envelope { ok: boolean; result: {status: string; reason?: string; regeneration?: {text:string;policy:string}}; artifacts: Record<string,string>; artifactHashes: Record<string,string>; sourceHashes: Record<string,string>; inputs: Record<string,string>; }
function body(stdout: string): Envelope { return JSON.parse(stdout) as Envelope; }
function prepared() {
  const prior=inputs(({block})=>{block.visualEvents[0]!.range.endTokenId=id(4);block.visualEvents[0]!.range.quotedText="Bravo Charlie Delta";});
  const block=prior.currentDocument.activeDraft.blocks[1];if(block?.type!=="narration")throw new Error("missing row");
  const edit={expectedDocumentHash:sha256CanonicalJson(prior.currentDocument),blockId:block.id,tokenIds:[id(3)]};
  const revision=applyAcceptedOmission(prior.currentDocument,edit);
  const dependencies=structuredClone(prior.dependencies);const replacement=dependencies.narration[0]!;
  const row=revision.document.activeDraft.blocks[1];if(row?.type!=="narration")throw new Error("missing revised row");
  replacement.blockRevision=row.version;replacement.assetId="b".repeat(64);replacement.audioHash=hash("b");
  replacement.textHash=digest(row.text);replacement.audio.locator=`Media/Narration/${replacement.assetId}.wav`;
  replacement.audio.durationSamples=192_000;
  replacement.timing.marks=row.tokens.map((token,index)=>({kind:"word",timeMs:index*800+index*index*40,startUtf16:token.startOffset,endUtf16:token.endOffset,value:token.value}));
  // Deliberately synthetic service-shaped values; the pure child is not an
  // acceptance/provider verifier. Python integration separately tests real cache.
  const handoff={schemaVersion:"issue-144-row-narration/v1",evidenceLevel:"synthetic_injected",baselineSnapshotId:"b".repeat(64),revisedDocumentHash:digest(revision.documentJson),sources:{"code.py":hash("f")},dependencies,replacements:[{blockId:row.id,assetId:replacement.assetId,origin:"/proof/cache/narration.wav",audioHash:replacement.audioHash,assetRecordPath:"/proof/cache/asset.json",assetRecordHash:hash("c"),timingPath:"/proof/cache/timing.json",timingHash:hash("d"),requestHash:hash("e"),providerAdapter:"issue144-test/v1"}]};
  return {prior,edit,revision,handoff};
}
afterEach(()=>{for(const root of roots.splice(0))rmSync(root,{recursive:true});});

describe("Issue144 internal omission canonical stdout bridge (no decision authority)",()=>{
  it("invokes actual transformation with raw/source hashes and one full-row request",()=>{
    const data=prepared();const paths=files([data.prior.currentDocument,data.edit]);const before=paths.map(path=>readFileSync(path,"utf8"));
    const result=invoke("revise-omission",paths);expect(result.status).toBe(0);expect(result.stderr).toBe("");
    const receipt=body(result.stdout);expect(receipt.ok).toBe(true);expect(receipt.result.status).toBe("prepared");
    expect(receipt.result.regeneration).toEqual(data.revision.regeneration);
    expect(receipt.artifacts).toEqual({"script-document.json":data.revision.documentJson});
    expect(receipt.inputs).toEqual(Object.fromEntries(before.map((text,index)=>[String(index),digest(text)])));
    expect(receipt.sourceHashes["./issue-144-text-revision.ts"]).toBe(digest(readFileSync(new URL("../src/issue-144-text-revision.ts",import.meta.url),"utf8")));
    expect(invoke("revise-omission",paths).stdout).toBe(result.stdout);expect(paths.map(path=>readFileSync(path,"utf8"))).toEqual(before);
  });
  it("finalizes replacement dependencies/fresh IDs and exact actual compiler preview",()=>{
    const data=prepared();const paths=files([data.revision.document,data.prior.dependencies,data.handoff]);const before=paths.map(path=>readFileSync(path,"utf8"));
    const result=invoke("finalize-omission",paths);expect(result.status,result.stdout+result.stderr).toBe(0);expect(result.stderr).toBe("");
    const receipt=body(result.stdout);expect(receipt.result.status).toBe("finalized");
    expect(Object.keys(receipt.artifacts).sort()).toEqual(["build-report.json","compiler-dependencies.json","timeline-manifest.json"]);
    const dependencies=JSON.parse(receipt.artifacts["compiler-dependencies.json"]!) as CompilerDependenciesV1;
    for(const kind of ["buildId","manifestId","reportId"] as const)expect(dependencies.build[kind]).not.toBe(data.prior.dependencies.build[kind]);
    expect(dependencies.narration).toEqual(data.handoff.dependencies.narration);
    const compiled=compileTimeline(data.revision.document,dependencies);expect(compiled.ok).toBe(true);if(!compiled.ok)throw Error("failed preview");
    expect(receipt.artifacts["timeline-manifest.json"]).toBe(canonicalJson(compiled.manifest));expect(receipt.artifacts["build-report.json"]).toBe(canonicalJson(compiled.report));
    for(const [name,text] of Object.entries(receipt.artifacts))expect(receipt.artifactHashes[name]).toBe(digest(text));
    expect(invoke("finalize-omission",paths).stdout).toBe(result.stdout);expect(paths.map(path=>readFileSync(path,"utf8"))).toEqual(before);
    data.handoff.replacements[0]!.requestHash=hash("f");const second=body(invoke("finalize-omission",files([data.revision.document,data.prior.dependencies,data.handoff])).stdout);
    expect(second.artifacts["compiler-dependencies.json"]).not.toBe(receipt.artifacts["compiler-dependencies.json"]);
  });
  it.each(["documentHash","oldAudio","asset","row","extraReplacement","metadata","unchangedRow","lane"])("refuses inconsistent handoff %s",kind=>{
    const data=prepared();
    if(kind==="documentHash")data.handoff.revisedDocumentHash=hash("f");
    if(kind==="oldAudio")data.handoff.dependencies.narration[0]!.audioHash=data.prior.dependencies.narration[0]!.audioHash;
    if(kind==="asset")data.handoff.replacements[0]!.assetId=id(301);
    if(kind==="row")data.handoff.replacements[0]!.blockId=id(302);
    if(kind==="extraReplacement")data.handoff.replacements.push(structuredClone(data.handoff.replacements[0]!));
    if(kind==="metadata")data.handoff.dependencies.build.timeline.width+=1;
    if(kind==="unchangedRow")data.handoff.dependencies.narration.push(structuredClone(data.handoff.dependencies.narration[0]!));
    if(kind==="lane")data.handoff.evidenceLevel="real_issue145";
    const result=invoke("finalize-omission",files([data.revision.document,data.prior.dependencies,data.handoff]));
    expect(result.status).toBe(1);expect(body(result.stdout)).toMatchObject({ok:false,result:{status:"refused"},artifacts:{}});
  });
  it("refuses stale edit before revision artifacts",()=>{
    const data=prepared();data.edit.expectedDocumentHash=hash("f");
    const result=invoke("revise-omission",files([data.prior.currentDocument,data.edit]));expect(result.status).toBe(1);expect(body(result.stdout).artifacts).toEqual({});
  });
  it("refuses an in-place change to an untouched dependency with the same inventory length",()=>{
    const data=prepared();
    // Exercise this dependency guard before compilation. The real two-row
    // service/compiler/package positive is covered by the Python integration.
    const other=structuredClone(data.prior.dependencies.narration[0]!);other.blockId=id(303);
    data.prior.dependencies.narration.push(other);
    data.handoff.dependencies.narration.push(structuredClone(other));
    data.handoff.dependencies.narration[1]!.textHash=hash("f");
    const result=invoke("finalize-omission",files([data.revision.document,data.prior.dependencies,data.handoff]));
    expect(result.status).toBe(1);
    expect(body(result.stdout)).toMatchObject({ok:false,result:{status:"refused",reason:"unchanged row dependencies changed"},artifacts:{}});
  });
  it("refuses compilation against old wording dependencies",()=>{
    const data=prepared();data.handoff.dependencies=structuredClone(data.prior.dependencies);
    const result=invoke("finalize-omission",files([data.revision.document,data.prior.dependencies,data.handoff]));expect(result.status).toBe(1);expect(body(result.stdout).ok).toBe(false);
  });
  it("distinguishes malformed parse/usage from a semantic refusal",()=>{
    const paths=files([{}]);writeFileSync(paths[0]!,"{");
    const parsed=invoke("revise-omission",[paths[0]!,paths[0]!]);expect(parsed.status).toBe(65);expect(parsed.stdout).toBe("");
    const usage=invoke("finalize-omission",paths);expect(usage.status).toBe(64);expect(usage.stdout).toBe("");
  });
});
