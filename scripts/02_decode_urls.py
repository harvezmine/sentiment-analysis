#!/usr/bin/env python3
"""Tahap 2: filter relevansi + decode URL Google News -> URL publisher asli.
Output: data/urls_decoded.jsonl
"""
import json, os, re, sys, threading
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gnews_decode import get_decoding_params, decode_batch

from konteks import T, D, jendela_tanggal  # noqa: E402
from datetime import timedelta  # noqa: E402

IN = D("urls_raw.jsonl")
OUT = D("urls_decoded.jsonl")

STRICT = re.compile(T.JUDUL_KUAT, re.I)
LOOSE = re.compile(T.JUDUL_LONGGAR, re.I)
_AWAL, _AKHIR = jendela_tanggal()


def in_window(r):
    """Tanggal terbit di dalam jendela topik (±1 hari untuk selisih zona waktu)."""
    try:
        d = parsedate_to_datetime(r["pub_date"]).date()
    except Exception:
        return False
    return _AWAL - timedelta(days=1) <= d <= _AKHIR + timedelta(days=1)


def main():
    rows = [json.loads(l) for l in open(IN, encoding="utf-8")]
    cand = []
    seen = set()
    for r in rows:
        if not in_window(r):
            continue
        t = r["title"]
        if STRICT.search(t):
            r["match"] = "strict"
        elif LOOSE.search(t):
            r["match"] = "loose"
        else:
            continue
        if r["gnews_url"] in seen:
            continue
        seen.add(r["gnews_url"])
        cand.append(r)
    print(f"[decode] kandidat: {len(cand)}", flush=True)

    lock = threading.Lock()
    results = []
    counter = {"n": 0, "ok": 0}
    CH = 10

    def work(chunk):
        s = requests.Session()
        params, keep = [], []
        for r in chunk:
            try:
                p = get_decoding_params(r["gnews_url"].split("?")[0].rsplit("/", 1)[-1], s)
            except Exception:
                p = None
            if p:
                params.append(p); keep.append(r)
        urls = []
        if params:
            try:
                urls = decode_batch(params, s)
            except Exception:
                urls = []
        out = []
        for r, u in zip(keep, urls):
            if u:
                r2 = dict(r); r2["url"] = u
                out.append(r2)
        with lock:
            counter["n"] += len(chunk); counter["ok"] += len(out)
            results.extend(out)
            if counter["n"] % 200 < CH:
                print(f"  {counter['n']}/{len(cand)} decoded_ok={counter['ok']}", flush=True)
        return len(out)

    chunks = [cand[i:i + CH] for i in range(0, len(cand), CH)]
    with ThreadPoolExecutor(max_workers=12) as ex:
        list(as_completed([ex.submit(work, c) for c in chunks]))

    # dedupe by canonical url
    def canon(u):
        u = re.sub(r"[?#].*$", "", u).rstrip("/")
        return u.lower()

    uniq, seen_u = [], set()
    for r in results:
        c = canon(r["url"])
        if c in seen_u:
            continue
        seen_u.add(c)
        uniq.append(r)
    with open(OUT, "w", encoding="utf-8") as fh:
        for r in uniq:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[decode] selesai: {len(uniq)} URL unik -> {OUT}")


if __name__ == "__main__":
    main()
