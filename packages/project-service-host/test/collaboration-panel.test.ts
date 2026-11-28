import { readFileSync } from "node:fs";
import { chromium } from "playwright";
import { expect, it } from "vitest";
import type { SyncState } from "@vera/project-collaboration/client";

type Snapshot = {
  state: SyncState; hasUnsyncedChanges: boolean; role: string; hold: boolean;
  recoverableFailure: boolean; actorId: string;
  roster: { actorId: string; canEdit: boolean; awarenessClientIds: number[] }[];
  presence: { actorId: string; selectedRowId?: string; selectedCardId?: string; cursor?: number; recentEdit?: boolean }[];
};
type Harness = Window & {
  snapshot: Snapshot; update: (patch: Partial<Snapshot>) => void; calls: number;
  subscriptions: Set<() => void>; panel: { destroy(): void }; announcements: number;
};

it("renders all sync states, verified presence, gated retry, responsive reveal and cleanup", async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    const source = readFileSync(new URL("../browser/collaboration-panel.js", import.meta.url), "utf8");
    const css = readFileSync(new URL("../browser/collaboration-panel.css", import.meta.url), "utf8");
    await page.route("https://collaboration.test/**", async route => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/panel.js") await route.fulfill({ contentType: "text/javascript", body: source });
      else if (path === "/panel.css") await route.fulfill({ contentType: "text/css", body: css });
      else await route.fulfill({ contentType: "text/html", body: `
        <link rel="stylesheet" href="/panel.css">
        <style>body{background:#181818;color:white} #root{width:700px}
        @media(max-width:1100px){#root{width:230px}}</style>
        <button id="before">Before</button><div id="root"></div><button id="after">After</button>
        <script type="module">
        import { mountCollaborationPanel } from "/panel.js";
        window.snapshot = {state:"synced",hasUnsyncedChanges:false,role:"editor",hold:false,
          recoverableFailure:false,actorId:"me",roster:[
            {actorId:"me",canEdit:true,awarenessClientIds:[1]},
            {actorId:"jonah",canEdit:true,awarenessClientIds:[2]}
          ],presence:[{actorId:"jonah",selectedRowId:"r1",cursor:5,name:"Fake name"},
          {actorId:"outsider",selectedRowId:"r1",cursor:7}]};
        window.calls=0; window.subscriptions=new Set();
        window.update=patch=>{Object.assign(window.snapshot,patch);for(const fn of window.subscriptions)fn()};
        window.panel=mountCollaborationPanel({root:document.querySelector("#root"),
          binding:{read:()=>window.snapshot,subscribe:fn=>{window.subscriptions.add(fn);return()=>window.subscriptions.delete(fn)},
          retry:()=>{window.calls++}},
          labelForActor:id=>id==="jonah"?"Jonah":undefined,
          labelForRow:id=>id==="r1"?"row 1":undefined,
          labelForCard:id=>id==="c1"?"visual 1":undefined});
        window.announcements=0;
        new MutationObserver(()=>window.announcements++).observe(document.querySelector("[role=status]"),{childList:true});
        </script>` });
    });
    await page.goto("https://collaboration.test/");
    await page.waitForFunction(() => !!(window as unknown as Harness).panel);
    const update = (patch: Partial<Snapshot>) => page.evaluate(p => (window as unknown as Harness).update(p), patch);
    const sync = page.locator(".collaboration-panel__sync");
    const presence = page.locator(".collaboration-panel__presence");
    const tooltip = page.locator(".collaboration-panel__reveal");
    const retry = page.getByRole("button", { name: "Try again" });
    expect(await sync.textContent()).toBe("Synced");
    expect(await presence.getAttribute("aria-label")).toBe("Jonah is editing row 1");
    expect(await presence.getAttribute("tabindex")).toBeNull();
    await presence.hover();
    expect(await tooltip.isVisible()).toBe(false);
    await update({ state: "local changes", hasUnsyncedChanges: true });
    expect(await sync.textContent()).toBe("Local changes");
    await update({ state: "syncing" });
    expect(await sync.textContent()).toBe("Saving…");
    await update({ state: "offline" });
    expect(await sync.textContent()).toBe("Offline · changes kept here");
    await update({ hasUnsyncedChanges: false });
    expect(await sync.textContent()).toBe("Offline");
    await update({ state: "sync failed", hasUnsyncedChanges: true });
    expect(await sync.textContent()).toBe("Sync failed");
    expect(await retry.count()).toBe(0);
    await update({ recoverableFailure: true, role: "viewer" });
    expect(await retry.count()).toBe(0);
    await update({ role: "editor", hold: true });
    expect(await retry.count()).toBe(0);
    await update({ hold: false });
    expect(await retry.isVisible()).toBe(true);
    await retry.click();
    await retry.evaluate(el => (el as HTMLButtonElement).click());
    expect(await page.evaluate(() => (window as unknown as Harness).calls)).toBe(1);
    await update({ state: "syncing" });
    expect(await retry.count()).toBe(0);
    await update({ state: "sync failed" });
    expect(await retry.isEnabled()).toBe(true);

    await page.setViewportSize({ width: 1024, height: 768 });
    await page.waitForFunction(() => document.querySelector(".collaboration-panel__presence")?.getAttribute("tabindex") === "0");
    await page.locator("#before").focus();
    await page.keyboard.press("Tab");
    await page.keyboard.press("Tab");
    expect(await presence.evaluate(el => el === document.activeElement)).toBe(true);
    expect(await tooltip.isVisible()).toBe(true);
    expect(await tooltip.textContent()).toBe("Jonah is editing row 1");
    const retryBox = (await retry.boundingBox())!;
    const tipBox = (await tooltip.boundingBox())!;
    expect(tipBox.y).toBeGreaterThanOrEqual(retryBox.y + retryBox.height / 2);
    await page.keyboard.press("Escape");
    expect(await tooltip.isVisible()).toBe(false);
    const count = await page.evaluate(() => (window as unknown as Harness).announcements);
    await update({});
    await presence.blur();
    await presence.focus();
    expect(await page.evaluate(() => (window as unknown as Harness).announcements)).toBe(count);
    await update({ presence: [{ actorId: "jonah", selectedRowId: "r1", recentEdit: true }] });
    expect(await presence.getAttribute("aria-label")).toBe("Jonah edited row 1 · just now");
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.waitForFunction(() => !document.querySelector(".collaboration-panel__presence")?.hasAttribute("tabindex"));
    expect(await tooltip.isVisible()).toBe(false);

    await update({ roster: [{ actorId: "<b>unknown</b>", canEdit: false, awarenessClientIds: [3] }],
      presence: [{ actorId: "<b>unknown</b>", selectedCardId: "c1", selectedRowId: "r1", cursor: 1 }] });
    expect(await presence.getAttribute("aria-label")).toBe("<b>unknown</b> selected visual 1");
    expect(await page.locator("#root b").count()).toBe(0);
    await update({ roster: [] });
    expect(await presence.isVisible()).toBe(false);
    await page.evaluate(() => { const h = window as unknown as Harness; h.panel.destroy(); h.panel.destroy(); h.update({ state: "synced" }); });
    expect(await page.evaluate(() => (window as unknown as Harness).subscriptions.size)).toBe(0);
    expect(await page.locator(".collaboration-panel").count()).toBe(0);
  } finally {
    await browser.close();
  }
}, 30_000);
