import { chromium } from "playwright";
import { describe, expect, it } from "vitest";

import { locatePassage } from "../src/passage.js";

describe("locatePassage", () => {
  it("uses context to select a repeated wrapped passage and returns 2x rectangles", async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({
      viewport: { width: 180, height: 180 },
      deviceScaleFactor: 2,
    });
    try {
      await page.setContent(`
        <style>
          html, body { margin: 0; }
          body { font: 20px/20px monospace; }
          p { position: absolute; left: 20px; width: 130px; margin: 0; }
          #first { top: 20px; }
          #second { top: 620px; }
        </style>
        <p id="first">first marker <span class="target"><span>repeat</span> <em>phrase wraps</em></span></p>
        <p id="second">second marker <br><span class="target"><span>repeat</span> <em>phrase wraps</em></span></p>
      `);

      await expect(
        locatePassage(page, { exact: "repeat phrase wraps" }),
      ).rejects.toThrow("ambiguous");
      await expect(
        locatePassage(page, { exact: "markerrepeat" }),
      ).rejects.toThrow("not found");

      const actual = await locatePassage(page, {
        exact: "repeat phrase wraps",
        prefix: "second marker",
      });
      const targetBox = await page.locator("#second .target").boundingBox();
      if (!targetBox) throw new Error("Expected the synthetic target to render.");
      expect(actual.length).toBeGreaterThan(1);
      expect(actual[0]?.x).toBe(Math.round(targetBox.x * 2));
      expect(actual[0]?.y).toBe(Math.round(targetBox.y * 2));
      expect(actual.every((rect) => rect.x === actual[0]?.x)).toBe(true);
      expect(actual.at(-1)?.y).toBeGreaterThan(actual[0]?.y ?? -1);

      const partial = await locatePassage(page, {
        exact: "peat phrase wrap",
        prefix: "second marker re",
      });
      expect(partial[0]?.x).toBeGreaterThan(actual[0]?.x ?? -1);
      expect(partial.at(-1)?.width).toBeLessThan(actual.at(-1)?.width ?? Infinity);
      expect(await page.evaluate(() => scrollY)).toBeGreaterThan(0);
    } finally {
      await browser.close();
    }
  });
});
