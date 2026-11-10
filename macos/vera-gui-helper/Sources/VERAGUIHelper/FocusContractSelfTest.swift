// Standalone pure Swift test executable, not compiled into the signed helper.
// This does not launch an application, ask for Accessibility or inspect Resolve.
import Foundation

@main
enum FocusContractSelfTest {
    private static var verified = 0

    private static func demand(_ condition: Bool, _ name: String) {
        guard condition else { fatalError("FOCUS_CONTRACT_FAILED: " + name) }
        verified += 1
    }

    private static func refuses(_ raw: Data, _ name: String) {
        do {
            _ = try FocusRequest(raw)
            fatalError("FOCUS_CONTRACT_ACCEPTED_UNSAFE: " + name)
        } catch is FocusFailure {
            verified += 1
        } catch {
            fatalError("FOCUS_CONTRACT_UNEXPECTED_ERROR: " + name)
        }
    }

    private static func canonical(_ object: [String: Any]) -> Data {
        let data = try! JSONSerialization.data(
            withJSONObject: object, options: [.sortedKeys, .withoutEscapingSlashes]
        )
        return data + Data([10])
    }

    static func main() {
        let dateFormatter = ISO8601DateFormatter()
        dateFormatter.formatOptions = [.withInternetDateTime]
        let request: [String: Any] = [
            "schema": "vera.gui-helper-focus-request/v1",
            "requestId": "test-phase3-request-001",
            "deadlineAt": dateFormatter.string(
                from: Date().addingTimeInterval(45)
            ),
            "operation": "inspect",
            "resolvePid": 5182,
            "resolveBundleIdentifier": "com.blackmagic-design.DaVinciResolve",
            "windowName": "VERA Delivery disposable-window",
        ]
        do {
            let parsed = try FocusRequest(canonical(request))
            demand(parsed.operation == "inspect", "inspect accepted")
            demand(parsed.resolvePid == 5182, "PID bound")
        } catch {
            fatalError("VALID_REQUEST_REFUSED: " + String(describing: error))
        }
        var focus = request
        focus["operation"] = "focus"
        demand((try? FocusRequest(canonical(focus))) != nil, "bounded focus accepted")
        for (key, value) in [
            ("operation", "roll"),
            ("resolveBundleIdentifier", "com.apple.finder"),
            ("windowName", ""),
            ("requestId", "../unsafe"),
            ("deadlineAt", "2020-01-01T00:00:00Z"),
        ] {
            var modified = request
            modified[key] = value
            refuses(canonical(modified), "bad " + key)
        }
        var boolPid = request
        boolPid["resolvePid"] = true
        refuses(canonical(boolPid), "boolean PID")
        var fractionalPid = request
        fractionalPid["resolvePid"] = 5182.5
        refuses(canonical(fractionalPid), "fractional PID")
        var missing = request
        missing.removeValue(forKey: "resolvePid")
        refuses(canonical(missing), "missing PID")
        var extra = request
        extra["shellCommand"] = "echo no"
        refuses(canonical(extra), "extra arbitrary effect")
        let plain = canonical(request)
        refuses(Data(plain.dropLast()), "missing canonical newline")
        refuses(Data(plain.dropLast()) + Data([32, 10]), "noncanonical whitespace")
        // Inject a missing Accessibility grant: no OS permission changes,
        // prompts or UI actions are needed to prove fail-closed admission.
        do {
            try TargetInspection.requireAccessibility(trusted: { false })
            fatalError("ACCESSIBILITY_MISSING_BUT_ACCEPTED")
        } catch is FocusFailure {
            verified += 1
        } catch {
            fatalError("ACCESSIBILITY_UNEXPECTED_ERROR")
        }
        do {
            try TargetInspection.requireAccessibility(trusted: { true })
            verified += 1
        } catch {
            fatalError("ACCESSIBILITY_PRESENT_REFUSED")
        }
        print("FOCUS_CONTRACT_SELFTEST_PASS \(verified) assertions")
    }
}
