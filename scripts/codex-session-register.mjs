#!/usr/bin/env node
/** Interactive, zero-model-turn registration of existing local Codex threads. */
import readline from 'node:readline/promises';
import { stdin as input, stdout as output } from 'node:process';
import { canonicalIssueKey, parseLocalCodexLink } from './codex-session-links.mjs';
import { registerLocalCodexThread } from './codex-session-register-lib.mjs';

const args = process.argv.slice(2);
if (args.length === 1 && args[0] === '--help') {
  console.log('Usage: node scripts/codex-session-register.mjs [GitHub issue URL]');
  console.log('Paste a desktop Copy chat deep link when prompted. No Codex or network calls.');
} else if (!input.isTTY || !output.isTTY || args.length > 1) {
  console.error('Interactive local terminal required; do not supply private deep links as shell arguments.');
  process.exitCode = 2;
} else {
  const terminal = readline.createInterface({ input, output });
  try {
    const issueUrl = args[0] ?? (await terminal.question('GitHub issue URL: '));
    const issueKey = canonicalIssueKey(issueUrl);
    if (!issueKey) throw new Error('Invalid GitHub issue URL');
    const deepLink = await terminal.question('Paste Copy chat deep link from the EXISTING local Codex thread: ');
    const parsed = parseLocalCodexLink(deepLink);
    if (!parsed) throw new Error('Not an exact existing-local Codex thread UUID link');
    console.log(`Issue: ${issueKey}; local thread ending ...${parsed.threadId.slice(-8)}`);
    const confirmation = await terminal.question(`Type CONFIRM ${issueKey} to record this association: `);
    if (confirmation !== `CONFIRM ${issueKey}`) throw new Error('Canceled: Producer confirmation did not match');
    let replaced = false;
    try {
      await registerLocalCodexThread({ issueUrl, deepLink, confirmed: true });
    } catch (error) {
      if (!/Existing primary session differs/.test(error?.message ?? '')) throw error;
      const second = await terminal.question('An existing primary would become history. Type REPLACE to confirm: ');
      if (second !== 'REPLACE') throw new Error('Canceled: existing primary left unchanged');
      await registerLocalCodexThread({ issueUrl, deepLink, confirmed: true, replaceExisting: true });
      replaced = true;
    }
    console.log(replaced ? 'Producer-attested local association updated.' : 'Producer-attested local association recorded.');
    console.log('No Codex thread was opened, started, or resumed; no GitHub records changed.');
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  } finally {
    terminal.close();
  }
}
