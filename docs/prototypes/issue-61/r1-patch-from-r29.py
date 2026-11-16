import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()

def once(s, old, new):
    assert s.count(old) == 1, (s.count(old), old[:80])
    return s.replace(old, new)

# ---------- (A) constants ----------
CONST = r'''// ---- issue 61 r1 (S16): YouTube page composite on the accepted S03 r29 surface. Simulated only: no capture, download, compositing or Resolve call happens here. ----
const Y61 = {
  tpl: { name: "Watch page, standard", rev: 1, rect: { x: 4.2, y: 10.5, w: 61.5, h: 61.5 } },
  zoom: 1.18,
  revA: { n: 1, at: "14 Nov 2026, 09:12", views: "214,880 views", comments: 2, shift: 0 },
  revB: { at: "16 Nov 2026, 16:40", views: "231,402 views", comments: 3, shift: 3.2 },
  page: { title: "Harbor mouth at the turn of the tide", channel: "Tidewatch Field Notes", subs: "18.4K subscribers", date: "3 Aug 2026",
    desc: "Filmed from the north piling at low water. Fictional sample page made for this prototype.", banner: "New this week: live premieres (fictional banner)" },
  build: { n: 12, at: "14 Nov 2026" }
};
const Y61_NEW = (state) => ({ state: state || "ready", clip: "ok", rev: 1, revs: [DEEP(Y61.revA)], rect: DEEP(Y61.tpl.rect), rectBy: "template", check: false, aspect: "16:9", motion: "zoom", focus: null, age: "", builds: [] });

class Component extends DCLogic {'''
s = once(s, "class Component extends DCLogic {", CONST)

# ---------- (B) menu item ----------
TRIM = '''if (slot.media) menuItems.push({ label: "Trim", style: st, pick: () => { this._playerOpener = document.querySelector('[data-slot="' + slot.id + '"]'); this.setState({ menu: null }); this.openPlayer(row.id, slot.id, true); } });'''
MENU = TRIM + '''
        if (slot.kind === "clip" && slot.media && !s.srt) menuItems.push(slot.ytc
          ? { label: "Open YouTube page composite", style: st, pick: () => { this.setState({ menu: null }); this.y61Open(row.id, slot.id); } }
          : { label: "Present on YouTube page", meta: "captures the public watch page once; the clip plays in its player", style: st, pick: () => this.y61Make(row.id, slot.id) });'''
s = once(s, TRIM, MENU)

# ---------- (C) methods ----------
METHODS = r'''  // ---- issue 61 r1 (S16): YouTube page composite ----
  y61Ref() { const p = this.state.y61Panel; if (!p) return null; const row = (this.state.rows || []).find(r => r.id === p.rowId), slot = row && row.visuals.find(v => v.id === p.slotId); return slot && slot.ytc ? { row, slot, y: slot.ytc } : null; }
  y61Name(slot) { return slot.dispName || slot.title || "this clip"; }
  y61Say(msg) { this.setState({ cmToast: { msg, undo: false } }); }
  y61Stop() { if (this._y61T) { clearInterval(this._y61T); this._y61T = null; } }
  y61Focus(sel) { const go = (n) => setTimeout(() => { const d = document.querySelector("[data-y61]"), el = d && (d.querySelector(sel || "[data-y61play]") || d.querySelector("button")); if (el && document.activeElement !== el) el.focus(); if (n > 0 && (!el || document.activeElement !== el || n > 2)) go(n - 1); }, 90); go(4); }
  y61Open(rowId, slotId) { this.y61Stop(); this._y61Back = '[data-slot="' + slotId + '"]'; this.setState({ y61Panel: { rowId, slotId }, y61Pos: 0, y61Play: false, y61Mode: null, y61Draft: null, player: null, playerPlaying: false }, () => this.y61Focus()); }
  y61Close() { this.y61Stop(); const back = this._y61Back; this.setState({ y61Panel: null, y61Play: false, y61Mode: null, y61Draft: null }, () => { const el = back && document.querySelector(back); if (el) el.focus(); }); }
  // patch the composite without an Undo entry (simulated background work finishing, or a harness sample)
  y61Raw(rowId, slotId, fn, after) { const rows = DEEP(this.state.rows), row = rows.find(r => r.id === rowId), slot = row && row.visuals.find(v => v.id === slotId); if (!slot) return; fn(slot); this.setState({ rows }, after); }
  y61Edit(label, fn, msg) { const r = this.y61Ref(); if (!r) return; this.commit(label, rows => { const row = rows.find(x => x.id === r.row.id), slot = row && row.visuals.find(v => v.id === r.slot.id); if (slot && slot.ytc) fn(slot.ytc, slot); }, () => { if (msg) this.y61Say(msg); }); }
  y61Capture(rowId, slotId) { setTimeout(() => this.y61Raw(rowId, slotId, sl => { if (sl.ytc && sl.ytc.state === "capturing") { sl.ytc.state = "ready"; if (!sl.ytc.revs.length) { sl.ytc.revs = [Object.assign(DEEP(Y61.revA), { at: "16 Nov 2026, 14:02" })]; sl.ytc.rev = 1; } } }, () => this.y61Say("Page captured. The clip now plays inside the frozen page.")), 1500); }
  y61Make(rowId, slotId) {
    const row = this.state.rows.find(r => r.id === rowId), slot = row && row.visuals.find(v => v.id === slotId); if (!slot) return;
    this.commit("Present " + this.y61Name(slot) + " on its YouTube page", rows => { const x = rows.find(r => r.id === rowId), v = x && x.visuals.find(w => w.id === slotId); if (v) { v.ytc = Y61_NEW("capturing"); v.ytc.revs = []; } },
      () => { this.y61Open(rowId, slotId); this.y61Capture(rowId, slotId); });
  }
  y61Remove() { const r = this.y61Ref(); if (!r) return; const id = r.slot.id; this.y61Stop(); this.commit("Show " + this.y61Name(r.slot) + " as plain Footage", rows => { const row = rows.find(x => x.id === r.row.id), slot = row && row.visuals.find(v => v.id === id); if (slot) delete slot.ytc; }, () => { this.setState({ y61Panel: null, y61Mode: null, y61Draft: null }); this.y61Say("Shown as plain Footage. The page captures are kept. Undo brings the composite back."); const el = document.querySelector('[data-slot="' + id + '"]'); if (el) el.focus(); }); }
  y61Retry() { const r = this.y61Ref(); if (!r) return; this.y61Edit("Capture the YouTube page again", y => { y.state = "capturing"; }); this.y61Capture(r.row.id, r.slot.id); }
  y61Refresh() { this.y61Edit("Refresh the YouTube page capture", y => { const n = y.revs.length + 1; y.revs.push(Object.assign(DEEP(Y61.revB), { n })); y.rev = n; y.check = true; y.age = ""; }, "New capture selected for this visual. Earlier builds keep the capture they used."); }
  y61UseRev(n) { this.y61Edit("Use page capture revision " + n, y => { y.rev = n; y.check = y.rectBy === "hand"; }, "Revision " + n + " selected for this visual."); }
  y61Toggle() {
    const r = this.y61Ref(); if (!r || this.state.y61Mode) return; const m = r.slot.media, dur = Math.max(0.5, (m.out === null || m.out === undefined ? m.total : m.out) - m.in);
    if (this.state.y61Play) { this.y61Stop(); this.setState({ y61Play: false }); return; }
    this.y61Stop(); const from = (this.state.y61Pos || 0) >= dur - 0.05 ? 0 : (this.state.y61Pos || 0);
    this.setState({ y61Play: true, y61Pos: from });
    this._y61T = setInterval(() => { const p = (this.state.y61Pos || 0) + 0.1; if (p >= dur || !this.state.y61Panel) { this.y61Stop(); this.setState({ y61Play: false, y61Pos: dur }); } else this.setState({ y61Pos: p }); }, 100);
  }
  y61Begin(mode) { const r = this.y61Ref(); if (!r) return; this.y61Stop(); const y = r.y, f = y.focus || { x: Math.round((y.rect.x + y.rect.w / 2) * 10) / 10, y: Math.round((y.rect.y + y.rect.h / 2) * 10) / 10 };
    this.setState({ y61Mode: mode, y61Draft: mode === "rect" ? DEEP(y.rect) : f, y61Play: false, y61Pos: 0 }, () => this.y61Focus(mode === "rect" ? "[data-y61rect]" : "[data-y61focus]")); }
  y61Done() { const m = this.state.y61Mode, d = this.state.y61Draft; if (!m || !d) return; this.setState({ y61Mode: null, y61Draft: null });
    if (m === "rect") this.y61Edit("Adjust the player rectangle", y => { y.rect = d; y.rectBy = "hand"; y.check = false; }, "Player rectangle saved for this visual. Earlier builds keep the rectangle they used.");
    else this.y61Edit("Move the zoom focus point", y => { y.focus = d; }, "Zoom focus point saved.");
    this.y61Focus(m === "rect" ? "[data-y61b='rect']" : "[data-y61b='focus']"); }
  y61Cancel() { const m = this.state.y61Mode; this.setState({ y61Mode: null, y61Draft: null }); this.y61Focus(m === "rect" ? "[data-y61b='rect']" : "[data-y61b='focus']"); }
  y61Clamp(kind, d, dx, dy) { const c = (v, a, b) => Math.round(Math.max(a, Math.min(b, v)) * 10) / 10;
    if (kind === "focus") return { x: c(d.x + dx, 0, 100), y: c(d.y + dy, 0, 100) };
    if (kind === "size") return Object.assign({}, d, { w: c(d.w + dx, 10, 100 - d.x), h: c(d.h + dy, 10, 100 - d.y) });
    return Object.assign({}, d, { x: c(d.x + dx, 0, 100 - d.w), y: c(d.y + dy, 0, 100 - d.h) }); }
  y61Drag(e, kind) { if (e.button || !this.state.y61Draft) return; e.preventDefault(); e.stopPropagation();
    const st = document.querySelector("[data-y61stage]"); if (!st) return; const b = st.getBoundingClientRect(), d0 = DEEP(this.state.y61Draft), x0 = e.clientX, y0 = e.clientY;
    const mv = (ev) => this.setState({ y61Draft: this.y61Clamp(kind, d0, (ev.clientX - x0) / b.width * 100, (ev.clientY - y0) / b.height * 100) });
    const up = () => { document.removeEventListener("pointermove", mv); document.removeEventListener("pointerup", up); };
    document.addEventListener("pointermove", mv); document.addEventListener("pointerup", up); }
  y61Nudge(e, kind) { const K = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key]; if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); this.y61Done(); return; }
    if (!K || !this.state.y61Draft) return; e.preventDefault(); e.stopPropagation(); const st = e.altKey ? 0.1 : 0.5;
    this.setState({ y61Draft: this.y61Clamp(kind === "rect" ? (e.shiftKey ? "size" : "move") : "focus", this.state.y61Draft, K[0] * st, K[1] * st) }); }
  // harness samples: apply a composite state to the first Footage card, without an Undo entry
  y61Sample(key) {
    let hit = null; (this.state.rows || []).some(r => (r.visuals || []).some(v => { if (v.kind === "clip" && v.media && v.img && document.querySelector('[data-slot="' + v.id + '"]')) { hit = { rowId: r.id, slotId: v.id }; return true; } return false; }));
    if (!hit) return; this.y61Stop();
    const make = () => { const y = Y61_NEW("ready");
      if (key === "ready") y.builds = [{ n: Y61.build.n, at: Y61.build.at, rev: 1 }];
      if (key === "capturing") { y.state = "capturing"; y.revs = []; }
      if (key === "missing") { y.state = "missing"; y.revs = []; }
      if (key === "old") { y.revs[0].at = "6 Oct 2026, 11:30"; y.age = "41 days"; y.builds = [{ n: Y61.build.n, at: Y61.build.at, rev: 1 }]; }
      if (key === "refreshed") { y.revs.push(Object.assign(DEEP(Y61.revB), { n: 2 })); y.rev = 2; y.check = true; y.builds = [{ n: Y61.build.n, at: Y61.build.at, rev: 1 }]; }
      if (key === "denied") y.clip = "denied";
      if (key === "aspect") y.aspect = "4:3";
      return y; };
    this.y61Raw(hit.rowId, hit.slotId, sl => { if (key === "plain") delete sl.ytc; else sl.ytc = make(); }, () => {
      const el = document.querySelector('[data-slot="' + hit.slotId + '"]'); if (el && el.scrollIntoView) el.scrollIntoView({ block: "center" });
      if (key === "plain") this.setState({ y61Panel: null, y61Mode: null, y61Draft: null, y61Scn: key }); else { this.setState({ y61Scn: key }); this.y61Open(hit.rowId, hit.slotId); } });
  }
  r61Vals(out, cmp) {
    const s = this.state, res = {}, hb = out.hBtn || {};
    const SC = [["plain", "Plain Footage"], ["ready", "Composite ready"], ["capturing", "Capturing"], ["missing", "No page capture"], ["old", "Old capture"], ["refreshed", "After a refresh"], ["denied", "Clip access denied"], ["aspect", "4:3 clip"]];
    res.h61 = SC.map(([k, l]) => ({ key: k, label: l, on: s.y61Scn === k ? "true" : "false", pick: () => this.y61Sample(k),
      style: Object.assign({}, hb, s.y61Scn === k ? { background: "#3c424b", color: "#ffffff", borderColor: "#3c424b" } : {}) }));
    res.h61Note = "S16 r1 YouTube page composite (issue 61). Each sample applies to the first Footage card. Or use a Footage card's ⋯ menu › Present on YouTube page. Page text, counts, capture, clip access and the zoom are fixtures; nothing is captured, downloaded, composited or sent to Resolve.";
    // cards
    const attn = (y) => y.state === "missing" || y.clip === "denied" || y.check;
    (out.sections || []).forEach(sec => (sec.rows || []).forEach(r => { const rowS = (s.rows || []).find(x => x.id === r.id); if (!rowS) return;
      (r.items || []).forEach(it => { if (!it.isCard) return; const v = rowS.visuals.find(x => x.id === it.id); if (!v || !v.ytc) return; const y = v.ytc, bad = attn(y);
        const t = y.state === "capturing" ? "On YouTube page · capturing…" : bad ? "⚠ On YouTube page · needs attention" : "On YouTube page";
        it.badges = (it.badges || []).concat([{ t, style: { flex: "0 0 auto", display: "inline-flex", alignItems: "center", height: "18px", padding: "0 6px", border: "1px solid " + (bad ? "#c98a82" : "#b9a06a"), borderRadius: "999px", background: bad ? "#fbf1ef" : "#fbf3e2", color: bad ? "#8c2f26" : "#6b4f12", font: "600 10.5px/1 var(--font-ui)", whiteSpace: "nowrap" } }]);
        if (typeof it.cardAria === "string") it.cardAria = "YouTube page composite" + (bad ? ", needs attention" : "") + ". " + it.cardAria + " Opens the composite.";
        const open = () => this.y61Open(rowS.id, v.id), key0 = it.cardKey;
        it.cardClick = (e) => { if (e && e.target && e.target.closest && e.target.closest("button,select,input,textarea")) return; open(); };
        it.cardKey = (e) => { if ((e.key === "Enter" || e.key === " ") && e.target === e.currentTarget) { e.preventDefault(); open(); return; } if (key0) key0(e); }; }); }));
    const R = this.y61Ref();
    res.y61On = !!R; if (!R) return res;
    const { row, slot, y } = R, m = slot.media, mIn = m.in || 0, mOut = m.out === null || m.out === undefined ? m.total : m.out, dur = Math.max(0.5, mOut - mIn), n1 = (x) => (Math.round(x * 10) / 10).toFixed(1);
    const mode = s.y61Mode || null, draft = s.y61Draft, rect = mode === "rect" && draft ? draft : y.rect, rev = y.revs.find(x => x.n === y.rev) || null;
    const focus = mode === "focus" && draft ? draft : (y.focus || { x: y.rect.x + y.rect.w / 2, y: y.rect.y + y.rect.h / 2 });
    const hasPage = y.state === "ready" && !!rev, clipOk = y.clip !== "denied", pos = Math.min(dur, s.y61Pos || 0), prog = dur ? pos / dur : 0;
    const narr = this.wordsOf(row).length > 0, W = cmp ? 440 : 500;
    // place the panel left of the card, inside the app frame
    const card = document.querySelector('[data-slot="' + slot.id + '"]'), fr = card && card.closest("[data-frame]"), fb = fr ? fr.getBoundingClientRect() : { left: 8, top: 8, right: (window.innerWidth || 1280) - 8, bottom: (window.innerHeight || 800) - 8 }, cb = card ? card.getBoundingClientRect() : null;
    const top = Math.max(8, fb.top + 70), maxH = Math.max(320, Math.min(fb.bottom - 112, (window.innerHeight || 800) - 8) - top);
    let left = cb ? cb.left - W - 18 : fb.left + 24; left = Math.max(fb.left + 12, Math.min(left, fb.right - W - 12));
    res.y61Style = { position: "fixed", zIndex: 82, left: left + "px", top: top + "px", width: W + "px", maxHeight: maxH + "px", overflowY: "auto", boxSizing: "border-box", display: "grid", gridAutoRows: "max-content", alignContent: "start", gap: cmp ? "var(--space-6)" : "var(--space-8)",
      padding: cmp ? "var(--space-10) var(--space-12)" : "var(--space-12) var(--space-14)", border: "var(--border-w) solid #2a2f38", borderRadius: "var(--radius-panel)", background: "#161920", boxShadow: "0 22px 54px rgb(0 0 0 / 58%)" };
    const btn = (on) => this.barBtn(on), txt = (c, sz, w) => ({ font: (w || 400) + " " + (sz || 11.5) + "px/1.4 var(--font-ui)", color: c || "#c3c8d0", textWrap: "pretty", minWidth: 0 });
    Object.assign(res, {
      y61Title: "YouTube page composite", y61Sub: this.y61Name(slot) + " · " + (slot.source || "Research clip") + " · template “" + Y61.tpl.name + "” r" + Y61.tpl.rev,
      y61Close: () => this.y61Close(), y61CloseStyle: Object.assign(btn(false), { width: "26px", padding: 0 }),
      y61HeadStyle: { display: "flex", alignItems: "center", gap: "var(--space-8)" },
      y61TitleStyle: { font: "var(--type-subhead-weight) var(--type-subhead-size)/var(--type-subhead-leading) var(--type-subhead-family)", color: "#e7e4dd" },
      y61SimStyle: { padding: "1px 6px", border: "1px dashed #5b626c", borderRadius: "4px", font: "600 10.5px/1.4 var(--font-ui)", color: "#aab0ba", whiteSpace: "nowrap" },
      y61SubStyle: txt("#8b929e", 11.5),
      y61Key: (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); if (this.state.y61Mode) this.y61Cancel(); else this.y61Close(); } else if (e.key !== "Tab") e.stopPropagation(); }
    });
    // alert (one at a time, most blocking first)
    const A = (tone, text, btns) => { res.y61Alert = true; res.y61AlertText = text; res.y61AlertBtns = btns.map(b => Object.assign({ style: btn(false) }, b));
      res.y61AlertStyle = { display: "flex", flexWrap: "wrap", alignItems: "center", gap: "6px 8px", padding: "7px 9px", borderRadius: "6px", border: "1px solid " + (tone === "bad" ? "#724342" : "#6b5a2c"), background: tone === "bad" ? "#2b1d1d" : "#262117", color: tone === "bad" ? "#f0c9c5" : "#f4e1b9", font: "500 12px/1.4 var(--font-ui)", textWrap: "pretty" }; };
    res.y61Alert = false; res.y61AlertBtns = [];
    if (y.state === "missing") A("bad", "⚠ No page capture. The page refused a public capture (simulated). Until a capture exists, the next build puts a labelled placeholder here.", [{ label: "Try the capture again", pick: () => this.y61Retry() }, { label: "Show as plain Footage", pick: () => this.y61Remove() }]);
    else if (!clipOk) A("bad", "⚠ The clip’s video can’t be used: access to this Research clip was denied (simulated). The page capture is kept. The next build puts a labelled placeholder here.", [{ label: "Check access again", pick: () => this.y61Say("Access is still denied (simulated). Nothing changed.") }]);
    else if (y.check && hasPage && !mode) A("warn", "◆ Check the player rectangle. This capture is new for this visual, and VERA does not find the player by itself.", [{ label: "Adjust rectangle", pick: () => this.y61Begin("rect") }, { label: "It lines up", pick: () => this.y61Edit("Confirm the player rectangle", z => { z.check = false; }, "Rectangle confirmed for revision " + y.rev + ".") }]);
    else if (y.age && hasPage && !mode) A("warn", "◆ This capture is " + y.age + " old. The live page may have changed. VERA only looks again when you refresh.", [{ label: "Refresh page now", pick: () => this.y61Refresh() }]);
    // stage
    const sh = rev ? (rev.shift || 0) : 0, k = (W - (cmp ? 26 : 30)) / 1280, px = (n) => Math.max(1, n * k).toFixed(2) + "px";
    const box = (x, yy, w, h, st, t) => ({ t: t || "", style: Object.assign({ position: "absolute", left: x + "%", top: yy + "%", width: w + "%", height: h + "%", boxSizing: "border-box", overflow: "hidden", whiteSpace: "nowrap" }, st) });
    const line = (x, yy, w, t, size, st) => box(x, yy, w, 5, Object.assign({ height: "auto", font: "500 " + px(size) + "/1.25 Inter,sans-serif", color: "#0f0f0f", textOverflow: "ellipsis" }, st || {}), t);
    const boxes = [];
    if (hasPage) {
      const P = Y61.page, base = Y61.tpl.rect;
      boxes.push(box(0, 0, 100, 7.5, { background: "#ffffff", borderBottom: "1px solid #e5e5e5" }));
      boxes.push(line(2, 2.1, 20, "▶ Video site (fictional)", 20, { fontWeight: 700 }));
      boxes.push(box(32, 1.6, 36, 4.4, { border: "1px solid #cfcfcf", borderRadius: "999px", background: "#f8f8f8" }));
      if (sh) boxes.push(box(0, 7.5, 100, sh, { background: "#fff4d6", color: "#5a4300", font: "600 " + px(15) + "/1 Inter,sans-serif", display: "flex", alignItems: "center", paddingLeft: "4.2%" }, P.banner));
      boxes.push(box(base.x, base.y + sh, base.w, base.h, { background: "#1b1b1b", color: "#8a8a8a", borderRadius: px(10), display: "flex", alignItems: "center", justifyContent: "center", font: "600 " + px(40) + "/1 Inter,sans-serif" }, "▶"));
      const ty = base.y + base.h + sh;
      boxes.push(line(base.x, ty + 2.2, base.w, slot.title || P.title, 26, { fontWeight: 700 }));
      boxes.push(box(base.x, ty + 8.6, 3.6, 6.4, { borderRadius: "50%", background: "#7a94a8" }));
      boxes.push(line(base.x + 4.6, ty + 8.6, 30, P.channel, 19, { fontWeight: 600 }));
      boxes.push(line(base.x + 4.6, ty + 12, 30, P.subs, 15, { color: "#606060" }));
      boxes.push(box(base.x + 38, ty + 9.2, 10, 5, { borderRadius: "999px", background: "#0f0f0f" }));
      boxes.push(box(base.x, ty + 17.2, base.w, 30, { borderRadius: px(12), background: "#f2f2f2" }));
      boxes.push(line(base.x + 1.2, ty + 18.6, base.w - 3, rev.views + " · " + P.date, 17, { fontWeight: 600 }));
      boxes.push(line(base.x + 1.2, ty + 22.2, base.w - 3, P.desc, 16, { color: "#303030" }));
      for (let i = 0; i < 6; i++) { const yy = 10.5 + sh + i * 15.4; boxes.push(box(69, yy, 12.5, 12.5, { borderRadius: px(8), background: ["#b9c4cc", "#c9bfb0", "#aebdaa", "#c2b7c6", "#b5c2c9", "#c8c0b2"][i] })); boxes.push(box(82.6, yy + 1, 13, 2.4, { borderRadius: "2px", background: "#d0d0d0" })); boxes.push(box(82.6, yy + 4.6, 9, 2, { borderRadius: "2px", background: "#e2e2e2" })); }
    }
    const hatch = "repeating-linear-gradient(135deg, #1b1f26 0 8px, #232831 8px 16px)";
    const editR = mode === "rect", editF = mode === "focus", zoomOn = y.motion === "zoom" && hasPage, z = zoomOn && !mode ? 1 + (Y61.zoom - 1) * prog : 1;
    const outline = editR || (y.check && hasPage);
    Object.assign(res, {
      y61Boxes: boxes,
      y61StageStyle: { position: "relative", width: "100%", aspectRatio: "16 / 9", borderRadius: "var(--radius-chip)", border: "var(--border-w) solid #2a2f38", overflow: "hidden", background: hasPage ? "#ffffff" : hatch },
      y61StageAria: !hasPage ? (y.state === "capturing" ? "Composite preview. The page is being captured." : "Composite preview. There is no page capture.") : "Composite preview, simulated. Frozen capture of the fictional watch page, revision " + y.rev + ", " + rev.views + ". " + (clipOk ? "The clip " + this.y61Name(slot) + " fills the player area at " + n1(rect.x) + " percent from the left and " + n1(rect.y) + " percent from the top." : "The clip is unavailable.") + (zoomOn ? " The whole composite zooms slowly toward a point " + n1(focus.x) + " percent from the left and " + n1(focus.y) + " percent from the top." : " No motion."),
      y61ZoomStyle: { position: "absolute", inset: 0, transformOrigin: focus.x + "% " + focus.y + "%", transform: "scale(" + z.toFixed(4) + ")" },
      y61StageMsg: hasPage ? "" : y.state === "capturing" ? "Capturing the public page…" : "No page capture",
      y61MsgStyle: { position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", font: "600 12.5px/1.4 var(--font-ui)", color: "#c3c8d0", textAlign: "center", padding: "0 12px" },
      y61ClipOn: hasPage,
      y61RectStyle: { position: "absolute", left: rect.x + "%", top: rect.y + "%", width: rect.w + "%", height: rect.h + "%", boxSizing: "border-box", background: clipOk ? "#000000" : hatch, display: "flex", alignItems: "center", justifyContent: "center",
        outline: outline ? "2px dashed #d1ad67" : "none", outlineOffset: "1px", cursor: editR ? "move" : "default", touchAction: "none" },
      y61RectTab: editR ? "0" : "-1",
      y61RectAria: editR ? "Player rectangle. " + n1(rect.x) + " percent from the left, " + n1(rect.y) + " percent from the top, " + n1(rect.w) + " percent wide, " + n1(rect.h) + " percent tall. Arrow keys move it. Shift and arrow keys resize it. Hold Alt for fine steps. Enter saves." : "Clip in the player area",
      y61RectDown: (e) => { if (editR) this.y61Drag(e, "move"); }, y61RectKey: (e) => { if (editR) this.y61Nudge(e, "rect"); },
      y61PicStyle: clipOk ? { display: "block", height: "100%", width: y.aspect === "4:3" ? "75%" : "100%", backgroundImage: slot.img ? "url('" + IMG[slot.img] + "')" : "none", backgroundSize: "cover", backgroundPosition: "center" } : { display: "none" },
      y61ClipMsg: clipOk ? "" : "Clip unavailable", y61ClipMsgStyle: { font: "600 " + px(26) + "/1.2 var(--font-ui)", color: "#f0c9c5" },
      y61Tc: clipOk ? n1(mIn + pos) + "s" : "",
      y61TcStyle: { position: "absolute", left: "2%", bottom: "3%", padding: "1px 4px", borderRadius: "3px", background: "rgb(10 12 16 / 70%)", font: "500 10px/1.2 var(--font-mono)", color: "#e7e4dd", display: clipOk ? "block" : "none" },
      y61SizeOn: editR, y61SizeDown: (e) => this.y61Drag(e, "size"),
      y61SizeStyle: { position: "absolute", right: "-7px", bottom: "-7px", width: "14px", height: "14px", borderRadius: "3px", border: "2px solid #17120a", background: "#d1ad67", cursor: "nwse-resize", touchAction: "none" },
      y61FocusOn: zoomOn, y61FocusTab: editF ? "0" : "-1",
      y61FocusAria: editF ? "Zoom focus point. " + n1(focus.x) + " percent from the left, " + n1(focus.y) + " percent from the top. Arrow keys move it. Hold Alt for fine steps. Enter saves." : "Zoom focus point",
      y61FocusDown: (e) => { if (editF) this.y61Drag(e, "focus"); }, y61FocusKey: (e) => { if (editF) this.y61Nudge(e, "focus"); },
      y61FocusStyle: { position: "absolute", left: focus.x + "%", top: focus.y + "%", width: editF ? "26px" : "16px", height: editF ? "26px" : "16px", margin: editF ? "-13px 0 0 -13px" : "-8px 0 0 -8px", borderRadius: "50%", border: "2px solid #d1ad67", boxShadow: "0 0 0 1.5px #17120a, inset 0 0 0 1.5px #17120a", background: "rgb(23 18 10 / 35%)", color: "#f4e1b9", display: "flex", alignItems: "center", justifyContent: "center", font: "700 " + (editF ? 15 : 10) + "px/1 var(--font-ui)", cursor: editF ? "move" : "default", touchAction: "none", boxSizing: "border-box" },
      y61BarStyle: { display: "block", height: "100%", width: (prog * 100).toFixed(1) + "%", background: "var(--gold)" },
      y61PlayOn: hasPage && clipOk && !mode, y61PlayLabel: s.y61Play ? "■ Pause" : "▶ Play", y61PlayPressed: s.y61Play ? "true" : "false", y61PlayStyle: btn(!!s.y61Play), y61Toggle: () => this.y61Toggle(),
      y61Range: hasPage && clipOk ? "clip " + n1(mIn) + "s – " + n1(mOut) + "s · " + n1(dur) + "s" + (zoomOn ? " · zoom ×1.00 → ×" + Y61.zoom.toFixed(2) : " · no motion") : "",
      y61RangeStyle: { font: "var(--type-mono-meta-weight) var(--type-mono-meta-size)/1.4 var(--type-mono-meta-family)", color: "#c3c8d0" },
      y61EditOn: !!mode,
      y61EditText: editR ? "Drag the rectangle, or its corner handle, until the clip covers the player in the capture. Keyboard: arrows move, Shift+arrows resize, Enter saves." : "Drag the ring to where the zoom should head. Keyboard: arrows move, Enter saves.",
      y61EditStyle: Object.assign(txt("#f4e1b9", 12, 500), { display: "flex", flexWrap: "wrap", alignItems: "center", gap: "6px 8px", padding: "7px 9px", border: "1px solid #6b5a2c", borderRadius: "6px", background: "#262117" }),
      y61EditBtns: !mode ? [] : [{ label: "Save", pick: () => this.y61Done(), style: Object.assign(btn(true), {}) }, { label: "Cancel", pick: () => this.y61Cancel(), style: btn(false) },
        { label: editR ? "Reset to the template" : "Reset to the player", pick: () => this.setState({ y61Draft: editR ? DEEP(Y61.tpl.rect) : { x: Math.round((y.rect.x + y.rect.w / 2) * 10) / 10, y: Math.round((y.rect.y + y.rect.h / 2) * 10) / 10 } }), style: btn(false) }]
    });
    // settings rows
    const B = (label, pick, o) => Object.assign({ label, pick, pressed: "false", key: "", style: btn(false) }, o || {});
    const rows = [];
    rows.push({ l: "Clip", v: this.y61Name(slot) + " · " + n1(mIn) + "–" + n1(mOut) + " s",
      n: "The whole frame at YouTube’s shape. Never cropped or stretched; “Hide baked-in black bars” does not apply here." + (y.aspect === "4:3" ? " This clip is 4:3, so it sits in the 16:9 player with black at the sides, as it does on YouTube." : ""),
      b: [B("Trim…", () => { const rid = row.id, sid = slot.id; this.y61Close(); this.openPlayer(rid, sid, true); })] });
    if (y.state === "ready" && rev) rows.push({ l: "Page capture", v: "Revision " + rev.n + " · captured " + rev.at + " · " + rev.views,
      n: "A frozen picture of the public page. A refresh changes only this visual in this draft.",
      b: [B("Refresh page now", () => this.y61Refresh())].concat(y.revs.length > 1 ? y.revs.map(x => B("Revision " + x.n, () => { if (x.n !== y.rev) this.y61UseRev(x.n); }, { pressed: x.n === y.rev ? "true" : "false", style: btn(x.n === y.rev) })) : []) });
    else rows.push({ l: "Page capture", v: y.state === "capturing" ? "Capturing… (simulated)" : "None", n: "VERA captures the public page as anyone would see it signed out. It never uses your YouTube sign-in.", b: [] });
    if (hasPage) rows.push({ l: "Player rectangle", v: (y.rectBy === "hand" ? "Adjusted by hand" : "From the template") + (y.check ? " · needs a check" : ""), n: "", b: [B("Adjust rectangle", () => this.y61Begin("rect"), { key: "rect" })] });
    if (hasPage) rows.push({ l: "Motion", v: y.motion === "zoom" ? "Slow zoom toward " + (y.focus ? "your focus point" : "the player") : "No motion",
      n: "Zooms page and clip together for the visual’s full length. Not buildable until one Resolve check passes.",
      b: [B("Slow zoom", () => { if (y.motion !== "zoom") this.y61Edit("Turn on the composite’s slow zoom", z2 => { z2.motion = "zoom"; }); }, { pressed: y.motion === "zoom" ? "true" : "false", style: btn(y.motion === "zoom") }),
        B("No motion", () => { if (y.motion !== "none") this.y61Edit("Turn off the composite’s motion", z2 => { z2.motion = "none"; }); }, { pressed: y.motion === "none" ? "true" : "false", style: btn(y.motion === "none") })]
        .concat(y.motion === "zoom" ? [B("Move focus point", () => this.y61Begin("focus"), { key: "focus" })] : []) });
    rows.push({ l: "Sound", v: narr ? "Silent. Narration plays over it." : "The clip’s own sound plays (this row has no narration).", n: "Same rule as any Footage card. The page adds no sound.", b: [] });
    rows.push({ l: "Builds", v: y.builds.length ? y.builds.map(b => "Build " + b.n + " · " + b.at + " used revision " + b.rev + " with its own clip range and rectangle.").join(" ") : "Not built yet.",
      n: y.builds.length ? "Earlier builds keep exactly the parts they used." : "", b: [] });
    const lab = { font: "600 11px/1.4 var(--font-ui)", color: "#8b929e", letterSpacing: ".02em" };
    res.y61Rows = rows.map(r => ({ l: r.l, v: r.v, n: r.n, hasN: !!r.n, b: r.b, hasB: r.b.length > 0, labStyle: lab, valStyle: txt("#e7e4dd", 12.5, 500), noteStyle: txt("#9aa1ab", 11.5),
      aria: r.l + " actions" }));
    res.y61RowStyle = { display: "grid", gridTemplateColumns: (cmp ? "92px" : "104px") + " minmax(0, 1fr)", columnGap: "10px", alignItems: "start", padding: "7px 0 0", borderTop: "var(--border-w) solid #2a2f38" };
    res.y61RowsOff = !!mode;
    res.y61Next = y.state === "missing" || !clipOk || y.state === "capturing" ? (y.state === "capturing" ? "Next build: waits for the capture." : "Next build: a labelled placeholder, until this is fixed.")
      : "Next build: revision " + y.rev + " · clip " + n1(mIn) + "–" + n1(mOut) + " s · " + (y.motion === "zoom" ? "slow zoom (pending its Resolve check)" : "no motion") + " · " + (narr ? "silent under narration" : "clip sound");
    res.y61NextStyle = txt("#c3c8d0", 11.5, 500);
    res.y61Remove = () => this.y61Remove(); res.y61RemoveStyle = btn(false);
    res.y61FootStyle = { display: "flex", flexWrap: "wrap", alignItems: "center", gap: "6px 10px", paddingTop: "8px", borderTop: "var(--border-w) solid #2a2f38" };
    return res;
  }

  renderVals('''
s = once(s, "\n  renderVals(", "\n" + METHODS)

# ---------- (D) chain ----------
s = once(s, "Object.assign(out, this.r24Vals(out)); }\n    else { out.trPopOpen = false;", "Object.assign(out, this.r24Vals(out)); Object.assign(out, this.r61Vals(out, cmp)); }\n    else { out.y61On = false; out.h61 = []; out.trPopOpen = false;")

# ---------- (E) template ----------
HARN = '''<div data-h61="1" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;max-width:1240px">
<span style="color:#5b626c;font:600 11px/1 ui-monospace,Menlo,monospace">S16 COMPOSITE</span>
<sc-for list="{{ h61 }}" as="h" hint-placeholder-count="8"><button type="button" data-h61b="{{ h.key }}" onClick="{{ h.pick }}" aria-pressed="{{ h.on }}" style="{{ h.style }}">{{ h.label }}</button></sc-for>
<span style="color:#5b626c;font:500 11px/1.4 ui-monospace,Menlo,monospace;flex:1 1 100%;min-width:0;white-space:normal">{{ h61Note }}</span>
</div>
<sc-if value="{{ testOn }}"'''
s = once(s, '<sc-if value="{{ testOn }}"', HARN)

DLG = '''<sc-if value="{{ y61On }}" hint-placeholder-val="{{ false }}">
<div role="dialog" aria-label="YouTube page composite" data-y61="1" onKeyDown="{{ y61Key }}" style="{{ y61Style }}">
<div style="{{ y61HeadStyle }}">
<span style="{{ y61TitleStyle }}">{{ y61Title }}</span>
<span style="{{ y61SimStyle }}">Simulated preview</span>
<span style="flex:1 1 auto"></span>
<button type="button" onClick="{{ y61Close }}" aria-label="Close the YouTube page composite" style="{{ y61CloseStyle }}" style-focus="outline:2px solid #c49b50;outline-offset:1px">✕</button>
</div>
<span style="{{ y61SubStyle }}">{{ y61Sub }}</span>
<sc-if value="{{ y61Alert }}" hint-placeholder-val="{{ false }}"><div role="status" data-y61alert="1" style="{{ y61AlertStyle }}"><span style="flex:1 1 240px;min-width:0">{{ y61AlertText }}</span><sc-for list="{{ y61AlertBtns }}" as="b" hint-placeholder-count="2"><button type="button" onClick="{{ b.pick }}" style="{{ b.style }}" style-focus="outline:2px solid #c49b50;outline-offset:1px">{{ b.label }}</button></sc-for></div></sc-if>
<div data-y61stage="1" role="group" aria-label="{{ y61StageAria }}" style="{{ y61StageStyle }}">
<div style="{{ y61ZoomStyle }}">
<sc-for list="{{ y61Boxes }}" as="b" hint-placeholder-count="0"><span aria-hidden="true" style="{{ b.style }}">{{ b.t }}</span></sc-for>
<sc-if value="{{ y61ClipOn }}" hint-placeholder-val="{{ false }}"><div data-y61rect="1" tabindex="{{ y61RectTab }}" role="group" aria-label="{{ y61RectAria }}" onPointerDown="{{ y61RectDown }}" onKeyDown="{{ y61RectKey }}" style="{{ y61RectStyle }}" style-focus="outline:2px solid #f4e1b9;outline-offset:2px">
<span aria-hidden="true" style="{{ y61PicStyle }}"></span><span style="{{ y61ClipMsgStyle }}">{{ y61ClipMsg }}</span>
<span aria-hidden="true" style="{{ y61TcStyle }}">{{ y61Tc }}</span>
<sc-if value="{{ y61SizeOn }}" hint-placeholder-val="{{ false }}"><span aria-hidden="true" data-y61size="1" onPointerDown="{{ y61SizeDown }}" style="{{ y61SizeStyle }}"></span></sc-if>
</div></sc-if>
<sc-if value="{{ y61FocusOn }}" hint-placeholder-val="{{ false }}"><span data-y61focus="1" tabindex="{{ y61FocusTab }}" role="group" aria-label="{{ y61FocusAria }}" onPointerDown="{{ y61FocusDown }}" onKeyDown="{{ y61FocusKey }}" style="{{ y61FocusStyle }}" style-focus="outline:2px solid #f4e1b9;outline-offset:2px">+</span></sc-if>
</div>
<sc-if value="{{ y61StageMsg }}" hint-placeholder-val="{{ false }}"><span role="status" style="{{ y61MsgStyle }}">{{ y61StageMsg }}</span></sc-if>
</div>
<div style="height:5px;border-radius:var(--radius-pill);background:#2a2f38;overflow:hidden"><span style="{{ y61BarStyle }}"></span></div>
<sc-if value="{{ y61PlayOn }}" hint-placeholder-val="{{ false }}"><div style="display:flex;align-items:center;gap:var(--space-8);flex-wrap:wrap">
<button type="button" data-y61play="1" onClick="{{ y61Toggle }}" aria-pressed="{{ y61PlayPressed }}" style="{{ y61PlayStyle }}" style-focus="outline:2px solid #c49b50;outline-offset:1px">{{ y61PlayLabel }}</button>
<span style="{{ y61RangeStyle }}">{{ y61Range }}</span>
</div></sc-if>
<sc-if value="{{ y61EditOn }}" hint-placeholder-val="{{ false }}"><div data-y61edit="1" style="{{ y61EditStyle }}"><span style="flex:1 1 240px;min-width:0">{{ y61EditText }}</span><sc-for list="{{ y61EditBtns }}" as="b" hint-placeholder-count="3"><button type="button" onClick="{{ b.pick }}" style="{{ b.style }}" style-focus="outline:2px solid #c49b50;outline-offset:1px">{{ b.label }}</button></sc-for></div></sc-if>
<sc-for list="{{ y61Rows }}" as="r" hint-placeholder-count="6"><div data-y61row="{{ r.l }}" style="{{ y61RowStyle }}">
<span style="{{ r.labStyle }}">{{ r.l }}</span>
<div style="display:grid;gap:4px;min-width:0">
<span style="{{ r.valStyle }}">{{ r.v }}</span>
<sc-if value="{{ r.hasN }}" hint-placeholder-val="{{ true }}"><span style="{{ r.noteStyle }}">{{ r.n }}</span></sc-if>
<sc-if value="{{ r.hasB }}" hint-placeholder-val="{{ true }}"><div role="group" aria-label="{{ r.aria }}" style="display:flex;flex-wrap:wrap;gap:6px;padding-top:2px"><sc-for list="{{ r.b }}" as="b" hint-placeholder-count="2"><button type="button" data-y61b="{{ b.key }}" onClick="{{ b.pick }}" aria-pressed="{{ b.pressed }}" style="{{ b.style }}" style-focus="outline:2px solid #c49b50;outline-offset:1px">{{ b.label }}</button></sc-for></div></sc-if>
</div>
</div></sc-for>
<div style="{{ y61FootStyle }}">
<span style="{{ y61NextStyle }}">{{ y61Next }}</span>
<span style="flex:1 1 auto"></span>
<button type="button" data-y61remove="1" onClick="{{ y61Remove }}" style="{{ y61RemoveStyle }}" style-focus="outline:2px solid #c49b50;outline-offset:1px">Show as plain Footage</button>
</div>
</div>
</sc-if>

<sc-if value="{{ playerVisible }}" hint-placeholder-val="{{ false }}">'''
s = once(s, '<sc-if value="{{ playerVisible }}" hint-placeholder-val="{{ false }}">', DLG)
open(p, "w", encoding="utf-8").write(s)
print("patched", len(s))
