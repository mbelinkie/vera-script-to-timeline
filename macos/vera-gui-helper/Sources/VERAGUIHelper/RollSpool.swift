import Foundation
import Darwin

// This is the same owner-only LaunchAgent spool as focus, but a separate
// consumed-intent namespace. A physical restart never makes an intent fresh.
final class DurableRollJournal: RollAudit {
    let directory: URL

    init(directory: URL) { self.directory = directory }

    private func assertPrivate() throws {
        var info = stat()
        guard lstat(directory.path, &info) == 0,
              (info.st_mode & mode_t(S_IFMT)) == mode_t(S_IFDIR),
              info.st_uid == getuid(), (info.st_mode & 0o077) == 0 else {
            throw FocusFailure.refused("Roll spool ownership/permissions unsafe")
        }
    }

    private func syncDirectory() throws {
        let fd = open(directory.path, O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW)
        guard fd >= 0 else { throw FocusFailure.refused("Roll parent cannot be flushed") }
        let result = fsync(fd)
        let closed = close(fd)
        guard result == 0 && closed == 0 else {
            throw FocusFailure.refused("Roll parent directory fsync uncertain")
        }
    }

    private func eventBytes(_ record: [String: Any]) throws -> Data {
        try JSONSerialization.data(withJSONObject: record, options: [.sortedKeys, .withoutEscapingSlashes])
            + Data([10])
    }

    func claim(_ request: RollRequest) throws -> Bool {
        try assertPrivate()
        // Key by immutable intent digest, not a caller-picked requestId.
        // A different request ID cannot make an already spent intent fresh.
        let name = "intent-" + request.intentDigest + ".roll-consumed.json"
        let target = directory.appendingPathComponent(name)
        let record: [String: Any] = [
            "schema": "vera.gui-helper-roll-consumed/v1",
            "requestId": request.requestId,
            "requestSha256": RollRequest.digest(request.raw),
            "intentSha256": request.intentDigest,
            "jobId": request.value["jobId"]!,
            "stageOperationId": request.value["stageOperationId"]!,
            "helperPid": Int(getpid()),
        ]
        let content = try eventBytes(record)
        let fd = open(target.path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        if fd < 0 {
            if errno == EEXIST { return false }
            throw FocusFailure.refused("cannot claim one-use Roll intent")
        }
        // Even a partial marker is intentionally never removed or retried.
        let result = content.withUnsafeBytes { write(fd, $0.baseAddress, $0.count) }
        let synced = fsync(fd)
        let closed = close(fd)
        guard result == content.count, synced == 0, closed == 0 else {
            throw FocusFailure.refused("Roll intent marker durability uncertain")
        }
        try syncDirectory()
        return true
    }

    func note(_ request: RollRequest, step: String, event: String, api: Int32?) throws {
        try assertPrivate()
        let path = directory.appendingPathComponent("intent-" + request.intentDigest + ".roll-events.jsonl")
        let record: [String: Any] = [
            "schema": "vera.gui-helper-roll-api-event/v1",
            "requestSha256": RollRequest.digest(request.raw),
            "helperPid": Int(getpid()),
            "step": step,
            "event": event,
            "apiResult": api.map { Int($0) } ?? NSNull(),
            "observedAt": Date().timeIntervalSince1970,
        ]
        let content = try eventBytes(record)
        let fd = open(path.path, O_WRONLY | O_CREAT | O_APPEND | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { throw FocusFailure.refused("Roll step journal unavailable") }
        var info = stat()
        let okay = fstat(fd, &info) == 0 &&
            (info.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG) &&
            info.st_uid == getuid() && (info.st_mode & 0o077) == 0 &&
            info.st_size <= 65536
        if !okay {
            close(fd)
            throw FocusFailure.refused("Roll step journal unsafe or full")
        }
        let count = content.withUnsafeBytes { write(fd, $0.baseAddress, $0.count) }
        let synced = fsync(fd)
        let closed = close(fd)
        guard count == content.count, synced == 0, closed == 0 else {
            throw FocusFailure.refused("Roll API result journal uncertain")
        }
        try syncDirectory()
    }
}

final class RollSpool {
    private let directory: URL
    private let journal: DurableRollJournal
    private(set) var isBusy = false

    init() throws {
        guard let base = ProcessInfo.processInfo.environment["VERA_GUI_HELPER_SPOOL"],
              base.hasPrefix("/"), !base.contains("/../"), !base.hasSuffix("/..") else {
            throw FocusFailure.refused("private helper spool not configured")
        }
        directory = URL(fileURLWithPath: base, isDirectory: true)
        journal = DurableRollJournal(directory: directory)
        // No automatic creation and no permission modification.
        var info = stat()
        guard lstat(directory.path, &info) == 0,
              (info.st_mode & mode_t(S_IFMT)) == mode_t(S_IFDIR),
              info.st_uid == getuid(), (info.st_mode & 0o077) == 0 else {
            throw FocusFailure.refused("unsafe Roll request directory")
        }
    }

    private func read(_ path: URL) throws -> Data {
        let fd = open(path.path, O_RDONLY | O_NOFOLLOW | O_CLOEXEC)
        guard fd >= 0 else { throw FocusFailure.refused("unsafe Roll request path") }
        defer { close(fd) }
        var info = stat()
        guard fstat(fd, &info) == 0,
              (info.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG),
              info.st_uid == getuid(), (info.st_mode & 0o077) == 0,
              info.st_size > 0, info.st_size <= 32768 else {
            throw FocusFailure.refused("invalid Roll request size/owner")
        }
        var bytes = [UInt8](repeating: 0, count: Int(info.st_size))
        var offset = 0
        while offset < bytes.count {
            let remaining = bytes.count - offset
            let n = bytes.withUnsafeMutableBytes { raw in
                Darwin.read(fd, raw.baseAddress!.advanced(by: offset), remaining)
            }
            guard n > 0 else { throw FocusFailure.refused("short Roll request read") }
            offset += n
        }
        return Data(bytes)
    }

    private func publish(_ request: RollRequest, outcome: RollOutcome) throws {
        let target = directory.appendingPathComponent(request.requestId + ".reply.json")
        let temp = directory.appendingPathComponent(request.requestId + ".reply.tmp")
        let record: [String: Any] = [
            "schema": "vera.gui-helper-reply/v1",
            "requestId": request.requestId,
            "requestSha256": RollRequest.digest(request.raw),
            "status": outcome.status,
            "helperPid": Int(getpid()),
            "actorPin": request.actorPin,
            "detail": String(outcome.detail.prefix(160)),
        ]
        let bytes = try JSONSerialization.data(
            withJSONObject: record, options: [.sortedKeys, .withoutEscapingSlashes]
        ) + Data([10])
        let fd = open(temp.path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { throw FocusFailure.refused("cannot publish Roll reply") }
        let count = bytes.withUnsafeBytes { write(fd, $0.baseAddress, $0.count) }
        let synced = fsync(fd)
        let closed = close(fd)
        guard count == bytes.count, synced == 0, closed == 0,
              access(target.path, F_OK) != 0,
              rename(temp.path, target.path) == 0 else {
            throw FocusFailure.refused("Roll reply publication uncertain")
        }
        let parent = open(directory.path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
        guard parent >= 0 else { throw FocusFailure.refused("Roll reply parent absent") }
        let parentSynced = fsync(parent)
        let parentClosed = close(parent)
        guard parentSynced == 0 && parentClosed == 0 else {
            throw FocusFailure.refused("Roll reply directory fsync uncertain")
        }
    }

    func poll() {
        if isBusy { return }
        do {
            let names = try FileManager.default.contentsOfDirectory(atPath: directory.path)
                .filter { $0.hasSuffix(".request.json") && !$0.hasSuffix(".focus-request.json") }
                .sorted()
            for filename in names {
                let raw = try read(directory.appendingPathComponent(filename))
                let request = try RollRequest(raw)
                guard filename == request.requestId + ".request.json" else {
                    throw FocusFailure.refused("Roll request filename/ID mismatch")
                }
                // A spent request is NEVER claimed again, even after restart.
                let spent = directory.appendingPathComponent(
                    "intent-" + request.intentDigest + ".roll-consumed.json"
                )
                if FileManager.default.fileExists(atPath: spent.path) { continue }
                isBusy = true
                DispatchQueue.global(qos: .userInitiated).async {
                    let outcome = FixedRoll.execute(
                        request, accessibility: NativeRollAccessibility(),
                        journal: self.journal, pins: NativeRollPins()
                    )
                    do { try self.publish(request, outcome: outcome) }
                    catch { fputs("VERA helper: Roll result publication uncertain; no replay\n", stderr) }
                    DispatchQueue.main.async { self.isBusy = false }
                }
                return
            }
        } catch {
            // Untrusted/corrupt requests never trigger an AX action.
            fputs("VERA helper: invalid Roll request refused without GUI effect\n", stderr)
        }
    }
}
