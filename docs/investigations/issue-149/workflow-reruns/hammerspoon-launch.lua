-- One named menu action. The injected probe supplies project/source guards.
local bundle = "com.blackmagic-design.DaVinciResolve"
local project = "VERA Issue 149 Workflow Reruns 20261002-kit-01"
local menu = {"Workspace", "Workflow Integrations", "VERA Issue 149 Workflow Reruns"}

local function target(initial)
    assert(hs.accessibilityState(), "Hammerspoon Accessibility permission is required")
    local app = hs.application.get(bundle)
    assert(app and app:bundleID() == bundle, "Resolve must already be running")
    local window = app:mainWindow()
    local matches = window and window:title() == project
    if initial then
        for _, candidate in ipairs(app:allWindows()) do
            if candidate:title() == "Project Manager" then matches = true end
        end
    end
    assert(matches, "Exact new synthetic project (or initial Project Manager) must be open")
    return app
end

local function check(initial)
    local app = target(initial)
    local item = app:findMenuItem(menu)
    local window = app:mainWindow()
    return hs.json.encode({
        bundleId = app:bundleID(),
        menuFound = item ~= nil,
        menuEnabled = item ~= nil and item.enabled == true,
        windowTitle = window and window:title() or "",
        triggered = false,
    })
end

local function run(initial)
    local app = target(initial)
    assert(app:activate(), "Could not focus Resolve")
    hs.timer.usleep(1000000)
    local front = hs.application.frontmostApplication()
    assert(front and front:bundleID() == bundle, "Resolve is not frontmost; stop")
    local window = app:mainWindow()
    local observedTitle = window and window:title() or "<no main window>"
    if initial then
        target(true)
    else
        assert(observedTitle == project, "Project changed; stop: " .. observedTitle)
    end
    local item = app:findMenuItem(menu)
    assert(item and item.enabled, "The exact observation menu item is unavailable")
    assert(app:selectMenuItem(menu), "Menu selection failed; do not retry automatically")
    return "Observation menu selected once; verify the new injected result before any next action"
end

return {check = check, run = run}
