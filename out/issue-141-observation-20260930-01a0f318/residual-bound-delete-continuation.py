#!/usr/bin/env python3
"""Continue the already completed R2-residual two-cut experiment safely."""
import argparse, ast, hashlib, json
from pathlib import Path

OUT = Path(__file__).resolve().parent
RECORD = "residual-two-cut-continuation-record.json"
RECORD_SHA = "6b6cabe45187ad66530b39abeb6cff0abf4c0fd5071cf6a7c1fbfd303d7cb447"
import importlib.util
spec = importlib.util.spec_from_file_location("residual_sequence", OUT / "independent-residual-sequence.py")
seq = importlib.util.module_from_spec(spec); spec.loader.exec_module(seq)


def source_paths():
    return {
        "independent-native-call.py": OUT / "independent-native-call.py",
        "independent-residual-sequence.py": OUT / "independent-residual-sequence.py",
        "editorial-cases.py": seq.HERE / "editorial-cases.py",
        "probe.py": seq.HERE / "probe.py",
    }


def relative_output_path(value):
    path = Path(value)
    if path.is_absolute():
        path = path.resolve().relative_to(OUT.resolve())
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise RuntimeError("Evidence path is not a safe output-relative path")
    return str(path)


def review():
    _, r = seq.contained_record(RECORD, RECORD_SHA)
    if r.get("status") != "residual-two-cut-continuation" or r.get("case") != "R2-residual":
        raise ValueError("Pinned continuation record identity differs")
    sources = source_paths()
    if seq.sha(sources["independent-native-call.py"]) != seq.PINS["independent-native-call.py"]:
        raise RuntimeError("Independent native call source pin changed")
    native = seq.load("independent_native_call", sources["independent-native-call.py"])
    cases = seq.load("residual_editorial_cases", sources["editorial-cases.py"])
    probe = seq.load("residual_probe", sources["probe.py"]); reader = cases._reader(probe)
    values = {k: seq.contained_record(r[k]["path"], r[k]["sha256"])[1]
              for k in ("preparation", "position", "secondReadback", "secondReview", "selectionDiagnostic", "terminal")}
    prep, pos, read, rev, diag, terminal = (values[k] for k in ("preparation", "position", "secondReadback", "secondReview", "selectionDiagnostic", "terminal"))
    first_path = seq.bound_path(r["firstSplitPair"])
    if (prep.get("status") != "case-prepared" or prep.get("case") != "R2-residual"
        or prep.get("originalPlayhead") != "00:00:00:00" or prep.get("originalLocks") is None
        or pos.get("status") != "second-position-ready" or pos.get("case") != "R2-residual"
        or pos.get("preparationResult") != r["preparation"] or pos.get("firstSplitPair") != r["firstSplitPair"]
        or pos.get("target", {}).get("splitFrame") != 4570 or pos.get("menuCommandDispatched") is not False
        or read.get("status") != "editorial-readback-retained" or read.get("label") != "r2-residual-second-split"
        or read.get("readOnly") is not True or read.get("failure") is not None
        or rev.get("status") != "split-readback-retained" or rev.get("case") != "R2-residual"
        or rev.get("saveDispatched") is not False
        or diag.get("status") != "editorial-readback-retained" or diag.get("label") != "r2-residual-interval-selected"
        or "Resumed interval selection" not in terminal.get("failure", "")):
        raise ValueError("Pinned completed phase metadata is incomplete or inconsistent")
    first_pair = json.loads(first_path.read_text(encoding="utf-8"))
    second_ref = read.get("pair", {})
    second_pair = json.loads(seq.bound_path(second_ref).read_text(encoding="utf-8"))
    if rev.get("splitPair",{}).get("sha256") != second_ref.get("sha256"):
        raise ValueError("Successful second review is not bound to the pinned second-split pair")
    pstate, ppool = reader._validate_read_pair(first_pair, probe)
    sstate, spool = reader._validate_read_pair(second_pair, probe)
    children = cases._named_linked_children(prep, pstate, ppool, sstate, spool, reader, "R2-residual", "second")
    child_ids = {k: [x["GetUniqueId"]["value"] for x in v] for k, v in children.items()}
    if (rev.get("childUids") != child_ids
        or rev.get("ranges") != [[4500,4560,0,60],[4560,4570,60,70],[4570,4699,70,199]]
        or pos.get("target", {}).get("firstSplitUids") != {
            k: [x["GetUniqueId"]["value"] for x in cases._named_linked_children(prep,pstate,ppool,pstate,ppool,reader,"R2-residual","first")[k]] for k in ("video","audio")
        }):
        raise ValueError("Second-cut child derivation differs from reviewed split")
    diagnostic_pair=diag.get("pair",{})
    diagnostic_passes=diag.get("selectionPasses",[])
    selected=[[i.get("GetUniqueId",{}).get("value") for i in p.get("items",[])] for p in diagnostic_passes]
    if (diagnostic_pair.get("sha256") != second_ref.get("sha256") or len(diagnostic_passes)!=2
        or len(selected[0]) != 2 or selected[1] != selected[0]
        or any(p.get("playhead")!="00:03:02:20" for p in diagnostic_passes)):
        raise ValueError("Recorded UI selection diagnostic is not stable against the second-split pair")
    passes = read.get("selectionPasses", [])
    if len(passes) != 2 or any(x.get("playhead") != "00:03:02:20" for x in passes):
        raise ValueError("Second-split pair does not retain frame 4570 twice")
    registration=json.loads((OUT/"residual-position-source-registration.json").read_text())
    actual={n:seq.sha(p) for n,p in sources.items()}
    registered=registration.get("hashes",{})
    identity={n:registered.get(n)==h for n,h in actual.items()}
    return r, prep, pos, read, rev, diag, native, child_ids, identity


def pre_dispatch(identity, native, sources):
    """Run main's local guards before the first Resolve dispatch."""
    if not all(identity.values()):
        raise RuntimeError("Source registration is stale; refresh reviewed pins before --run")
    native.assert_dispatch_module("editorial-readback")
    tree = ast.parse(sources["probe.py"].read_text(encoding="utf-8"))
    tables = [
        ast.literal_eval(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "owned_modules"
                for target in node.targets)
    ]
    cases_pin = seq.sha(sources["editorial-cases.py"])
    if len(tables) != 1 or tables[0].get("editorial-case-prepare") != (
        "editorial-cases.py", cases_pin
    ):
        raise RuntimeError("Probe dispatcher does not pin the registered editorial case helper")


def write_index(directory, status, phases, **extra):
    payload = {
        "schema": "issue141-residual-bound-driver-execution-index/v1",
        "status": status,
        "nativeDispatched": bool(extra.pop("nativeDispatched", False)),
        "phases": phases,
        **extra,
    }
    path = directory / "execution-index.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": str(path.resolve().relative_to(OUT.resolve())), "sha256": seq.sha(path)}


def main():
    ap = argparse.ArgumentParser(); group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true"); group.add_argument("--run", action="store_true")
    args = ap.parse_args(); r, prep, pos, read, rev, diag, native, children, identity = review()
    sources = source_paths()
    result = {"status":"local-check-passed", "record":{"path":RECORD,"sha256":RECORD_SHA},
              "preparation":r["preparation"],"firstSplitPair":r["firstSplitPair"],"position":r["position"],
              "secondReadback":r["secondReadback"],"secondReview":r["secondReview"],
              "selectionDiagnostic":r["selectionDiagnostic"],"terminal":r["terminal"],
              "childTargetUids":{k:[v[1]] for k,v in children.items()},"sourceRegistrationMatches":identity,"nativeDispatched":False}
    if args.check:
        pre_dispatch(identity, native, sources)
        try:
            seq.contained_record(RECORD, "0" * 64)
        except ValueError:
            pass
        else:
            raise AssertionError("Mismatched record hash accepted")
        out = OUT / "residual-bound-driver-local-result.json"
        out.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8")
        print("R2 residual continuation record, source pins, child derivation and mismatch refusal passed; no native action.")
        return
    pre_dispatch(identity, native, sources)
    directory = OUT / "residual-bound-delete-continuation-r2"
    directory.mkdir(exist_ok=True)
    phases = []
    native_dispatched = False
    write_index(directory, "ready", phases, nativeDispatched=native_dispatched)
    try:
        phases.append({"name": "fresh-context-readback", "status": "dispatching"})
        native_dispatched = True
        write_index(directory, "running", phases, nativeDispatched=native_dispatched)
        fresh_ref, fresh, fresh_pair_path, fresh_sha = seq.readback(native, OUT, "r2-residual-context")
        phases[-1].update(status="complete", evidence=fresh_ref)
        write_index(directory, "running", phases, nativeDispatched=native_dispatched)
        if fresh_sha != read.get("pair", {}).get("sha256"):
            raise RuntimeError("Fresh context differs from completed second-split pair")
        passes = fresh.get("selectionPasses", [])
        if len(passes) != 2 or any(x.get("playhead") != "00:03:02:20" for x in passes):
            raise RuntimeError("Fresh context does not retain frame 4570 twice")
        phases.append({"name": "interval-delete", "status": "dispatching"})
        write_index(directory, "running", phases, nativeDispatched=native_dispatched)
        second_split_path = relative_output_path(read["pair"]["path"])
        delete = native.invoke({"action":"r2-linked-interval-delete","case":"R2-residual",
            "preparationResult":r["preparation"]["path"],"preparationResultSha256":r["preparation"]["sha256"],
            "firstSplitPair":r["firstSplitPair"]["path"],"firstSplitPairSha256":r["firstSplitPair"]["sha256"],
            "secondPositionResult":r["position"]["path"],"secondPositionResultSha256":r["position"]["sha256"],
            "secondSplitPair":second_split_path,"secondSplitPairSha256":read["pair"]["sha256"],
            "selectionResult":r["selectionDiagnostic"]["path"],"selectionResultSha256":r["selectionDiagnostic"]["sha256"]})
        delete_ref, delete = seq.save(directory,"interval-delete.json",delete)
        phases[-1].update(
            status=("complete" if delete.get("status") == "interval-deleted-unsaved" else "failed"),
            evidence=delete_ref,
            resultStatus=delete.get("status"),
        )
        write_index(directory, "running", phases, nativeDispatched=native_dispatched)
        if delete.get("status") != "interval-deleted-unsaved" or delete.get("saveDispatched") is not False:
            raise RuntimeError("Interval delete refused or save was dispatched")
        after = delete.get("afterPair", {}); seq.bound_path(after)
        phases.append({"name": "deleted-state-readback", "status": "dispatching"})
        write_index(directory, "running", phases, nativeDispatched=native_dispatched)
        deleted_ref, deleted, _, deleted_sha = seq.readback(native, directory, "r2-residual-deleted")
        phases[-1].update(status="complete", evidence=deleted_ref)
        write_index(directory, "running", phases, nativeDispatched=native_dispatched)
        if deleted_sha != after.get("sha256"):
            raise RuntimeError("Deleted-state fresh pair differs from delete.afterPair")
        phases.append({"name": "editorial-case-restore", "status": "dispatching"})
        write_index(directory, "running", phases, nativeDispatched=native_dispatched)
        restored = native.invoke({"action":"editorial-case-restore","case":"R2-residual",
            "preparationResult":r["preparation"]["path"],"preparationResultSha256":r["preparation"]["sha256"],
            "postEditPair":after["path"],"postEditPairSha256":after["sha256"]})
        restore_ref, restored = seq.save(directory,"restoration.json",restored)
        phases[-1].update(status="complete", evidence=restore_ref)
        write_index(directory, "running", phases, nativeDispatched=native_dispatched)
        if restored.get("status") != "restored-unsaved" or restored.get("originalLocks") != prep.get("originalLocks") or restored.get("originalPlayhead") != "00:00:00:00" or restored.get("saveDispatched") is not False:
            raise RuntimeError("Original locks/playhead restoration failed")
        phases.append({"name": "context-restoration-and-final-readback", "status": "dispatching"})
        write_index(directory, "running", phases, nativeDispatched=native_dispatched)
        for menu in ("auto-none","auto-v1","auto-a1","deselect"): native.invoke(menu=menu)
        final_ref, final, _, final_sha = seq.readback(native,directory,"r2-residual-context")
        phases[-1].update(status="complete", evidence=final_ref)
        write_index(directory, "running", phases, nativeDispatched=native_dispatched)
        fp = final.get("selectionPasses", [])
        if final_sha != restored.get("restoredPair",{}).get("sha256") or len(fp)!=2 or any(x.get("items") != [] or x.get("playhead") != "00:00:00:00" for x in fp):
            raise RuntimeError("Final restored context verification failed")
        result.update(status="complete",nativeDispatched=True,freshContext=fresh_ref,intervalDelete=delete_ref,
            deletedReadback=deleted_ref,restoration=restore_ref,finalReadback=final_ref,finalPairSha256=final_sha,
            skippedCompletedSteps=["preparation","first cut","second positioning","second cut"],saveDispatched=False,
            executionIndex=write_index(directory, "complete", phases, nativeDispatched=native_dispatched))
        (OUT/"residual-bound-driver-local-result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print(json.dumps(result,indent=2,sort_keys=True))
    except Exception as error:
        index = write_index(directory, "native-failed", phases, nativeDispatched=native_dispatched,
            failure=f"{type(error).__name__}: {error}")
        result.update(status="native-failed", nativeDispatched=native_dispatched,
            executionIndex=index, failure=f"{type(error).__name__}: {error}")
        (OUT/"residual-bound-driver-local-result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        raise

if __name__ == "__main__": main()
