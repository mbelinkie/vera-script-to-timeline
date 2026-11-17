import { renderRows } from "./view.js";

const element = (id) => document.getElementById(id);
const home = element("home-view");
const homeStatus = element("home-status");
const newForm = element("new-project-form");
const newTitle = element("new-project-title");
const openForm = element("open-project-form");
const openLink = element("open-script-link");
const authoring = element("authoring-view");
const projectTitle = element("project-title");
const saveStatus = element("save-status");
const retrySave = element("retry-save");
const openSaved = element("conflict-open-saved");

const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/iu;
let project;
let pendingName;
let pendingCreate;
let saveTimer;
let saving = false;
let opening = false;
let conflicted = false;

async function api(path, method = "GET", data) {
  const headers = { "X-VERA-Authoring": "1" };
  if (data) headers["Content-Type"] = "application/json";
  const response = await fetch(`/authoring/projects${path}`, {
    method, headers, body: data && JSON.stringify(data),
    signal: AbortSignal.timeout(12_000),
  });
  if (!response.ok) throw new ApiError(response.status);
  return await response.json();
}

class ApiError extends Error {
  constructor(status) {
    super("Project request failed.");
    this.status = status;
  }
}

function viewPreference(id, property, defaultValue) {
  const input = element(id);
  const key = `vera.authoring.${id}`;
  try { input.value = localStorage.getItem(key) ?? String(defaultValue); } catch {
    input.value = String(defaultValue);
  }
  const update = () => {
    const percent = Number(input.value);
    document.documentElement.style.setProperty(property, String(percent / 100));
    if (id === "thumbnail-size") document.documentElement.dataset.thumbnailScale = String(percent);
    input.setAttribute("aria-valuetext", `${percent}%`);
    const output = authoring.querySelector(`output[for="${id}"]`);
    if (output) output.value = `${percent}%`;
  };
  input.addEventListener("input", () => {
    update();
    try { localStorage.setItem(key, input.value); } catch { /* Current tab still scales. */ }
  });
  update();
}

viewPreference("authoring-size", "--authoring-zoom", 100);
viewPreference("thumbnail-size", "--thumbnail-scale", 22);

function projectLink(projectId) {
  return `/?project=${projectId}`;
}

function readProjectId(text) {
  let candidate = text.trim();
  if (!uuid.test(candidate)) {
    try {
      const url = new URL(candidate, location.origin);
      candidate = url.origin === location.origin && url.pathname === "/" ?
        url.searchParams.get("project") ?? "" : "";
    } catch { return null; }
  }
  return uuid.test(candidate) ? candidate.toLowerCase() : null;
}

async function showScript(projectId) {
  const [{ project: savedProject }, savedScript] = await Promise.all([
    api(`/${projectId}`), api(`/${projectId}/document`),
  ]);
  renderRows(element("script-rows"), savedScript.document);
  project = savedProject;
  element("script-title").textContent = savedScript.document.title;
  document.title = `${savedScript.document.title} · VERA Authoring`;
  projectTitle.value = project.title;
  openSaved.href = projectLink(projectId);
  history.replaceState(null, "", projectLink(projectId));
  home.hidden = true;
  authoring.hidden = false;
  setSaveStatus("Saved");
  element("script-title").focus();
}

function showOpenError(error) {
  homeStatus.textContent = error instanceof ApiError && [403, 404].includes(error.status) ?
    "Couldn’t open that script. Check the link or project ID." :
    "Couldn’t load the script. Check that VERA Authoring is running and try again.";
}

async function openScript(projectId) {
  if (opening) return;
  opening = true;
  homeStatus.textContent = "Opening script…";
  try { await showScript(projectId); } catch (error) { showOpenError(error); }
  finally { opening = false; }
}

function newScript(title) {
  const projectId = crypto.randomUUID();
  return {
    projectId, title, clientRequestId: crypto.randomUUID(),
    document: {
      schemaVersion: "script-document/v2", id: crypto.randomUUID(), projectId, title,
      activeDraft: { blocks: [], supportingItems: [] }, ideaOutline: [], extras: [],
      liveHeadSequence: 0, liveStateVector: "", liveContentHash: `sha256:${"0".repeat(64)}`,
    },
  };
}

newForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (opening) return;
  const title = newTitle.value.trim();
  if (!title) {
    homeStatus.textContent = "Enter a name for the new script.";
    return;
  }
  opening = true;
  newTitle.readOnly = true;
  homeStatus.textContent = "Saving new script…";
  if (pendingCreate?.title !== title) pendingCreate = newScript(title);
  let created = false;
  try {
    await api("", "POST", pendingCreate);
    created = true;
    await showScript(pendingCreate.projectId);
    pendingCreate = undefined;
  } catch {
    homeStatus.textContent = created ?
      "Script saved. Couldn’t open it. Try Start script again." :
      "Couldn’t save the new script. Its name is still here. Try Start script again.";
  } finally {
    newTitle.readOnly = false;
    opening = false;
  }
});

openForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const id = readProjectId(openLink.value);
  if (id) void openScript(id);
  else homeStatus.textContent = "Enter a saved script link or project ID.";
});

function setSaveStatus(message, action) {
  saveStatus.textContent = message;
  retrySave.hidden = action !== "retry";
  openSaved.hidden = action !== "conflict";
}

async function saveName() {
  clearTimeout(saveTimer);
  if (!project || saving || conflicted) return;
  const title = projectTitle.value.trim();
  if (!pendingName) {
    if (!title) {
      setSaveStatus("Project name is required. Your change is unsaved.");
      return;
    }
    if (title === project.title) {
      setSaveStatus("Saved");
      return;
    }
    pendingName = {
      title, expectedProjectVersion: project.projectVersion, clientMutationId: crypto.randomUUID(),
    };
  }
  saving = true;
  setSaveStatus("Saving…");
  try {
    ({ project } = await api(`/${project.projectId}`, "PATCH", pendingName));
    pendingName = undefined;
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      conflicted = true;
      setSaveStatus("A newer project name was saved elsewhere. Your unsaved name is still here.", "conflict");
    } else {
      setSaveStatus("Couldn’t save the project name. Your unsaved name is still here.", "retry");
    }
    return;
  } finally { saving = false; }
  // Replay the same receipt after a failed request. Any newer typing is saved
  // only after that request confirms the next project version.
  if (projectTitle.value.trim() !== project.title) void saveName();
  else setSaveStatus("Saved");
}

projectTitle.addEventListener("input", () => {
  if (saving || conflicted || pendingName) return;
  clearTimeout(saveTimer);
  setSaveStatus("Unsaved changes");
  saveTimer = setTimeout(() => { void saveName(); }, 350);
});
projectTitle.addEventListener("blur", () => {
  if (!pendingName) void saveName();
});
projectTitle.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    projectTitle.blur();
  }
});
retrySave.addEventListener("click", () => { void saveName(); });

function protectDraft(event) {
  if (pendingCreate || pendingName || (project && projectTitle.value.trim() !== project.title)) {
    event.preventDefault();
    event.returnValue = true;
  }
}

window.addEventListener("beforeunload", protectDraft);
const initialProject = new URLSearchParams(location.search).get("project");
if (initialProject !== null) {
  openLink.value = initialProject;
  if (uuid.test(initialProject)) void openScript(initialProject.toLowerCase());
  else homeStatus.textContent = "Enter a saved script link or project ID.";
}
