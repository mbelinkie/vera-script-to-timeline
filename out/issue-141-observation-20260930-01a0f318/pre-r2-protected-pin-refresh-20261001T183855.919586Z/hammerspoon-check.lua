-- Run with the bundled hs CLI, passing hammerspoon-launch.lua after this file.
local source = assert(_cli.args[2], "Pass the launch Lua file path")
local calls, mode = {}, "ok"
local bundle = "com.blackmagic-design.DaVinciResolve"
local app = {}
function app:bundleID() return mode == "wrong-app" and "other" or bundle end
function app:mainWindow()
    if mode == "activation-window-missing" and #calls > 0 then return nil end
    return {title = function()
        return mode == "wrong-project" and "other" or "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
    end}
end
function app:activate() table.insert(calls, "activate"); return true end
function app:findMenuItem(path)
    assert(table.concat(path, "/") == "Workspace/Workflow Integrations/VERA Issue 141 Observation")
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
local action = assert(loadfile(source, "t", {hs = fake, assert = assert}))()
assert(action.check().triggered == false and #calls == 0)
action.run()
assert(table.concat(calls, ",") == "activate,select")
for _, failure in ipairs({"wrong-app", "wrong-project", "no-access", "lost-focus", "disabled", "activation-window-missing"}) do
    mode, calls = failure, {}
    assert(not pcall(action.run), failure .. " must refuse")
    for _, call in ipairs(calls) do assert(call ~= "select", "Must refuse before click") end
end
return "Named-action success and pre-click refusals passed; no real Resolve interaction"
