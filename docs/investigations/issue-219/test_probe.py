"""Issue-owned refusal checks; no Resolve connection or template mutation."""

import copy
import unittest

import probe


class RefusalTests(unittest.TestCase):
    def setUp(self):
        self.case = copy.deepcopy(probe.CASES["overlap"])
        self.writes = []

    def attempt(self, case, **kwargs):
        probe.guarded_write(case, self.writes.append, **kwargs)

    def test_four_hardcoded_schedules_pass(self):
        for case in probe.CASES.values():
            probe.preflight(case)

    def test_unknown_target_state_and_empty_targets_refuse_without_writes(self):
        for targets, state in [
            (["missing"], "emphasis"),
            (["target-a"], "muted"),
            ([], "emphasis"),
        ]:
            case = copy.deepcopy(self.case)
            case["cues"][0]["targets"] = targets
            case["cues"][0]["state"] = state
            with self.assertRaises(ValueError):
                self.attempt(case)
            self.assertEqual(self.writes, [])

    def test_contradiction_refuses_entire_schedule_before_first_write(self):
        self.case["cues"].append(
            {
                "targets": ["target-a"],
                "state": "base",
                "start": 80,
                "end": 90,
                "timing": "interval",
            }
        )
        with self.assertRaisesRegex(ValueError, "contradictory"):
            self.attempt(self.case)
        self.assertEqual(self.writes, [])

    def test_bad_times_and_unordered_cues_refuse(self):
        for start, end in [(-1, 96), (48, 241), (72, 72), (True, 96), (48.5, 96)]:
            case = copy.deepcopy(self.case)
            case["cues"][0].update(start=start, end=end)
            with self.assertRaises(ValueError):
                self.attempt(case)
        self.case["cues"].reverse()
        with self.assertRaises(ValueError):
            self.attempt(self.case)
        self.assertEqual(self.writes, [])

    def test_start_only_requires_explicit_policy_and_boundaries(self):
        for timing, end in [("start-only", 72), ("until-next", 73), ("until-end", 239)]:
            case = copy.deepcopy(probe.CASES["start-only"])
            case["cues"][0].update(timing=timing, end=end)
            with self.assertRaises(ValueError):
                self.attempt(case)
        self.assertEqual(self.writes, [])

    def test_dataset_reorder_or_label_edit_invalidates_mapping(self):
        for data in [
            probe.DATA.replace("Alpha\t18\nBeta\t27", "Beta\t27\nAlpha\t18"),
            probe.DATA.replace("Alpha", "Renamed"),
        ]:
            with self.assertRaisesRegex(ValueError, "dataset"):
                self.attempt(self.case, data=data)
        self.assertEqual(self.writes, [])

    def test_manifest_graph_control_or_pin_mismatch_refuses(self):
        for kwargs in [
            {"manifest": "other"},
            {"graph_ok": False},
            {"control_type": "Number"},
            {"asset_hash": "0" * 64},
        ]:
            with self.assertRaises(ValueError):
                self.attempt(self.case, **kwargs)
        self.assertEqual(self.writes, [])

    def test_wrong_aggregate_cannot_clobber_active_target(self):
        self.case["steps"][2] = (72, "2")
        with self.assertRaisesRegex(ValueError, "aggregate"):
            self.attempt(self.case)
        self.assertEqual(self.writes, [])

    def test_continuation_has_no_base_write_at_touching_boundary(self):
        self.attempt(probe.CASES["continuation"])
        self.assertEqual(self.writes, [(0, ""), (48, "1"), (96, "")])


if __name__ == "__main__":
    unittest.main()
