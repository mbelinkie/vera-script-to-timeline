-- ONE literal Trim > Roll > Start to Playhead on exact signed disposable.
-- No Nudge, Resize, Ripple, loop, retry, Save, project picker or navigation.
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
      set rollItem to menu item "Start to Playhead" of menu 1 of menu item "Roll" of menu "Trim" of menu bar 1
      if not (enabled of rollItem) then error "Roll Start to Playhead disabled"
      if unix id is not expectedPid then error "PID changed before one Roll"
      if name of front window is not targetName then error "wrong window before one Roll"
      click rollItem
    end tell
  end tell
end run
