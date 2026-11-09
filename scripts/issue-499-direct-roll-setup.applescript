-- Selection-only setup for one signed synthetic VERA #499 target.
-- Fixed context setters only, no Roll, Nudge, Resize, Ripple or Save.
on run argv
  if (count of argv) is not 2 then error "PID/name required"
  set expectedPid to (item 1 of argv) as integer
  set targetName to item 2 of argv
  if expectedPid <= 0 then error "invalid PID"
  if targetName is not "VERA Delivery 75ba39c0-4c56-4d85-ac88-58f0092163a8 c191e694fc19" then error "wrong target"
  tell application "System Events"
    set matches to every application process whose unix id is expectedPid
    if (count of matches) is not 1 then error "PID not unique"
    tell item 1 of matches
      if bundle identifier is not "com.blackmagic-design.DaVinciResolve" then error "bundle changed"
      if not frontmost then error "Resolve not frontmost"
      if (count of windows) is not 1 then error "unexpected windows"
      if name of front window is not targetName then error "wrong main window"
      if (value of attribute "AXMain" of front window) is not true then error "not main window"
      if exists sheet 1 of front window then error "modal present"
      set editMenu to menu "Edit" of menu bar 1
      set deselectItem to menu item "Deselect All" of editMenu
      if enabled of deselectItem then click deselectItem
      set tracksMenu to menu 1 of menu item "Auto Select" of menu "Timeline" of menu bar 1
      if not (enabled of menu item "Auto Deselect All Tracks" of tracksMenu) then error "absolute track reset disabled"
      click menu item "Auto Deselect All Tracks" of tracksMenu
      set tracksMenu to menu 1 of menu item "Auto Select" of menu "Timeline" of menu bar 1
      if not (enabled of menu item "Auto Select/Deselect V1" of tracksMenu) then error "V1 selection disabled"
      click menu item "Auto Select/Deselect V1" of tracksMenu
      set normalMode to menu item "Normal Edit Mode" of menu "Trim" of menu bar 1
      if not (enabled of normalMode) then error "normal edit mode unavailable"
      click normalMode
      if (count of windows) is not 1 then error "window changed after selection"
      if name of front window is not targetName then error "selection targeted wrong window"
      if exists sheet 1 of front window then error "modal after selection"
    end tell
  end tell
end run
