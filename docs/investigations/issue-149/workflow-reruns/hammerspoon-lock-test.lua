-- One named W7 menu action per call. Native state guards stay with the root actor.
local bundle = "com.blackmagic-design.DaVinciResolve"
local project = "VERA Issue 149 Workflow Reruns 20261002-kit-01"
local menus = {
    focusTimeline = {"Workspace", "Active Panel Selection", "Timeline"},
    deselectAll = {"Edit", "Deselect All"},
    selectNearest = {"Trim", "Select Nearest", "Clip/Gap"},
    deleteSelected = {"Edit", "Delete Selected"},
}

local function target(action)
    local menu = assert(menus[action], "Unknown W7 menu action")
    assert(hs.accessibilityState(), "Hammerspoon Accessibility permission is required")
    local app = hs.application.get(bundle)
    assert(app and app:bundleID() == bundle, "Resolve must already be running")
    local window = app:mainWindow()
    assert(window and window:title() == project, "Exact new synthetic project is required")
    return app, menu
end

local function dispatch(action, attestation)
    if action == "deleteSelected" then
        assert(type(attestation) == "table", "Delete Selected requires a lock attestation")
        assert(type(attestation.lockedStateId) == "string" and attestation.lockedStateId ~= "",
            "Delete Selected requires lockedStateId")
        assert(type(attestation.expectedUids) == "table" and #attestation.expectedUids > 0,
            "Delete Selected requires a nonempty expectedUids list")
        for _, uid in ipairs(attestation.expectedUids) do
            assert(type(uid) == "string" and uid ~= "", "Delete Selected expectedUids must be strings")
        end
        assert(type(attestation.lockedProofPath) == "string" and attestation.lockedProofPath ~= "",
            "Delete Selected requires lockedProofPath")
        assert(type(attestation.lockedProofSha256) == "string"
            and #attestation.lockedProofSha256 == 64
            and not string.find(attestation.lockedProofSha256, "[^0-9a-f]"),
            "Delete Selected requires lockedProofSha256")
    end
    local app, menu = target(action)
    assert(app:activate(), "Could not focus Resolve")
    hs.timer.usleep(1000000)
    local front = hs.application.frontmostApplication()
    assert(front and front:bundleID() == bundle, "Resolve is not frontmost; stop")
    local window = app:mainWindow()
    assert(window and window:title() == project, "Project changed; stop")
    local item = app:findMenuItem(menu)
    assert(item and item.enabled == true, "Exact W7 menu item is unavailable")
    assert(app:selectMenuItem(menu), "W7 menu selection failed; do not retry")
    local receipt = {
        action = action,
        menu = menu,
        bundleId = app:bundleID(),
        projectName = project,
        windowTitle = window:title(),
        triggered = true,
    }
    if attestation ~= nil then
        receipt.lockedStateId = attestation.lockedStateId
        receipt.expectedUids = attestation.expectedUids
        receipt.lockedProofPath = attestation.lockedProofPath
        receipt.lockedProofSha256 = attestation.lockedProofSha256
    end
    return hs.json.encode(receipt)
end

local function focusTimeline()
    return dispatch("focusTimeline")
end

local function deselectAll()
    return dispatch("deselectAll")
end

local function selectNearest()
    return dispatch("selectNearest")
end

local function deleteSelected(attestation)
    return dispatch("deleteSelected", attestation)
end

return {
    focusTimeline = focusTimeline,
    deselectAll = deselectAll,
    selectNearest = selectNearest,
    deleteSelected = deleteSelected,
}
