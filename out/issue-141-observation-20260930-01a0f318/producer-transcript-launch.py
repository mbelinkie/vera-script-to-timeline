"""One read-only supplemental dispatch; restore the paused configuration."""
import hashlib,json,pathlib,subprocess,sys,time
from datetime import UTC,datetime
OUT=pathlib.Path(__file__).resolve().parent
PLUGIN=pathlib.Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins")
CONFIG=PLUGIN/"vera-issue-141-observation.json"
ROOT=OUT.parents[1]
MODULE=OUT/"producer-transcript-probe.py"
HS="/Applications/Hammerspoon.app/Contents/Frameworks/hs/hs"
MACRO=ROOT/"docs/investigations/issue-141/hammerspoon-launch.lua"
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def run(digest):
    assert not MODULE.is_symlink() and sha(MODULE)==digest
    assert sha(MACRO)=="f3c9a76b5c95f6fbb04d546f33a5ae23d37579e8f890851a86f3daf9a9d5f5b1"
    original=CONFIG.read_bytes(); before=json.loads(original)
    assert before["action"]=="observe" and before["externalScriptingSetting"]=="None"
    assert before["projectName"]=="VERA Issue 141 Synthetic Probe 20260930-01a0f318"
    audit=OUT/("producer-transcript-dispatch-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ"));audit.mkdir()
    (audit/"previous-config.json").write_bytes(original)
    staged={**before,"action":"producer-transcript-probe","probePath":str(MODULE),"probeSha256":digest}
    (audit/"staged-config.json").write_text(json.dumps(staged,indent=2)+"\n")
    prior=set(PLUGIN.glob("vera-issue-141-observation-result-*.json"))
    CONFIG.write_text(json.dumps(staged,indent=2)+"\n")
    try:
        lua="return dofile("+json.dumps(str(MACRO))+").run()"
        returned=subprocess.run([HS,"-c",lua],capture_output=True,text=True,timeout=10)
        (audit/"dispatch.json").write_text(json.dumps({"exitCode":returned.returncode,"stdout":returned.stdout,"stderr":returned.stderr},indent=2)+"\n")
        if returned.returncode: raise RuntimeError("Exact menu dispatch refused; no retry")
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            fresh=set(PLUGIN.glob("vera-issue-141-observation-result-*.json"))-prior
            if fresh:
                assert len(fresh)==1,"Multiple new results; retain and stop"
                path=fresh.pop()
                try: result=json.loads(path.read_text())
                except json.JSONDecodeError: time.sleep(.2);continue
                ref={"path":str(path),"sha256":sha(path),"status":result.get("status")}
                (audit/"result-reference.json").write_text(json.dumps(ref,indent=2)+"\n")
                print(json.dumps({"auditDirectory":str(audit),"result":ref}));return
            time.sleep(.2)
        raise RuntimeError("Native result pending; do not redispatch; inspect retained progress")
    finally:
        live=json.loads(CONFIG.read_text())
        disarmed={**staged,"action":"observe","stage":"baseline-repeat"}
        if live not in (staged,disarmed): raise RuntimeError("Private config changed unexpectedly; retain and stop")
        CONFIG.write_bytes(original)
        (audit/"configuration-restored.json").write_text(json.dumps({"restored":CONFIG.read_bytes()==original,"action":"observe"})+"\n")
if __name__=="__main__":
    assert len(sys.argv)==2,"Pass independently checked module SHA256"
    run(sys.argv[1])
