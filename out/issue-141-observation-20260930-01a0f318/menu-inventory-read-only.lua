local app = assert(hs.application.get("com.blackmagic-design.DaVinciResolve"))
assert(hs.accessibilityState())
assert(app:mainWindow() and app:mainWindow():title() == "VERA Issue 141 Synthetic Probe 20260930-01a0f318")
local tree=assert(app:getMenuItems())
local results={}
local function visit(rows,path)
 for _,row in ipairs(rows) do
  local nextpath={table.unpack(path)}
  if row.AXTitle and row.AXTitle~="" then table.insert(nextpath,row.AXTitle) end
  if row.AXTitle and (nextpath[1] == "Trim" or row.AXTitle:lower():find("blade") or row.AXTitle:lower():find("split") or row.AXTitle:lower():find("trim") or row.AXTitle:lower():find("copy") or row.AXTitle:lower():find("paste") or row.AXTitle:lower():find("move") or row.AXTitle:lower():find("select")) then
   table.insert(results,{path=nextpath,enabled=row.AXEnabled,ticked=row.AXMenuItemMarkChar,shortcut=row.AXMenuItemCmdChar,modifiers=row.AXMenuItemCmdModifiers})
  end
  if row.AXChildren then visit(row.AXChildren,nextpath) elseif row.AXRole == nil and type(row) == "table" then visit(row,path) end
 end
end
visit(tree,{})
return hs.json.encode({at=hs.timer.secondsSinceEpoch(),triggered=false,items=results})
