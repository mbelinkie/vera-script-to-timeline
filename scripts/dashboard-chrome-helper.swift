import AppKit
import ApplicationServices
import CoreFoundation
import Foundation

private let chatGPTURL = URL(string: "https://chatgpt.com/")!
private let chromeBundleID = "com.google.Chrome"
private let maxPromptBytes = 64 * 1024
private let pageWaitSeconds: TimeInterval = 45
private let responseWaitSeconds: TimeInterval = 180

private func emit(_ fields: [String: Any]) {
    guard JSONSerialization.isValidJSONObject(fields),
          let data = try? JSONSerialization.data(withJSONObject: fields, options: [.sortedKeys]),
          let line = String(data: data, encoding: .utf8) else {
        print("{\"ok\":false,\"reason\":\"output_error\"}")
        return
    }
    print(line)
}

private func fail(_ mode: String, _ reason: String, nonce: String? = nil,
                  trusted: Bool = true, sendInvoked: Bool = false,
                  promptObserved: Bool = false, responseObserved: Bool = false,
                  threadURL: String? = nil, draftOpened: Bool = false) {
    var result: [String: Any] = [
        "ok": false, "mode": mode, "reason": reason,
        "accessibilityTrusted": trusted, "sendInvoked": sendInvoked,
        "promptObserved": promptObserved, "assistantResponseObserved": responseObserved,
        "draftOpened": draftOpened
    ]
    if let nonce { result["requestNonce"] = nonce }
    if let threadURL { result["threadURL"] = threadURL }
    if !trusted {
        result["permissionStep"] = "Enable Accessibility for this helper under System Settings > Privacy & Security > Accessibility."
    }
    emit(result)
}

private func axValue(_ element: AXUIElement, _ name: String) -> CFTypeRef? {
    var value: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, name as CFString, &value) == .success else { return nil }
    return value
}

private func axString(_ element: AXUIElement, _ name: String) -> String? {
    guard let value = axValue(element, name) else { return nil }
    if let string = value as? String { return string }
    if let url = value as? URL { return url.absoluteString }
    if let url = value as? NSURL { return url.absoluteString }
    return nil
}

private func axChildren(_ element: AXUIElement) -> [AXUIElement] {
    (axValue(element, "AXChildren") as? [AXUIElement]) ?? []
}

private func axRole(_ element: AXUIElement) -> String? { axString(element, "AXRole") }

private func axTree(_ roots: [AXUIElement], limit: Int = 6000) -> [AXUIElement] {
    var result: [AXUIElement] = []
    var stack = Array(roots.reversed())
    var seen = Set<CFHashCode>()
    while let element = stack.popLast(), result.count < limit {
        let key = CFHash(element)
        guard seen.insert(key).inserted else { continue }
        result.append(element)
        stack.append(contentsOf: axChildren(element).reversed())
    }
    return result
}

private func sameAXElement(_ lhs: AXUIElement, _ rhs: AXUIElement) -> Bool {
    CFEqual(lhs, rhs)
}

private func containingWindow(_ element: AXUIElement) -> AXUIElement? {
    var current = element
    for _ in 0..<30 {
        if axRole(current) == "AXWindow" { return current }
        guard let parent = axValue(current, "AXParent"), CFGetTypeID(parent) == AXUIElementGetTypeID() else { return nil }
        current = unsafeBitCast(parent, to: AXUIElement.self)
    }
    return nil
}

private func chatGPTWebAreas(pid: pid_t) -> [AXUIElement] {
    let app = AXUIElementCreateApplication(pid)
    let windows = (axValue(app, "AXWindows") as? [AXUIElement]) ?? []
    return axTree(windows).filter { axRole($0) == "AXWebArea" }
}

private func isChatGPTPage(_ element: AXUIElement) -> Bool {
    guard let raw = axString(element, "AXURL"), let url = URL(string: raw) else { return false }
    return url.scheme?.lowercased() == "https" && url.host?.lowercased() == "chatgpt.com"
}

private func textLabels(_ element: AXUIElement) -> [String] {
    ["AXTitle", "AXDescription", "AXHelp", "AXPlaceholderValue"]
        .compactMap { axString(element, $0) }
}

private func composerText(_ element: AXUIElement) -> String {
    (axString(element, "AXValue") ?? "").trimmingCharacters(in: .newlines)
}

// Chrome's accessibility tree may flatten blank lines and use nonbreaking spaces.
private func comparableText(_ value: String) -> String {
    value.split(whereSeparator: \.isWhitespace).joined(separator: " ")
}

private func effortPicker(_ page: AXUIElement) -> AXUIElement? {
    let controls = axTree([page]).filter {
        textLabels($0).contains("Select ChatGPT model")
            && ["AXPopUpButton", "AXButton"].contains(axRole($0) ?? "")
    }
    return controls.count == 1 ? controls[0] : nil
}

private func highEffortSelected(_ page: AXUIElement) -> Bool {
    guard let control = effortPicker(page) else { return false }
    return visibleText(control).contains("High")
        && (axValue(control, "AXExpanded") as? NSNumber)?.boolValue != true
}

private func selectHighEffort(page: AXUIElement, window: AXUIElement, pid: pid_t) -> Bool {
    for _ in 0..<40 {
        if effortPicker(page) != nil { break }
        Thread.sleep(forTimeInterval: 0.25)
    }
    if highEffortSelected(page) { return true }
    guard let control = effortPicker(page) else { return false }
    let chrome = AXUIElementCreateApplication(pid)
    _ = AXUIElementSetAttributeValue(chrome, "AXFrontmost" as CFString, kCFBooleanTrue)
    func targetIsFrontmost() -> Bool {
        guard (axValue(chrome, "AXFrontmost") as? NSNumber)?.boolValue == true,
              let focused = axValue(chrome, "AXFocusedWindow"),
              CFGetTypeID(focused) == AXUIElementGetTypeID() else { return false }
        return sameAXElement(unsafeBitCast(focused, to: AXUIElement.self), window)
            && axTree([window]).contains { axRole($0) == "AXWebArea" && sameAXElement($0, page) }
    }
    func postKey(_ key: CGKeyCode, modifiers: CGEventFlags = []) -> Bool {
        guard targetIsFrontmost(),
              let down = CGEvent(keyboardEventSource: nil, virtualKey: key, keyDown: true),
              let up = CGEvent(keyboardEventSource: nil, virtualKey: key, keyDown: false) else { return false }
        down.flags = modifiers
        up.flags = modifiers
        down.post(tap: .cghidEventTap)
        up.post(tap: .cghidEventTap)
        return true
    }
    _ = AXUIElementPerformAction(window, "AXRaise" as CFString)
    for _ in 0..<8 {
        if targetIsFrontmost() { break }
        Thread.sleep(forTimeInterval: 0.25)
    }
    guard targetIsFrontmost() else { return false }
    if (axValue(control, "AXExpanded") as? NSNumber)?.boolValue != true {
        guard postKey(46, modifiers: [.maskControl, .maskShift]) else { return false } // Control-Shift-M opens Thinking effort.
    }
    func powerFocused() -> Bool {
        guard (axValue(control, "AXExpanded") as? NSNumber)?.boolValue == true,
              let value = axValue(chrome, "AXFocusedUIElement"),
              CFGetTypeID(value) == AXUIElementGetTypeID() else { return false }
        let focused = unsafeBitCast(value, to: AXUIElement.self)
        return axRole(focused) == "AXMenuItem" && textLabels(focused).contains("Power")
    }
    for _ in 0..<12 {
        if powerFocused() { break }
        Thread.sleep(forTimeInterval: 0.25)
    }
    // Two Right presses reach the top of the three-level picker from Low or Medium.
    for _ in 0..<2 {
        guard powerFocused(), postKey(124) else { return false }
        Thread.sleep(forTimeInterval: 0.25)
    }
    guard powerFocused(), postKey(53) else { return false }
    for _ in 0..<8 {
        Thread.sleep(forTimeInterval: 0.25)
        if highEffortSelected(page) { return true }
    }
    return false
}

private func isEmptyComposer(_ element: AXUIElement, page: AXUIElement) -> Bool {
    let value = composerText(element)
    if value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return true }
    // Chrome exposes the empty editor's placeholder as its AXValue.
    guard value == "Ask ChatGPT" else { return false }
    let buttons = axTree([page]).filter { axRole($0) == "AXButton" }
    return !buttons.contains { textLabels($0).contains("Send")
        && (axValue($0, "AXEnabled") as? NSNumber)?.boolValue == true }
}

private func visibleText(_ root: AXUIElement) -> [String] {
    axTree([root]).compactMap { element in
        guard let role = axRole(element),
              ["AXStaticText", "AXText", "AXTextArea"].contains(role),
              let value = axString(element, "AXValue"), !value.isEmpty else { return nil }
        return value
    }
}

private func canonicalThreadURL(_ page: AXUIElement) -> String? {
    guard let raw = axString(page, "AXURL"), let url = URL(string: raw),
          url.scheme?.lowercased() == "https", url.host?.lowercased() == "chatgpt.com",
          url.path.hasPrefix("/c/"), url.user == nil, url.password == nil else { return nil }
    var parts = URLComponents(url: url, resolvingAgainstBaseURL: false)
    parts?.query = nil
    parts?.fragment = nil
    return parts?.url?.absoluteString
}

private func pinCurrentChat(window: AXUIElement, threadURL: String) -> String {
    func parent(_ element: AXUIElement) -> AXUIElement? {
        guard let value = axValue(element, "AXParent"), CFGetTypeID(value) == AXUIElementGetTypeID() else { return nil }
        return unsafeBitCast(value, to: AXUIElement.self)
    }
    func buttons(_ root: AXUIElement, _ label: String) -> [AXUIElement] {
        axTree([root]).filter { axRole($0) == "AXButton" && textLabels($0).contains(label) }
    }
    func anchorLinks() -> [AXUIElement] {
        axTree([window]).filter { axRole($0) == "AXLink" && canonicalThreadURL($0) == threadURL }
    }
    func row(_ link: AXUIElement) -> (AXUIElement, AXUIElement, [AXUIElement], [AXUIElement])? {
        var current: AXUIElement? = link
        for _ in 0..<12 {
            guard let container = current, !sameAXElement(container, window) else { return nil }
            let nodes = axTree([container])
            let links = nodes.filter { axRole($0) == "AXLink" && sameAXElement($0, link) }
            let menus = nodes.filter { ["AXPopUpButton", "AXButton"].contains(axRole($0) ?? "")
                && textLabels($0).contains("Chat actions") }
            let pins = buttons(container, "Pin chat")
            let unpins = buttons(container, "Unpin chat")
            if links.count == 1 && menus.count == 1 { return (container, menus[0], pins, unpins) }
            current = parent(container)
        }
        return nil
    }
    func press(_ element: AXUIElement) -> Bool {
        var actions: CFArray?
        return AXUIElementCopyActionNames(element, &actions) == .success
            && (actions as? [String])?.contains("AXPress") == true
            && AXUIElementPerformAction(element, "AXPress" as CFString) == .success
    }
    var openedSidebar = false
    defer {
        if openedSidebar {
            let hide = buttons(window, "Hide sidebar")
            if hide.count == 1 { _ = press(hide[0]) }
        }
    }
    var links = anchorLinks()
    if links.count > 1 { return "unavailable" }
    if links.isEmpty {
        let show = buttons(window, "Show sidebar")
        guard show.count == 1, press(show[0]) else { return "unavailable" }
        openedSidebar = true
        let deadline = Date().addingTimeInterval(8)
        repeat {
            Thread.sleep(forTimeInterval: 0.25)
            links = anchorLinks()
        } while links.isEmpty && Date() < deadline
    }
    guard links.count == 1, let anchor = links.first, var currentRow = row(anchor) else { return "unavailable" }
    if currentRow.3.count == 1 && currentRow.2.isEmpty { return "pinned" }
    guard currentRow.3.isEmpty, currentRow.2.count <= 1 else { return "unavailable" }
    if currentRow.2.isEmpty {
        guard press(currentRow.1) else { return "unavailable" }
        let deadline = Date().addingTimeInterval(5)
        repeat {
            Thread.sleep(forTimeInterval: 0.25)
            guard let refreshed = row(anchor) else { return "unconfirmed" }
            currentRow = refreshed
            if currentRow.3.count == 1 && currentRow.2.isEmpty { return "pinned" }
        } while currentRow.2.isEmpty && Date() < deadline
    }
    guard currentRow.2.count == 1, currentRow.3.isEmpty, press(currentRow.2[0]) else { return "unavailable" }
    let verifyDeadline = Date().addingTimeInterval(8)
    repeat {
        Thread.sleep(forTimeInterval: 0.25)
        guard anchorLinks().count == 1, let refreshed = row(anchor) else { return "unconfirmed" }
        if refreshed.3.count == 1 && refreshed.2.isEmpty { return "pinned" }
    } while Date() < verifyDeadline
    return "unconfirmed"
}

private func readPrompt(_ path: String) -> String? {
    let url = URL(fileURLWithPath: path)
    guard let attributes = try? FileManager.default.attributesOfItem(atPath: url.path),
          (attributes[.type] as? FileAttributeType) == .typeRegular,
          let size = attributes[.size] as? NSNumber,
          size.intValue > 0, size.intValue <= maxPromptBytes,
          let data = try? Data(contentsOf: url),
          let prompt = String(data: data, encoding: .utf8),
          !prompt.isEmpty,
          !prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
          !prompt.unicodeScalars.contains(where: { $0.value == 0 }) else { return nil }
    return prompt
}

private func openChromeApp(_ appURL: URL) -> NSRunningApplication? {
    if let existing = NSRunningApplication.runningApplications(withBundleIdentifier: chromeBundleID)
        .first(where: { !$0.isTerminated }) { return existing }
    let semaphore = DispatchSemaphore(value: 0)
    var opened: NSRunningApplication?
    NSWorkspace.shared.openApplication(at: appURL, configuration: NSWorkspace.OpenConfiguration()) { app, _ in
        opened = app
        semaphore.signal()
    }
    guard semaphore.wait(timeout: .now() + 20) == .success,
          let app = opened, app.bundleIdentifier == chromeBundleID else { return nil }
    return app
}

private func openChatGPTInChrome(_ appURL: URL, prompt: String) -> NSRunningApplication? {
    let semaphore = DispatchSemaphore(value: 0)
    var opened: NSRunningApplication?
    var succeeded = false
    let config = NSWorkspace.OpenConfiguration()
    config.activates = true
    var parts = URLComponents(url: chatGPTURL, resolvingAgainstBaseURL: false)!
    parts.queryItems = [URLQueryItem(name: "q", value: prompt)]
    NSWorkspace.shared.open([parts.url!], withApplicationAt: appURL, configuration: config) { app, error in
        opened = app
        succeeded = error == nil
        semaphore.signal()
    }
    guard semaphore.wait(timeout: .now() + 20) == .success,
          succeeded, let app = opened, app.bundleIdentifier == chromeBundleID else { return nil }
    return app
}

private func submit(prompt: String, nonce: String, prepareOnly: Bool = false) {
    guard AXIsProcessTrusted() else {
        fail("submit", "accessibility_permission_required", nonce: nonce, trusted: false)
        return
    }
    guard let appURL = NSWorkspace.shared.urlForApplication(withBundleIdentifier: chromeBundleID),
          let initialApp = openChromeApp(appURL) else {
        fail("submit", "chrome_unavailable", nonce: nonce)
        return
    }
    let pid = initialApp.processIdentifier
    let before = chatGPTWebAreas(pid: pid)
    if prepareOnly {
        let matching = before.filter(isChatGPTPage).filter { page in
            axTree([page]).contains { axRole($0) == "AXTextArea"
                && textLabels($0).contains("Ask ChatGPT")
                && comparableText(composerText($0)) == comparableText(prompt) }
        }
        if matching.count == 1, let existing = matching.first, let window = containingWindow(existing) {
            let selected = selectHighEffort(page: existing, window: window, pid: pid)
            emit(["ok": selected, "mode": "prepare", "requestNonce": nonce,
                "effort": selected ? "high" : "unknown", "sendInvoked": false])
            return
        }
    }
    guard !before.filter(isChatGPTPage).contains(where: { page in
        axTree([page]).contains { axRole($0) == "AXTextArea"
            && textLabels($0).contains("Ask ChatGPT") && !isEmptyComposer($0, page: page) }
    }) else {
        fail("submit", "composer_has_existing_draft", nonce: nonce)
        return
    }
    guard let openedApp = openChatGPTInChrome(appURL, prompt: prompt), openedApp.processIdentifier == pid else {
        fail("submit", "chrome_open_failed", nonce: nonce)
        return
    }

    var page: AXUIElement?
    let pageDeadline = Date().addingTimeInterval(pageWaitSeconds)
    while Date() < pageDeadline {
        let candidates = chatGPTWebAreas(pid: pid).filter { candidate in
            isChatGPTPage(candidate) && !before.contains(where: { sameAXElement($0, candidate) })
        }
        if candidates.count == 1 { page = candidates[0]; break }
        if candidates.count > 1 {
            fail("submit", "ambiguous_chatgpt_page", nonce: nonce, draftOpened: true)
            return
        }
        Thread.sleep(forTimeInterval: 0.5)
    }
    guard let page else {
        fail("submit", "new_chatgpt_page_not_identified", nonce: nonce, draftOpened: true)
        return
    }
    guard let window = containingWindow(page) else {
        fail("submit", "target_window_not_identified", nonce: nonce, draftOpened: true)
        return
    }

    var composers: [AXUIElement] = []
    let composerDeadline = Date().addingTimeInterval(20)
    while Date() < composerDeadline {
        composers = axTree([page]).filter { element in
        axRole(element) == "AXTextArea" && textLabels(element).contains {
            $0.trimmingCharacters(in: .whitespacesAndNewlines).caseInsensitiveCompare("Ask ChatGPT") == .orderedSame
        }
        }
        if composers.count == 1, comparableText(composerText(composers[0])) == comparableText(prompt) { break }
        Thread.sleep(forTimeInterval: 0.25)
    }
    guard composers.count == 1, let composer = composers.first else {
        fail("submit", "composer_not_unique", nonce: nonce, draftOpened: true)
        return
    }
    let baselineText = Set(visibleText(page))
    guard comparableText(composerText(composer)) == comparableText(prompt) else {
        fail("submit", "prompt_verification_failed", nonce: nonce, draftOpened: true)
        return
    }
    guard selectHighEffort(page: page, window: window, pid: pid) else {
        fail("submit", "high_effort_unverified", nonce: nonce, draftOpened: true)
        return
    }
    if prepareOnly {
        emit(["ok": true, "mode": "prepare", "requestNonce": nonce, "effort": "high", "sendInvoked": false])
        return
    }

    var sendButtons: [AXUIElement] = []
    let sendDeadline = Date().addingTimeInterval(15)
    while Date() < sendDeadline {
        sendButtons = axTree([page]).filter { element in
            axRole(element) == "AXButton" && textLabels(element).contains {
                $0.trimmingCharacters(in: .whitespacesAndNewlines).caseInsensitiveCompare("Send") == .orderedSame
            }
        }
        if sendButtons.count == 1,
           (axValue(sendButtons[0], "AXEnabled") as? NSNumber)?.boolValue == true { break }
        Thread.sleep(forTimeInterval: 0.25)
    }
    guard sendButtons.count == 1, let sendButton = sendButtons.first,
          (axValue(sendButton, "AXEnabled") as? NSNumber)?.boolValue == true else {
        fail("submit", "send_button_not_unique_or_enabled", nonce: nonce, draftOpened: true)
        return
    }
    var actionNames: CFArray?
    guard AXUIElementCopyActionNames(sendButton, &actionNames) == .success,
          let actions = actionNames as? [String], actions.contains("AXPress") else {
        fail("submit", "send_action_unavailable", nonce: nonce, draftOpened: true)
        return
    }

    guard comparableText(composerText(composer)) == comparableText(prompt) else {
        fail("submit", "prompt_verification_failed", nonce: nonce, draftOpened: true)
        return
    }
    guard highEffortSelected(page) else {
        fail("submit", "high_effort_unverified", nonce: nonce, draftOpened: true)
        return
    }
    let sendError = AXUIElementPerformAction(sendButton, "AXPress" as CFString)
    guard sendError == .success else {
        fail("submit", "send_action_failed", nonce: nonce, sendInvoked: true)
        return
    }

    var promptObserved = false
    var responseObserved = false
    var threadURL: String?
    let responseDeadline = Date().addingTimeInterval(responseWaitSeconds)
    while Date() < responseDeadline {
        let currentPages = axTree([window]).filter { axRole($0) == "AXWebArea" && isChatGPTPage($0) }
        guard currentPages.count == 1, let currentPage = currentPages.first else {
            Thread.sleep(forTimeInterval: 1)
            continue
        }
        let values = visibleText(currentPage)
        let combined = values.joined(separator: "\n")
        promptObserved = comparableText(combined).contains(comparableText(prompt))
        threadURL = canonicalThreadURL(currentPage)
        let newResponseText = values.contains { value in
            !baselineText.contains(value) && !value.isEmpty && value != prompt && !prompt.contains(value)
        }
        let currentNodes = axTree([currentPage])
        let generating = currentNodes.contains { element in
            axRole(element) == "AXButton" && textLabels(element).contains {
                $0.localizedCaseInsensitiveCompare("Stop generating") == .orderedSame
            }
        }
        let hasAssistantHeading = currentNodes.contains { element in
            axRole(element) == "AXHeading" && visibleText(element).contains("ChatGPT said:")
        }
        let composerIsEmpty = currentNodes.contains { element in
            axRole(element) == "AXTextArea" && textLabels(element).contains("Ask ChatGPT")
                && isEmptyComposer(element, page: currentPage)
        }
        responseObserved = promptObserved && hasAssistantHeading && newResponseText && !generating && composerIsEmpty
        if responseObserved && threadURL != nil { break }
        Thread.sleep(forTimeInterval: 1)
    }
    let pinState = promptObserved && responseObserved && threadURL != nil
        ? pinCurrentChat(window: window, threadURL: threadURL!) : "unavailable"
    var result: [String: Any] = [
        "ok": promptObserved && responseObserved && threadURL != nil,
        "mode": "submit", "requestNonce": nonce,
        "accessibilityTrusted": true, "sendInvoked": true,
        "promptObserved": promptObserved,
        "assistantResponseObserved": responseObserved,
        "pinState": pinState
    ]
    if let threadURL { result["threadURL"] = threadURL }
    if !promptObserved { result["reason"] = "prompt_not_observed_after_send" }
    else if !responseObserved { result["reason"] = "assistant_response_not_observed_before_timeout" }
    else if threadURL == nil { result["reason"] = "thread_url_not_observed" }
    emit(result)
}

@main
private struct DashboardChromeHelper {
    static func main() {
        let arguments = Array(CommandLine.arguments.dropFirst())
        switch arguments.first ?? "" {
        case "status" where arguments.count == 1:
            emit(["ok": true, "mode": "status", "accessibilityTrusted": AXIsProcessTrusted()])
        case "request-access" where arguments.count == 1:
            let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
            let trusted = AXIsProcessTrustedWithOptions(options)
            emit(["ok": true, "mode": "request-access", "accessibilityTrusted": trusted,
                  "promptRequested": !trusted])
        case "submit" where arguments.count == 3, "prepare" where arguments.count == 3:
            let nonce = arguments[2]
            let validNonce = nonce.range(of: "^[A-Za-z0-9_-]{16,64}$", options: .regularExpression) != nil
            guard validNonce else { fail("submit", "invalid_request_nonce", trusted: AXIsProcessTrusted()); return }
            guard let prompt = readPrompt(arguments[1]) else {
                fail("submit", "invalid_prompt_file", nonce: nonce, trusted: AXIsProcessTrusted())
                return
            }
            submit(prompt: prompt, nonce: nonce, prepareOnly: arguments[0] == "prepare")
        default:
            emit(["ok": false, "reason": "usage", "usage": "status | request-access | (submit | prepare) <prompt-file> <request-nonce>"])
        }
    }
}
