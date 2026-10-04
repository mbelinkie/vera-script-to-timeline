/** Pure compiler preview. The Python host owns decisions and service/cache verification. */
import { createHash } from "node:crypto";
import { canonicalJson, compileTimeline, sha256CanonicalJson } from "./compiler-core.js";
import type { CompilerDependenciesV1, ScriptDocumentV1 } from "./generated/contracts.js";
import { revisionId } from "./issue-144-semantics.js";

interface Replacement {
  blockId: string; assetId: string; origin: string; audioHash: string;
  assetRecordPath: string; assetRecordHash: string; timingPath: string;
  timingHash: string; requestHash: string; providerAdapter: string;
}
export interface VerifiedRowHandoff {
  schemaVersion: string; evidenceLevel: string; baselineSnapshotId: string;
  revisedDocumentHash: string; sources: Record<string,string>;
  dependencies: CompilerDependenciesV1; replacements: Replacement[];
}
function requireFact(condition: boolean, message: string): asserts condition { if(!condition)throw new Error(message); }
const equal=(left:unknown,right:unknown):boolean=>canonicalJson(left)===canonicalJson(right);
const withoutNarration=(dependencies:CompilerDependenciesV1):object=>Object.fromEntries(Object.entries(dependencies).filter(([key])=>key!=="narration"));
const exactKeys=(value:object,keys:string[]):boolean=>equal(Object.keys(value).sort(),keys.sort());

export function finalizeOmission(document: ScriptDocumentV1, prior: CompilerDependenciesV1, handoff: VerifiedRowHandoff) {
  // A service-shaped JSON file alone proves neither generation nor acceptance.
  // The host must pass its just-rederived handoff and verify bytes/cache itself.
  requireFact(exactKeys(handoff,["schemaVersion","evidenceLevel","baselineSnapshotId","revisedDocumentHash","sources","dependencies","replacements"]),"unexpected handoff fields");
  requireFact(handoff.schemaVersion==="issue-144-row-narration/v1"&&handoff.evidenceLevel==="synthetic_injected"&&/^[a-f0-9]{64}$/u.test(handoff.baselineSnapshotId),"unsupported whole-row handoff identity/lane");
  requireFact(handoff.revisedDocumentHash===sha256CanonicalJson(document),"revised canonical document hash differs");
  requireFact(typeof handoff.sources==="object"&&handoff.sources!==null&&Object.keys(handoff.sources).length>0&&Object.values(handoff.sources).every(value=>/^sha256:[a-f0-9]{64}$/u.test(value)),"missing handoff source hashes");
  requireFact(Array.isArray(handoff.replacements)&&handoff.replacements.length===1,"exactly one whole-row replacement required");
  const replacement=handoff.replacements[0]!;
  requireFact(exactKeys(replacement,["blockId","assetId","origin","audioHash","assetRecordPath","assetRecordHash","timingPath","timingHash","requestHash","providerAdapter"]),"unexpected replacement fields");
  requireFact([replacement.blockId,replacement.assetId,replacement.origin,replacement.assetRecordPath,replacement.timingPath,replacement.providerAdapter].every(value=>typeof value==="string"&&value.length>0)&&[replacement.audioHash,replacement.assetRecordHash,replacement.timingHash,replacement.requestHash].every(value=>/^sha256:[a-f0-9]{64}$/u.test(value)),"incomplete replacement bindings");
  const dependencies=structuredClone(handoff.dependencies);
  requireFact(equal(withoutNarration(dependencies),withoutNarration(prior)),"non-narration dependencies changed");
  requireFact(dependencies.narration.length===prior.narration.length&&new Set(prior.narration.map(row=>row.blockId)).size===prior.narration.length,"narration inventory differs");
  const index=prior.narration.findIndex(row=>row.blockId===replacement.blockId);
  const block=document.activeDraft.blocks.find(row=>row.id===replacement.blockId);
  requireFact(index>=0&&block?.type==="narration"&&block.state==="active","replacement row is missing or inactive");
  const old=prior.narration[index]!;const changed=dependencies.narration[index]!;
  requireFact(prior.narration.every((row,i)=>i===index?changed.blockId===row.blockId:equal(row,dependencies.narration[i])),"unchanged row dependencies changed");
  requireFact(changed.assetId===replacement.assetId&&changed.audioHash===replacement.audioHash&&changed.assetId!==old.assetId&&changed.audioHash!==old.audioHash&&changed.blockRevision===old.blockRevision+1&&changed.blockRevision===block.version&&changed.textHash===`sha256:${createHash("sha256").update(block.text,"utf8").digest("hex")}`,"fresh whole-row asset/text/revision binding differs");
  const seed=sha256CanonicalJson({document,priorDependencies:prior,verifiedHandoff:handoff});
  dependencies.build.buildId=revisionId(seed,"build");dependencies.build.manifestId=revisionId(seed,"manifest");dependencies.build.reportId=revisionId(seed,"report");
  const compiled=compileTimeline(document,dependencies);
  requireFact(compiled.ok,`replacement revision does not compile: ${compiled.ok?"":canonicalJson(compiled.diagnostics)}`);
  return {dependencies,manifest:compiled.manifest,report:compiled.report};
}
