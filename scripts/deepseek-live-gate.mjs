// Read-only public authorization for one separately approved live receiver action.
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  continuationApprovalMetadata, readPublicGh, verifyPublicApproval
} from './deepseek-continuation-gate.mjs';

export { readPublicGh };

export function liveApprovalMetadata(identity) {
  return {
    ...continuationApprovalMetadata(identity),
    executionMode: 'live',
    transportContract: 'VERA_DEEPSEEK_RECEIVER_V2'
  };
}

export function verifyLiveApproval(readGh, identity) {
  return verifyPublicApproval(readGh, identity, 'live');
}

export function main(argv = process.argv.slice(2), readGh = readPublicGh) {
  if (argv.length !== 1 || typeof argv[0] !== 'string') {
    throw new Error('Expected one live identity JSON argument');
  }
  let identity;
  try { identity = JSON.parse(argv[0]); }
  catch { throw new Error('Expected one live identity JSON argument'); }
  return verifyLiveApproval(readGh, identity);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    console.log(JSON.stringify(main()));
  } catch {
    console.error('Live approval refused; no provider request was made.');
    process.exitCode = 1;
  }
}
