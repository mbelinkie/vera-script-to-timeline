#!/usr/bin/env node
// Standalone preflight for Codex/CI entrypoints outside scripts/roadmap.mjs.
import { main } from './chat-review-approval.mjs';
main(['verify', ...process.argv.slice(2)]).catch(e => { console.error(e.message); process.exitCode = 1; });
