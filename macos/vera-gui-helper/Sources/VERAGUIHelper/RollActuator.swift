import AppKit
import ApplicationServices
import CoreFoundation
import CryptoKit
import Darwin
import Foundation
import Security

// An immutable, Python-admitted M4 edited-stage request. There is no caller
// supplied AX path, key, coordinate, command, target override or retry count.
struct RollRequest {
    static let fields: Set<String> = [
        "schema", "requestId", "deadlineAt", "operation", "jobId", "stageOperationId",
        "fixtureId", "trialId", "resolvePid", "windowName", "projectUid", "timelineUid",
        "sourceGraphSha256", "actorPin", "pristineCaptureSha256", "oneUseIntentSha256",
        "authoritySha256",
    ]
    static let binaryFields: Set<String> = [
        "executablePath", "sha256", "codeDirectoryHash", "designatedRequirement",
        "teamIdentifier", "bundleIdentifier",
    ]
    let raw: Data
    let value: [String: Any]
    let actorPin: [String: Any]
    let binaryPin: [String: Any]
    let requestId: String
    let pid: pid_t
    let windowName: String
    let intentDigest: String
    let expires: Date

    static func digest(_ data: Data) -> String {
        SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }

    static func asciiToken(_ s: String) -> Bool {
        (8...128).contains(s.utf8.count) && s.utf8.allSatisfy {
            ($0 >= 65 && $0 <= 90) || ($0 >= 97 && $0 <= 122) ||
            ($0 >= 48 && $0 <= 57) || $0 == 45 || $0 == 95
        }
    }

    static func hex(_ s: String, length: Int) -> Bool {
        s.utf8.count == length && s.utf8.allSatisfy {
            ($0 >= 48 && $0 <= 57) || ($0 >= 97 && $0 <= 102)
        }
    }

    static func safeName(_ s: String) -> Bool {
        !s.isEmpty && s.utf8.count <= 160 &&
            !s.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) })
    }

    init(_ raw: Data, now: Date = Date(), pinProbeOnly: Bool = false) throws {
        guard !raw.isEmpty, raw.count <= 32768,
              let object = try JSONSerialization.jsonObject(with: raw) as? [String: Any],
              Set(object.keys) == Self.fields,
              object["schema"] as? String == "vera.gui-helper-request/v1",
              let operation = object["operation"] as? String,
              operation == (pinProbeOnly ? "M4.edited.verify-actor-no-edit" : "M4.edited.roll-start-to-playhead"),
              object["fixtureId"] as? String == "synthetic-312",
              let requestId = object["requestId"] as? String, Self.asciiToken(requestId),
              let jobId = object["jobId"] as? String, Self.asciiToken(jobId),
              let operationId = object["stageOperationId"] as? String, Self.asciiToken(operationId),
              let trialId = object["trialId"] as? String, Self.asciiToken(trialId),
              let number = object["resolvePid"] as? NSNumber,
              CFGetTypeID(number) != CFBooleanGetTypeID(),
              number.doubleValue == Double(number.int64Value),
              number.int64Value > 0, number.int64Value <= Int32.max,
              let window = object["windowName"] as? String, Self.safeName(window),
              let project = object["projectUid"] as? String, Self.safeName(project),
              let timeline = object["timelineUid"] as? String, Self.safeName(timeline),
              let graph = object["sourceGraphSha256"] as? String, Self.hex(graph, length: 64),
              let pristine = object["pristineCaptureSha256"] as? String, Self.hex(pristine, length: 64),
              let intent = object["oneUseIntentSha256"] as? String, Self.hex(intent, length: 64),
              let authority = object["authoritySha256"] as? String, Self.hex(authority, length: 64),
              let actor = object["actorPin"] as? [String: Any],
              Set(actor.keys) == ["schema", "sourceManifestSha256", "binary"],
              actor["schema"] as? String == "vera.gui-helper-actor/v1",
              let manifest = actor["sourceManifestSha256"] as? String,
              Self.hex(manifest, length: 64),
              let binary = actor["binary"] as? [String: Any],
              Set(binary.keys) == Self.binaryFields,
              let exe = binary["executablePath"] as? String,
              exe.hasPrefix("/"), !exe.split(separator: "/").contains(".."),
              exe.hasSuffix("/VERA GUI Helper.app/Contents/MacOS/VERAGUIHelper"),
              let exeSHA = binary["sha256"] as? String, Self.hex(exeSHA, length: 64),
              let cdHash = binary["codeDirectoryHash"] as? String, Self.hex(cdHash, length: 40),
              let requirement = binary["designatedRequirement"] as? String,
              (20...2048).contains(requirement.utf8.count),
              requirement.contains("identifier \"org.vera.resolve-test-bench.gui\""),
              let team = binary["teamIdentifier"] as? String,
              team.utf8.count == 10, team.utf8.allSatisfy({
                ($0 >= 65 && $0 <= 90) || ($0 >= 48 && $0 <= 57)
              }),
              binary["bundleIdentifier"] as? String == "org.vera.resolve-test-bench.gui",
              let deadline = object["deadlineAt"] as? String, deadline.hasSuffix("Z")
        else {
            throw FocusFailure.refused("Roll request schema, target or actor pin refused")
        }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        var parsed = formatter.date(from: deadline)
        if parsed == nil {
            formatter.formatOptions = [.withInternetDateTime]
            parsed = formatter.date(from: deadline)
        }
        guard let parsed, parsed > now, parsed.timeIntervalSince(now) <= 120 else {
            throw FocusFailure.refused("Roll request deadline expired or unbounded")
        }
        // Canonical bytes also reject duplicate JSON members at ANY depth.
        guard let canonical = try? JSONSerialization.data(
            withJSONObject: object, options: [.sortedKeys, .withoutEscapingSlashes]
        ), canonical + Data([10]) == raw else {
            throw FocusFailure.refused("noncanonical or duplicate Roll request")
        }
        self.raw = raw
        self.value = object
        self.actorPin = actor
        self.binaryPin = binary
        self.requestId = requestId
        self.pid = pid_t(number.int32Value)
        self.windowName = window
        self.intentDigest = intent
        self.expires = parsed
    }

    func requireLiveDeadline(now: Date = Date()) throws {
        guard now < expires else { throw FocusFailure.refused("Roll deadline passed mid-dispatch") }
    }
}

protocol RollAccessibility {
    func observe(_ request: RollRequest) throws -> FocusObservation
    func enabled(_ request: RollRequest, path: [String]) throws -> Bool
    // One low-level AXPress call maximum per invocation. No retries.
    func press(_ request: RollRequest, path: [String]) throws -> Int32
}

final class NativeRollAccessibility: RollAccessibility {
    private var admittedLaunchDate: Date?

    private func requireSameProcess(_ request: RollRequest) throws {
        guard let process = NSRunningApplication(processIdentifier: request.pid),
              !process.isTerminated,
              process.bundleIdentifier == "com.blackmagic-design.DaVinciResolve",
              let launched = process.launchDate else {
            throw FocusFailure.refused("Resolve process unavailable or replaced")
        }
        if let original = admittedLaunchDate {
            guard launched == original else {
                throw FocusFailure.refused("Resolve process generation changed")
            }
        } else {
            admittedLaunchDate = launched
        }
    }

    func observe(_ request: RollRequest) throws -> FocusObservation {
        try requireSameProcess(request)
        return try TargetInspection.inspectTarget(pid: request.pid, windowName: request.windowName)
    }
    func enabled(_ request: RollRequest, path: [String]) throws -> Bool {
        try requireSameProcess(request)
        return try TargetInspection.menuEnabled(pid: request.pid, windowName: request.windowName, path: path)
    }
    func press(_ request: RollRequest, path: [String]) throws -> Int32 {
        try requireSameProcess(request)
        return try TargetInspection.pressMenu(pid: request.pid, windowName: request.windowName, path: path).rawValue
    }
}

protocol RollAudit {
    // Persistent across restarts. claim MUST fsync before returning true.
    func claim(_ request: RollRequest) throws -> Bool
    // Persistent before or after every native API result; failure aborts.
    func note(_ request: RollRequest, step: String, event: String, api: Int32?) throws
}

protocol RollPins {
    func verify(_ request: RollRequest) throws
}

// Runtime pins are verified against the actual running, signed helper, not
// merely copied from a caller-supplied actorPin. Phase 5 configures frozen
// source/actor digests on the direct Aqua LaunchAgent; absent pins REFUSE.
struct NativeRollPins: RollPins {
    func verify(_ request: RollRequest) throws {
        let env = ProcessInfo.processInfo.environment
        guard let actorDigest = env["VERA_GUI_HELPER_ACTOR_PIN_SHA256"],
              let sourceGraph = env["VERA_GUI_HELPER_SOURCE_GRAPH_SHA256"],
              RollRequest.hex(actorDigest, length: 64),
              RollRequest.hex(sourceGraph, length: 64),
              sourceGraph == request.value["sourceGraphSha256"] as? String,
              let canonicalActor = try? JSONSerialization.data(
                withJSONObject: request.actorPin, options: [.sortedKeys, .withoutEscapingSlashes]
              ), RollRequest.digest(canonicalActor + Data([10])) == actorDigest,
              Bundle.main.bundleIdentifier == "org.vera.resolve-test-bench.gui",
              Bundle.main.executablePath == request.binaryPin["executablePath"] as? String
        else {
            throw FocusFailure.refused("running helper actor/source pins unproven")
        }
        let exe = Bundle.main.executablePath!
        var metadata = stat()
        guard lstat(exe, &metadata) == 0,
              (metadata.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG) else {
            throw FocusFailure.refused("installed helper executable missing or aliased")
        }
        let fd = open(exe, O_RDONLY | O_NOFOLLOW | O_CLOEXEC)
        guard fd >= 0 else { throw FocusFailure.refused("signed helper executable cannot be read") }
        var bytes = Data()
        var block = [UInt8](repeating: 0, count: 65536)
        while true {
            let count = block.withUnsafeMutableBytes { read(fd, $0.baseAddress, $0.count) }
            if count == 0 { break }
            if count < 0 || bytes.count > 128_000_000 - count {
                close(fd)
                throw FocusFailure.refused("signed helper executable changed/unreadable")
            }
            bytes.append(contentsOf: block.prefix(count))
        }
        let closeResult = close(fd)
        guard closeResult == 0,
              RollRequest.digest(bytes) == request.binaryPin["sha256"] as? String else {
            throw FocusFailure.refused("running executable SHA-256 mismatch")
        }
        var runningCode: SecCode?
        guard SecCodeCopySelf([], &runningCode) == errSecSuccess, let runningCode,
              SecCodeCheckValidity(runningCode, [], nil) == errSecSuccess else {
            throw FocusFailure.refused("helper code signature is not valid")
        }
        var staticCode: SecStaticCode?
        guard SecStaticCodeCreateWithPath(URL(fileURLWithPath: exe) as CFURL, [], &staticCode) == errSecSuccess,
              let staticCode,
              SecStaticCodeCheckValidity(staticCode, [], nil) == errSecSuccess else {
            throw FocusFailure.refused("installed helper static code signature invalid")
        }
        var info: CFDictionary?
        guard SecCodeCopySigningInformation(staticCode, SecCSFlags(rawValue: kSecCSSigningInformation), &info) == errSecSuccess,
              let values = info as? [String: Any],
              values[kSecCodeInfoTeamIdentifier as String] as? String == request.binaryPin["teamIdentifier"] as? String,
              let unique = values[kSecCodeInfoUnique as String] as? Data,
              unique.map({ String(format: "%02x", $0) }).joined() == request.binaryPin["codeDirectoryHash"] as? String else {
            throw FocusFailure.refused("helper code-directory/team pin mismatch")
        }
        var requirement: SecRequirement?
        var requirementString: CFString?
        guard SecCodeCopyDesignatedRequirement(staticCode, [], &requirement) == errSecSuccess,
              let requirement,
              SecRequirementCopyString(requirement, [], &requirementString) == errSecSuccess,
              let observed = requirementString as String?,
              observed == request.binaryPin["designatedRequirement"] as? String else {
            throw FocusFailure.refused("helper designated requirement pin mismatch")
        }
    }
}

struct RollOutcome {
    let status: String
    let detail: String
}

enum FixedRoll {
    static let setupPaths: [[String]] = [
        ["Edit", "Deselect All"],
        ["Timeline", "Auto Select", "Auto Deselect All Tracks"],
        ["Timeline", "Auto Select", "Auto Select/Deselect V1"],
        ["Trim", "Normal Edit Mode"],
    ]
    static let rollPath = ["Trim", "Roll", "Start to Playhead"]

    static func execute(
        _ request: RollRequest, accessibility: RollAccessibility,
        journal: RollAudit, pins: RollPins
    ) -> RollOutcome {
        var possibleEffect = false
        var step = "admission"
        do {
            try request.requireLiveDeadline()
            try pins.verify(request)
            // All GUI effects (including Deselect All) are AFTER the durable
            // one-use claim. An uncertain claim is permanently ineligible.
            guard try journal.claim(request) else {
                throw FocusFailure.refused("one-use Roll intent already consumed")
            }
            try journal.note(request, step: step, event: "consumed", api: nil)
            for (index, path) in (setupPaths + [rollPath]).enumerated() {
                step = index == setupPaths.count ? "roll" : "setup-\(index + 1)"
                try request.requireLiveDeadline()
                // Inspect before each menu lookup and again immediately
                // before each press. A missing/unknown state is NOT ready.
                try requireTarget(accessibility.observe(request), request: request,
                                  requireRoll: index == setupPaths.count)
                let enabled = try accessibility.enabled(request, path: path)
                try journal.note(request, step: step, event: enabled ? "enabled" : "disabled", api: nil)
                if !enabled {
                    if index == 0 {
                        // Deselect All is conditional. All-tracks-off is NOT.
                        try journal.note(request, step: step, event: "skipped-disabled", api: nil)
                        continue
                    }
                    throw FocusFailure.refused("required menu path disabled at \(step)")
                }
                try requireTarget(accessibility.observe(request), request: request,
                                  requireRoll: index == setupPaths.count)
                try request.requireLiveDeadline()
                try journal.note(request, step: step, event: "press-attempted", api: nil)
                // No AXPress is ever retried, even if an API throws/returns
                // timeout, the helper dies, or AX reports apparent failure.
                possibleEffect = true
                let api = try accessibility.press(request, path: path)
                try journal.note(request, step: step, event: "api-result", api: api)
                guard api == 0 else {
                    throw FocusFailure.refused("AXPress ambiguous/refused at \(step): \(api)")
                }
            }
            return RollOutcome(status: "dispatched-unknown", detail: "one fixed Roll AXPress attempted; native edit unverified")
        } catch {
            let cause = (error as? FocusFailure)?.message ?? "Roll actor API result unknown"
            return RollOutcome(
                status: possibleEffect ? "dispatched-unknown" : "refused",
                detail: "last step \(step): \(cause)"
            )
        }
    }

    static func requireTarget(
        _ observation: FocusObservation, request: RollRequest, requireRoll: Bool
    ) throws {
        guard observation.pid == request.pid,
              observation.bundle == "com.blackmagic-design.DaVinciResolve",
              observation.title == request.windowName,
              observation.main, observation.foreground, observation.noModalOrSheet,
              !requireRoll || observation.rollEnabled else {
            throw FocusFailure.refused("exact PID/window/focus/modal/Roll readiness changed")
        }
    }
}
