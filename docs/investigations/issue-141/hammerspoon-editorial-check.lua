-- Fake-only dispatch check; never calls the real application APIs.
local source = "REPOSITORY/docs/investigations/issue-141/hammerspoon-editorial.lua"
local bundle = "com.blackmagic-design.DaVinciResolve"
local project = "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
local mode, calls, expected, activated = "ok", {}, nil, false
local app = {}
function app:bundleID() return mode == "wrong-app" and "other" or bundle end
function app:mainWindow()
    table.insert(calls, "mainWindow")
    if mode == "missing-window-after-activate" and activated then return nil end
    return {title = function() return mode == "wrong-project" and "other" or project end}
end
function app:activate() activated = true; table.insert(calls, "activate"); return true end
function app:findMenuItem(path)
    assert(table.concat(path, "/") == expected)
    return {enabled = mode ~= "disabled"}
end
function app:selectMenuItem(path)
    self:findMenuItem(path)
    table.insert(calls, "select")
    return true
end
local fake = {
    accessibilityState = function() return mode ~= "no-access" end,
    application = {get = function(id) assert(id == bundle); return app end,
        frontmostApplication = function() if mode == "lost-focus" then return nil end; return app end},
    timer = {usleep = function() end},
    json = {encode = function(value) return value end},
}
local helper = assert(loadfile(source, "t", {hs = fake, assert = assert}))()
local paths = {
    ["edit-page"] = "Workspace/Switch to Page/Edit",
    ["step-forward"] = "Playback/Step One/Frame Forward",
    ["timeline-start"] = "Playback/Go To/Timeline Start",
    ["save-project"] = "File/Save Project",
    ["focus-timeline"] = "Workspace/Active Panel Selection/Timeline",
    ["auto-none"] = "Timeline/Auto Select/Auto Deselect All Tracks",
    ["auto-v1"] = "Timeline/Auto Select/Auto Select/Deselect V1",
    ["auto-a1"] = "Timeline/Auto Select/Auto Select/Deselect A1",
    ["auto-a3"] = "Timeline/Auto Select/Auto Select/Deselect A3",
    deselect = "Edit/Deselect All", select = "Trim/Select Nearest/Clip/Gap",
    split = "Timeline/Split Clips", ["trim-end"] = "Trim/Resize/End to Playhead",
    ["nudge-right"] = "Trim/Nudge/One Frame Right", copy = "Edit/Copy", paste = "Edit/Paste",
}
for action, path in pairs(paths) do
    mode, calls, expected, activated = "ok", {}, path, false
    assert(helper.check(action).triggered == false and table.concat(calls, ",") == "mainWindow")
    calls, activated = {}, false
    helper.run(action)
    assert(table.concat(calls, ",") == "mainWindow,activate,mainWindow,select")
end
for _, failure in ipairs({"wrong-app", "wrong-project", "no-access", "lost-focus", "disabled", "missing-window-after-activate"}) do
    mode, calls, expected, activated = failure, {}, paths.split, false
    assert(not pcall(helper.run, "split"))
    for _, call in ipairs(calls) do assert(call ~= "select") end
end
calls = {}
assert(not pcall(helper.run, "arbitrary") and #calls == 0)
return "Editorial helper fake success/refusals passed; no real Resolve interaction"
