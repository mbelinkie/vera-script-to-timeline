import { chromium } from "playwright";
import { describe, expect, it } from "vitest";

import { locatePassage } from "../src/passage.js";
import { CaptureDenied } from "../src/policy.js";

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
      ).rejects.toMatchObject({
        code: "passage_unavailable",
        safeMessage: "Passage was ambiguous.",
        phase: "response",
        navigationStarted: true,
      });
      try {
        await locatePassage(page, { exact: "repeat phrase wraps" });
        throw new Error("Expected the repeated passage to be rejected.");
      } catch (error) {
        expect(error).toBeInstanceOf(CaptureDenied);
      }
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

  it("scrolls nested auto containers but refuses hidden overflow", async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({
      viewport: { width: 180, height: 180 },
      deviceScaleFactor: 2,
    });
    try {
      await page.setContent(`
        <style>
          html, body { margin: 0; }
          #outer { width: 170px; height: 110px; overflow: auto; scroll-behavior: smooth; }
          #inner { width: 300px; height: 300px; overflow: auto; }
          #inner::before, #inner::after { content: ""; display: block; height: 340px; }
          /* Keep the wrapped passage short enough to fit across monospace fonts. */
          #target { width: 14ch; margin: 0; position: relative; top: 0.25px; font: 18px/20px monospace; }
        </style>
        <div id="outer"><div id="inner"><p id="target">nested target phrase wraps across lines</p></div></div>
      `);
      const rects = await locatePassage(page, { exact: "nested target phrase wraps across lines" });
      const scrollState = await page.evaluate(() => ({
        outer: document.querySelector("#outer")?.scrollTop ?? 0,
        inner: document.querySelector("#inner")?.scrollTop ?? 0,
      }));
      expect(scrollState.outer).toBeGreaterThan(0);
      expect(scrollState.inner).toBeGreaterThan(0);
      expect(rects.length).toBeGreaterThan(1);
      for (const rect of rects) {
        expect(rect.x).toBeGreaterThanOrEqual(0);
        expect(rect.y).toBeGreaterThanOrEqual(0);
        expect(rect.x + rect.width).toBeLessThanOrEqual(170 * 2);
        expect(rect.y + rect.height).toBeLessThanOrEqual(110 * 2);
      }

      await page.setContent(`
        <style>
          html, body { margin: 0; }
          #clip { width: 160px; height: 40px; overflow: hidden; }
          #hidden-target { margin-top: 100px; font: 18px/20px monospace; }
        </style>
        <div id="clip"><p id="hidden-target">hidden overflow phrase</p></div>
      `);
      await expect(
        locatePassage(page, { exact: "hidden overflow phrase" }),
      ).rejects.toMatchObject({
        code: "passage_unavailable",
        safeMessage: "Passage was clipped.",
      });
    } finally {
      await browser.close();
    }
  });

  it("coalesces more than 64 inline text fragments into passage lines", async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({ viewport: { width: 600, height: 700 }, deviceScaleFactor: 2 });
    try {
      const lines = Array.from({ length: 20 }, (_, index) => `Line ${index} with linked and styled words.`);
      const markup = lines.map((line) =>
        `<div>${line.replace("linked", "<a href='#'>linked</a>").replace("styled", "<strong>styled</strong>")}</div>`,
      ).join("");
      await page.setContent(`
        <style>body { font: 18px/24px monospace; } a { font-size: 16px; }</style>
        ${markup}
      `);

      const rects = await locatePassage(page, { exact: lines.join(" ") });
      expect(rects).toHaveLength(lines.length);
    } finally {
      await browser.close();
    }
  });

  it("uses text-fragment edges for fractional 2x rectangles", async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({
      viewport: { width: 180, height: 180 },
      deviceScaleFactor: 2,
    });
    try {
      await page.setContent(`
        <style>
          html, body { margin: 0; }
          #target { position: absolute; left: 10.25px; top: 12.25px; margin: 0; font: 17px/19px monospace; }
        </style>
        <p id="target">fractional phrase</p>
      `);
      const [actual] = await locatePassage(page, { exact: "fractional phrase" });
      const source = await page.locator("#target").evaluate((element) => {
        const text = element.firstChild;
        if (!(text instanceof Text)) throw new Error("Expected direct synthetic text.");
        const range = document.createRange();
        range.setStart(text, 0);
        range.setEnd(text, text.length);
        const rect = range.getClientRects()[0];
        if (!rect) throw new Error("Expected the synthetic text to render.");
        return { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom };
      });
      const left = Math.max(0, Math.min(180, source.left));
      const top = Math.max(0, Math.min(180, source.top));
      const right = Math.max(0, Math.min(180, source.right));
      const bottom = Math.max(0, Math.min(180, source.bottom));
      const x = Math.floor(left * 2);
      const y = Math.floor(top * 2);
      expect(actual).toEqual({
        x,
        y,
        width: Math.ceil(right * 2) - x,
        height: Math.ceil(bottom * 2) - y,
      });
    } finally {
      await browser.close();
    }
  });
});
