-- One named menu action. The injected probe supplies project/source guards.
local bundle = "com.blackmagic-design.DaVinciResolve"
local project = "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
local menu = {"Workspace", "Workflow Integrations", "VERA Issue 141 Observation"}

local function target()
    assert(hs.accessibilityState(), "Hammerspoon Accessibility permission is required")
    local app = hs.application.get(bundle)
    assert(app and app:bundleID() == bundle, "Resolve must already be running")
    local window = app:mainWindow()
    assert(window and window:title() == project, "Exact synthetic project must be open")
    return app
end

local function check()
    local app = target()
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

local function run()
    local app = target()
    assert(app:activate(), "Could not focus Resolve")
    hs.timer.usleep(1000000)
    local front = hs.application.frontmostApplication()
    assert(front and front:bundleID() == bundle, "Resolve is not frontmost; stop")
    local window = app:mainWindow()
    local observedTitle = window and window:title() or "<no main window>"
    assert(observedTitle == project, "Project changed; stop: " .. observedTitle)
    local item = app:findMenuItem(menu)
    assert(item and item.enabled, "The exact observation menu item is unavailable")
    assert(app:selectMenuItem(menu), "Menu selection failed; do not retry automatically")
    return "Observation menu selected once; verify the new injected result before any next action"
end

return {check = check, run = run}
