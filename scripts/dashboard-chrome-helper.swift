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
                  threadURL: String? = nil) {
    var result: [String: Any] = [
        "ok": false, "mode": mode, "reason": reason,
        "accessibilityTrusted": trusted, "sendInvoked": sendInvoked,
        "promptObserved": promptObserved, "assistantResponseObserved": responseObserved
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

private func isEmptyComposer(_ element: AXUIElement, page: AXUIElement) -> Bool {
    let value = composerText(element)
    if value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return true }
    // Chrome exposes the empty editor's placeholder as its AXValue.
    guard value == "Ask ChatGPT" else { return false }
    let buttons = axTree([page]).filter { axRole($0) == "AXButton" }
    return buttons.contains { textLabels($0).contains("Start Voice") }
        && !buttons.contains { textLabels($0).contains("Send") }
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

private func submit(prompt: String, nonce: String) {
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
            fail("submit", "ambiguous_chatgpt_page", nonce: nonce)
            return
        }
        Thread.sleep(forTimeInterval: 0.5)
    }
    guard let page else {
        fail("submit", "new_chatgpt_page_not_identified", nonce: nonce)
        return
    }
    guard let window = containingWindow(page) else {
        fail("submit", "target_window_not_identified", nonce: nonce)
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
        if composers.count == 1, composerText(composers[0]) == prompt { break }
        Thread.sleep(forTimeInterval: 0.25)
    }
    guard composers.count == 1, let composer = composers.first else {
        fail("submit", "composer_not_unique", nonce: nonce)
        return
    }
    let baselineText = Set(visibleText(page))
    guard composerText(composer) == prompt else {
        fail("submit", "prompt_verification_failed", nonce: nonce)
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
        fail("submit", "send_button_not_unique_or_enabled", nonce: nonce)
        return
    }
    var actionNames: CFArray?
    guard AXUIElementCopyActionNames(sendButton, &actionNames) == .success,
          let actions = actionNames as? [String], actions.contains("AXPress") else {
        fail("submit", "send_action_unavailable", nonce: nonce)
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
        promptObserved = combined.contains(prompt)
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
    var result: [String: Any] = [
        "ok": promptObserved && responseObserved && threadURL != nil,
        "mode": "submit", "requestNonce": nonce,
        "accessibilityTrusted": true, "sendInvoked": true,
        "promptObserved": promptObserved,
        "assistantResponseObserved": responseObserved
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
        case "submit" where arguments.count == 3:
            let nonce = arguments[2]
            let validNonce = nonce.range(of: "^[A-Za-z0-9_-]{16,64}$", options: .regularExpression) != nil
            guard validNonce else { fail("submit", "invalid_request_nonce", trusted: AXIsProcessTrusted()); return }
            guard let prompt = readPrompt(arguments[1]) else {
                fail("submit", "invalid_prompt_file", nonce: nonce, trusted: AXIsProcessTrusted())
                return
            }
            submit(prompt: prompt, nonce: nonce)
        default:
            emit(["ok": false, "reason": "usage", "usage": "status | request-access | submit <prompt-file> <request-nonce>"])
        }
    }
}
