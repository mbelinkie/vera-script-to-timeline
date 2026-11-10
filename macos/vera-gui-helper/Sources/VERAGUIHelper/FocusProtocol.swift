import Foundation
import Darwin
import CoreFoundation
import CryptoKit
import ApplicationServices

// Phase 3's read-only/focus protocol is deliberately separate from the
// future one-use M4 Roll request. The helper MUST NOT inspect or execute
// *.request.json (Roll) until the Phase 4 consumed-intent actuator exists.
private let focusRequestSchema = "vera.gui-helper-focus-request/v1"
private let focusReplySchema = "vera.gui-helper-focus-reply/v1"
private let resolveBundleID = "com.blackmagic-design.DaVinciResolve"
private let focusFields: Set<String> = [
    "schema", "requestId", "deadlineAt", "operation", "resolvePid",
    "resolveBundleIdentifier", "windowName",
]

struct FocusRequest {
    let requestId: String
    let operation: String
    let resolvePid: pid_t
    let windowName: String
    let raw: Data

    init(_ raw: Data) throws {
        guard !raw.isEmpty, raw.count <= 8192,
              let object = try JSONSerialization.jsonObject(with: raw) as? [String: Any],
              Set(object.keys) == focusFields,
              let schema = object["schema"] as? String, schema == focusRequestSchema,
              let token = object["requestId"] as? String,
              (8...128).contains(token.utf8.count),
              token.utf8.allSatisfy({ ($0 >= 65 && $0 <= 90) ||
                  ($0 >= 97 && $0 <= 122) || ($0 >= 48 && $0 <= 57) ||
                  $0 == 45 || $0 == 95 }),
              let action = object["operation"] as? String,
              action == "inspect" || action == "focus",
              let bundle = object["resolveBundleIdentifier"] as? String,
              bundle == resolveBundleID,
              let number = object["resolvePid"] as? NSNumber,
              CFGetTypeID(number) != CFBooleanGetTypeID(),
              number.doubleValue == Double(number.int64Value),
              number.int64Value > 0, number.int64Value <= Int32.max,
              let name = object["windowName"] as? String,
              !name.isEmpty, name.utf8.count <= 160,
              !name.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }),
              let deadline = object["deadlineAt"] as? String,
              let date = FocusRequest.parseUTC(deadline),
              date.timeIntervalSinceNow > 0, date.timeIntervalSinceNow <= 120
        else {
            throw FocusFailure.refused("invalid, expired or unsupported focus request")
        }
        // Canonical, newline-terminated JSON catches duplicate members, aliases
        // and alternate representations. Only ASCII requests are supported in
        // this diagnostic phase; no normalization of Unicode window titles.
        guard let canonical = try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys, .withoutEscapingSlashes]),
              var canonicalString = String(data: canonical, encoding: .utf8),
              canonicalString.utf8.allSatisfy({ $0 < 128 })
        else {
            throw FocusFailure.refused("noncanonical focus request")
        }
        canonicalString += "\n"
        guard Data(canonicalString.utf8) == raw else {
            throw FocusFailure.refused("noncanonical or duplicate focus request")
        }
        self.requestId = token
        self.operation = action
        self.resolvePid = pid_t(number.int32Value)
        self.windowName = name
        self.raw = raw
    }

    private static func parseUTC(_ text: String) -> Date? {
        guard text.hasSuffix("Z") else { return nil }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: text) { return date }
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.date(from: text)
    }
}

enum FocusFailure: Error {
    case refused(String)

    var message: String {
        switch self {
        case .refused(let reason): return reason
        }
    }
}

struct FocusObservation {
    let pid: pid_t
    let bundle: String
    let title: String
    let main: Bool
    let foreground: Bool
    let noModalOrSheet: Bool
    let rollEnabled: Bool

    func json() -> [String: Any] {
        return [
            "resolvePid": Int(pid),
            "bundleIdentifier": bundle,
            "windowName": title,
            "mainWindow": main,
            "foreground": foreground,
            "noModalOrSheet": noModalOrSheet,
            "rollEnabled": rollEnabled,
        ]
    }
}

final class FocusSpool {
    private let directory: URL
    private var inFlight = false
    var isBusy: Bool { inFlight }

    init() throws {
        guard let base = ProcessInfo.processInfo.environment["VERA_GUI_HELPER_SPOOL"],
              base.hasPrefix("/"), !base.contains("/../"), !base.hasSuffix("/..") else {
            throw FocusFailure.refused("absolute private spool must be configured by LaunchAgent")
        }
        self.directory = URL(fileURLWithPath: base, isDirectory: true)
        try assertPrivateDirectory()
    }

    private func assertPrivateDirectory() throws {
        var statbuf = stat()
        guard lstat(directory.path, &statbuf) == 0,
              (statbuf.st_mode & mode_t(S_IFMT)) == mode_t(S_IFDIR),
              statbuf.st_uid == getuid(), (statbuf.st_mode & 0o077) == 0
        else {
            throw FocusFailure.refused("helper spool not a private owner directory")
        }
    }

    // This observation is written by the *running, direct-LaunchAgent process*,
    // not by Terminal, Python, osascript or a differently signed subprocess.
    // It is not proof of a native Roll or an authority to perform an effect.
    func publishSelfStatus() throws {
        try assertPrivateDirectory()
        let record: [String: Any] = [
            "schema": "vera.gui-helper-self-status/v1",
            "helperPid": Int(getpid()),
            "bundleIdentifier": Bundle.main.bundleIdentifier ?? "",
            "executablePath": Bundle.main.executablePath ?? "",
            "accessibilityTrusted": AXIsProcessTrusted(),
            "observedAt": Date().timeIntervalSince1970,
        ]
        let data = try JSONSerialization.data(withJSONObject: record, options: [.sortedKeys]) + Data([10])
        let temp = directory.appendingPathComponent(".self-status-" + String(getpid()) + ".tmp")
        let target = directory.appendingPathComponent("self-status.json")
        let fd = open(temp.path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { throw FocusFailure.refused("cannot write helper self observation") }
        let size = data.count
        let written = data.withUnsafeBytes { write(fd, $0.baseAddress, size) }
        let synced = fsync(fd)
        let closed = close(fd)
        guard written == size, synced == 0, closed == 0,
              rename(temp.path, target.path) == 0 else {
            throw FocusFailure.refused("cannot publish helper self observation")
        }
        let parent = open(directory.path, O_RDONLY | O_DIRECTORY | O_CLOEXEC)
        defer { if parent >= 0 { close(parent) } }
        guard parent >= 0 && fsync(parent) == 0 else {
            throw FocusFailure.refused("cannot flush helper self observation")
        }
    }

    func promptForAccessibilityOnce() throws {
        try assertPrivateDirectory()
        guard !AXIsProcessTrusted() else { return }
        let marker = directory.appendingPathComponent("accessibility-prompt-issued")
        let fd = open(marker.path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        if fd < 0 {
            if errno == EEXIST { return }
            throw FocusFailure.refused("cannot persist Accessibility prompt marker")
        }
        let synced = fsync(fd)
        let closed = close(fd)
        let parent = open(directory.path, O_RDONLY | O_DIRECTORY | O_CLOEXEC)
        let parentSynced = parent >= 0 ? fsync(parent) : -1
        if parent >= 0 { close(parent) }
        guard synced == 0 && closed == 0 && parentSynced == 0 else {
            throw FocusFailure.refused("Accessibility prompt marker durability uncertain")
        }
        // Request ONLY the helper's Accessibility consent. macOS owns the
        // UI; it is never clicked programmatically or treated as granted.
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        _ = AXIsProcessTrustedWithOptions(options)
    }

    private func readSafely(_ url: URL) throws -> Data {
        let fd = open(url.path, O_RDONLY | O_NOFOLLOW | O_CLOEXEC)
        guard fd >= 0 else { throw FocusFailure.refused("request cannot be opened safely") }
        defer { close(fd) }
        var metadata = stat()
        guard fstat(fd, &metadata) == 0,
              (metadata.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG),
              metadata.st_uid == getuid(), (metadata.st_mode & 0o077) == 0,
              metadata.st_size > 0, metadata.st_size <= 8192 else {
            throw FocusFailure.refused("unsafe request ownership or size")
        }
        var buffer = [UInt8](repeating: 0, count: Int(metadata.st_size))
        var offset = 0
        let total = buffer.count
        while offset < total {
            let count = buffer.withUnsafeMutableBytes { storage in
                read(fd, storage.baseAddress!.advanced(by: offset), total - offset)
            }
            guard count > 0 else { throw FocusFailure.refused("short request read") }
            offset += count
        }
        return Data(buffer)
    }

    private func durableConsume(_ request: FocusRequest) throws -> Bool {
        let path = directory.appendingPathComponent(request.requestId + ".focus-consumed").path
        let fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        if fd < 0 {
            if errno == EEXIST { return false }
            throw FocusFailure.refused("cannot persist consumed focus request")
        }
        let digest = SHA256.hash(data: request.raw).map { String(format: "%02x", $0) }.joined() + "\n"
        let bytes = [UInt8](digest.utf8)
        let written = bytes.withUnsafeBytes { write(fd, $0.baseAddress, $0.count) }
        let flushed = fsync(fd)
        let closed = close(fd)
        let dirFD = open(directory.path, O_RDONLY | O_DIRECTORY | O_CLOEXEC)
        let parentFlushed = dirFD >= 0 ? fsync(dirFD) : -1
        if dirFD >= 0 { close(dirFD) }
        guard written == bytes.count, flushed == 0, closed == 0, parentFlushed == 0 else {
            throw FocusFailure.refused("consumed marker durability uncertain")
        }
        return true
    }

    private func publishReply(_ request: FocusRequest,
                              observation: FocusObservation?,
                              error: String?) throws {
        let target = directory.appendingPathComponent(request.requestId + ".focus-reply.json")
        var record: [String: Any] = [
            "schema": focusReplySchema,
            "requestId": request.requestId,
            "requestSha256": SHA256.hash(data: request.raw)
                .map { String(format: "%02x", $0) }.joined(),
            "helperPid": Int(getpid()),
            "status": error == nil ? "ready" : "refused",
            "detail": error ?? "exact read-only target and menu observations complete",
        ]
        if let observation { record["observation"] = observation.json() }
        // Python's queue.canonical uses sorted keys, unescaped `/` and LF.
        // An otherwise valid signed focus reply must be byte-canonical too.
        let content = try JSONSerialization.data(withJSONObject: record, options: [.sortedKeys, .withoutEscapingSlashes])
            + Data([10])
        let temp = directory.appendingPathComponent(request.requestId + ".focus-reply.tmp")
        let fd = open(temp.path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { throw FocusFailure.refused("cannot create exclusive focus reply") }
        let written = content.withUnsafeBytes { write(fd, $0.baseAddress, $0.count) }
        let flushed = fsync(fd)
        let closed = close(fd)
        guard written == content.count, flushed == 0, closed == 0,
              access(target.path, F_OK) != 0,
              rename(temp.path, target.path) == 0 else {
            throw FocusFailure.refused("focus reply publication uncertain")
        }
        let dirFD = open(directory.path, O_RDONLY | O_DIRECTORY | O_CLOEXEC)
        defer { if dirFD >= 0 { close(dirFD) } }
        guard dirFD >= 0 && fsync(dirFD) == 0 else {
            throw FocusFailure.refused("focus reply directory fsync failed")
        }
    }

    func poll(_ run: @escaping (FocusRequest, @escaping (Result<FocusObservation, Error>) -> Void) -> Void) {
        if inFlight { return }
        do {
            try assertPrivateDirectory()
            let names = try FileManager.default.contentsOfDirectory(atPath: directory.path)
                .filter { $0.hasSuffix(".focus-request.json") }.sorted()
            for filename in names {
                let token = String(filename.dropLast(".focus-request.json".count))
                guard !FileManager.default.fileExists(
                    atPath: directory.appendingPathComponent(token + ".focus-consumed").path
                ) else { continue }
                let data = try readSafely(directory.appendingPathComponent(filename))
                let request = try FocusRequest(data)
                guard token == request.requestId, try durableConsume(request) else { continue }
                inFlight = true
                run(request) { result in
                    do {
                        switch result {
                        case .success(let observed):
                            try self.publishReply(request, observation: observed, error: nil)
                        case .failure(let cause):
                            let detail = (cause as? FocusFailure)?.message ?? "native focus inspection refused"
                            try self.publishReply(request, observation: nil, error: detail)
                        }
                    } catch {
                        fputs("VERA helper: refusal/uncertain reply publication\n", stderr)
                    }
                    self.inFlight = false
                }
                return
            }
        } catch {
            // Never turn malformed/spoofed input into a focus or menu effect.
            fputs("VERA helper: invalid/private focus request refused\n", stderr)
        }
    }
}
