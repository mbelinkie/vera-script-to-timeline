// #500: observational, read-only macOS probe. Run only via the Python reporter.
// No AX action, AppleEvent dispatch, menu click, keystroke, activation, or TCC prompt.
import ApplicationServices
import Carbon
import Cocoa
import CoreGraphics
import Foundation

let expectedBundle = "com.blackmagic-design.DaVinciResolve"
let automationTarget = "com.apple.systemevents"

func read(_ element: AXUIElement, _ name: String) -> CFTypeRef? {
    var result: CFTypeRef?
    let status = AXUIElementCopyAttributeValue(element, name as CFString, &result)
    return status == .success ? result : nil
}

func string(_ value: CFTypeRef?) -> String? {
    guard let value else { return nil }
    return value as? String
}

func boolean(_ value: CFTypeRef?) -> Bool? {
    guard let value else { return nil }
    return value as? Bool
}

func element(_ value: CFTypeRef?) -> AXUIElement? {
    guard let value, CFGetTypeID(value) == AXUIElementGetTypeID() else { return nil }
    return (value as! AXUIElement)
}

func children(_ parent: AXUIElement) -> [AXUIElement]? {
    guard let value = read(parent, kAXChildrenAttribute as String) else { return nil }
    return value as? [AXUIElement]
}

func findNamed(_ parent: AXUIElement, name: String, remainingDepth: Int) -> AXUIElement? {
    if string(read(parent, kAXTitleAttribute as String)) == name { return parent }
    guard remainingDepth > 0, let kids = children(parent) else { return nil }
    for child in kids.prefix(100) {
        if let found = findNamed(child, name: name, remainingDepth: remainingDepth - 1) {
            return found
        }
    }
    return nil
}

func namedMenuItem(_ app: AXUIElement, _ path: [String]) -> AXUIElement? {
    guard let root = element(read(app, kAXMenuBarAttribute as String)) else { return nil }
    var current = root
    for part in path {
        guard let next = findNamed(current, name: part, remainingDepth: 3) else { return nil }
        current = next
    }
    return current
}

func menuObservation(_ app: AXUIElement, _ path: [String]) -> [String: Any] {
    guard let item = namedMenuItem(app, path) else {
        return ["path": path, "found": false, "enabled": NSNull(),
                "mark": NSNull(), "cmdChar": NSNull(), "cmdModifiers": NSNull(),
                "reason": "menu_path_not_observable"]
    }
    return [
        "path": path, "found": true,
        "enabled": boolean(read(item, kAXEnabledAttribute as String)) as Any? ?? NSNull(),
        "mark": string(read(item, "AXMenuItemMarkChar")) as Any? ?? NSNull(),
        "cmdChar": string(read(item, "AXMenuItemCmdChar")) as Any? ?? NSNull(),
        "cmdModifiers": read(item, "AXMenuItemCmdModifiers") as Any? ?? NSNull(),
    ]
}

// This function uses the *actual* AEDesc* C ABI. It never sends an AppleEvent.
// In particular askUserIfNeeded=false cannot create an Automation permission prompt.
func queryAutomationNoPrompt(_ targetBundle: String) -> [String: Any] {
    var target = AEDesc()
    let bytes = Array(targetBundle.utf8)
    let createStatus: OSErr = bytes.withUnsafeBytes { (buffer: UnsafeRawBufferPointer) -> OSErr in
        AECreateDesc(typeApplicationBundleID, buffer.baseAddress, buffer.count, &target)
    }
    guard createStatus == noErr else {
        return ["status": NSNull(), "createStatus": createStatus,
                "targetBundleId": targetBundle,
                "promptRequested": false, "abi": "AEDesc*"]
    }
    defer { AEDisposeDesc(&target) }
    let status = AEDeterminePermissionToAutomateTarget(
        &target, typeWildCard, typeWildCard, false
    )
    return ["status": status, "targetBundleId": targetBundle,
            "promptRequested": false, "abi": "AEDesc*"]
}

func run() -> [String: Any] {
    let running = NSRunningApplication.runningApplications(withBundleIdentifier: expectedBundle)
    let foregroundPID = NSWorkspace.shared.frontmostApplication?.processIdentifier
    let apps: [[String: Any]] = running.map { app in
        let bundle = app.bundleURL.flatMap { Bundle(url: $0) }
        return [
            "pid": Int(app.processIdentifier),
            "bundleId": app.bundleIdentifier as Any? ?? NSNull(),
            "name": app.localizedName as Any? ?? NSNull(),
            "executablePath": app.executableURL?.path as Any? ?? NSNull(),
            "version": bundle?.infoDictionary?["CFBundleShortVersionString"] as Any? ?? NSNull(),
            "build": bundle?.infoDictionary?["CFBundleVersion"] as Any? ?? NSNull(),
            "frontmost": app.processIdentifier == foregroundPID,
        ]
    }

    let trusted = AXIsProcessTrustedWithOptions(
        [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: false] as CFDictionary
    )
    var window: [String: Any] = [
        "count": NSNull(), "title": NSNull(), "main": NSNull(),
        "focused": NSNull(), "modalPresent": NSNull(),
        "focusRole": NSNull(), "focusDescription": NSNull(),
        "focusAncestry": [],
    ]
    var menuItems: [String: Any] = [:]

    // Do not query a guessed PID when two Resolve processes are running.
    if running.count == 1 && trusted {
        let appAX = AXUIElementCreateApplication(running[0].processIdentifier)
        let windows = read(appAX, kAXWindowsAttribute as String) as? [AXUIElement]
        window["count"] = windows?.count as Any? ?? NSNull()
        if let windows, windows.count == 1, let first = windows.first {
            window["title"] = string(read(first, kAXTitleAttribute as String)) as Any? ?? NSNull()
            window["main"] = boolean(read(first, kAXMainAttribute as String)) as Any? ?? NSNull()
            window["focused"] = boolean(read(first, kAXFocusedAttribute as String)) as Any? ?? NSNull()
            if let descendants = children(first), descendants.contains(where: {
                string(read($0, kAXRoleAttribute as String)) == "AXSheet"
            }) {
                // Direct-child enumeration can prove a sheet exists, but cannot
                // prove none exists deeper in the AX hierarchy. Leave absent
                // sheets unknown rather than falsely reporting modal-free.
                window["modalPresent"] = true
            }
            if let focused = element(read(appAX, kAXFocusedUIElementAttribute as String)) {
                window["focusRole"] = string(read(focused, kAXRoleAttribute as String)) as Any? ?? NSNull()
                window["focusDescription"] = string(read(focused, kAXRoleDescriptionAttribute as String)) as Any? ?? NSNull()
                var ancestry: [[String: Any]] = []
                var current: AXUIElement? = focused
                for _ in 0..<12 {
                    guard let node = current else { break }
                    ancestry.append([
                        "role": string(read(node, kAXRoleAttribute as String)) as Any? ?? NSNull(),
                        "title": string(read(node, kAXTitleAttribute as String)) as Any? ?? NSNull(),
                        "description": string(read(node, kAXRoleDescriptionAttribute as String)) as Any? ?? NSNull(),
                    ])
                    current = element(read(node, kAXParentAttribute as String))
                }
                window["focusAncestry"] = ancestry
            }
        }

        let paths: [String: [String]] = [
            "page_edit": ["Workspace", "Switch to Page", "Edit"],
            "timeline_focus": ["Workspace", "Active Panel Selection", "Timeline"],
            "auto_none": ["Timeline", "Auto Select", "Auto Deselect All Tracks"],
            "auto_v1": ["Timeline", "Auto Select", "Auto Select/Deselect V1"],
            "trim_roll": ["Trim", "Select Nearest Edit To", "Roll"],
            "nudge_right": ["Trim", "Nudge", "One Frame Right"],
            "save_control": ["File", "Save Project"],
        ]
        for (name, path) in paths {
            menuItems[name] = menuObservation(appAX, path)
        }
    }

    let session = CGSessionCopyCurrentDictionary() as? [String: Any] ?? [:]
    return [
        "schema": 1, "source": "native-swift-ax", "platform": "macOS",
        "bundleId": expectedBundle, "applications": apps,
        // System Events is the Automation destination used by the GUI script.
        "tcc": queryAutomationNoPrompt(automationTarget),
        // Negative/control destination: not substituted for System Events consent.
        "tccControl": queryAutomationNoPrompt(expectedBundle),
        "ax": ["trusted": trusted, "promptRequested": false],
        "window": window,
        "menuItems": menuItems,
        "session": [
            "onConsole": session["kCGSessionOnConsoleKey"] as Any? ?? NSNull(),
            "loginDone": session["kCGSessionLoginDoneKey"] as Any? ?? NSNull(),
        ],
    ]
}

let report = run()
if let encoded = try? JSONSerialization.data(withJSONObject: report, options: [.sortedKeys]),
   let output = String(data: encoded, encoding: .utf8) {
    print(output)
} else {
    fputs("read-only macOS probe could not serialize observations\n", stderr)
    exit(2)
}
