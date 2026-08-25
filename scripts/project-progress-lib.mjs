import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

export const STATUS_WEIGHTS = Object.freeze({
  Accepted: 1,
  "Agent complete": 0.9,
  "In progress": 0.5,
  Paused: 0.5,
  Blocked: 0.25,
  Queued: 0,
});

const STATUS_CLASS = Object.freeze({
  Accepted: "accepted",
  "Agent complete": "agent-complete",
  "In progress": "in-progress",
  Paused: "paused",
  Blocked: "blocked",
  Queued: "queued",
});

const ROADMAP_START = "## 11. Execution plan: slices";
const ROADMAP_END = "## 12.";

function normalizeMarkdownText(value) {
  return value
    .replaceAll("\n", " ")
    .replaceAll(/\s+/g, " ")
    .replaceAll("**", "")
    .replaceAll("`", "")
    .trim();
}

function roadmapSection(specification) {
  const start = specification.indexOf(ROADMAP_START);
  if (start === -1) {
    throw new Error(`Could not find roadmap heading: ${ROADMAP_START}`);
  }

  const end = specification.indexOf(ROADMAP_END, start);
  if (end === -1) {
    throw new Error(`Could not find the end of the roadmap before: ${ROADMAP_END}`);
  }

  return specification.slice(start, end);
}

function phaseLadder(specification) {
  const start = specification.indexOf("## 5. The phase ladder");
  const end = specification.indexOf("## 6.", start);
  if (start === -1 || end === -1) {
    throw new Error("Could not find the phase ladder");
  }

  const ladder = specification.slice(start, end);
  return new Map(
    [...ladder.matchAll(/^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$/gm)].map(
      (match) => [
        Number(match[1]),
        {
          name: match[2]?.trim(),
          promise: normalizeMarkdownText(match[3]),
        },
      ],
    ),
  );
}

export function parseRoadmap(specification) {
  const roadmap = roadmapSection(specification);
  const ladder = phaseLadder(specification);
  const phaseMatches = [
    ...roadmap.matchAll(/^### Phase (\d+) — (.+)$/gm),
  ];

  if (phaseMatches.length === 0) {
    throw new Error("No phases found in the roadmap");
  }

  const phases = phaseMatches.map((match, index) => {
    const id = Number(match[1]);
    const name = match[2]?.trim();
    const bodyStart = (match.index ?? 0) + match[0].length;
    const nextMatch = phaseMatches[index + 1];
    const bodyEnd = nextMatch?.index ?? roadmap.length;
    const body = roadmap.slice(bodyStart, bodyEnd);
    const ladderPhase = ladder.get(id);
    const gateMatch = body.match(
      new RegExp(`\\n\\*\\*Phase ${id} gate:\\*\\* ([\\s\\S]*?)\\s*$`),
    );
    const slices = [
      ...body.matchAll(/^\*\*Slice (\d+\.\d+) — (.+?)\.\*\*/gm),
    ].map((sliceMatch) => ({
      id: sliceMatch[1],
      name: sliceMatch[2]?.trim(),
    }));

    if (!name || !ladderPhase?.promise || !gateMatch || slices.length === 0) {
      throw new Error(`Phase ${id} is missing a name, promise, gate, or slices`);
    }

    if (ladderPhase.name !== name) {
      throw new Error(`Phase ${id} has inconsistent names in sections 5 and 11`);
    }

    return {
      id,
      name,
      promise: ladderPhase.promise,
      gate: normalizeMarkdownText(gateMatch[1]),
      slices,
    };
  });

  const sliceIds = phases.flatMap((phase) =>
    phase.slices.map((slice) => slice.id),
  );
  if (new Set(sliceIds).size !== sliceIds.length) {
    throw new Error("The roadmap contains duplicate slice IDs");
  }

  return phases;
}

export function parseProgressTracker(progressDocument) {
  const trackerStart = progressDocument.indexOf("## Slice tracker");
  if (trackerStart === -1) {
    throw new Error("Could not find the slice tracker");
  }

  const trackerEnd = progressDocument.indexOf("\n## ", trackerStart + 1);
  const tracker = progressDocument.slice(
    trackerStart,
    trackerEnd === -1 ? progressDocument.length : trackerEnd,
  );
  const statuses = new Map();
  const rowPattern =
    /^\|\s*(\d+\.\d+)\s+[^|]*\|\s*(Queued|In progress|Agent complete|Accepted|Paused|Blocked)\s*\|/gm;

  for (const match of tracker.matchAll(rowPattern)) {
    statuses.set(match[1], match[2]);
  }

  if (statuses.size === 0) {
    throw new Error("The slice tracker contains no recognized status rows");
  }

  const lastUpdated =
    progressDocument.match(/^Last updated:\s*(.+)$/m)?.[1]?.trim() ?? "Unknown";
  return { statuses, lastUpdated };
}

function percentage(value, total) {
  return total === 0 ? 0 : (value / total) * 100;
}

export function buildProgressModel(phases, tracker) {
  const knownSliceIds = new Set(
    phases.flatMap((phase) => phase.slices.map((slice) => slice.id)),
  );
  const unknownTrackedSlices = [...tracker.statuses.keys()].filter(
    (sliceId) => !knownSliceIds.has(sliceId),
  );
  if (unknownTrackedSlices.length > 0) {
    throw new Error(
      `Tracked slices missing from the roadmap: ${unknownTrackedSlices.join(", ")}`,
    );
  }

  const modeledPhases = phases.map((phase) => {
    const slices = phase.slices.map((slice) => {
      const status = tracker.statuses.get(slice.id) ?? "Queued";
      return { ...slice, status, weight: STATUS_WEIGHTS[status] };
    });
    const accepted = slices.filter((slice) => slice.status === "Accepted").length;
    const estimatedUnits = slices.reduce((sum, slice) => sum + slice.weight, 0);

    return {
      ...phase,
      slices,
      accepted,
      estimatedUnits,
      acceptedPercent: percentage(accepted, slices.length),
      estimatedPercent: percentage(estimatedUnits, slices.length),
      complete: accepted === slices.length,
    };
  });

  const slices = modeledPhases.flatMap((phase) => phase.slices);
  const totalSlices = slices.length;
  const acceptedSlices = slices.filter((slice) => slice.status === "Accepted").length;
  const estimatedUnits = slices.reduce((sum, slice) => sum + slice.weight, 0);
  const statusCounts = Object.fromEntries(
    Object.keys(STATUS_WEIGHTS).map((status) => [
      status,
      slices.filter((slice) => slice.status === status).length,
    ]),
  );

  return {
    phases: modeledPhases,
    lastUpdated: tracker.lastUpdated,
    totalPhases: modeledPhases.length,
    acceptedPhases: modeledPhases.filter((phase) => phase.complete).length,
    totalSlices,
    acceptedSlices,
    estimatedUnits,
    acceptedPercent: percentage(acceptedSlices, totalSlices),
    estimatedPercent: percentage(estimatedUnits, totalSlices),
    statusCounts,
  };
}

export function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatPercent(value) {
  return `${value.toFixed(1)}%`;
}

function renderSlice(slice) {
  const statusClass = STATUS_CLASS[slice.status];
  return `
                <li class="slice ${statusClass}">
                  <span class="slice-dot" aria-hidden="true"></span>
                  <span class="slice-id">${escapeHtml(slice.id)}</span>
                  <span class="slice-name">${escapeHtml(slice.name)}</span>
                  <span class="status-label">${escapeHtml(slice.status)}</span>
                </li>`;
}

function renderPhase(phase) {
  const phaseStatus = phase.complete
    ? "Accepted"
    : phase.estimatedUnits > 0
      ? "Underway"
      : "Queued";
  return `
          <details class="phase"${phase.estimatedUnits > 0 ? " open" : ""}>
            <summary>
              <span class="phase-number">${phase.id}</span>
              <span class="phase-heading">
                <span class="phase-kicker">Phase ${phase.id} · ${phase.slices.length} slices</span>
                <strong>${escapeHtml(phase.name)}</strong>
              </span>
              <span class="phase-meter-wrap">
                <span class="phase-percent" data-estimated="${formatPercent(phase.estimatedPercent)}" data-accepted="${formatPercent(phase.acceptedPercent)}">${formatPercent(phase.estimatedPercent)}</span>
                <span class="phase-meter" aria-hidden="true">
                  <span data-progress-estimated="${phase.estimatedPercent.toFixed(2)}" data-progress-accepted="${phase.acceptedPercent.toFixed(2)}" style="width:${phase.estimatedPercent.toFixed(2)}%"></span>
                </span>
              </span>
              <span class="phase-state">${phaseStatus}</span>
            </summary>
            <div class="phase-body">
              <p class="phase-promise">You can now ${escapeHtml(phase.promise)}</p>
              <ul class="slice-list">${phase.slices.map(renderSlice).join("")}
              </ul>
              <p class="phase-gate"><span>Gate</span> ${escapeHtml(phase.gate)}</p>
            </div>
          </details>`;
}

export function renderDashboard(model) {
  const accepted = model.statusCounts.Accepted;
  const queued = model.statusCounts.Queued;
  const estimate = formatPercent(model.estimatedPercent);
  const acceptedPercent = formatPercent(model.acceptedPercent);

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VERA Project Progress</title>
  <style>
    :root {
      color-scheme: dark;
      --ink: #f6f3ed;
      --muted: #a4acbd;
      --deep: #080b13;
      --panel: #111724;
      --panel-2: #171f2f;
      --line: #2b3445;
      --cyan: #60d8ee;
      --violet: #a58aff;
      --amber: #ffbf69;
      --green: #70dda4;
      --red: #ff7d83;
      --track: #242d3c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-width: 320px;
      background:
        radial-gradient(circle at 15% 0%, rgba(96, 216, 238, .12), transparent 34rem),
        radial-gradient(circle at 90% 12%, rgba(165, 138, 255, .13), transparent 30rem),
        var(--deep);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }
    button, summary { font: inherit; }
    .shell { width: min(1120px, calc(100% - 32px)); margin: 0 auto; padding: 54px 0 72px; }
    .eyebrow {
      margin: 0 0 10px;
      color: var(--cyan);
      font-size: .73rem;
      font-weight: 700;
      letter-spacing: .18em;
      text-transform: uppercase;
    }
    h1 { margin: 0; max-width: 780px; font-size: clamp(2.25rem, 6vw, 5.4rem); line-height: .96; letter-spacing: -.055em; }
    .intro { margin: 20px 0 0; max-width: 720px; color: var(--muted); font-size: 1rem; }
    .hero {
      display: grid;
      grid-template-columns: minmax(240px, .85fr) minmax(0, 2fr);
      gap: 28px;
      align-items: stretch;
      margin: 42px 0 28px;
    }
    .orbit-card, .stats-card {
      border: 1px solid var(--line);
      border-radius: 24px;
      background: linear-gradient(145deg, rgba(23,31,47,.94), rgba(13,18,29,.94));
      box-shadow: 0 24px 60px rgba(0,0,0,.22);
    }
    .orbit-card { display: grid; place-items: center; min-height: 294px; padding: 24px; }
    .orbit {
      --progress: ${model.estimatedPercent.toFixed(2)}%;
      position: relative;
      display: grid;
      place-items: center;
      width: 220px;
      aspect-ratio: 1;
      border-radius: 50%;
      background: conic-gradient(var(--cyan) 0 var(--progress), rgba(96,216,238,.11) var(--progress) 100%);
      box-shadow: 0 0 44px rgba(96,216,238,.12);
    }
    .orbit::before {
      content: "";
      position: absolute;
      inset: 13px;
      border-radius: 50%;
      background: var(--panel);
      box-shadow: inset 0 0 36px rgba(0,0,0,.4);
    }
    .orbit-copy { position: relative; z-index: 1; text-align: center; }
    .orbit-value { display: block; font-size: 3.45rem; font-weight: 750; line-height: 1; letter-spacing: -.07em; }
    .orbit-label { display: block; margin-top: 8px; color: var(--muted); font-size: .78rem; letter-spacing: .1em; text-transform: uppercase; }
    .stats-card { display: flex; flex-direction: column; justify-content: space-between; padding: 28px; }
    .mode-switch { display: inline-flex; align-self: flex-start; gap: 4px; padding: 4px; border-radius: 999px; background: #0b101a; border: 1px solid var(--line); }
    .mode-switch button { border: 0; border-radius: 999px; padding: 8px 14px; color: var(--muted); background: transparent; cursor: pointer; }
    .mode-switch button[aria-pressed="true"] { color: var(--deep); background: var(--cyan); font-weight: 700; }
    .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 30px; }
    .stat { padding: 16px; border-top: 1px solid var(--line); }
    .stat strong { display: block; font-size: 2rem; line-height: 1.1; letter-spacing: -.04em; }
    .stat span { color: var(--muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .08em; }
    .fine-print { margin: 24px 0 0; color: var(--muted); font-size: .82rem; }
    .fine-print strong { color: var(--ink); }
    .section-heading { display: flex; align-items: end; justify-content: space-between; gap: 16px; margin: 52px 0 16px; }
    h2 { margin: 0; font-size: 1.35rem; letter-spacing: -.02em; }
    .updated { color: var(--muted); font-size: .8rem; }
    .roadmap { display: grid; gap: 10px; }
    .phase { border: 1px solid var(--line); border-radius: 16px; background: rgba(17,23,36,.88); overflow: hidden; }
    .phase[open] { background: rgba(23,31,47,.94); }
    .phase summary {
      display: grid;
      grid-template-columns: 42px minmax(190px, 1fr) minmax(150px, .65fr) 88px 24px;
      gap: 16px;
      align-items: center;
      padding: 17px 20px;
      cursor: pointer;
      list-style: none;
    }
    .phase summary::-webkit-details-marker { display: none; }
    .phase summary::after { content: "+"; grid-column: 5; color: var(--muted); font-size: 1.25rem; }
    .phase[open] summary::after { content: "−"; }
    .phase-number { display: grid; place-items: center; width: 38px; aspect-ratio: 1; border-radius: 50%; color: var(--cyan); background: rgba(96,216,238,.09); font-weight: 800; }
    .phase-heading { display: flex; min-width: 0; flex-direction: column; }
    .phase-heading strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .phase-kicker { color: var(--muted); font-size: .7rem; letter-spacing: .08em; text-transform: uppercase; }
    .phase-meter-wrap { display: grid; grid-template-columns: 52px minmax(90px, 1fr); gap: 10px; align-items: center; }
    .phase-percent { color: var(--muted); font-variant-numeric: tabular-nums; font-size: .82rem; text-align: right; }
    .phase-meter { display: block; height: 7px; border-radius: 99px; overflow: hidden; background: var(--track); }
    .phase-meter > span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--violet), var(--cyan)); transition: width .25s ease; }
    .phase-state { color: var(--muted); font-size: .76rem; text-align: right; text-transform: uppercase; letter-spacing: .07em; }
    .phase-body { padding: 0 20px 22px 78px; }
    .phase-promise { margin: 0 0 17px; max-width: 760px; color: var(--muted); }
    .slice-list { display: grid; gap: 1px; margin: 0; padding: 0; list-style: none; border-radius: 12px; overflow: hidden; }
    .slice { display: grid; grid-template-columns: 12px 48px minmax(0, 1fr) 112px; gap: 10px; align-items: center; min-height: 43px; padding: 9px 13px; background: rgba(8,11,19,.48); }
    .slice-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--muted); }
    .slice.accepted .slice-dot { background: var(--green); box-shadow: 0 0 12px rgba(112,221,164,.44); }
    .slice.agent-complete .slice-dot { background: var(--violet); box-shadow: 0 0 12px rgba(165,138,255,.44); }
    .slice.in-progress .slice-dot { background: var(--cyan); box-shadow: 0 0 12px rgba(96,216,238,.44); }
    .slice.blocked .slice-dot { background: var(--red); }
    .slice-id { color: var(--muted); font-size: .82rem; font-variant-numeric: tabular-nums; }
    .slice-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .status-label { color: var(--muted); font-size: .75rem; text-align: right; }
    .phase-gate { margin: 16px 0 0; max-width: 850px; color: var(--muted); font-size: .82rem; }
    .phase-gate span { margin-right: 7px; color: var(--amber); font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
    .legend { display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 22px; color: var(--muted); font-size: .78rem; }
    .legend span { white-space: nowrap; }
    .legend b { color: var(--ink); }
    @media (max-width: 820px) {
      .hero { grid-template-columns: 1fr; }
      .orbit-card { min-height: 260px; }
      .stats-grid { grid-template-columns: repeat(2, 1fr); }
      .phase summary { grid-template-columns: 42px minmax(0, 1fr) 82px 24px; }
      .phase-meter-wrap { grid-column: 2 / 4; grid-row: 2; }
      .phase-state { grid-column: 3; grid-row: 1; }
      .phase summary::after { grid-column: 4; grid-row: 1; }
      .phase-body { padding-left: 20px; }
    }
    @media (max-width: 520px) {
      .shell { width: min(100% - 20px, 1120px); padding-top: 34px; }
      .stats-card { padding: 20px; }
      .phase summary { padding: 14px; gap: 10px; }
      .phase-body { padding: 0 12px 16px; }
      .phase-state { display: none; }
      .slice { grid-template-columns: 10px 38px minmax(0, 1fr); }
      .status-label { grid-column: 3; text-align: left; }
      .section-heading { align-items: start; flex-direction: column; }
    }
    @media (prefers-reduced-motion: reduce) { .phase-meter > span { transition: none; } }
  </style>
</head>
<body>
  <main class="shell" id="progress-dashboard">
    <p class="eyebrow">VERA · Project flight recorder</p>
    <h1>From script<br>to finished timeline.</h1>
    <p class="intro">A just-for-fun view of the full roadmap. It is generated from the authoritative product spec and the producer-controlled slice tracker—not a separate project plan.</p>

    <section class="hero" aria-label="Overall progress">
      <div class="orbit-card">
        <div class="orbit" role="img" aria-label="${estimate} weighted estimated progress">
          <div class="orbit-copy">
            <strong class="orbit-value" data-estimated="${estimate}" data-accepted="${acceptedPercent}">${estimate}</strong>
            <span class="orbit-label" data-mode-label>weighted estimate</span>
          </div>
        </div>
      </div>
      <div class="stats-card">
        <div>
          <div class="mode-switch" aria-label="Progress calculation">
            <button type="button" data-mode="estimated" aria-pressed="true">Estimated</button>
            <button type="button" data-mode="accepted" aria-pressed="false">Accepted only</button>
          </div>
          <p class="fine-print"><strong>Acceptance stays sacred.</strong> The estimate gives partial credit to active work; the accepted-only view counts only producer-accepted slices.</p>
        </div>
        <div class="stats-grid">
          <div class="stat"><strong>${model.totalPhases}</strong><span>Phases</span></div>
          <div class="stat"><strong>${model.totalSlices}</strong><span>Total slices</span></div>
          <div class="stat"><strong>${accepted}</strong><span>Accepted</span></div>
          <div class="stat"><strong>${queued}</strong><span>Queued</span></div>
        </div>
      </div>
    </section>

    <div class="section-heading">
      <h2>The eleven-phase climb</h2>
      <span class="updated">Tracker updated ${escapeHtml(model.lastUpdated)} · ${model.acceptedPhases}/${model.totalPhases} phase gates complete</span>
    </div>
    <section class="roadmap" aria-label="Roadmap phases">${model.phases.map(renderPhase).join("")}
    </section>
    <div class="legend" aria-label="Estimate weights">
      <span><b>Accepted</b> 100%</span>
      <span><b>Agent complete</b> 90%</span>
      <span><b>In progress</b> 50%</span>
      <span><b>Blocked</b> 25%</span>
      <span><b>Queued</b> 0%</span>
    </div>
  </main>
  <script>
    (() => {
      const root = document.getElementById("progress-dashboard");
      const orbit = root.querySelector(".orbit");
      const orbitValue = root.querySelector(".orbit-value");
      const modeLabel = root.querySelector("[data-mode-label]");
      const buttons = [...root.querySelectorAll("[data-mode]")];
      const phaseValues = [...root.querySelectorAll(".phase-percent")];
      const phaseMeters = [...root.querySelectorAll("[data-progress-estimated]")];

      function setMode(mode) {
        const estimated = mode === "estimated";
        buttons.forEach((button) => {
          button.setAttribute("aria-pressed", String(button.dataset.mode === mode));
        });
        orbitValue.textContent = estimated ? orbitValue.dataset.estimated : orbitValue.dataset.accepted;
        modeLabel.textContent = estimated ? "weighted estimate" : "producer accepted";
        orbit.style.setProperty("--progress", estimated ? orbitValue.dataset.estimated : orbitValue.dataset.accepted);
        orbit.setAttribute("aria-label", orbitValue.textContent + " " + modeLabel.textContent + " progress");
        phaseValues.forEach((value) => {
          value.textContent = estimated ? value.dataset.estimated : value.dataset.accepted;
        });
        phaseMeters.forEach((meter) => {
          meter.style.width = (estimated ? meter.dataset.progressEstimated : meter.dataset.progressAccepted) + "%";
        });
      }

      buttons.forEach((button) => {
        button.addEventListener("click", () => setMode(button.dataset.mode));
      });
    })();
  </script>
</body>
</html>
`;
}

export async function loadProgressModel(repositoryRoot) {
  const specificationPath = path.join(
    repositoryRoot,
    "docs",
    "Script-to-Timeline Product Spec - Fable Rev2.md",
  );
  const progressPath = path.join(
    repositoryRoot,
    "docs",
    "IMPLEMENTATION_PROGRESS.md",
  );
  const [specification, progressDocument] = await Promise.all([
    readFile(specificationPath, "utf8"),
    readFile(progressPath, "utf8"),
  ]);

  return buildProgressModel(
    parseRoadmap(specification),
    parseProgressTracker(progressDocument),
  );
}

export async function writeDashboard(repositoryRoot, outputPath) {
  const model = await loadProgressModel(repositoryRoot);
  const html = renderDashboard(model);
  await mkdir(path.dirname(outputPath), { recursive: true });
  await writeFile(outputPath, html, "utf8");
  return model;
}

export function terminalSummary(model, outputPath) {
  return [
    "VERA project progress",
    `  ${formatPercent(model.estimatedPercent)} estimated (${model.estimatedUnits.toFixed(1)} of ${model.totalSlices} slice-equivalents)`,
    `  ${formatPercent(model.acceptedPercent)} accepted (${model.acceptedSlices} of ${model.totalSlices} slices)`,
    `  ${model.acceptedPhases} of ${model.totalPhases} phase gates complete`,
    `  Dashboard: ${outputPath}`,
  ].join("\n");
}
