// Read-only standalone diagnostic run by the engineering preflight on the Mac.
// This file is NOT part of the signed production helper executable, and must
// never be used as authority to focus a Producer project.
import AppKit
import ApplicationServices
import Foundation

let apps = NSRunningApplication.runningApplications(
    withBundleIdentifier: "com.blackmagic-design.DaVinciResolve"
)
let front = NSWorkspace.shared.frontmostApplication
print("resolveCount=\(apps.count) frontmostPID=\(front?.processIdentifier ?? -1)")
for app in apps {
    let ax = AXUIElementCreateApplication(app.processIdentifier)
    var value: CFTypeRef?
    let status = AXUIElementCopyAttributeValue(ax, kAXWindowsAttribute as CFString, &value)
    if status != .success {
        print("pid=\(app.processIdentifier) AXWindows=UNKNOWN error=\(status.rawValue)")
        continue
    }
    guard let windows = value as? [AXUIElement] else {
        print("pid=\(app.processIdentifier) AXWindows=UNKNOWN type")
        continue
    }
    print("pid=\(app.processIdentifier) count=\(windows.count)")
    for window in windows {
        var titleValue: CFTypeRef?
        var mainValue: CFTypeRef?
        var modalValue: CFTypeRef?
        let titleStatus = AXUIElementCopyAttributeValue(
            window, kAXTitleAttribute as CFString, &titleValue)
        let mainStatus = AXUIElementCopyAttributeValue(
            window, kAXMainAttribute as CFString, &mainValue)
        let modalStatus = AXUIElementCopyAttributeValue(
            window, kAXModalAttribute as CFString, &modalValue)
        let title = titleStatus == .success ? (titleValue as? String ?? "UNKNOWN") : "UNKNOWN"
        let main = mainStatus == .success ? String(describing: mainValue!) : "UNKNOWN"
        let modal = modalStatus == .success ? String(describing: modalValue!) : "UNKNOWN"
        print("title=\(String(reflecting: title)) main=\(main) modal=\(modal)")
        var attributes: CFArray?
        let attrsStatus = AXUIElementCopyAttributeNames(window, &attributes)
        let attrs = attrsStatus == .success ? (attributes as? [String] ?? []) : []
        print("sheetAttributePresent=\(attrs.contains("AXSheets")) childrenAttributePresent=\(attrs.contains("AXChildren"))")
        var childrenValue: CFTypeRef?
        let childStatus = AXUIElementCopyAttributeValue(window, kAXChildrenAttribute as CFString, &childrenValue)
        if childStatus == .success, let children = childrenValue as? [AXUIElement] {
            print("directChildren=\(children.count)")
            for child in children.prefix(20) {
                var roleValue: CFTypeRef?
                let roleStatus = AXUIElementCopyAttributeValue(child, kAXRoleAttribute as CFString, &roleValue)
                let role = roleStatus == .success ? (roleValue as? String ?? "UNKNOWN") : "UNKNOWN"
                print("childRole=\(role)")
            }
        } else { print("directChildren=UNKNOWN status=\(childStatus.rawValue)") }
    }
}
