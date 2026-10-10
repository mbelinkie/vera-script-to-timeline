#!/usr/bin/env python3
"""A-CHAR wrapper: Charsiu en_w2v2_fc_10ms forced aligner, per ALIGNER-CONTRACT.md.
Runs inside the container. Charsiu is MIT code; model licence unstated -> evaluation only."""

import argparse
import difflib
import hashlib
import json
import os
import re
import resource
import sys
import time
from itertools import chain, groupby

sys.path.insert(0, "/opt/charsiu/src")
import importlib.metadata as md

import numpy as np
import soundfile as sf
import torch
from huggingface_hub import snapshot_download

CHARSIU_SHA = "13a69f2a22ca0c0962b75cc693399b0ae23a12c9"
MODEL_ID, MODEL_REV = (
    "charsiu/en_w2v2_fc_10ms",
    "e9bf8dd314313fc57f6e4d0b5425bde4bbeac80f",
)
TOK_ID, TOK_REV = "charsiu/tokenizer_en_cmu", "10507401aedf5e0aba164128535b49225ff95260"
SIL_THRESHOLD = 4
RES = 0.01


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", required=True)
    ap.add_argument("--audio-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--variant", default="en_w2v2_fc_10ms")
    a = ap.parse_args()
    t0 = time.time()

    from models import Wav2Vec2ForFrameClassification
    from processors import CharsiuPreprocessor_en
    from transformers import (
        Wav2Vec2CTCTokenizer,
        Wav2Vec2FeatureExtractor,
        Wav2Vec2Processor,
    )
    from utils import forced_align, seq2duration

    mdir = snapshot_download(MODEL_ID, revision=MODEL_REV)
    tdir = snapshot_download(TOK_ID, revision=TOK_REV)
    model = Wav2Vec2ForFrameClassification.from_pretrained(mdir).eval()
    # Build the English preprocessor without its hard-coded hub lookup (unpinned).
    pre = CharsiuPreprocessor_en.__new__(CharsiuPreprocessor_en)
    from g2p_en import G2p

    tok = Wav2Vec2CTCTokenizer.from_pretrained(tdir)
    fe = Wav2Vec2FeatureExtractor(
        feature_size=1,
        sampling_rate=16000,
        padding_value=0.0,
        do_normalize=True,
        return_attention_mask=False,
    )
    pre.processor = Wav2Vec2Processor(feature_extractor=fe, tokenizer=tok)
    pre.g2p = G2p()
    pre.sil = "[SIL]"
    pre.sil_idx = pre.mapping_phone2id("[SIL]")
    pre.punctuation = set()

    def sil_mask(cost):
        m = []
        for key, grp in groupby(np.argmax(cost, axis=-1)):
            grp = list(grp)
            m += (
                [-1] * len(grp)
                if (key == pre.sil_idx and len(grp) < SIL_THRESHOLD)
                else grp
            )
        return np.array(m)

    inp = json.load(open(a.segments))
    audio, sr = sf.read(os.path.join(a.audio_dir, inp["audio"]), dtype="float32")
    assert sr == 16000, f"expected 16 kHz, got {sr}"
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    off = float(inp.get("offsetSec", 0.0))
    result = {}
    sharedw = set()
    dbg = {"unmatched": 0, "shared": 0, "ambig": 0}

    for seg in inp["segments"]:
        words = seg["words"]
        # per input word: phone tuple (concatenated over g2p_en/Charsiu tokens); empty -> dropped
        wph = []
        for w in words:
            try:
                ph, _ = pre.get_phones_and_words(w["text"])
                wph.append(tuple(chain.from_iterable(ph)))
            except Exception:
                wph.append(())
        flat = [(re.sub(r"\d", "", p), k) for k, ph in enumerate(wph) for p in ph]
        keep = lambda k: k  # noqa
        if not flat:
            continue
        x = audio[int(round(seg["start"] * 16000)) : int(round(seg["end"] * 16000))]
        feats = pre.audio_preprocess(x, sr=16000)
        with torch.no_grad():
            out = model(torch.Tensor(feats).unsqueeze(0))
        cost = torch.softmax(out.logits, dim=-1).detach().cpu().numpy().squeeze()
        m = sil_mask(cost)
        nonsil = np.argwhere(m != pre.sil_idx).squeeze()
        if nonsil.size == 0:
            continue
        ids = pre.get_phone_ids([tuple(p for p, _ in flat)])  # adds SIL at both ends
        aligned = forced_align(cost[nonsil, :], ids[1:-1])
        names = [pre.mapping_id2phone(ids[1:-1][i]) for i in aligned]
        merged = []  # re-insert silence (mirrors charsiu_forced_aligner._merge_silence)
        it = iter(names)
        for v in m:
            merged.append("[SIL]" if v == pre.sil_idx else next(it))
        durs = [d for d in seq2duration(merged, resolution=RES) if d[-1] != "[SIL]"]

        # Map expected phones -> observed intervals with a sequence alignment, so a
        # local mismatch only fails the words it touches. seq2duration merges equal
        # neighbouring frames, so compare run-collapsed label sequences.
        def runs(items):  # items: (label, payload) -> [(label, [payloads])]
            out = []
            for lab, pl in items:
                if out and out[-1][0] == lab:
                    out[-1][1].append(pl)
                else:
                    out.append((lab, [pl]))
            return out

        eruns = runs(flat)  # payload = word idx
        oruns = runs([(d[2], (d[0], d[1])) for d in durs])  # payload = (s, e)
        sm = difflib.SequenceMatcher(
            None, [r[0] for r in eruns], [r[0] for r in oruns], autojunk=False
        )
        phone_iv = [None] * len(flat)  # per expected phone: (s, e) or None
        pos = 0
        starts = []
        for lab, ks in eruns:
            starts.append(pos)
            pos += len(ks)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "equal":
                dbg["unmatched"] += sum(len(eruns[i][1]) for i in range(i1, i2))
                continue
            for ei, oi in zip(range(i1, i2), range(j1, j2)):
                ks, ivs = eruns[ei][1], oruns[oi][1]
                if len(ivs) == len(ks):
                    for n, iv in enumerate(ivs):
                        phone_iv[starts[ei] + n] = iv
                elif len(ivs) == 1:  # merged phones: split interval equally
                    s0, e0 = ivs[0]
                    for n in range(len(ks)):
                        phone_iv[starts[ei] + n] = (
                            s0 + (e0 - s0) * n / len(ks),
                            s0 + (e0 - s0) * (n + 1) / len(ks),
                        )
                    if len(set(ks)) > 1:
                        dbg["shared"] += 1
                        for k in set(ks):
                            sharedw.add((seg["id"], k))
                else:
                    dbg["ambig"] += len(ks)
        spans = {}
        for (p, k), iv in zip(flat, phone_iv):
            if iv is None:
                spans[k] = None
            elif spans.get(k, 0) is not None:
                s, e = spans.get(k, iv)
                spans[k] = (min(s, iv[0]), max(e, iv[1]))
        for k, v in spans.items():
            if v is None:
                continue
            result[(words[k]["i"], words[k].get("sub"))] = (
                round(seg["start"] + off + v[0], 3),
                round(seg["start"] + off + v[1], 3),
                (seg["id"], k) in sharedw,
            )

    rows = []
    for seg in inp["segments"]:
        for w in seg["words"]:
            r = result.get((w["i"], w.get("sub")))
            row = {"i": w["i"]}
            if "sub" in w:
                row["sub"] = w["sub"]
            rows.append(
                {
                    **row,
                    "start": r[0] if r else None,
                    "end": r[1] if r else None,
                    "status": "aligned" if r else "failed",
                    **({"sharedBoundary": True} if r and r[2] else {}),
                }
            )
    models = []
    for rid, rev, d in ((MODEL_ID, MODEL_REV, mdir), (TOK_ID, TOK_REV, tdir)):
        for fn in sorted(os.listdir(d)):
            p = os.path.realpath(os.path.join(d, fn))
            if os.path.isfile(p) and not fn.startswith("."):
                models.append(
                    {"id": rid, "revision": rev, "file": fn, "sha256": sha256(p)}
                )
    pk = {
        n: md.version(n)
        for n in (
            "torch",
            "transformers",
            "g2p_en",
            "nltk",
            "numpy",
            "librosa",
            "huggingface_hub",
        )
    }
    pk["charsiu(git)"] = CHARSIU_SHA
    json.dump(
        {
            "aligner": "A-CHAR",
            "variant": a.variant,
            "words": rows,
            "provenance": {
                "packages": pk,
                "models": models,
                "settings": {
                    "frameMs": 10,
                    "silThreshold": SIL_THRESHOLD,
                    "debug": dbg,
                    "licenceNote": "Charsiu code MIT; model licence unstated: evaluation only",
                },
                "platform": "linux/amd64 docker",
                "wallSeconds": round(time.time() - t0, 2),
                "peakRssBytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                * 1024,
            },
        },
        open(a.out, "w"),
        indent=1,
    )


if __name__ == "__main__":
    main()
