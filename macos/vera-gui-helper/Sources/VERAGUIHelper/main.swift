import AppKit
import Foundation
import ApplicationServices

// Dedicated user Aqua-session LSUIElement application. launchd owns lifecycle;
// Python must NEVER spawn this process and a restart must NEVER resubmit a
// consumed focus request. Roll requests are intentionally unsupported here.
final class HelperApplication: NSObject, NSApplicationDelegate {
    private var spool: FocusSpool?
    private var pollTimer: Timer?
    private var statusTimer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        do {
            spool = try FocusSpool()
            try spool?.publishSelfStatus()
            try spool?.promptForAccessibilityOnce()
        } catch {
            fputs("VERA GUI helper: private request spool unavailable; exiting fail-closed\n", stderr)
            NSApplication.shared.terminate(nil)
            return
        }
        pollTimer = Timer.scheduledTimer(withTimeInterval: 0.2, repeats: true) { [weak self] _ in
            self?.spool?.poll { request, finished in
                TargetInspection.perform(request, completion: finished)
            }
        }
        pollTimer?.tolerance = 0.02
        statusTimer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in
            do { try self?.spool?.publishSelfStatus() }
            catch { fputs("VERA GUI helper: self-status observation unavailable\n", stderr) }
        }
        statusTimer?.tolerance = 0.25
    }

    func applicationWillTerminate(_ notification: Notification) {
        pollTimer?.invalidate()
        statusTimer?.invalidate()
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let delegate = HelperApplication()
app.delegate = delegate
app.run()
