const node = (tag, text, props = {}) => Object.assign(document.createElement(tag), { textContent: text, ...props });
const roles = ["producer", "editor", "viewer"];
const roleName = (role) => role[0].toUpperCase() + role.slice(1);

/** No identity credential is stored here. Capabilities are display hints only. */
export function mountAccountPanel({ root, request, onAccess, onSessionEnded, beforeSignOut }) {
  let mode = "local", csrfToken = "", actorId, projectId, role, membershipVersion, refreshPending = false;
  root.className = "account-panel";
  const status = node("span", "", { role: "status" });
  const member = node("span", "");
  const manage = node("button", "Manage access", { type: "button", hidden: true });
  const login = node("button", "Sign in", { type: "button", hidden: true });
  const logout = node("button", "Sign out", { type: "button", hidden: true });
  const dialog = node("dialog", "", { className: "account-panel__dialog" });
  const heading = node("h2", "Manage access");
  heading.id = "account-access-heading";
  dialog.setAttribute("aria-labelledby", heading.id);
  const note = node("p", "Add an existing member code. A script link grants no access. Research permissions are separate.");
  const feedback = node("p", "", { role: "status" });
  const roster = node("ul", "");
  const form = node("form", "");
  const label = node("label", "Member code");
  const code = node("input", "", { required: true, autocomplete: "off" });
  code.id = "account-member-code"; label.htmlFor = code.id;
  code.pattern = "[a-fA-F0-9]{8}(-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}";
  const choose = () => {
    const select = node("select", "");
    for (const value of roles) select.append(node("option", roleName(value), { value }));
    return select;
  };
  const selected = choose(); selected.value = "viewer"; selected.setAttribute("aria-label", "New member role");
  form.append(label, code, selected, node("button", "Add member", { type: "submit" }));
  const close = node("button", "Close", { type: "button" });
  close.onclick = () => dialog.close();
  dialog.addEventListener("close", () => {
    const active = document.activeElement;
    if (!active || active === document.body || dialog.contains(active)) manage.focus();
  });
  dialog.append(heading, note, feedback, roster, form, close);
  root.append(status, member, manage, login, logout, dialog);

  async function accountRequest(path = "", method = "GET") {
    return await fetch(`/authoring/account${path}`, { method, headers: {
      "X-VERA-Authoring": "1", "X-VERA-CSRF": csrfToken,
    }, signal: AbortSignal.timeout(12_000) });
  }
  async function connect() {
    try {
      const response = await accountRequest();
      if (response.status === 404) { root.hidden = true; return; }
      mode = "account"; root.hidden = false;
      const result = await response.json();
      if (!response.ok) {
        status.textContent = response.status === 401 ? "Signed out" : "Account sign-in unavailable";
        login.hidden = response.status !== 401;
        return;
      }
      csrfToken = result.csrfToken; actorId = result.actorId;
      status.textContent = "Signed in";
      member.textContent = `Member code: ${actorId}`;
      logout.hidden = false;
    } catch { mode = "account"; root.hidden = false; status.textContent = "Account service unavailable"; }
  }
  login.onclick = async () => {
    login.disabled = true;
    try {
      const response = await accountRequest("/sign-in", "POST");
      // The trusted host supplies a bounded same-origin or HTTPS login destination.
      const result = await response.json();
      const destination = new URL(result.url, location.origin);
      if (!response.ok || destination.username || destination.password ||
          (destination.origin !== location.origin && destination.protocol !== "https:")) throw new Error();
      location.assign(destination.href);
    } catch { status.textContent = "Sign-in is unavailable. Try again later."; }
    finally { login.disabled = false; }
  };
  logout.onclick = async () => {
    if (!beforeSignOut()) return;
    try {
      const response = await accountRequest("/sign-out", "POST");
      if (!response.ok) throw new Error();
      csrfToken = ""; onSessionEnded(); location.assign("/");
    } catch { status.textContent = "Couldn’t sign out. Try again."; }
  };
  async function loadMembers() {
    const result = await request(`/${projectId}/members`);
    roster.replaceChildren();
    for (const entry of result.members) {
      const row = node("li", "");
      const select = choose(); select.value = entry.role;
      select.setAttribute("aria-label", `Role for ${entry.actorId}`);
      const save = node("button", "Change role", { type: "button" });
      const remove = node("button", "Remove", { type: "button" });
      const change = async (nextRole) => {
        save.disabled = remove.disabled = true;
        try {
          await request(`/${projectId}/members/${entry.actorId}`, "PATCH", { role: nextRole });
          feedback.textContent = "Access updated.";
          await refresh();
          if (role === "producer") await loadMembers();
        } catch { feedback.textContent = "Access could not be changed. Keep at least one Producer; use a known member code."; }
        finally { save.disabled = remove.disabled = false; }
      };
      save.onclick = () => { void change(select.value); };
      remove.onclick = () => {
        if (window.confirm("Remove this member’s access immediately?")) void change(null);
      };
      row.append(node("code", entry.actorId), select, save, remove); roster.append(row);
    }
  }
  manage.onclick = async () => {
    feedback.textContent = "Loading members…";
    dialog.showModal();
    try { await loadMembers(); feedback.textContent = ""; code.focus(); }
    catch { roster.replaceChildren(); feedback.textContent = "Members are unavailable or you no longer have permission."; }
  };
  form.onsubmit = async (event) => {
    event.preventDefault();
    const button = form.querySelector("button"); button.disabled = true;
    try {
      await request(`/${projectId}/members/${code.value.trim()}`, "PATCH", { role: selected.value });
      code.value = ""; feedback.textContent = "Member added."; await loadMembers();
    } catch { feedback.textContent = "Couldn’t add this member. Ask them for their signed-in member code."; }
    finally { button.disabled = false; }
  };
  async function refresh() {
    if (mode !== "account" || !projectId || refreshPending) return;
    refreshPending = true;
    try {
      const access = await request(`/${projectId}/access`);
      // Never let a changed login adopt the previous actor's pending edits.
      if (access.actorId !== actorId) { onSessionEnded(); return; }
      role = access.role;
      status.textContent = `${roleName(role)}${role === "viewer" ? " · read only" : ""}`;
      manage.hidden = role !== "producer";
      if (manage.hidden && dialog.open) dialog.close();
      const changed = membershipVersion !== undefined && membershipVersion !== access.membershipVersion;
      membershipVersion = access.membershipVersion;
      onAccess({ role, actorId, changed });
    } catch (error) {
      manage.hidden = true;
      if (dialog.open) dialog.close();
      roster.replaceChildren();
      onAccess({ role: null, denied: error.status === 401 || error.status === 403,
        unavailable: error.status !== 401 && error.status !== 403 });
    } finally { refreshPending = false; }
  }
  const timer = setInterval(() => { if (!document.hidden) void refresh(); }, 1000);
  timer.unref?.();
  window.addEventListener("focus", () => { void refresh(); });
  return { connect, refresh, setProject: async (id) => { projectId = id; await refresh(); },
    headers: () => mode === "account" ? { "X-VERA-CSRF": csrfToken } : {},
    accountMode: () => mode === "account" };
}
