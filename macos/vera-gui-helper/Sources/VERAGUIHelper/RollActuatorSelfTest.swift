// Native Swift unit tests: injected AX, no real Resolve, no prompt or AXPress.
import Foundation

@main
enum RollActuatorSelfTest {
    static var assertions = 0

    static func check(_ okay: Bool, _ label: String) {
        guard okay else { fatalError("ROLL_SELFTEST_FAILED: " + label) }
        assertions += 1
    }

    static func canonical(_ value: [String: Any]) -> Data {
        try! JSONSerialization.data(
            withJSONObject: value, options: [.sortedKeys, .withoutEscapingSlashes]
        ) + Data([10])
    }

    static func request(_ id: Int) -> RollRequest {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        let record: [String: Any] = [
            "schema": "vera.gui-helper-request/v1",
            "requestId": "roll-request-\(id)",
            "deadlineAt": formatter.string(from: Date().addingTimeInterval(100)),
            "operation": "M4.edited.roll-start-to-playhead",
            "jobId": "fixture-job-001",
            "stageOperationId": "fixture-edited-001",
            "fixtureId": "synthetic-312",
            "trialId": "fixture-trial-\(id)",
            "resolvePid": 5182,
            "windowName": "VERA Delivery disposable-window",
            "projectUid": "project-native-001",
            "timelineUid": "timeline-native-001",
            "sourceGraphSha256": String(repeating: "a", count: 64),
            "actorPin": [
                "schema": "vera.gui-helper-actor/v1",
                "sourceManifestSha256": String(repeating: "b", count: 64),
                "binary": [
                    "executablePath": "/tmp/VERA GUI Helper.app/Contents/MacOS/VERAGUIHelper",
                    "sha256": String(repeating: "c", count: 64),
                    "codeDirectoryHash": String(repeating: "d", count: 40),
                    "designatedRequirement": "identifier \"org.vera.resolve-test-bench.gui\" and anchor apple generic",
                    "teamIdentifier": "D3Z8Y24NKY",
                    "bundleIdentifier": "org.vera.resolve-test-bench.gui",
                ],
            ],
            "pristineCaptureSha256": String(repeating: "e", count: 64),
            "oneUseIntentSha256": String(format: "%064x", id),
            "authoritySha256": String(repeating: "f", count: 64),
        ]
        return try! RollRequest(canonical(record))
    }

    final class Shared {
        var spent = Set<String>()
    }

    final class Journal: RollAudit {
        let shared: Shared
        var events = [String]()
        var throwAt: String?
        init(_ shared: Shared) { self.shared = shared }
        func claim(_ request: RollRequest) throws -> Bool {
            if shared.spent.contains(request.intentDigest) { return false }
            shared.spent.insert(request.intentDigest)
            return true
        }
        func note(_ request: RollRequest, step: String, event: String, api: Int32?) throws {
            events.append("\(step):\(event):\(api.map(String.init) ?? "-")")
            if "\(step):\(event)" == throwAt {
                throw FocusFailure.refused("simulated write/crash boundary")
            }
        }
    }

    struct Pins: RollPins {
        var allow = true
        func verify(_ request: RollRequest) throws {
            guard allow,
                  request.value["sourceGraphSha256"] as? String == String(repeating: "a", count: 64),
                  request.actorPin["sourceManifestSha256"] as? String == String(repeating: "b", count: 64)
            else { throw FocusFailure.refused("source/actor pin drift") }
        }
    }

    final class AX: RollAccessibility {
        var presses = [[String]]()
        var queries = [[String]]()
        var observations = 0
        var disabled = Set<Int>()
        var missingStep: Int?
        var duplicateStep: Int?
        var loseAtObservation: Int?
        var modalAtObservation: Int?
        var replaceAtObservation: Int?
        var crashOnPress: Int?
        var apiOnPress: Int?

        func observe(_ request: RollRequest) throws -> FocusObservation {
            observations += 1
            return FocusObservation(
                pid: observations == replaceAtObservation ? 9999 : request.pid,
                bundle: "com.blackmagic-design.DaVinciResolve",
                title: request.windowName,
                main: true,
                foreground: observations != loseAtObservation,
                noModalOrSheet: observations != modalAtObservation,
                rollEnabled: true
            )
        }
        func enabled(_ request: RollRequest, path: [String]) throws -> Bool {
            queries.append(path)
            let step = queries.count
            if step == missingStep { throw FocusFailure.refused("missing menu path") }
            if step == duplicateStep { throw FocusFailure.refused("duplicate menu path") }
            return !disabled.contains(step)
        }
        func press(_ request: RollRequest, path: [String]) throws -> Int32 {
            presses.append(path)
            if presses.count == crashOnPress { throw FocusFailure.refused("simulated AX timeout/crash") }
            if presses.count == apiOnPress { return -25202 }
            return 0
        }
    }

    static func main() {
        var n = 101
        func fresh() -> RollRequest { n += 1; return request(n) }
        do {
            let original = fresh()
            check(original.pid == 5182 && original.windowName.contains("Delivery"), "exact target parsed")
            var altered = original.value
            altered["operation"] = "run-osascript"
            check((try? RollRequest(canonical(altered))) == nil, "alternate action refused")
            altered = original.value
            altered["menuPath"] = ["Trim", "Roll"]
            check((try? RollRequest(canonical(altered))) == nil, "caller-supplied menu refused")
            altered = original.value
            altered["sourceGraphSha256"] = "bad"
            check((try? RollRequest(canonical(altered))) == nil, "source pin syntax refused")
            altered = original.value
            altered["resolvePid"] = true
            check((try? RollRequest(canonical(altered))) == nil, "boolean PID refused")
            altered = original.value
            altered["windowName"] = "Café non-ascii"
            check((try? RollRequest(canonical(altered))) == nil,
                  "non-ASCII window refused before any GUI claim")
            altered = original.value
            altered["deadlineAt"] = "2020-01-01T00:00:00Z"
            check((try? RollRequest(canonical(altered))) == nil, "expired Roll refused")
            check((try? RollRequest(Data(canonical(original.value).dropLast()))) == nil,
                  "noncanonical Roll refused")

            // Separate verify-only protocol may authenticate the SAME Swift
            // source/actor pins, but may NEVER enter FixedRoll.execute.
            var probeValue = original.value
            probeValue["operation"] = "M4.edited.verify-actor-no-edit"
            let probeRaw = canonical(probeValue)
            check(RollRequest.digest(canonical(original.actorPin)) ==
                  "9cbc933da7d23e0cb76b0996eeac3913ace4906e25423e1cd9da82c842e27f3c",
                  "actor canonical SHA256 equals Python queue.canonical golden")
            check((try? RollRequest(probeRaw)) == nil, "no-edit request refused by Roll parser")
            check((try? RollRequest(probeRaw, pinProbeOnly: true)) != nil,
                  "closed no-edit probe parser accepted")
            check((try? RollRequest(canonical(original.value), pinProbeOnly: true)) == nil,
                  "Roll action cannot impersonate no-edit pin probe")

            let req = fresh()
            let ax = AX(); let shared = Shared(); let journal = Journal(shared)
            let outcome = FixedRoll.execute(req, accessibility: ax, journal: journal, pins: Pins())
            check(outcome.status == "dispatched-unknown", "Roll never claims native success")
            check(ax.presses == FixedRoll.setupPaths + [FixedRoll.rollPath], "exact literal five actions")
            check(ax.queries == FixedRoll.setupPaths + [FixedRoll.rollPath], "resolve menu fresh per step")
            check(ax.presses.filter { $0 == FixedRoll.rollPath }.count == 1, "one Roll maximum")
            check(ax.presses[1] == ["Timeline", "Auto Select", "Auto Deselect All Tracks"], "absolute all-off first")
            check(ax.presses[2] == ["Timeline", "Auto Select", "Auto Select/Deselect V1"], "V1 toggle after all-off")
            check(journal.events.contains("roll:press-attempted:-") && journal.events.contains("roll:api-result:0"),
                  "attempted step and individual API result persisted")
            let replayAX = AX()
            check(FixedRoll.execute(req, accessibility: replayAX,
                                    journal: Journal(shared), pins: Pins()).status == "refused" && replayAX.presses.isEmpty,
                  "spent intent not replayed after simulated restart")

            let skipped = AX(); skipped.disabled.insert(1)
            let skipResult = FixedRoll.execute(fresh(), accessibility: skipped,
                                               journal: Journal(Shared()), pins: Pins())
            check(skipResult.status == "dispatched-unknown", "optional disabled Deselect All may skip")
            check(skipped.presses == Array(FixedRoll.setupPaths.dropFirst()) + [FixedRoll.rollPath],
                  "disabled Deselect All skipped, absolute all-off retained")
            for step in 2...5 {
                let ax = AX(); ax.disabled.insert(step)
                let result = FixedRoll.execute(fresh(), accessibility: ax,
                                               journal: Journal(Shared()), pins: Pins())
                check(result.status != "ready" && !ax.presses.contains(FixedRoll.rollPath),
                      "required disabled path fails at \(step)")
            }
            for step in 1...5 {
                for variant in 0...1 {
                    let ax = AX()
                    if variant == 0 { ax.missingStep = step } else { ax.duplicateStep = step }
                    let result = FixedRoll.execute(fresh(), accessibility: ax,
                                                   journal: Journal(Shared()), pins: Pins())
                    check(result.status != "ready" && !ax.presses.contains(FixedRoll.rollPath),
                          "missing/duplicate path fails at \(step)")
                }
            }
            for breakAt in [1, 2, 3, 4, 5, 6, 8, 10] {
                for variant in 0...2 {
                    let ax = AX()
                    if variant == 0 { ax.loseAtObservation = breakAt }
                    if variant == 1 { ax.modalAtObservation = breakAt }
                    if variant == 2 { ax.replaceAtObservation = breakAt }
                    let result = FixedRoll.execute(fresh(), accessibility: ax,
                                                   journal: Journal(Shared()), pins: Pins())
                    check(result.status != "ready" && !ax.presses.contains(FixedRoll.rollPath),
                          "focus/modal/process drift stops before Roll")
                }
            }
            let denied = AX()
            check(FixedRoll.execute(fresh(), accessibility: denied,
                                    journal: Journal(Shared()), pins: Pins(allow: false)).status == "refused" &&
                  denied.presses.isEmpty, "source/actor pin gate precedes any action")
            for crash in 1...5 {
                let old = fresh(); let shared = Shared(); let ax = AX(); ax.crashOnPress = crash
                let first = FixedRoll.execute(old, accessibility: ax,
                                              journal: Journal(shared), pins: Pins())
                check(first.status == "dispatched-unknown", "crash/timeout after attempt is UNKNOWN")
                let restarted = AX()
                check(FixedRoll.execute(old, accessibility: restarted,
                                        journal: Journal(shared), pins: Pins()).status == "refused" &&
                      restarted.presses.isEmpty, "crash step \(crash) cannot replay after restart")
            }
            for crash in 1...5 {
                let old = fresh(); let shared = Shared(); let firstAX = AX()
                let journal = Journal(shared)
                journal.throwAt = (crash == 5 ? "roll" : "setup-\(crash)") + ":press-attempted"
                _ = FixedRoll.execute(old, accessibility: firstAX, journal: journal, pins: Pins())
                let restarted = AX()
                check(FixedRoll.execute(old, accessibility: restarted,
                                        journal: Journal(shared), pins: Pins()).status == "refused" &&
                      restarted.presses.isEmpty, "journal interrupted at step \(crash) cannot replay")
            }
            let failed = AX(); failed.apiOnPress = 1
            let failedReq = fresh(); let failureShared = Shared()
            let bad = FixedRoll.execute(failedReq, accessibility: failed,
                                        journal: Journal(failureShared), pins: Pins())
            check(bad.status == "dispatched-unknown" && failed.presses.count == 1,
                  "ambiguous AX return stops without retry")
            check(FixedRoll.execute(failedReq, accessibility: AX(),
                                    journal: Journal(failureShared), pins: Pins()).status == "refused",
                  "ambiguous AX result remains consumed")

            let temp = FileManager.default.temporaryDirectory.appendingPathComponent("vera-roll-sim-" + UUID().uuidString)
            try FileManager.default.createDirectory(at: temp, withIntermediateDirectories: false)
            defer { try? FileManager.default.removeItem(at: temp) }
            let durableReq = fresh()
            let durable = DurableRollJournal(directory: temp)
            check(try durable.claim(durableReq), "O_EXCL durable first claim")
            try durable.note(durableReq, step: "setup-1", event: "press-attempted", api: nil)
            try durable.note(durableReq, step: "setup-1", event: "api-result", api: -25202)
            check(try !DurableRollJournal(directory: temp).claim(durableReq), "physical journal remains spent after reopen")
            let events = try String(contentsOf: temp.appendingPathComponent(
                "intent-" + durableReq.intentDigest + ".roll-events.jsonl"), encoding: .utf8)
            check(events.contains("press-attempted") && events.contains("-25202"), "durable API status and attempted step")
            print("ROLL_ACTUATOR_SELFTEST_PASS \(assertions) assertions (injected AX only)")
        } catch {
            fatalError("ROLL_ACTUATOR_UNEXPECTED_ERROR: " + String(describing: error))
        }
    }
}
