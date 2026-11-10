import AppKit
import ApplicationServices
import Carbon
import Foundation
import CoreFoundation

// Phase 3 deliberately supports observation and the bounded, previously
// measured legacy foreground route ONLY. There is no AXPress in this file.
// The Phase 4 Roll actor must be implemented and tested independently.
enum TargetInspection {
    private static let resolveBundle = "com.blackmagic-design.DaVinciResolve"
    private static let rollPath = ["Trim", "Roll", "Start to Playhead"]
    private static let observationQueue = DispatchQueue(
        label: "org.vera.gui-helper.ax-observation", qos: .userInitiated
    )

    static func requireAccessibility(
        trusted: () -> Bool = { AXIsProcessTrusted() }
    ) throws {
        guard trusted() else {
            throw FocusFailure.refused("helper process lacks its own Accessibility grant")
        }
    }

    private static func attribute(_ element: AXUIElement, _ key: String) throws -> CFTypeRef {
        var value: CFTypeRef?
        let status = AXUIElementCopyAttributeValue(element, key as CFString, &value)
        guard status == .success, let value else {
            throw FocusFailure.refused("AX attribute \(key) unavailable: \(status.rawValue)")
        }
        return value
    }

    private static func elements(_ element: AXUIElement, _ key: String) throws -> [AXUIElement] {
        let value = try attribute(element, key)
        guard let items = value as? [AXUIElement] else {
            throw FocusFailure.refused("AX \(key) is not an element array")
        }
        return items
    }

    private static func bool(_ element: AXUIElement, _ key: String) throws -> Bool {
        let value = try attribute(element, key)
        guard CFGetTypeID(value) == CFBooleanGetTypeID() else {
            throw FocusFailure.refused("AX \(key) has unexpected type")
        }
        return CFBooleanGetValue((value as! CFBoolean))
    }

    private static func title(_ element: AXUIElement) throws -> String {
        let value = try attribute(element, kAXTitleAttribute as String)
        guard let text = value as? String else {
            throw FocusFailure.refused("AX title unavailable")
        }
        return text
    }

    private static func exactChild(_ parent: AXUIElement, _ name: String) throws -> AXUIElement {
        let found = try elements(parent, kAXChildrenAttribute as String)
            .filter { (try? title($0)) == name }
        guard found.count == 1 else {
            throw FocusFailure.refused("AX menu path has missing/ambiguous element: \(name)")
        }
        return found[0]
    }

    private static func rollEnabled(_ app: AXUIElement) throws -> Bool {
        let rawBar = try attribute(app, kAXMenuBarAttribute as String)
        guard CFGetTypeID(rawBar) == AXUIElementGetTypeID() else {
            throw FocusFailure.refused("AX menu bar element has wrong type")
        }
        let bar = rawBar as! AXUIElement
        var current = bar
        for name in rollPath {
            let item = try exactChild(current, name)
            if name == rollPath.last {
                return try bool(item, kAXEnabledAttribute as String)
            }
            let children = try elements(item, kAXChildrenAttribute as String)
            guard children.count == 1 else {
                throw FocusFailure.refused("AX menu hierarchy is missing or ambiguous")
            }
            current = children[0]
        }
        throw FocusFailure.refused("Roll leaf unavailable")
    }

    private static func noSheet(_ window: AXUIElement) throws -> Bool {
        var raw: CFTypeRef?
        let result = AXUIElementCopyAttributeValue(window, "AXSheets" as CFString, &raw)
        if result == .success {
            guard let sheets = raw as? [AXUIElement] else {
                throw FocusFailure.refused("AXSheets has unexpected type")
            }
            return sheets.isEmpty
        }
        guard result == .attributeUnsupported else {
            throw FocusFailure.refused("AXSheets state unavailable: \(result.rawValue)")
        }
        // Studio 21.1.1 Qt exposes a single top-level AXWindow with
        // AXModal=false but does not implement AXSheets. Sheets attached to
        // that top-level window, if present, have a direct AXSheet/AXDialog
        // child. Read the direct children (verified live on this Mac) and
        // reject any sheet/dialog/window role, missing role or oversized list.
        // Do not infer safe state merely from unsupported AXSheets.
        let children = try elements(window, kAXChildrenAttribute as String)
        guard children.count <= 128 else {
            throw FocusFailure.refused("AX child hierarchy exceeded safe inspection bound")
        }
        for child in children {
            let roleValue = try attribute(child, kAXRoleAttribute as String)
            guard let role = roleValue as? String else {
                throw FocusFailure.refused("AX child role not inspectable")
            }
            if role == "AXSheet" || role == "AXDialog" || role == "AXWindow" {
                return false
            }
        }
        return true
    }

    private static func authenticatedWindow(_ request: FocusRequest) throws -> (AXUIElement, AXUIElement) {
        try requireAccessibility()
        guard let process = NSRunningApplication(processIdentifier: request.resolvePid),
              !process.isTerminated,
              process.bundleIdentifier == resolveBundle else {
            throw FocusFailure.refused("Resolve PID/bundle mismatch or process replaced")
        }
        let app = AXUIElementCreateApplication(request.resolvePid)
        // We refuse if Resolve has multiple windows, including a deceptive
        // same-title duplicate. The case must have one exact disposable window.
        let windows = try elements(app, kAXWindowsAttribute as String)
        guard windows.count == 1 else {
            throw FocusFailure.refused("expected exactly one Resolve window")
        }
        let window = windows[0]
        var windowPID: pid_t = 0
        guard AXUIElementGetPid(window, &windowPID) == .success,
              windowPID == request.resolvePid,
              try title(window) == request.windowName else {
            throw FocusFailure.refused("Resolve window identity mismatch")
        }
        guard let role = try attribute(window, kAXRoleAttribute as String) as? String,
              role == (kAXWindowRole as String) else {
            throw FocusFailure.refused("target is not an AX window")
        }
        // Qt may omit AXModal or AXSheets. UNKNOWN is not evidence of
        // absence: refuse rather than assume a safe editor surface.
        guard try !bool(window, kAXModalAttribute as String),
              try noSheet(window) else {
            throw FocusFailure.refused("modal or sheet may cover exact Resolve window")
        }
        return (app, window)
    }

    static func inspect(_ request: FocusRequest) throws -> FocusObservation {
        let (app, window) = try authenticatedWindow(request)
        // Re-evaluate PID/bundle and modal state immediately before reporting
        // any readiness, not merely when finding the original handle.
        guard let process = NSRunningApplication(processIdentifier: request.resolvePid),
              !process.isTerminated, process.bundleIdentifier == resolveBundle,
              try !bool(window, kAXModalAttribute as String),
              try noSheet(window) else {
            throw FocusFailure.refused("target changed or acquired modal/sheet")
        }
        let main = try bool(window, kAXMainAttribute as String)
        let foreground = NSWorkspace.shared.frontmostApplication?.processIdentifier == request.resolvePid
        let enabled = try rollEnabled(app)
        return FocusObservation(
            pid: request.resolvePid, bundle: resolveBundle,
            title: request.windowName, main: main, foreground: foreground,
            noModalOrSheet: true, rollEnabled: enabled
        )
    }

    static func perform(
        _ request: FocusRequest,
        completion: @escaping (Result<FocusObservation, Error>) -> Void
    ) {
        observationQueue.async {
            do {
                if request.operation == "inspect" {
                    let observation = try inspect(request)
                    guard observation.foreground && observation.main && observation.rollEnabled else {
                        throw FocusFailure.refused("inspect requires foreground/main and enabled Roll")
                    }
                    DispatchQueue.main.async { completion(.success(observation)) }
                    return
                }
                guard request.operation == "focus" else {
                    throw FocusFailure.refused("unsupported focus operation")
                }
                let (_, window) = try authenticatedWindow(request)
                let setResult = AXUIElementSetAttributeValue(
                    window, kAXMainAttribute as CFString, kCFBooleanTrue
                )
                guard setResult == .success else {
                    throw FocusFailure.refused("AXMain=true refused: \(setResult.rawValue)")
                }
                // The narrow C bridge invokes exactly the demonstrated
                // Hammerspoon legacy activation route; never replace it with
                // a different activation API without requalification.
                guard VERASetFrontProcessFrontWindowOnly(request.resolvePid) == 0 else {
                    throw FocusFailure.refused("legacy SetFrontProcessWithOptions refused")
                }
                DispatchQueue.main.async {
                    watchForeground(
                        request, streak: 0,
                        deadline: Date().addingTimeInterval(2),
                        completion: completion
                    )
                }
            } catch {
                DispatchQueue.main.async { completion(.failure(error)) }
            }
        }
    }

    private static func watchForeground(
        _ request: FocusRequest,
        streak: Int,
        deadline: Date,
        completion: @escaping (Result<FocusObservation, Error>) -> Void
    ) {
        // Re-authenticate everything each observation (process replacement,
        // window, modal/sheet, main, menu and foreground).
        guard Date() < deadline else {
            completion(.failure(FocusFailure.refused("bounded focus/readiness observation timed out")))
            return
        }
        observationQueue.async {
            let current = try? inspect(request)
            DispatchQueue.main.async {
                let matching = current != nil && current!.foreground && current!.main && current!.rollEnabled
                let nextStreak = matching ? streak + 1 : 0
                guard Date() < deadline else {
                    completion(.failure(FocusFailure.refused("bounded focus/readiness observation timed out")))
                    return
                }
                if matching && nextStreak >= 2, let observation = current {
                    completion(.success(observation))
                    return
                }
                DispatchQueue.main.asyncAfter(deadline: .now() + .milliseconds(100)) {
                    watchForeground(request, streak: nextStreak, deadline: deadline, completion: completion)
                }
            }
        }
    }
}
