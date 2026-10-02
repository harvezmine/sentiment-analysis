#!/usr/bin/env python3
"""Tahap 8: panen komentar/balasan pada postingan X tentang KM Virgo Transport 8.

Memilih postingan dengan reply terbanyak lalu menarik thread-nya lewat
TweetDetail (dengan paginasi cursor). Balasan yang ikut terjaring juga
disimpan sebagai tweet penuh, sehingga bisa dianalisis sentimennya.

Output: data/x/replies.jsonl  +  data/x/threads.log
"""
import importlib.util
import json
import os
import sys
import random
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from konteks import T, D  # noqa: E402
import topik  # noqa: E402



def _load(name, path):
    sp = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", path))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


xc = _load("xc", "x_client.py")
xp = _load("xp", "x_parse.py")

SRC = D("x", "tweets.jsonl")
OUT = D("x", "replies.jsonl")
TLOG = D("x", "threads.log")

MIN_REPLIES = 2        # hanya thread yang benar-benar punya percakapan
MAX_THREADS = 900      # batas aman terhadap rate limit
MAX_PAGES = 5          # halaman balasan per thread


def cursor_of(obj, want=("Bottom", "ShowMoreThreads")):
    """Cari cursor lanjutan di dalam response TweetDetail."""
    st = [obj]
    while st:
        x = st.pop()
        if isinstance(x, dict):
            if x.get("cursorType") in want and x.get("value"):
                return x["value"]
            st.extend(x.values())
        elif isinstance(x, list):
            st.extend(x)
    return None


def main():
    if not os.path.exists(SRC):
        print("[reply] data/x/tweets.jsonl belum ada — jalankan tahap 7 dulu")
        return

    tweets = []
    for line in open(SRC, encoding="utf-8"):
        try:
            tweets.append(json.loads(line))
        except Exception:
            pass

    # tweet yang ditandai tidak relevan oleh tahap 9 (insiden kapal lain,
    # konser, dsb.) tidak dibuka utasnya: balasannya hanya akan mencemari data
    tidak_relevan = set()
    flab = D("x", "tweets_labeled.jsonl")
    if os.path.exists(flab):
        for line in open(flab, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("relevan") == 0:
                tidak_relevan.add(r["tweet_id"])

    # kandidat: tweet asli (bukan RT) di jendela topik, relevan, dan punya balasan;
    # balasan di luar jendela hanya akan dibuang dashboard, jadi tidak diminta
    awal, akhir = T.JENDELA
    cand = {}
    for t in tweets:
        if t.get("is_retweet") or t["tweet_id"] in tidak_relevan:
            continue
        if not (awal <= str(t.get("tanggal", ""))[:10] <= akhir):
            continue
        if not topik.relevan_x(T, t.get("teks", ""), t.get("kueri", "")):
            continue
        try:
            nrep = int(t.get("replies") or 0)
        except Exception:
            nrep = 0
        if nrep < MIN_REPLIES:
            continue
        tid = t.get("conversation_id") or t["tweet_id"]
        prev = cand.get(tid)
        if not prev or nrep > prev[0]:
            cand[tid] = (nrep, t)
    ranked = sorted(cand.items(), key=lambda kv: -kv[1][0])[:MAX_THREADS]
    print(f"[reply] {len(cand)} thread berkandidat, diproses {len(ranked)}", flush=True)

    seen = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                seen.add(json.loads(line)["tweet_id"])
            except Exception:
                pass
    done = set()
    if os.path.exists(TLOG):
        for line in open(TLOG, encoding="utf-8"):
            done.add(line.split("\t")[0])
    print(f"[reply] sudah punya {len(seen)} balasan, {len(done)} thread selesai", flush=True)

    c = xc.XClient()
    fo = open(OUT, "a", encoding="utf-8")
    fl = open(TLOG, "a", encoding="utf-8")
    total = 0

    for i, (tid, (nrep, src)) in enumerate(ranked, 1):
        if tid in done:
            continue
        cursor, pages, added = None, 0, 0
        stop = "max"
        for _ in range(MAX_PAGES):
            try:
                j = c.tweet_detail(tid, cursor)
            except Exception as e:
                stop = f"err:{str(e)[:60]}"
                break
            rows = xp.parse_blob(j)
            for r in rows:
                if r["tweet_id"] in seen:
                    continue
                seen.add(r["tweet_id"])
                r["thread_id"] = tid
                r["thread_author"] = src.get("username", "")
                r["is_focal"] = int(r["tweet_id"] == tid)
                fo.write(json.dumps(r, ensure_ascii=False) + "\n")
                added += 1
            fo.flush()
            pages += 1
            nc = cursor_of(j)
            if not nc or nc == cursor:
                stop = "habis"
                break
            cursor = nc
            time.sleep(2.5 + random.random() * 2)
        total += added
        fl.write(f"{tid}\t{pages}\t{added}\t{stop}\n")
        fl.flush()
        print(f"  [{i}/{len(ranked)}] @{src.get('username','')[:16]:16s} "
              f"rep={nrep:5d} +{added:4d} ({stop}) total={len(seen)}", flush=True)
        time.sleep(1.5 + random.random())

    fo.close()
    fl.close()
    print(f"[reply] selesai. balasan unik: {len(seen)} (+{total} baru)")


if __name__ == "__main__":
    main()
