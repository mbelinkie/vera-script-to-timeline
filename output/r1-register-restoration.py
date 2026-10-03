"""Reuse the retained registration audit for the reviewed restoration route."""
import ast
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "registration", Path(__file__).with_name("r1-register-reviewed.py")
)
registration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registration)
registration.EXPECTED_PROBE = "fdd2d31024a005489564e99bb4916e190e5830e26705b87ea6e56adbcf9e918b"
registration.EXPECTED_CALLER = "395805068e96517bfe67aa32497229226b6c7fad431790e1cac94f4ecaf5cd03"
OLD_HELPER = registration.HELPER_HASH
RESTORE = "r1-repeat-restore-selection"
registration.ACTIONS = (*registration.ACTIONS, RESTORE)


def transform(probe_source, caller_source):
    def extend(source, indent):
        return registration.replace_once(
            source, indent + '"r1-repeat-duplicate",\n',
            indent + '"r1-repeat-duplicate",\n' + indent + '"' + RESTORE + '",\n',
            "restoration route",
        )
    # The config allowlist and runtime gate are separate exact occurrences.
    start = probe_source.index('elif config["action"] in {')
    probe_new = extend(probe_source[:start], "        ") + extend(
        probe_source[start:], "        "
    )
    assert probe_new.count(OLD_HELPER) == 2
    probe_new = probe_new.replace(OLD_HELPER, registration.HELPER_HASH)
    probe_new = registration.replace_once(
        probe_new,
        f'            "r1-repeat-duplicate": ("r1-repeat-six.py", "{registration.HELPER_HASH}"),\n',
        f'            "r1-repeat-duplicate": ("r1-repeat-six.py", "{registration.HELPER_HASH}"),\n'
        f'            "{RESTORE}": ("r1-repeat-six.py", "{registration.HELPER_HASH}"),\n',
        "probe restoration pin",
    )
    assert caller_source.count(OLD_HELPER) == 2
    caller_new = caller_source.replace(OLD_HELPER, registration.HELPER_HASH)
    caller_new = registration.replace_once(
        caller_new, '    "r1-repeat-reopen", "r1-repeat-duplicate",\n',
        '    "r1-repeat-reopen", "r1-repeat-duplicate", "' + RESTORE + '",\n',
        "caller action",
    )
    caller_new = registration.replace_once(
        caller_new,
        f'    "r1-repeat-duplicate": ("r1-repeat-six.py", "{registration.HELPER_HASH}"),\n',
        f'    "r1-repeat-duplicate": ("r1-repeat-six.py", "{registration.HELPER_HASH}"),\n'
        f'    "{RESTORE}": ("r1-repeat-six.py", "{registration.HELPER_HASH}"),\n',
        "caller restoration pin",
    )
    caller_new = registration.replace_once(
        caller_new, '{"r1-repeat-reopen", "r1-repeat-duplicate"}',
        '{"r1-repeat-reopen", "r1-repeat-duplicate", "' + RESTORE + '"}',
        "exact case allowance",
    )
    caller_new = registration.replace_once(
        caller_new, '    assert_dispatch_module("r1-repeat-duplicate")\n',
        '    assert_dispatch_module("r1-repeat-duplicate")\n'
        f'    validate({{"action": "{RESTORE}", "case": "R1-repeat-six"}}, None)\n'
        f'    assert_dispatch_module("{RESTORE}")\n', "focused caller check",
    )
    ast.parse(probe_new)
    ast.parse(caller_new)
    return probe_new, caller_new


if __name__ == "__main__":
    # Exact reviewed helper hash is supplied by the coordinator, never inferred
    # from an unreviewed candidate on disk.
    if len(sys.argv) not in {2, 3} or len(sys.argv[1]) != 64:
        raise SystemExit("Usage: r1-register-restoration.py REVIEWED_HELPER_SHA [--check]")
    registration.HELPER_HASH = sys.argv.pop(1)
    registration.transform = transform
    registration.main()
