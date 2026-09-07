import { capture } from '../capture.mjs';
import { stubRender } from './helpers.mjs';

const [root, point] = process.argv.slice(2);
await capture({ root, command: 'crash-command', render: stubRender(),
  hit: async (where) => { if (where === point) process.kill(process.pid, 'SIGKILL'); } });
throw new Error('fault point was not reached');
