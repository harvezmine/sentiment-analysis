#!/usr/bin/env python3
"""Tahap 7: panen tweet X tentang KM Virgo Transport 8.

Strategi:
  - kata kunci & tagar inti (Top + Latest)
  - window harian untuk frasa inti -> menembus batas ~keluaran per kueri
  - sadar rate-limit: baca header x-rate-limit-*, tidur sampai reset saat habis
Output: data/x/tweets.jsonl (resume-safe), data/x/queries.log
"""
import importlib.util, json, os, random, sys, time
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from konteks import T, D, potong_jendela  # noqa: E402

def _load(name, path):
    sp = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", path))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
xc = _load("xc", "x_client.py")
xp = _load("xp", "x_parse.py")

OUT = D("x", "tweets.jsonl")
QLOG = D("x", "queries.log")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

CORE = T.KUERI_X
DAILY = T.KUERI_X_HARIAN


def build_jobs():
    jobs = []
    for q in CORE:
        jobs.append((q, "Latest", 18))
        jobs.append((q, "Top", 8))
    # jendela harian untuk periode pendek, pekanan untuk periode panjang
    for d, n in potong_jendela():
        for q in DAILY:
            jobs.append((f"{q} since:{d.isoformat()} until:{n.isoformat()}", "Latest", 12))
    return jobs


def cursor_of(o):
    st = [o]
    while st:
        x = st.pop()
        if isinstance(x, dict):
            if x.get("cursorType") == "Bottom" and x.get("value"):
                return x["value"]
            st.extend(x.values())
        elif isinstance(x, list):
            st.extend(x)
    return None


def main():
    seen = set()
    if os.path.exists(OUT):
        for l in open(OUT, encoding="utf-8"):
            try: seen.add(json.loads(l)["tweet_id"])
            except Exception: pass
    done_q = set()
    if os.path.exists(QLOG):
        for l in open(QLOG, encoding="utf-8"):
            done_q.add(l.split("\t")[0])
    print(f"[x] sudah punya {len(seen)} tweet, {len(done_q)} kueri selesai", flush=True)

    c = xc.XClient()
    fo = open(OUT, "a", encoding="utf-8")
    fq = open(QLOG, "a", encoding="utf-8")
    jobs = build_jobs()
    total_new = 0

    for idx, (q, product, maxp) in enumerate(jobs, 1):
        key = f"{q}|{product}"
        if key in done_q:
            continue
        cursor, pages, added = None, 0, 0
        stop = "max"
        for p in range(maxp):
            try:
                j = c.search(q, product, cursor)
            except Exception as e:
                stop = f"err:{str(e)[:60]}"; break
            rows = xp.parse_blob(j)
            new = 0
            for r in rows:
                if r["tweet_id"] not in seen:
                    seen.add(r["tweet_id"])
                    r["query"] = q; r["product"] = product
                    fo.write(json.dumps(r, ensure_ascii=False) + "\n")
                    new += 1
            fo.flush()
            added += new; pages += 1
            nc = cursor_of(j)
            if not nc or nc == cursor:
                stop = "habis"; break
            if not rows:
                stop = "kosong"; break
            cursor = nc
            time.sleep(2.5 + random.random() * 2.0)
        total_new += added
        fq.write(f"{key}\t{pages}\t{added}\t{stop}\n"); fq.flush()
        print(f"  [{idx}/{len(jobs)}] +{added:4d} (p{pages:2d} {stop:12s}) total={len(seen)} :: {q[:52]} [{product}]", flush=True)
        time.sleep(1.5 + random.random())

    fo.close(); fq.close()
    print(f"[x] selesai. tweet unik: {len(seen)} (+{total_new} baru)")


if __name__ == "__main__":
    main()
