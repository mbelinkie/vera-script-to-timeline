"""Frozen standard-library acceptance check for target.py.

Load only the explicit sibling target under Python isolated mode. This harness
does not import the repository or add project paths to sys.path.
"""

import runpy
import unittest
from pathlib import Path

TARGET_PATH = Path(__file__).resolve().with_name("target.py")
TARGET_NAMESPACE = runpy.run_path(str(TARGET_PATH))
safe_relative_path = TARGET_NAMESPACE.get("safe_relative_path")
if not callable(safe_relative_path):
    raise RuntimeError("target.py must define safe_relative_path(value: object) -> str")


class SafeRelativePathTests(unittest.TestCase):
    def assert_accepted(self, value: str) -> None:
        self.assertEqual(safe_relative_path(value), value)

    def assert_rejected(self, value: object) -> None:
        with self.subTest(value=repr(value)), self.assertRaises(ValueError):
            safe_relative_path(value)

    def test_accepts_one_relative_segment_unchanged(self) -> None:
        for value in ("README.md", "config.json", "folder"):
            self.assert_accepted(value)

    def test_accepts_nested_relative_posix_path_unchanged(self) -> None:
        self.assert_accepted("src/package/module.py")

    def test_preserves_ordinary_dots_inside_filenames(self) -> None:
        for value in ("release.v1.tar.gz", "folder/.env.example", "name..suffix"):
            self.assert_accepted(value)

    def test_preserves_spaces_in_path_segments(self) -> None:
        for value in ("folder with spaces/file name.py", "two words/a b.txt"):
            self.assert_accepted(value)

    def test_reserved_names_are_case_sensitive(self) -> None:
        for value in (
            ".Git/config",
            ".Github/workflows/a.yml",
            "a/.github/workflows/a.yml",
            ".githubish/file",
        ):
            self.assert_accepted(value)

    def test_rejects_non_strings(self) -> None:
        for value in (None, 1, 1.0, b"path", [], {}):
            self.assert_rejected(value)

    def test_rejects_empty_and_whitespace_only_values(self) -> None:
        for value in ("", " ", "   ", "\u2003"):
            self.assert_rejected(value)

    def test_rejects_absolute_posix_paths(self) -> None:
        for value in ("/file", "//host/share", "/"):
            self.assert_rejected(value)

    def test_rejects_leading_tilde(self) -> None:
        for value in ("~", "~/file", "~alice/file"):
            self.assert_rejected(value)

    def test_rejects_backslashes_anywhere(self) -> None:
        for value in ("a\\b", "folder\\file", "\\rooted"):
            self.assert_rejected(value)

    def test_rejects_colons_anywhere(self) -> None:
        for value in ("a:b", "C:/file", "folder/name:stream"):
            self.assert_rejected(value)

    def test_rejects_ascii_controls_below_space_and_delete(self) -> None:
        for codepoint in (*range(32), 127):
            self.assert_rejected("safe" + chr(codepoint) + "name")

    def test_rejects_empty_segments(self) -> None:
        for value in ("a//b", "a/", "a///b"):
            self.assert_rejected(value)

    def test_rejects_dot_segments(self) -> None:
        for value in (".", "./a", "a/./b", "a/."):
            self.assert_rejected(value)

    def test_rejects_parent_segments(self) -> None:
        for value in ("..", "../a", "a/../b", "a/.."):
            self.assert_rejected(value)

    def test_rejects_git_directory_segment_at_any_depth(self) -> None:
        for value in (".git", ".git/config", "a/.git", "a/.git/config"):
            self.assert_rejected(value)

    def test_rejects_github_directory_only_at_top_level(self) -> None:
        for value in (".github", ".github/workflows/a.yml"):
            self.assert_rejected(value)


if __name__ == "__main__":
    unittest.main(failfast=True, verbosity=1)
