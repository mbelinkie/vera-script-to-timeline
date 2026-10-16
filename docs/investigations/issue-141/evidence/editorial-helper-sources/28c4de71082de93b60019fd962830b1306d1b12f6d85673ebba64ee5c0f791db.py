"""Run the approved 25 nudges, with a complete native readback after each."""

import hashlib
import json
import subprocess
import sys
import time
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "out/issue-141-observation-20260930-01a0f318"
PLUGINS = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins"
)
CONFIG = PLUGINS / "vera-issue-141-observation.json"
HS = "/Applications/Hammerspoon.app/Contents/Frameworks/hs/hs"
MATRIX = "29ae8331-b86e-4041-a548-960695cc7b24"
UIDS = {
    "video": "9e990622-a172-4bab-96fc-1198d84b1279",
    "audio": "6f7c7dd4-9e80-444d-a4ae-b225cb5f5839",
}
OLD_SELECTION = {
    "36b5882f-d928-4424-b4a6-ee3f7dcc8e03",
    "17267938-81b0-4777-9db5-0a27d359dbfc",
}
PREPARATION = "editorial-case-20261001T060727.115823Z/result.json"
PREPARATION_SHA = "33136cd643c402835ad2c5daa4d26f92fd8f1d056887f002212e963befa5471b"
MACRO_SHA = "70015c4731538662ec66255861cd69a1b10577ad0caf86f85b4a7da666e6528c"
LAUNCH_SHA = "f3c9a76b5c95f6fbb04d546f33a5ae23d37579e8f890851a86f3daf9a9d5f5b1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_move(pair, frames):
    assert isinstance(frames, int) and 0 <= frames <= 25
    expected = deepcopy(pair)
    for state in expected["timelinePasses"]:
        matrices = [
            t for t in state["timelines"] if t["GetUniqueId"]["value"] == MATRIX
        ]
        assert len(matrices) == 1
        for kind, uid in UIDS.items():
            tracks = [
                t for t in matrices[0]["tracks"] if (t["type"], t["index"]) == (kind, 1)
            ]
            assert len(tracks) == 1
            items = [i for i in tracks[0]["items"] if i["GetUniqueId"]["value"] == uid]
            assert len(items) == 1
            item = items[0]
            assert item["GetStart"] == {"value": 1000}
            assert item["GetEnd"] == {"value": 1199}
            for key in ("GetStart", "GetStart(True)", "GetEnd", "GetEnd(True)"):
                item[key]["value"] += frames
    return expected


def verify(result, pair, expected, selected):
    assert result["status"] == "editorial-readback-retained"
    assert result["failure"] is None and result["readOnly"] is True
    assert result["environment"]["version"] == [21, 1, 0, 14, ""]
    assert pair == expected
    assert pair["selectedTimelineUid"] == MATRIX
    assert (
        pair["timelineConsistency"] == pair["poolConsistency"] == "equal-adjacent-reads"
    )
    assert pair["timelinePasses"][0] == pair["timelinePasses"][1]
    assert pair["poolPasses"][0] == pair["poolPasses"][1]
    assert len(result["selectionPasses"]) == 2
    assert result["selectionPasses"][0] == result["selectionPasses"][1]
    selection = result["selectionPasses"][0]
    assert selection["playhead"] == "00:00:44:00"
    ids = [i["GetUniqueId"]["value"] for i in selection["items"]]
    assert len(ids) == len(set(ids)) and set(ids) == selected


def run():
    assert PREPARATION != "PENDING"
    preparation_path = OUT / PREPARATION
    assert (
        not preparation_path.is_symlink() and sha(preparation_path) == PREPARATION_SHA
    )
    preparation = json.loads(preparation_path.read_text())
    assert preparation["status"] == "case-prepared" and preparation["case"] == "R1-move"
    assert preparation["target"]["uids"] == UIDS
    reference = preparation["preparedPair"]
    prepared_path = OUT / reference["path"]
    assert (
        prepared_path.resolve().is_relative_to(OUT.resolve())
        and not prepared_path.is_symlink()
    )
    assert sha(prepared_path) == reference["sha256"]
    prepared = json.loads(prepared_path.read_text())
    assert sha(HERE / "hammerspoon-editorial.lua") == MACRO_SHA
    assert sha(HERE / "hammerspoon-launch.lua") == LAUNCH_SHA
    probe_sha = sha(HERE / "probe.py")
    directory = OUT / datetime.now(UTC).strftime("r1-move-driver-%Y%m%dT%H%M%S.%fZ")
    directory.mkdir()
    journal = directory / "journal.jsonl"
    completed = 0

    def record(phase, value):
        with journal.open("a") as stream:
            stream.write(
                json.dumps(
                    {
                        "at": datetime.now(UTC).isoformat(),
                        "phase": phase,
                        "value": value,
                    }
                )
                + "\n"
            )

    def command(filename, action=None):
        assert filename in {"hammerspoon-launch.lua", "hammerspoon-editorial.lua"}
        assert sha(HERE / filename) == (LAUNCH_SHA if action is None else MACRO_SHA)
        if action is not None:
            assert action in {"deselect", "select", "nudge-right"}
        lua = f"return dofile({json.dumps(str(HERE / filename))}).run("
        lua += "" if action is None else json.dumps(action)
        lua += ")"
        record(
            "menu-request",
            {
                "source": filename,
                "sourceSha256": sha(HERE / filename),
                "namedCommand": action or "observation",
            },
        )
        returned = subprocess.run(
            [HS, "-c", lua], capture_output=True, text=True, timeout=10
        )
        record(
            "menu-return",
            {
                "exitCode": returned.returncode,
                "stdout": returned.stdout,
                "stderr": returned.stderr,
            },
        )
        assert returned.returncode == 0, "Menu refused; stop without retry"

    def observe(label, expected, selected):
        config = json.loads(CONFIG.read_text())
        assert (
            config["action"] == "observe"
            and config["externalScriptingSetting"] == "None"
        )
        assert sha(HERE / "probe.py") == config["probeSha256"] == probe_sha
        prior = set(PLUGINS.glob("vera-issue-141-observation-result-*.json"))
        config.update(action="editorial-readback", editorialReadbackLabel=label)
        CONFIG.write_text(json.dumps(config, indent=2) + "\n")
        command("hammerspoon-launch.lua")
        deadline = time.monotonic() + 50
        while time.monotonic() < deadline:
            fresh = (
                set(PLUGINS.glob("vera-issue-141-observation-result-*.json")) - prior
            )
            if fresh:
                assert len(fresh) == 1, "Multiple native results; stop"
                path = fresh.pop()
                try:
                    result = json.loads(path.read_text())
                except json.JSONDecodeError:
                    time.sleep(0.2)
                    continue
                record(
                    "native-result",
                    {
                        "path": path.name,
                        "sha256": sha(path),
                        "status": result.get("status"),
                    },
                )
                assert result.get("status") == "editorial-readback-retained", result
                pair_path = Path(result["pair"]["path"])
                assert (
                    pair_path.resolve().is_relative_to(OUT.resolve())
                    and not pair_path.is_symlink()
                )
                assert sha(pair_path) == result["pair"]["sha256"]
                pair = json.loads(pair_path.read_text())
                verify(result, pair, expected, selected)
                record(
                    "full-state-verified",
                    {
                        "pair": str(pair_path.relative_to(OUT)),
                        "sha256": sha(pair_path),
                        "selectedUids": sorted(selected),
                    },
                )
                return result
            time.sleep(0.25)
        raise RuntimeError("Native result pending; do not relaunch")

    def edit(action):
        assert json.loads(CONFIG.read_text())["action"] == "observe"
        command("hammerspoon-editorial.lua", action)

    outcome = {
        "status": "stopped-evidence-retained",
        "completedNudges": 0,
        "failure": None,
    }
    try:
        observe("r1-move-context", prepared, OLD_SELECTION)
        edit("deselect")
        observe("r1-move-deselected", prepared, set())
        edit("select")
        observe("r1-move-selected", prepared, set(UIDS.values()))
        for n in range(1, 26):
            edit("nudge-right")
            last = observe(
                "r1-move-edited", expected_move(prepared, n), set(UIDS.values())
            )
            completed = n
            print(json.dumps({"verifiedNudges": n, "total": 25}), flush=True)
        outcome.update(
            status="25-nudges-verified-restoration-pending", lastReadback=last["pair"]
        )
    except Exception as error:
        outcome["failure"] = f"{type(error).__name__}: {error}"
    outcome.update(
        completedNudges=completed,
        preparationSha256=PREPARATION_SHA,
        journal=str(journal),
    )
    (directory / "result.json").write_text(json.dumps(outcome, indent=2) + "\n")
    print(json.dumps(outcome), flush=True)
    if outcome["failure"]:
        raise SystemExit(1)


def demo():
    tracks = [
        {
            "type": kind,
            "index": 1,
            "items": [
                {
                    "GetUniqueId": {"value": uid},
                    "GetStart": {"value": 1000},
                    "GetStart(True)": {"value": 1000.0},
                    "GetEnd": {"value": 1199},
                    "GetEnd(True)": {"value": 1199.0},
                }
            ],
        }
        for kind, uid in UIDS.items()
    ]
    state = {"timelines": [{"GetUniqueId": {"value": MATRIX}, "tracks": tracks}]}
    pair = {
        "selectedTimelineUid": MATRIX,
        "timelineConsistency": "equal-adjacent-reads",
        "poolConsistency": "equal-adjacent-reads",
        "timelinePasses": [state, deepcopy(state)],
        "poolPasses": [{}, {}],
    }
    changed = expected_move(pair, 25)
    assert changed["timelinePasses"][0]["timelines"][0]["tracks"][0]["items"][0][
        "GetEnd"
    ] == {"value": 1224}
    selection = {
        "playhead": "00:00:44:00",
        "items": [{"GetUniqueId": {"value": uid}} for uid in UIDS.values()],
    }
    result = {
        "status": "editorial-readback-retained",
        "readOnly": True,
        "failure": None,
        "environment": {"version": [21, 1, 0, 14, ""]},
        "selectionPasses": [selection, deepcopy(selection)],
    }
    verify(result, changed, changed, set(UIDS.values()))
    for bad in (set(), {"other"}):
        try:
            verify(result, changed, changed, bad)
        except AssertionError:
            pass
        else:
            raise AssertionError("Incorrect selected IDs accepted")
    try:
        verify(result, changed, pair, set(UIDS.values()))
    except AssertionError:
        pass
    else:
        raise AssertionError("Unrelated full-state change accepted")
    print("Move driver arithmetic/selection/full-state guards pass; no native call.")


if __name__ == "__main__":
    demo() if sys.argv[1:] == ["--check"] else run()
