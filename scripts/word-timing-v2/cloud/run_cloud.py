#!/usr/bin/env python3
"""Cloud ASR runners for the word-timing v2 study (T-C sources / A-CLOUD timings).

Usage: run_cloud.py --audio X.wav --out-dir D [--providers eleven-or,assemblyai,...] [--tag T-C]

Sends the whole file, as lossless FLAC 48 kHz mono, to each provider. Nothing but
audio and fixed provider params is ever sent (no script, transcript or prompts). With --keyterms FILE, ONLY the
"keyterms" list of that prompter.json is also sent, via each provider's own vocabulary feature;
outputs get a -kt suffix (T-C-<id>-kt.json, raw-<id>-kt.json).
Writes D/raw-<id>.json and D/T-C-<id>.json. Keys come from the worktree .env and are
never printed or saved. Plain HTTPS via urllib only.
"""
import argparse, base64, datetime, hashlib, json, os, subprocess, sys, tempfile, time, uuid
import urllib.error, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV_PATH = HERE.parents[2] / ".env"
GCP_PROJECT = "vera-word-timing"
ALL = ["eleven-or", "assemblyai", "deepgram", "speechmatics", "revai", "chirp3", "chirp2"]
SECRETS: list[str] = []


def load_env() -> dict:
    env = {}
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    SECRETS.extend(v for v in env.values() if len(v) >= 8)
    return env


def scrub(s) -> str:
    s = str(s)
    for sec in SECRETS:
        s = s.replace(sec, "<redacted>")
    return s


class ApiError(Exception):
    pass


def http(method, url, headers=None, body=None, timeout=600, raw=False):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        raise ApiError(scrub(f"HTTP {e.code} {method} {url.split('?')[0]}: {e.read()[:600].decode('utf8', 'replace')}"))
    except Exception as e:
        raise ApiError(scrub(f"{type(e).__name__} {method} {url.split('?')[0]}: {e}"))
    return data if raw else json.loads(data)


def multipart(fields: dict, files: dict):
    """fields: name->str ; files: name->(filename, bytes, mime)"""
    b = "----vera" + uuid.uuid4().hex
    out = b""
    for k, v in fields.items():
        out += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, (fn, data, mime) in files.items():
        out += f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{fn}"\r\nContent-Type: {mime}\r\n\r\n'.encode() + data + b"\r\n"
    out += f"--{b}--\r\n".encode()
    return out, f"multipart/form-data; boundary={b}"


def ms(x):
    return None if x is None else round(float(x), 3)


def mk_result(pid, provider, model, words, transcript, params, api_version, started, wall, audio, endpoint, notes):
    return {"source": f"T-C-{pid}", "provider": provider, "model": model, "words": words, "transcript": transcript,
            "provenance": {"params": params, "apiVersion": api_version, "requestedAt": started, "wallSeconds": round(wall, 1),
                           "audioSent": audio, "endpoint": endpoint, "notes": notes}}


def number(words):
    for i, w in enumerate(words):
        w["k"] = i
    return words


# ---------- providers: each returns (raw, normalised_kwargs) ----------

def run_eleven_or(env, audio, ctx):
    key = env["OPENROUTER_API_KEY"]
    url = "https://openrouter.ai/api/v1/audio/transcriptions"
    # Verbatim by default (no_verbatim not set); tag_audio_events off. Slug for provider.options is "elevenlabs".
    opts = {"tag_audio_events": False}
    kt = (ctx or {}).get("keyterms")
    if kt:
        opts["keyterms"] = kt
    notes = []
    attempts = [
        ("with provider.options", {"provider": {"options": {"elevenlabs": opts}}}),
        ("without provider.options", {}),
    ] if not kt else [("with provider.options", {"provider": {"options": {"elevenlabs": opts}}})]
    raw = None
    for label, extra in attempts:
        body = {"model": "elevenlabs/scribe-v2", "input_audio": {"data": base64.b64encode(audio["bytes"]).decode(), "format": "flac"},
                "response_format": "verbose_json", "timestamp_granularities": ["word"], "language": "en", **extra}
        try:
            raw = http("POST", url, {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json.dumps(body).encode())
            notes.append(f"request {label}: accepted (HTTP 200)")
            applied = extra
            break
        except ApiError as e:
            notes.append(f"request {label}: rejected: {e}")
    if raw is None:
        raise ApiError("; ".join(notes))
    # Effectiveness check: audio events / spacing tokens present?
    types = {}
    for w in raw.get("words", []):
        types[w.get("type", "word")] = types.get(w.get("type", "word"), 0) + 1
    notes.append(f"returned word-entry types: {types}")
    notes.append("provider.options acceptance means the HTTP call succeeded; OpenRouter may drop unknown options silently, so effectiveness is judged only from the output (see audio-event count).")
    words = []
    for w in raw.get("words", []):
        t = w.get("type", "word")
        if t == "spacing":
            continue
        words.append({"text": w.get("word", w.get("text", "")), "start": ms(w.get("start")), "end": ms(w.get("end")),
                      "type": {"audio_event": "audio_event"}.get(t, t), "confidence": w.get("confidence", w.get("logprob"))})
    return raw, dict(provider="elevenlabs via openrouter", model=raw.get("model", "elevenlabs/scribe-v2"),
                     words=number(words), transcript=raw.get("text", ""),
                     params={"model": "elevenlabs/scribe-v2", "response_format": "verbose_json", "timestamp_granularities": ["word"],
                             "language": "en", "provider.options.elevenlabs": opts if "provider" in applied else None},
                     api_version="openrouter /api/v1/audio/transcriptions (JSON base64 input_audio)",
                     endpoint=url, notes=" | ".join(notes) + f" | usage={raw.get('usage')}")


def run_assemblyai(env, audio, ctx):
    h = {"Authorization": env["ASSEMBLYAI_API_KEY"]}
    base = "https://api.assemblyai.com/v2"
    up = http("POST", base + "/upload", {**h, "Content-Type": "application/octet-stream"}, audio["bytes"])
    params = {"audio_url": up["upload_url"], "speech_models": ["universal-3-5-pro"], "disfluencies": True, "language_code": "en"}
    if (ctx or {}).get("keyterms"):
        params["keyterms_prompt"] = ctx["keyterms"]
    job = http("POST", base + "/transcript", {**h, "Content-Type": "application/json"}, json.dumps(params).encode())
    while True:
        time.sleep(3)
        r = http("GET", f"{base}/transcript/{job['id']}", h)
        if r["status"] in ("completed", "error"):
            break
    if r["status"] == "error":
        raise ApiError(scrub(r.get("error")))
    words = [{"text": w["text"], "start": ms(w["start"] / 1000), "end": ms(w["end"] / 1000), "type": "word", "confidence": w.get("confidence")}
             for w in r["words"]]
    p = {k: v for k, v in params.items() if k != "audio_url"}
    return r, dict(provider="assemblyai", model=r.get("speech_model_used") or r.get("speech_model") or "universal-3-5-pro",
                   words=number(words), transcript=r.get("text", ""), params=p, api_version="v2",
                   endpoint=base + "/transcript",
                   notes=f"speech_model_used={r.get('speech_model_used')}; disfluencies in response={r.get('disfluencies')}; filler/disfluency tokens are not tagged by AssemblyAI (type=word).")


def run_deepgram(env, audio, ctx):
    q = "model=nova-3&filler_words=true&punctuate=true&language=en"
    kt = (ctx or {}).get("keyterms") or []
    if kt:
        q += "".join("&keyterm=" + urllib.parse.quote(t) for t in kt)
    url = "https://api.deepgram.com/v1/listen?" + q
    r = http("POST", url, {"Authorization": f"Token {env['DEEPGRAM_API_KEY']}", "Content-Type": "audio/flac"}, audio["bytes"])
    alt = r["results"]["channels"][0]["alternatives"][0]
    words = [{"text": w["word"], "start": ms(w["start"]), "end": ms(w["end"]), "type": "word", "confidence": w.get("confidence"),
              "display": w.get("punctuated_word")} for w in alt["words"]]
    return r, dict(provider="deepgram", model=(r.get("metadata", {}).get("model_info") or {}).get(r.get("metadata", {}).get("models", [""])[0], {}).get("arch", "nova-3") and "nova-3",
                   words=number(words), transcript=alt.get("transcript", ""),
                   params={"model": "nova-3", "filler_words": True, "punctuate": True, "language": "en", **({"keyterm": kt} if kt else {})},
                   api_version="v1 /listen", endpoint="https://api.deepgram.com/v1/listen",
                   notes=f"metadata.model_info={r.get('metadata', {}).get('model_info')}; fillers are not tagged by Deepgram (type=word). 'display' = punctuated_word.")


def run_speechmatics(env, audio, ctx):
    h = {"Authorization": f"Bearer {env['SPEECHMATICS_API_KEY']}"}
    base = "https://asr.api.speechmatics.com/v2"
    tc = {"language": "en", "operating_point": "enhanced", "enable_entities": False,
          "transcript_filtering_config": {"remove_disfluencies": False}}
    if (ctx or {}).get("keyterms"):
        tc["additional_vocab"] = [{"content": t} for t in ctx["keyterms"]]
    config = {"type": "transcription", "transcription_config": tc}
    notes = []
    for variant in ("operating_point", "model"):
        c = json.loads(json.dumps(config))
        if variant == "model":
            c["transcription_config"].pop("operating_point")
            c["transcription_config"]["model"] = "enhanced"
        body, ct = multipart({"config": json.dumps(c)}, {"data_file": ("audio.flac", audio["bytes"], "audio/flac")})
        try:
            job = http("POST", base + "/jobs", {**h, "Content-Type": ct}, body)
            config = c
            notes.append(f"submitted with {variant}=enhanced")
            break
        except ApiError as e:
            notes.append(f"submit with {variant} failed: {e}")
            job = None
    if not job:
        raise ApiError(" | ".join(notes))
    jid = job["id"]
    while True:
        time.sleep(4)
        st = http("GET", f"{base}/jobs/{jid}", h)["job"]
        if st["status"] in ("done", "rejected", "deleted", "expired"):
            break
    if st["status"] != "done":
        raise ApiError(f"job status {st['status']}: {st.get('errors')}")
    r = http("GET", f"{base}/jobs/{jid}/transcript?format=json-v2", h)
    words, parts = [], []
    for it in r["results"]:
        a = it["alternatives"][0]
        if it["type"] == "punctuation":
            if parts:
                parts[-1] += a["content"]
            continue
        tags = a.get("tags") or []
        typ = "filler" if "disfluency" in tags else it["type"]
        words.append({"text": a["content"], "start": ms(it["start_time"]), "end": ms(it["end_time"]), "type": typ, "confidence": a.get("confidence")})
        parts.append(a["content"])
    ttype = {}
    for it in r["results"]:
        for t in it["alternatives"][0].get("tags") or []:
            ttype[t] = ttype.get(t, 0) + 1
    return r, dict(provider="speechmatics", model="enhanced", words=number(words), transcript=" ".join(parts),
                   params={"transcription_config": config["transcription_config"]},
                   api_version=f"batch v2 ({r.get('format')}), asr {r.get('metadata', {}).get('transcription_config', {}).get('operating_point')}",
                   endpoint=base + "/jobs", notes=" | ".join(notes) + f" | tags seen={ttype}; type=filler where alternatives[0].tags has 'disfluency'")


def run_revai(env, audio, ctx):
    h = {"Authorization": f"Bearer {env['REVAI_ACCESS_TOKEN']}"}
    base = "https://api.rev.ai/speechtotext/v1"
    rev_notes = []
    opts = {"transcriber": "machine", "verbatim": True, "language": "en", "skip_diarization": True}
    if (ctx or {}).get("keyterms"):
        import re
        ok = [t for t in ctx["keyterms"] if re.fullmatch(r"[ -/:-~]+", t) and re.search(r"[A-Za-z]", t)]  # Rev.ai: no digits / non-ASCII
        dropped = [t for t in ctx["keyterms"] if t not in ok]
        opts["custom_vocabularies"] = [{"phrases": ok}]
        if dropped:
            rev_notes.append(f"Rev.ai rejects phrases with digits or non-ASCII; dropped client-side: {dropped}")
    body, ct = multipart({"options": json.dumps(opts)}, {"media": ("audio.flac", audio["bytes"], "audio/flac")})
    job = http("POST", base + "/jobs", {**h, "Content-Type": ct}, body)
    jid = job["id"]
    while True:
        time.sleep(5)
        st = http("GET", f"{base}/jobs/{jid}", h)
        if st["status"] in ("transcribed", "failed"):
            break
    if st["status"] == "failed":
        raise ApiError(f"failed: {st.get('failure_detail')}")
    r = http("GET", f"{base}/jobs/{jid}/transcript", {**h, "Accept": "application/vnd.rev.transcript.v1.0+json"})
    words, text = [], ""
    for mono in r["monologues"]:
        for e in mono["elements"]:
            text += e["value"]
            if e["type"] == "text":
                words.append({"text": e["value"], "start": ms(e["ts"]), "end": ms(e["end_ts"]), "type": "word", "confidence": e.get("confidence")})
    return r, dict(provider="rev.ai", model=f"{st.get('transcriber', 'machine')}", words=number(words), transcript=text.strip(),
                   params=opts, api_version="speechtotext v1 (transcript v1.0)", endpoint=base + "/jobs",
                   notes=" | ".join(rev_notes) + f" job metadata: transcriber={st.get('transcriber')} verbatim echoed={st.get('verbatim')}; fillers/false starts not tagged separately (type=word).")


# ---- Google Speech V2 BatchRecognize ----
def gcloud_token():
    return subprocess.check_output(["gcloud", "auth", "application-default", "print-access-token"], text=True).strip()


def ensure_bucket(location):
    name = f"vera-word-timing-asr-{location}"
    d = subprocess.run(["gcloud", "storage", "buckets", "describe", f"gs://{name}", "--format=value(name)"], capture_output=True, text=True)
    if d.returncode != 0:
        c = subprocess.run(["gcloud", "storage", "buckets", "create", f"gs://{name}", f"--project={GCP_PROJECT}", f"--location={location}",
                            "--uniform-bucket-level-access", "--public-access-prevention"], capture_output=True, text=True)
        if c.returncode != 0:
            raise ApiError("bucket create failed: " + c.stderr[-500:])
    return name


def run_google(model, locs, pid):
    def f(env, audio, ctx):
        errs = []
        for loc in locs:
            try:
                return _google(model, loc, audio, errs, (ctx or {}).get("keyterms"))
            except ApiError as e:
                errs.append(f"{loc}: {scrub(e)[:300]}")
        raise ApiError(" | ".join(errs))
    return f


def _google(model, loc, audio, errs, kt=None):
    bucket_loc = loc
    if True:
        bucket = ensure_bucket(bucket_loc)
        obj = f"{audio['sha256'][:16]}.flac"
        uri = f"gs://{bucket}/{obj}"
        up = subprocess.run(["gcloud", "storage", "cp", str(audio["path"]), uri], capture_output=True, text=True)
        if up.returncode != 0:
            raise ApiError("upload failed: " + up.stderr[-500:])
        host = "speech.googleapis.com" if loc == "global" else f"{loc}-speech.googleapis.com"
        tok = gcloud_token()
        h = {"Authorization": f"Bearer {tok}", "x-goog-user-project": GCP_PROJECT, "Content-Type": "application/json"}
        cfg = {"model": model, "languageCodes": ["en-US"], "features": {"enableWordTimeOffsets": True, "enableAutomaticPunctuation": True},
               "autoDecodingConfig": {}}
        if kt:
            cfg["adaptation"] = {"phraseSets": [{"inlinePhraseSet": {"phrases": [{"value": t} for t in kt]}}]}
        req = {"config": cfg, "files": [{"uri": uri}], "recognitionOutputConfig": {"inlineResponseConfig": {}}}
        url = f"https://{host}/v2/projects/{GCP_PROJECT}/locations/{loc}/recognizers/_:batchRecognize"
        op = http("POST", url, h, json.dumps(req).encode())
        while not op.get("done"):
            time.sleep(5)
            h["Authorization"] = f"Bearer {gcloud_token()}"
            op = http("GET", f"https://{host}/v2/{op['name']}", h)
        if "error" in op:
            raise ApiError(scrub(json.dumps(op["error"])))
        res = op["response"]["results"][uri]
        if "error" in res:
            raise ApiError(scrub(json.dumps(res["error"])))
        words, text = [], []
        for r in res.get("transcript", {}).get("results", []):
            if not r.get("alternatives"):
                continue
            a = r["alternatives"][0]
            text.append(a.get("transcript", "").strip())
            for w in a.get("words", []):
                words.append({"text": w["word"], "start": ms(w["startOffset"].rstrip("s")) if "startOffset" in w else 0.0,
                              "end": ms(w["endOffset"].rstrip("s")), "type": "word", "confidence": w.get("confidence")})
        return op, dict(provider="google speech-to-text v2", model=model, words=number(words), transcript=" ".join(text),
                        params={"model": model, "location": loc, "languageCodes": ["en-US"], "enableWordTimeOffsets": True,
                                "enableAutomaticPunctuation": True, "autoDecodingConfig": {}, "output": "inlineResponseConfig",
                                **({"adaptation": cfg["adaptation"]} if kt else {})},
                        api_version="speech v2 BatchRecognize", endpoint=url,
                        notes=(" | ".join(errs) + " | " if errs else "") + f"audio staged at {uri} (private bucket, uniform access, public-access-prevention enforced; bucket location {bucket_loc}). "
                              f"Missing startOffset treated as 0 (proto3 default). word confidence usually absent for chirp.")


RUNNERS = {"eleven-or": run_eleven_or, "assemblyai": run_assemblyai, "deepgram": run_deepgram, "speechmatics": run_speechmatics,
           "revai": run_revai, "chirp3": run_google("chirp_3", ["us"], "chirp3"), "chirp2": run_google("chirp_2", ["us-central1", "europe-west4"], "chirp2")}


def prepare_audio(src: Path, workdir: Path):
    flac = workdir / (src.stem + "-mono48k.flac")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "48000", "-c:a", "flac", str(flac)], check=True)
    b = flac.read_bytes()
    return {"path": flac, "bytes": b, "sha256": hashlib.sha256(b).hexdigest(), "format": f"flac 48000 Hz mono (ffmpeg downmix of {src.name}), {len(b)} bytes",
            "src_sha256": hashlib.sha256(src.read_bytes()).hexdigest()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--providers", default=",".join(ALL))
    ap.add_argument("--keyterms", type=Path, default=None, help="prompter.json; only its 'keyterms' list is sent")
    a = ap.parse_args()
    env = load_env()
    ctx, suffix, ktsha = None, "", None
    if a.keyterms:
        kt = json.loads(a.keyterms.expanduser().read_text())["keyterms"]
        assert kt and all(isinstance(t, str) and t.strip() for t in kt)
        ctx = {"keyterms": kt}
        suffix = "-kt"
        ktsha = hashlib.sha256(json.dumps(kt, ensure_ascii=False).encode()).hexdigest()
    a.out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        audio = prepare_audio(a.audio.expanduser(), Path(td))
        # keep the exact bytes sent for the record
        keep = a.out_dir / "audio-sent.flac"
        keep.write_bytes(audio["bytes"])
        audio["path"] = keep
        print(f"audio: {audio['format']} sha256={audio['sha256']}", flush=True)
        for pid in a.providers.split(","):
            pid = pid.strip()
            started = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
            t0 = time.time()
            try:
                raw, kw = RUNNERS[pid](env, audio, ctx)
            except Exception as e:
                print(f"[{pid}] FAILED: {scrub(e)}", flush=True)
                (a.out_dir / f"error-{pid}{suffix}.log").write_text(scrub(e) + "\n")
                continue
            wall = time.time() - t0
            (a.out_dir / f"raw-{pid}{suffix}.json").write_text(scrub(json.dumps(raw, indent=1)))
            res = mk_result(pid, kw["provider"], kw["model"], kw["words"], kw["transcript"], kw["params"], kw["api_version"], started, wall,
                            {"format": audio["format"], "sha256": audio["sha256"]}, kw["endpoint"], scrub(kw["notes"]))
            res["source"] = f"T-C-{pid}{suffix}"
            if ctx:
                res["provenance"]["keytermsSha256"] = ktsha
                res["provenance"]["keytermsFile"] = a.keyterms.name
                res["provenance"]["keytermCount"] = len(ctx["keyterms"])
                res["provenance"]["notes"] += " | KEYTERMS run: only the keyterm list was sent as vocabulary (see params); sha256 is of the JSON-dumped list."
            (a.out_dir / f"T-C-{pid}{suffix}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
            print(f"[{pid}] ok words={len(kw['words'])} wall={wall:.1f}s", flush=True)


if __name__ == "__main__":
    main()
