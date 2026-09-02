import { mkdtemp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { PNG } from 'pngjs';
import { PROFILE } from '../profile.mjs';

export const temporaryStore = () => mkdtemp(path.join(tmpdir(), 'vera-capture-test-'));
export function stubRender(color = 42) {
  return async ({ cleanProfileId }) => {
    const png = new PNG(PROFILE.viewport);
    png.data.fill(color);
    return { raster: PNG.sync.write(png), title: 'unit-test renderer (not browser evidence)',
      warnings: [], runtime: { cleanProfileId, importedState: false, initialCookies: 0, finalCookies: 0, browser: 'unit-test-stub' },
      timing: { load: 'unit-test-stub', captureInstant: new Date().toISOString() } };
  };
}
