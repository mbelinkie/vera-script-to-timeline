"""Offline consistency check for issue141 owned-module dispatch registration."""
import ast
from pathlib import Path


def check(source):
    tree = ast.parse(source)
    owned = aliases = runtime = allowed = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Set):
            try:
                value = ast.literal_eval(node)
            except (ValueError, TypeError):
                continue
            if {"prepare", "observe", "av-output"} <= value:
                allowed = value
        if isinstance(node, ast.Assign):
            names = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if "owned_modules" in names:
                owned = ast.literal_eval(node.value)
            if "module_key" in names and isinstance(node.value, ast.Call):
                aliases = ast.literal_eval(node.value.func.value)
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
            and len(node.test.comparators) == 1
            and isinstance(node.test.comparators[0], ast.Set)):
            try:
                value = ast.literal_eval(node.test.comparators[0])
            except (ValueError, TypeError):
                continue
            if "av-output" in value and "r4-wrong-bytes" in value:
                runtime = value
    assert all(x is not None for x in (owned, aliases, runtime, allowed))
    assert set(owned) | set(aliases) == runtime, (set(owned) | set(aliases)) ^ runtime
    assert runtime <= allowed, runtime - allowed
    assert set(aliases.values()) <= set(owned)
    assert "av-output-full-matrix-continue" in runtime
    return len(runtime)


def demo():
    source = Path(__file__).with_name("probe.py").read_text()
    count = check(source)
    start = source.index('elif config["action"] in {')
    broken = source[:start] + source[start:].replace('"av-output-full-matrix-continue",\n', '', 1)
    assert broken != source
    try:
        check(broken)
    except AssertionError:
        pass
    else:
        raise AssertionError("A mapped but undispatched action was accepted")
    print(f"{count} owned dispatch routes consistent; missing-route regression refused. No native calls.")


if __name__ == "__main__":
    demo()
