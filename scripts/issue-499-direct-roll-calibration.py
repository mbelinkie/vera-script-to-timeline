#!/usr/bin/env python3
"""One authorized #499 disposable direct-Roll calibration; NEVER a M4 receipt.

Only one new, name-pinned synthetic case is permitted. Each mutating phase
has a durable pre-effect intent: an interrupted phase is UNKNOWN, not retryable.
There is exactly one GUI roll command, no Nudge/recovery/edit replay. The
existing #473 native owner is required for every Resolve interaction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import time
from pathlib import Path
from typing import Any

from vera_timeline_agent import resolve_native_owner as owner
from vera_timeline_agent.resolve_test_bench_gui_stage import _read_only_playhead_frame

NAME = "VERA Delivery 75ba39c0-4c56-4d85-ac88-58f0092163a8 c191e694fc19"
BASE_COMMIT = "bbe5c64be58e0c841a985ea6a5aed41b3372a873"
GRAPH = "54ffaaeef7d5f21a631f9aa478a98c431e0cd3e0a9831f454306b170b5821ba1"
ROOT = Path.home() / ".local/state/vera/issue-499-one-roll-75ba39c0"
AUTH = ROOT.with_name(ROOT.name + "-authority.json")
EXPECTED = (("video", 1, "Root"), ("video", 2, "Overlay"),
            ("video", 3, "Presenter"), ("video", 4, "Placeholder"),
            ("video", 5, "Markers"), ("audio", 1, "Narration"))
EVENTS = (
    ("video", 1, 0, 327, "root"), ("video", 1, 327, 151, "root"),
    ("video", 1, 478, 237, "root"), ("video", 1, 715, 214, "root"),
    ("video", 1, 929, 261, "root"), ("video", 1, 1190, 217, "root"),
    ("video", 2, 71, 47, "overlay"), ("video", 2, 800, 70, "overlay"),
    ("audio", 1, 0, 478, "audio"), ("audio", 1, 478, 452, "audio"),
    ("audio", 1, 930, 477, "audio"),
)
ROLL = Path(__file__).with_name("issue-499-direct-roll-once.applescript")
SETUP = Path(__file__).with_name("issue-499-direct-roll-setup.applescript")


def need(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError("#499 calibrated Roll REFUSED: " + message)


def raw(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(file: Path) -> dict[str, Any]:
    need(file.is_file() and not file.is_symlink(), "missing one-use evidence: " + file.name)
    data = file.read_bytes()
    need(len(data) < 40000, "unbounded evidence file")
    obj = json.loads(data)
    need(type(obj) is dict and data == raw(obj), "noncanonical evidence")
    return obj


def once(file: Path, obj: dict[str, Any]) -> None:
    need(not file.exists() and not file.is_symlink(), "spent intent: " + file.name)
    fd = os.open(file, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw(obj))
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(file.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def sealed() -> dict[str, Any]:
    need(ROOT.is_dir() and not ROOT.is_symlink(), "private case root absent")
    st = ROOT.stat()
    need(st.st_uid == os.getuid() and stat.S_IMODE(st.st_mode) == 0o700,
         "private root ownership/permissions differ")
    need(AUTH.is_file() and not AUTH.is_symlink()
         and AUTH.stat().st_uid == os.getuid()
         and stat.S_IMODE(AUTH.stat().st_mode) == 0o600,
         "case authority owner/mode not private")
    auth = read(AUTH)
    worktree = Path(__file__).resolve().parents[1]
    rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                         cwd=worktree, text=True, check=True, timeout=8).stdout.strip()
    need(auth == {
        "schema": "vera.issue499.direct-roll-calibration.authority/v1",
        "projectName": NAME,
        "baseCommit": BASE_COMMIT,
        "checkoutCommit": rev,
        "sourceGraphSha256": GRAPH,
        "pythonSha256": digest(Path(__file__).read_bytes()),
        "setupSha256": digest(SETUP.read_bytes()),
        "rollSha256": digest(ROLL.read_bytes()),
        "authorized": "one_new_disposable_project_and_at_most_one_roll_start_to_playhead",
    }, "actor/source hash or explicit one-case authorization differs")
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", BASE_COMMIT, rev],
                              cwd=worktree, capture_output=True, timeout=8, check=False)
    need(ancestor.returncode == 0, "new calibration is not descended from adopted #499 branch")
    status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                            cwd=worktree, capture_output=True, text=True, check=True, timeout=8)
    need(status.stdout == "", "tracked source files changed after actor review")
    from vera_timeline_agent.resolve_test_bench_full_loop import _source_hash
    need(_source_hash() == GRAPH, "native source graph changed")
    return auth


def connected() -> Any:
    resolve = owner._local_resolve_connection()
    need(resolve is not None and resolve.GetVersion()[:4] == [21, 1, 1, 10],
         "wrong installed Studio 21.1.1.10 connection")
    return resolve


def selected(resolve: Any, receipt: dict[str, Any]) -> tuple[Any, Any, Any]:
    manager = resolve.GetProjectManager()
    project = manager.GetCurrentProject() if manager else None
    timeline = project.GetCurrentTimeline() if project else None
    need(project is not None and timeline is not None
         and project.GetName() == NAME and project.GetUniqueId() == receipt["projectUid"]
         and timeline.GetName() == NAME and timeline.GetUniqueId() == receipt["timelineUid"]
         and project.IsRenderingInProgress() is False,
         "exact newly authorized native project/timeline identity differs")
    return manager, project, timeline


def snapshot(tl: Any) -> dict[str, Any]:
    result: list[dict[str, Any]] = []
    tracks: list[dict[str, Any]] = []
    need(all(tl.GetTrackCount(k) == n for k, n in
             (("video", 5), ("audio", 1), ("subtitle", 0))),
         "unexpected track count")
    for kind, index, name in EXPECTED:
        locked = tl.GetIsTrackLocked(kind, index)
        need(locked is ((kind, index) != ("video", 1)), "SDK track lock differs")
        need(tl.GetTrackName(kind, index) == name, "track name changed")
        tracks.append({"kind": kind, "index": index, "name": name, "locked": locked})
        clips = tl.GetItemListInTrack(kind, index)
        need(type(clips) in {tuple, list} and len(clips) <= 11,
             "native item list is unreadable")
        for item in clips:
            media = item.GetMediaPoolItem()
            links = item.GetLinkedItems()
            need(media is not None and isinstance(links, (list, tuple)),
                 "native media/links unavailable")
            result.append({
                "uid": item.GetUniqueId(), "mediaUid": media.GetUniqueId(),
                "kind": kind, "track": index, "recordStart": item.GetStart(False),
                "recordDuration": item.GetDuration(False),
                "sourceStart": item.GetSourceStartFrame(),
                "sourceEnd": item.GetSourceEndFrame(),
                "links": sorted(v.GetUniqueId() for v in links),
            })
    result.sort(key=lambda x: (x["kind"], x["track"], x["recordStart"], x["uid"]))
    need(len(result) == 11 and len({x["uid"] for x in result}) == 11,
         "exactly 11 unique native item UIDs required")
    return {"tracks": tracks, "items": result}


def baseline_match(tl: Any) -> dict[str, Any]:
    expected = read(ROOT / "pristine.json")["native"]
    actual = snapshot(tl)
    need(actual == expected, "live eleven UID / six track baseline differs")
    video = sorted((x for x in actual["items"] if x["kind"] == "video" and x["track"] == 1),
                   key=lambda x: x["recordStart"])
    need([(x["recordStart"], x["recordDuration"]) for x in video]
         == [(0,327),(327,151),(478,237),(715,214),(929,261),(1190,217)],
         "unique source frame 327 V1 picture cut missing")
    need(all(not x["links"] for x in actual["items"]), "linked clip could move")
    return actual


def generate_assets() -> None:
    need(not ROOT.exists() and not ROOT.is_symlink(), "new case already reserved")
    need(AUTH.is_file() and not AUTH.is_symlink(), "case authority must exist BEFORE asset setup")
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=False)
    # Requires prior review/frozen external authority; assets never touch Resolve.
    sealed()
    assets = ROOT / "assets"
    assets.mkdir(mode=0o700)
    ffmpeg = "/usr/local/bin/ffmpeg"
    for colour, name in (("red", "root"), ("blue", "overlay")):
        dest = assets / (name + ".mp4")
        subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                        f"color=c={colour}:s=320x180:r=24000/1001", "-frames:v", "720",
                        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                        "-an", str(dest)], check=True, timeout=25)
    dest = assets / "audio.wav"
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=48000", "-t", "65", "-ac", "2",
                    "-c:a", "pcm_s16le", str(dest)], check=True, timeout=25)
    for name in ("root.mp4", "overlay.mp4", "audio.wav"):
        # Real 720-frame 320x180 solid-colour H.264 from installed ffmpeg is
        # ~12.8 KiB; its 720 decoded frames were independently ffprobed.
        # Native clip-property frame-count is checked again before Roll.
        need((assets / name).stat().st_size > 2000, "synthetic media missing")
    once(ROOT / "assets.json", {name: digest((assets / name).read_bytes()) for name in
                                ("root.mp4", "overlay.mp4", "audio.wav")})


def construct() -> None:
    sealed()
    assets = read(ROOT / "assets.json")
    for name, sha in assets.items():
        need(digest((ROOT / "assets" / name).read_bytes()) == sha,
             "synthetic source digest differs")
    need(not (ROOT / "provision-intent.json").exists(), "prior creation is UNKNOWN")
    with owner.native_owner(output_lane=True):
        owner.preflight_independent_disposable(NAME)
        resolve = connected()
        once(ROOT / "provision-intent.json", {"operation": "create_and_populate_one_new_case", "name": NAME})
        from vera_timeline_agent.resolve_test_queue_m4_provision import _new_target
        original_manager = resolve.GetProjectManager()
        original_folder = original_manager.GetCurrentFolder()
        need(type(original_folder) is str and bool(original_folder),
             "original project folder getter unavailable")
        p_uid, t_uid = _new_target(resolve, NAME)
        receipt = {"projectUid": p_uid, "timelineUid": t_uid, "folder": original_folder}
        manager, project, tl = selected(resolve, receipt)
        need(tl.SetStartTimecode("00:00:00:00") is True,
             "new synthetic zero timeline origin refused")
        for kind, index, name in EXPECTED:
            while tl.GetTrackCount(kind) < index:
                need((tl.AddTrack(kind, "stereo") if kind == "audio" else tl.AddTrack(kind)) is True,
                     "native AddTrack refused")
            need(tl.SetTrackName(kind, index, name) is True, "native SetTrackName refused")
        pool = project.GetMediaPool()
        files = {k: ROOT / "assets" / f"{k}.{ext}" for k,ext in
                 (("root","mp4"),("overlay","mp4"),("audio","wav"))}
        imported = pool.ImportMedia([str(files[k]) for k in ("root","overlay","audio")])
        need(type(imported) in {list, tuple} and len(imported) == 3,
             "fresh synthetic media import failed")
        by_path = {str(Path(m.GetClipProperty()["File Path"]).resolve()): m for m in imported}
        need(set(by_path) == {str(v.resolve()) for v in files.values()},
             "Resolve imported unexpected media")
        for kind,index,start,duration,media_key in EVENTS:
            media=by_path[str(files[media_key].resolve())]
            info={"mediaPoolItem":media,"startFrame":0,"endFrame":duration,
                  "mediaType":2 if kind=="audio" else 1,
                  "trackIndex":index,"recordFrame":start}
            placed=pool.AppendToTimeline([info])
            need(type(placed) in {tuple,list} and len(placed)==1,
                 "native synthetic append did not produce exactly one item")
            item=placed[0]
            need(item.GetStart(False)==start and item.GetDuration(False)==duration,
                 "new synthetic native clip record range differs")
        for kind,index,_name in EXPECTED:
            lock = (kind,index)!=("video",1)
            need(tl.SetTrackLock(kind,index,lock) is True and
                 tl.GetIsTrackLocked(kind,index) is lock,
                 "new synthetic track containment lock refused")
        captured=snapshot(tl)
        need(manager.GetCurrentProject().GetUniqueId()==p_uid and
             project.IsRenderingInProgress() is False,"save identity/render changed")
        need(manager.SaveProject() is True,"new synthetic project save refused")
        once(ROOT / "pristine.json", {"target":receipt,"native":captured,
                                      "assets":assets,"sourceCommit":BASE_COMMIT,"graph":GRAPH})
        print(json.dumps({"status":"new_synthetic_saved","target":receipt,
                          "pristineSha256":digest(raw(read(ROOT/"pristine.json")))}, sort_keys=True))


def invoke(file: Path, pid: int) -> dict[str, Any]:
    # Snapshot the exact reviewed UTF-8 bytes ONCE and pass them by argv to
    # osascript. The actor never rereads a file after hash verification.
    authority=read(AUTH)
    field="setupSha256" if file == SETUP else "rollSha256"
    script=file.read_bytes()
    need(digest(script)==authority[field] and b"\x00" not in script,
         "reviewed OS actor changed immediately before invocation")
    r = subprocess.run(["/usr/bin/osascript", "-e", script.decode("utf-8"), str(pid), NAME],
                       capture_output=True, text=True, timeout=25, check=False)
    return {"exitCode": r.returncode, "stdout": r.stdout[:2000], "stderr": r.stderr[:2000]}


def current_pid() -> int:
    # Do not activate a process on this path: only accept the explicitly
    # source-matched synthetic target already in front, not any active project.
    proc = subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", "-e",
                           'ObjC.import("AppKit");var w=$.NSWorkspace.sharedWorkspace;'
                           'var a=w.frontmostApplication;JSON.stringify({'
                           'pid:Number(a.processIdentifier),bundle:ObjC.unwrap(a.bundleIdentifier)})'],
                          capture_output=True,text=True,timeout=10,check=True)
    info = json.loads(proc.stdout)
    need(info.get("bundle")=="com.blackmagic-design.DaVinciResolve" and
         type(info.get("pid")) is int and info["pid"]>0,
         "correct Resolve app is not already foreground")
    return info["pid"]


def no_prompt_tcc() -> None:
    # The installed JXA client checks Apple Event Automation without ever
    # requesting access. Python itself separately needs AX trust for this host.
    import ctypes
    ax=ctypes.CDLL("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
    ax.AXIsProcessTrusted.restype=ctypes.c_bool
    need(ax.AXIsProcessTrusted() is True,"native actor has no Accessibility trust")
    source=(
        'ObjC.import("AppKit");ObjC.import("Carbon");'
        'ObjC.bindFunction("AEDeterminePermissionToAutomateTarget",'
        '["int",["void*","uint32_t","uint32_t","bool"]]);'
        'var d=$.NSAppleEventDescriptor.descriptorWithBundleIdentifier('
        '$("com.apple.systemevents"));'
        '$.AEDeterminePermissionToAutomateTarget(d.aeDesc,0x2a2a2a2a,0x2a2a2a2a,false)'
    )
    proc=subprocess.run(["/usr/bin/osascript","-l","JavaScript","-e",source],
                        capture_output=True,text=True,timeout=10,check=True)
    need(proc.stdout.strip()=="0","Automation permission absent/UNKNOWN; no prompt")


def activate_exact_synthetic(resolve: Any, target: dict[str, Any]) -> int:
    # Activation is permitted ONLY after the SDK confirms the signed NEW
    # project, and is a single window activation, never a project load/edit.
    selected(resolve, target)
    source = (
        'ObjC.import("AppKit");var w=$.NSWorkspace.sharedWorkspace;'
        'var a=ObjC.unwrap(w.runningApplications).filter(function(x){'
        'return ObjC.unwrap(x.bundleIdentifier)==="com.blackmagic-design.DaVinciResolve";});'
        'if(a.length!==1)throw Error("Resolve process ambiguous");'
        'a[0].activateWithOptions(3);Number(a[0].processIdentifier)'
    )
    proc = subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", "-e", source],
                          capture_output=True, text=True, timeout=10, check=True)
    pid = int(proc.stdout.strip())
    for _ in range(5):
        try:
            if current_pid() == pid:
                selected(resolve, target)
                return pid
        except RuntimeError:
            pass
        time.sleep(0.3)
    raise RuntimeError("Resolve exact synthetic window activation unproven")


def prepare() -> None:
    sealed()
    need(not (ROOT/"setup-intent.json").exists(),"UI setup already attempted or UNKNOWN")
    with owner.native_owner(output_lane=True):
        resolve=connected()
        target=read(ROOT/"pristine.json")["target"]
        _mgr,_project,tl=selected(resolve,target)
        baseline_match(tl)
        need(resolve.OpenPage("edit") is True and resolve.GetCurrentPage()=="edit",
             "new synthetic Edit-page open failed")
        need(tl.SetCurrentTimecode("00:00:14:15") is True and
             _read_only_playhead_frame(tl)==351,
             "new synthetic frame 351 navigation failed")
        # A newly appended clip can remain selected in Resolve. Deselect All
        # is deliberately part of the one-use setup, so require the *after*
        # getter to be empty rather than refusing harmless initial selection.
        need(type(tl.GetSelectedClips()) is list,"selected-clip API unavailable")
        no_prompt_tcc()
        once(ROOT/"activation-intent.json", {"target":target,"operation":"activate_one_synthetic_window"})
        pid=activate_exact_synthetic(resolve, target)
        once(ROOT/"setup-intent.json", {"pid":pid,"name":NAME,"scriptSha256":digest(SETUP.read_bytes())})
        observed=invoke(SETUP,pid)
        once(ROOT/"setup-result.json",observed)
        need(observed["exitCode"]==0,"GUI track-selection setup uncertain; no retry")
        selected(resolve,target)
        need(resolve.GetCurrentPage()=="edit" and _read_only_playhead_frame(tl)==351,
             "SDK Edit page/playhead drift after setup")
        need(tl.GetSelectedClips()==[],"unexpected selected clips after setup")
        baseline_match(tl)
        once(ROOT/"ready.json", {"pid":pid,"target":target,"baselineSha256":digest(raw(read(ROOT/"pristine.json")))})
        print(json.dumps({"status":"native_synthetic_ui_setup_ready","pid":pid,"geometryUnchanged":True},sort_keys=True))


def attempt() -> None:
    sealed()
    ready=read(ROOT/"ready.json")
    need(not (ROOT/"roll-intent.json").exists(),"one-use Roll already attempted or UNKNOWN")
    with owner.native_owner(output_lane=True):
        resolve=connected()
        target=read(ROOT/"pristine.json")["target"]
        mgr,project,tl=selected(resolve,target)
        before=baseline_match(tl)
        need(ready["target"]==target and ready["baselineSha256"]==digest(raw(read(ROOT/"pristine.json"))),
             "new case target/signature changed")
        need(resolve.GetCurrentPage()=="edit" and _read_only_playhead_frame(tl)==351,
             "Edit page/playhead changed before one-use Roll")
        need(tl.GetSelectedClips()==[],"whole clips selected; Roll targeting not bounded")
        need(current_pid()==ready["pid"],"frontmost Resolve PID changed")
        need(mgr.GetCurrentFolder()==target["folder"],"project folder changed after construction")
        video=[i for i in before["items"] if i["kind"]=="video" and i["track"]==1]
        left=next(i for i in video if i["recordStart"]==0 and i["recordDuration"]==327)
        right=next(i for i in video if i["recordStart"]==327 and i["recordDuration"]==151)
        need(sum(i["recordStart"]<=351<i["recordStart"]+i["recordDuration"] for i in video)==1,
             "no unique V1 picture at frame 351")
        need(left["links"]==right["links"]==[] and left["sourceStart"]==right["sourceStart"]==0,
             "linked/trimmed boundary ambiguous")
        # Read real imported video length, not the selected clip's used source range.
        clip=next((item for item in tl.GetItemListInTrack("video",1)
                   if item.GetUniqueId()==left["uid"]),None)
        need(clip is not None,"left native source not found")
        frames=clip.GetMediaPoolItem().GetClipProperty().get("Frames")
        need(type(frames) is str and frames.isdigit() and int(frames)>=351,
             "24-frame left source handle unverified")
        once(ROOT/"roll-intent.json", {"operation":"exact_one_Trim_Roll_Start_to_Playhead",
             "pid":ready["pid"],"target":target,"baselineSha256":ready["baselineSha256"],
             "scriptSha256":digest(ROLL.read_bytes()),"from":327,"to":351})
        try:
            result=invoke(ROLL,ready["pid"])
        except Exception as e:
            result={"exitCode":None,"error":type(e).__name__+": "+str(e)}
        once(ROOT/"roll-transport-result.json",result)
        # osascript can return before Resolve commits the actual edit. Observe
        # only; never issue another UI event or re-dispatch the one-use Roll.
        after: dict[str, Any] | None = None
        read_error: str | None = None
        for _ in range(20):
            try:
                selected(resolve,target)
                candidate=snapshot(tl)
                after=candidate
                now={item["uid"]:item for item in candidate["items"]}
                if now.get(left["uid"],{}).get("recordDuration")!=327:
                    break
            except Exception as e:
                read_error=type(e).__name__+": "+str(e)
                break
            time.sleep(0.25)
        once(ROOT/"post-roll-observation.json", {"target":target,"before":before,
             "after":after,"readError":read_error,"transport":result})
        need(after is not None and read_error is None,
             "post-Roll native state unreadable; no retry or save")
        need(result.get("exitCode")==0,"Roll command UNKNOWN; no retry, no save")
        old={item["uid"]:item for item in before["items"]}
        new={item["uid"]:item for item in after["items"]}
        need(old.keys()==new.keys(),"native item UIDs changed after Roll")
        for uid in old:
            if uid not in {left["uid"],right["uid"]}:
                need(old[uid]==new[uid],"other native clip changed; stop")
        need(new[left["uid"]]["recordStart"]==0 and new[left["uid"]]["recordDuration"]==351
             and new[right["uid"]]["recordStart"]==351
             and new[right["uid"]]["recordDuration"]==127,
             "exact 327 to 351 Roll was not measured; UNKNOWN")
        need(after["tracks"]==before["tracks"],"track state changed unexpectedly")
        need(new[left["uid"]]["mediaUid"]==left["mediaUid"] and
             new[right["uid"]]["mediaUid"]==right["mediaUid"],
             "source media changed")
        for old,new_item in ((left,new[left["uid"]]),(right,new[right["uid"]])):
            need(all(new_item[k]==old[k] for k in ("uid","kind","track","mediaUid","links")),
                 "boundary native identity/track/links/source changed")
        need(new[left["uid"]]["sourceStart"]==left["sourceStart"] and
             new[left["uid"]]["sourceEnd"]==left["sourceEnd"]+24,
             "left source handle did not advance exactly 24")
        # Different Resolve versions may keep or advance right source-in;
        # report the actual value. Neither form is automatically accepted
        # as M4: canonical verifier currently requires unchanged sourceStart.
        need(new[right["uid"]]["sourceEnd"]==right["sourceEnd"]
             and new[right["uid"]]["sourceStart"] in
             {right["sourceStart"],right["sourceStart"]+24},
             "right source range changed beyond one known 24-frame Roll")
        # Save only after exact observed frame/UID checks. Never save an
        # altered Producer project or normalize an UNKNOWN source transfer.
        need(mgr.GetCurrentProject().GetUniqueId()==target["projectUid"] and
             project.IsRenderingInProgress() is False,"target changed before SaveProject")
        once(ROOT/"save-reopen-intent.json", {"target":target,"operation":"verify_saved_native_roll"})
        need(mgr.SaveProject() is True,"new synthetic Roll save refused")
        once(ROOT/"saved.json", {"target":target,"saved":True})
        need(mgr.CloseProject(project) is True,"new synthetic project close refused")
        once(ROOT/"closed.json", {"target":target,"closed":True})
        need(mgr.GetCurrentFolder()==target["folder"],"project folder changed before reload")
        reopened=mgr.LoadProject(NAME)
        need(reopened is not None,"new synthetic project reload refused")
        _mgr2,_project2,tl2=selected(resolve,target)
        reopen=snapshot(tl2)
        once(ROOT/"reopened.json", {"target":target,"native":reopen})
        need(reopen==after,"new native Roll did not survive Save/Close/Load")
        print(json.dumps({"status":"one_direct_roll_native_reopened_observed",
            "leftUid":left["uid"],"rightUid":right["uid"],
            "rightSourceStartBefore":right["sourceStart"],
            "rightSourceStartAfter":new[right["uid"]]["sourceStart"],
            "m4Acceptance":False,"sourceGraph":GRAPH},sort_keys=True))


def audit() -> None:
    sealed()
    print(json.dumps({p.name:read(p) for p in sorted(ROOT.glob("*.json")) if p.name!="authority.json"},sort_keys=True))


if __name__ == "__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action",choices=("assets","construct","prepare","attempt","audit"))
    args=cli.parse_args()
    {"assets":generate_assets,"construct":construct,"prepare":prepare,
     "attempt":attempt,"audit":audit}[args.action]()
