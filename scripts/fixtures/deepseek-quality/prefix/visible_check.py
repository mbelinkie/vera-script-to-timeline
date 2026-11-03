import copy
import unittest

from target import solve


class PrefixCheck(unittest.TestCase):
    def test_first_interrupted_join_stops_the_prefix(self):
        payload = {
            "covered_ids": ["A", "B", "C", "D", "E"],
            "current_order": ["A", "B", "C", "E", "D"],
            "review": {"state": "current", "note": "keep"},
            "settings": {"audio_gain": -4, "captions": True},
        }
        self.assertEqual(
            solve(payload),
            {
                "retained_ids": ["A", "B", "C"],
                "review": payload["review"],
                "settings": payload["settings"],
            },
        )

    def test_unrelated_ids_do_not_break_a_moved_run(self):
        payload = {
            "covered_ids": ["one", "two", "three"],
            "current_order": [
                "outside-before",
                "one",
                "outside-middle",
                "two",
                "three",
                "outside-after",
            ],
            "review": {"state": "clear"},
            "settings": {"color": {"temperature": 5200}},
        }
        self.assertEqual(
            solve(payload),
            {
                "retained_ids": ["one", "two", "three"],
                "review": payload["review"],
                "settings": payload["settings"],
            },
        )

    def test_input_is_not_mutated(self):
        payload = {
            "covered_ids": ["x", "y"],
            "current_order": ["y", "x"],
            "review": {"state": "legacy-review-alert", "metadata": {"seen": False}},
            "settings": {"unrelated": [1, 2]},
        }
        before = copy.deepcopy(payload)
        solve(payload)
        self.assertEqual(payload, before)


if __name__ == "__main__":
    unittest.main()
