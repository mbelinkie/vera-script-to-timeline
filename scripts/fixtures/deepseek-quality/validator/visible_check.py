import copy
import unittest

from target import solve


class ValidatorCheck(unittest.TestCase):
    def test_inclusive_boundaries_are_valid(self):
        self.assertEqual(
            solve({"start_frame": 0, "duration_frames": 1, "track": 1}),
            {"valid": True, "errors": []},
        )
        self.assertEqual(
            solve(
                {
                    "start_frame": 1_000_000,
                    "duration_frames": 180_000,
                    "track": 16,
                }
            ),
            {"valid": True, "errors": []},
        )

    def test_boolean_is_not_accepted_as_an_integer(self):
        self.assertEqual(
            solve({"start_frame": True, "duration_frames": 10, "track": 2}),
            {"valid": False, "errors": ["start_frame:type"]},
        )

    def test_exact_keys_and_range_errors(self):
        self.assertEqual(
            solve(
                {
                    "start_frame": -1,
                    "duration_frames": 0,
                    "track": 17,
                    "extra": "no",
                }
            ),
            {"valid": False, "errors": ["keys"]},
        )
        self.assertEqual(
            solve({"start_frame": -1, "duration_frames": 0, "track": 17}),
            {
                "valid": False,
                "errors": [
                    "start_frame:range",
                    "duration_frames:range",
                    "track:range",
                ],
            },
        )

    def test_input_is_not_mutated(self):
        payload = {"start_frame": 12, "duration_frames": 24, "track": 3}
        before = copy.deepcopy(payload)
        solve(payload)
        self.assertEqual(payload, before)


if __name__ == "__main__":
    unittest.main()
