#!/usr/bin/env python3
"""Tahap 9: klasifikasi sentimen & narasi untuk data X (Twitter).

Catatan metodologis — dibaca dulu sebelum memakai angkanya:
Berita/percakapan musibah penuh kata negatif yang sifatnya FAKTUAL ("tewas",
"hilang", "tenggelam"). Lexicon polos akan melabeli hampir semuanya negatif dan
itu bukan temuan, melainkan artefak. Maka klasifikasi di sini memisahkan:

  sentimen  : nada evaluatif penulis  -> negatif / netral / positif
  emosi     : duka, marah, empati, takut, syukur, sinis
  stance    : sikap terhadap otoritas -> kritik / dukungan / netral
  narasi    : bingkai isu yang dipakai

Kata berkonotasi musibah dimasukkan daftar NETRAL_FAKTUAL agar tidak menyeret
skor. Yang menentukan negatif adalah penanda evaluatif (menyalahkan, menuntut,
mencurigai), bukan sekadar penyebutan korban.

Output: data/x/tweets_labeled.csv/.jsonl + ringkasan_x_*.csv
"""
import csv
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from konteks import T, D  # noqa: E402
import topik  # noqa: E402
WIB = timezone(timedelta(hours=7))

from label_teks import klasifikasi  # noqa: E402  (aturan dipakai bersama semua platform)

def relevan_x(teks, kueri):
    """Relevansi tweet menurut aturan topik aktif (topik/<slug>.py)."""
    return topik.relevan_x(T, teks, kueri)


def parse_dt(s):
    try:
        return datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y").astimezone(WIB)
    except Exception:
        return None


def main():
    srcs = [D("x", "tweets.jsonl"), D("x", "replies.jsonl")]
    rows, seen = [], set()
    for path in srcs:
        if not os.path.exists(path):
            continue
        tipe = "posting" if path.endswith("tweets.jsonl") else "balasan"
        for line in open(path, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r["tweet_id"] in seen:
                continue
            seen.add(r["tweet_id"])
            r["tipe"] = tipe
            rows.append(r)
    if not rows:
        print("[sentimen] belum ada data X")
        return
    print(f"[sentimen] {len(rows)} item ({Counter(r['tipe'] for r in rows)})")

    # Relevansi balasan mengikuti rantai balasan: balasan relevan bila teksnya sendiri relevan
    # atau tweet yang dibalasnya relevan. Satu balasan yang menyebut topik di tengah utas lain
    # hanya membuat turunannya ikut terhitung, bukan seluruh utas. Akar utas yang ikut terpanen
    # sebagai balasan dinilai dari teksnya sendiri; induk yang tidak terpanen mengikuti akar utas,
    # dan akar yang tidak terpanen dianggap relevan (utas dibuka karena tweet relevan di dalamnya).
    rel_posting = {r["tweet_id"]: relevan_x(r.get("teks", ""), r.get("query", ""))
                   for r in rows if r["tipe"] == "posting"}
    per_id = {str(r["tweet_id"]): r for r in rows}
    memo = {}

    def rel(r):
        rantai, x = [], r
        while True:
            tid = str(x["tweet_id"])
            if tid in memo:
                v = memo[tid]
                break
            rantai.append(tid)
            if x["tipe"] == "posting":
                v = rel_posting[x["tweet_id"]]
                break
            if relevan_x(x.get("teks", ""), ""):
                v = 1
                break
            induk = str(x.get("reply_to_tweet") or "")
            akar = str(x.get("thread_id") or x.get("conversation_id") or "")
            if not induk or induk == tid:
                v = 0                                  # akar utas: teksnya tidak relevan
                break
            if induk in per_id and induk not in rantai:
                x = per_id[induk]
                continue
            if akar in per_id and akar not in rantai:
                x = per_id[akar]
                continue
            v = rel_posting.get(akar, 1)
            break
        for tid in rantai:
            memo[tid] = v
        return v

    out = []
    for r in rows:
        lab = klasifikasi(r.get("teks", ""), narasi=T.NARASI, aturan=getattr(T, "ATURAN", None))
        d = parse_dt(r.get("created_at", ""))
        out.append({
            "tweet_id": r["tweet_id"], "tipe": r["tipe"],
            "tanggal": r.get("tanggal") or (d.strftime("%Y-%m-%d") if d else ""),
            "waktu_wib": r.get("waktu_wib", ""),
            "username": r.get("username", ""), "nama": r.get("nama", ""),
            "followers": r.get("followers", ""), "verified": r.get("verified", ""),
            "teks": r.get("teks", ""), "lang": r.get("lang", ""),
            "likes": r.get("likes", 0), "retweets": r.get("retweets", 0),
            "replies": r.get("replies", 0), "quotes": r.get("quotes", 0),
            "views": r.get("views", ""),
            "hashtags": r.get("hashtags", ""), "mentions": r.get("mentions", ""),
            "url": r.get("url", ""), "is_retweet": r.get("is_retweet", ""),
            "reply_to": r.get("reply_to_user", ""),
            "thread_id": r.get("thread_id", r.get("conversation_id", "")),
            # balasan jarang menyebut nama topik: relevansinya diwarisi dari akar utas (lihat rel)
            "relevan": rel(r),
            **lab,
        })

    df = pd.DataFrame(out)
    df = df[df.lang.isin(["in", "id", "", None]) | df.lang.isna()]
    print(f"[sentimen] relevan {int(df.relevan.sum())} / {len(df)} "
          f"(tidak relevan tetap disimpan, ditandai relevan=0)")
    df.to_csv(D("x", "tweets_labeled.csv"), index=False, quoting=csv.QUOTE_ALL)
    df.to_json(D("x", "tweets_labeled.jsonl"), orient="records",
               lines=True, force_ascii=False)

    df.groupby(["tanggal", "sentimen"]).size().unstack(fill_value=0).to_csv(
        D("x", "ringkasan_x_sentimen_harian.csv"))
    df.groupby("emosi").size().sort_values(ascending=False).to_csv(
        D("x", "ringkasan_x_emosi.csv"))
    nc = Counter(n for s in df.narasi.fillna("") for n in str(s).split("; ") if n)
    pd.DataFrame(nc.most_common(), columns=["narasi", "jumlah"]).to_csv(
        D("x", "ringkasan_x_narasi.csv"), index=False)
    top = df.sort_values("likes", ascending=False).head(200)
    top.to_csv(D("x", "top_posting.csv"), index=False, quoting=csv.QUOTE_ALL)
    akun = (df.groupby("username")
              .agg(posting=("tweet_id", "count"), total_like=("likes", "sum"),
                   total_rt=("retweets", "sum"), followers=("followers", "max"))
              .sort_values("total_like", ascending=False))
    akun.to_csv(D("x", "ringkasan_x_akun.csv"))

    print("\n=== SENTIMEN ===\n" + df.sentimen.value_counts().to_string())
    print("\n=== EMOSI ===\n" + df.emosi.value_counts().to_string())
    print("\n=== STANCE ===\n" + df.stance.value_counts().to_string())
    print("\n=== NARASI ===")
    for k, v in nc.most_common():
        print(f"  {v:5d}  {k}")
    print(f"\n[sentimen] {len(df)} baris -> data/x/tweets_labeled.csv")


if __name__ == "__main__":
    main()
