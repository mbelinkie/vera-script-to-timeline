-- Approved named commands only; native pre/post guards are staged separately.
local bundle = "com.blackmagic-design.DaVinciResolve"
local project = "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
local menus = {
    ["edit-page"] = {"Workspace", "Switch to Page", "Edit"},
    ["step-forward"] = {"Playback", "Step One", "Frame Forward"},
    ["timeline-start"] = {"Playback", "Go To", "Timeline Start"},
    ["save-project"] = {"File", "Save Project"},
    ["focus-timeline"] = {"Workspace", "Active Panel Selection", "Timeline"},
    ["auto-none"] = {"Timeline", "Auto Select", "Auto Deselect All Tracks"},
    ["auto-v1"] = {"Timeline", "Auto Select", "Auto Select/Deselect V1"},
    ["auto-a1"] = {"Timeline", "Auto Select", "Auto Select/Deselect A1"},
    ["auto-a3"] = {"Timeline", "Auto Select", "Auto Select/Deselect A3"},
    deselect = {"Edit", "Deselect All"},
    select = {"Trim", "Select Nearest", "Clip/Gap"},
    split = {"Timeline", "Split Clips"},
    ["trim-end"] = {"Trim", "Resize", "End to Playhead"},
    ["nudge-right"] = {"Trim", "Nudge", "One Frame Right"},
    copy = {"Edit", "Copy"},
    paste = {"Edit", "Paste"},
}

local function target(action)
    local menu = assert(menus[action], "Unknown editorial action")
    assert(hs.accessibilityState(), "Hammerspoon Accessibility permission required")
    local app = assert(hs.application.get(bundle), "Resolve must be running")
    assert(app:bundleID() == bundle, "Resolve identity differs")
    local window = app:mainWindow()
    assert(window and window:title() == project, "Exact synthetic project required")
    return app, menu
end

local function check(action)
    local app, menu = target(action)
    local item = app:findMenuItem(menu)
    return hs.json.encode({action = action, menu = menu, found = item ~= nil,
        enabled = item ~= nil and item.enabled == true, triggered = false})
end

local function run(action)
    local app, menu = target(action)
    assert(app:activate(), "Resolve focus refused")
    hs.timer.usleep(1000000)
    local front = hs.application.frontmostApplication()
    assert(front and front:bundleID() == bundle, "Resolve must remain frontmost")
    target(action)
    local item = app:findMenuItem(menu)
    assert(item and item.enabled, "Exact named command unavailable")
    assert(app:selectMenuItem(menu), "Named command failed; do not retry")
    return "Named editorial command selected once; verify injected postflight before continuing"
end

return {check = check, run = run}
