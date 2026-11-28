import { readFile } from "node:fs/promises";
import { chromium, type Page } from "playwright";
import { describe, expect, it, vi } from "vitest";
import type { ContributionFilter, ContributionReference, ContributionsProjection } from "../browser/contributions-panel.js";

vi.setConfig({ testTimeout: 90_000 });
const ref = (sequence: number, actorId: string, targetKind: string, removed = false): ContributionReference => ({
  sourceCursor: { stream: "document", sequence }, actorId, occurredAt: "2026-10-30T09:00:00.000Z",
  origin: "user", targetKind, semanticId: targetKind + "-" + sequence,
  changeKind: removed ? "removed" : "changed", evidence: { before: "before", after: "after" },
  removed, label: "In " + targetKind,
});
const records = [ref(1, "dana", "script"), ref(2, "dana", "script", true),
  ref(3, "jonah", "stash"), ref(4, "jonah", "comments"), ref(5, "self", "script")];
const fixtureProjection: ContributionsProjection = {
  selfActorId: "self", boundaryToken: "frozen-5", pendingCount: 5, rangeCount: 5, coverage: "partial",
  contributors: [
    { actorId: "dana", displayName: "Dana Cooper", count: 2 },
    { actorId: "jonah", displayName: "Jonah Reyes", count: 2 },
    { actorId: "self", displayName: "Mira Writer", count: 1 },
  ],
  visibleReferences: records,
  removedSummaries: [{ actorId: "dana", text: "Removed row" }],
  overwrittenSummaries: [{ actorId: "jonah", text: "Your later edit replaced 1 unreviewed change by Jonah Reyes." }],
};
interface Fixture {
  filters: ContributionFilter[];
  focused: ContributionReference[];
  submitted: string[];
  failNext: boolean;
  hold: boolean;
  release: (() => void) | null;
  pending: number;
  token: string;
  panel: { update(context: object): void; destroy(): void };
  project(): ContributionsProjection;
}
const fixture = (page: Page) => page.evaluate(() => (window as unknown as { fixture: Fixture }).fixture.filters);
const control = (page: Page, key: string) => page.locator('[data-contribution-control="' + key + '"]');
async function withPanel(width: number, pending: number, autoOpen: boolean, exercise: (page: Page) => Promise<void>) {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width, height: 800 }, timezoneId: "UTC" });
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.route("http://contributions.test/**", async route => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/contributions-panel.js" || path === "/contributions-panel.css") {
        await route.fulfill({ contentType: path.endsWith(".js") ? "text/javascript" : "text/css",
          body: await readFile(new URL("../browser" + path, import.meta.url), "utf8") });
      } else {
        await route.fulfill({ contentType: "text/html", body: `<!doctype html><link rel="stylesheet" href="/contributions-panel.css">
          <main style="width:70%;margin:auto" id="root"></main><script type="module">
          import {mountContributionsPanel} from '/contributions-panel.js';
          const base = ${JSON.stringify(fixtureProjection)};
          const state = window.fixture = {filters:[],focused:[],submitted:[],failNext:false,hold:false,release:null,
            pending:${pending}, token:"frozen-5", query:null};
          state.project = () => {
            const historical = state.query && state.query.range !== "rev";
            const people = historical ? base.contributors : base.contributors.filter(p => p.actorId !== "self");
            const refs = historical ? base.visibleReferences : base.visibleReferences.filter(r => r.actorId !== "self");
            const remaining = historical || state.pending > 0;
            const visibleReferences = remaining ? refs.filter(r => !state.query?.actorId || r.actorId === state.query.actorId)
              .filter(r => state.query?.showRemoved !== false || !r.removed) : [];
            return {...base, pendingCount:state.pending, rangeCount:remaining ? refs.length : 0,
              boundaryToken:state.token, contributors:remaining ? people : [], visibleReferences,
              overwrittenSummaries:state.pending >= 5 ? base.overwrittenSummaries : [],
              coverage:state.pending ? "partial" : "complete"};
          };
          state.panel = mountContributionsPanel({root:document.querySelector('#root'), projection:state.project(),
            role:"editor", autoOpen:${autoOpen}, setFilter(query) {
              state.filters.push(query); state.query=query; return state.project();
            }, focusTarget(ref) {state.focused.push(ref);}, async acknowledge(token) {
              state.submitted.push(token);
              if(state.failNext) {state.failNext=false;throw new Error("save failed");}
              if(state.hold) await new Promise(resolve=>{state.release=resolve;});
              state.pending = token === "frozen-5" ? Math.max(0,state.pending-5) : 0;
              return state.project();
            }});
          </script>` });
      }
    });
    await page.goto("http://contributions.test/");
    await control(page, "toggle").waitFor();
    await exercise(page);
    expect(errors).toEqual([]);
  } finally { await browser.close(); }
}
function alter(page: Page, changes: { pending?: number; token?: string; failNext?: boolean; hold?: boolean; role?: string; sorting?: boolean }) {
  return page.evaluate(changes => {
    const f = (window as unknown as { fixture: Fixture }).fixture;
    const { role, sorting, ...data } = changes;
    Object.assign(f, data);
    f.panel.update({ projection: f.project(), ...(role ? {role} : {}), ...(sorting === undefined ? {} : {sorting}) });
  }, changes);
}

describe("standalone contribution controls, real browser fixture", () => {
  it("first use, optional catch-up, keyboard hide/reopen, sorting and Viewer inspection", async () => {
    await withPanel(1280, 0, true, async page => {
      const bar = page.getByRole("region", { name: "Contributions" });
      expect(await bar.count()).toBe(0);
      await alter(page, { pending: 5 });
      await bar.waitFor();
      expect((await fixture(page)).at(-1)?.active).toBe(false);
      expect(await control(page, "actor:self").count()).toBe(0);
      await control(page, "close").focus();
      await page.keyboard.press("Enter");
      expect(await bar.count()).toBe(0);
      expect(await control(page, "toggle").evaluate(el => el === document.activeElement)).toBe(true);
      expect(await control(page, "toggle").innerText()).toContain("5");
      await page.keyboard.press("Space");
      await bar.waitFor();
      await control(page, "actor:dana").focus();
      await page.keyboard.press("Enter");
      expect(await control(page, "actor:dana").getAttribute("aria-pressed")).toBe("true");
      expect((await fixture(page)).at(-1)?.active).toBe(true);
      await alter(page, { sorting: true });
      expect(await bar.count()).toBe(0);
      expect(await control(page, "toggle").innerText()).toContain("5");
      expect((await fixture(page)).at(-1)?.active).toBe(false);
      await alter(page, { sorting: false, role: "viewer" });
      await bar.waitFor();
      expect(await control(page, "review").count()).toBe(0);
      await control(page, "actor:jonah").click();
      expect(await control(page, "actor:dana").getAttribute("aria-pressed")).toBe("false");
      expect(await control(page, "actor:jonah").getAttribute("aria-pressed")).toBe("true");
      await control(page, "next").click();
      expect(await page.evaluate(() => (window as unknown as {fixture: Fixture}).fixture.focused[0]?.semanticId)).toBe("comments-4");
      expect(await page.evaluate(() => (window as unknown as {fixture: Fixture}).fixture.submitted)).toEqual([]);
    });
    await withPanel(1024, 5, false, async page => {
      expect(await page.getByRole("region", {name: "Contributions"}).count()).toBe(0);
      expect(await control(page, "toggle").innerText()).toContain("5");
      await control(page, "toggle").click();
      expect(await page.getByRole("region", {name: "Contributions"}).count()).toBe(1);
    });
  });

  for (const width of [1280, 1024]) {
    it("range defaults, both custom endpoints, one author and responsive keyboard controls at " + width, async () => {
      await withPanel(width, 5, true, async page => {
        await control(page, "actor:jonah").click();
        expect(await page.getByText("Your later edit replaced", {exact: false}).count()).toBe(1);
        expect(await control(page, "removed").isChecked()).toBe(true);
        await control(page, "timeframe").click();
        for (const [range, expected] of [["visit", true], ["d1", true], ["d7", false], ["all", false]] as const) {
          await control(page, "range:" + range).check();
          await control(page, "actor:self").click();
          expect(await control(page, "removed").isChecked()).toBe(expected);
          expect(await control(page, "review").count()).toBe(0);
        }
        await control(page, "range:custom").check();
        await control(page, "from").fill("2026-10-29T09:00");
        expect((await fixture(page)).at(-1)).toMatchObject({valid: false, active: false});
        await control(page, "to").fill("2026-10-30T10:00");
        expect((await fixture(page)).at(-1)).toMatchObject({
          range: "custom", valid: true, from: "2026-10-29T09:00:00.000Z", to: "2026-10-30T10:00:59.999Z", showRemoved: false,
        });
        await control(page, "actor:dana").click();
        expect(await control(page, "removed").isChecked()).toBe(false);
        await control(page, "removed").check();
        expect((await fixture(page)).at(-1)?.showRemoved).toBe(true);
        await page.keyboard.press("Escape");
        expect(await control(page, "timeframe").getAttribute("aria-expanded")).toBe("false");
        const bounds = await page.getByRole("region", {name: "Contributions"}).boundingBox();
        expect(bounds).not.toBeNull();
        expect(bounds!.x).toBeGreaterThanOrEqual(0);
        expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      });
    });
  }

  it("acknowledges the frozen full boundary despite partial page, hidden removals, failure and later arrival", async () => {
    await withPanel(1024, 5, true, async page => {
      await control(page, "actor:dana").click();
      await control(page, "removed").uncheck();
      await alter(page, { failNext: true });
      await control(page, "review").click();
      await page.getByText("Couldn’t save your review.", {exact: false}).waitFor();
      expect(await control(page, "toggle").innerText()).toContain("5");
      expect(await control(page, "actor:dana").getAttribute("aria-pressed")).toBe("true");
      await alter(page, { hold: true });
      await control(page, "review").click();
      await control(page, "review").waitFor();
      expect(await control(page, "review").isDisabled()).toBe(true);
      await alter(page, { pending: 6, token: "frozen-6" });
      await page.evaluate(() => (window as unknown as {fixture: Fixture}).fixture.release?.());
      await page.getByText("Marked reviewed.", {exact: false}).waitFor();
      expect(await control(page, "toggle").innerText()).toContain("1");
      expect(await page.evaluate(() => (window as unknown as {fixture: Fixture}).fixture.submitted)).toEqual(["frozen-5", "frozen-5"]);
      expect(await control(page, "actor:dana").getAttribute("aria-pressed")).toBe("false");
      await alter(page, { hold: false });
      await control(page, "review").click();
      await page.getByText("Marked reviewed.", {exact: false}).waitFor();
      expect(await page.evaluate(() => (window as unknown as {fixture: Fixture}).fixture.submitted)).toEqual(["frozen-5", "frozen-5", "frozen-6"]);
      expect(await control(page, "review").count()).toBe(0);
    });
  });
});
