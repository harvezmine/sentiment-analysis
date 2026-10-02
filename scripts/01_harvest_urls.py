#!/usr/bin/env python3
"""Tahap 1: panen URL berita topik aktif dari Google News RSS.

Strategi memaksimalkan recall:
  - banyak varian kata kunci (T.KUERI_BERITA)
  - kata kunci inti per jendela waktu (after:/before:) supaya tidak kena cap
    ~100 item/kueri; harian untuk periode pendek, pekanan untuk periode panjang
  - kueri site: untuk media nasional + media lokal topik
Output: data/<topik>/urls_raw.jsonl  (1 baris = 1 item RSS, URL masih terenkode Google)
"""
import json, os, re, sys, time, urllib.parse
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from konteks import T, D, jendela_tanggal, potong_jendela  # noqa: E402
from topik import SITUS_NASIONAL  # noqa: E402

OUT = D("urls_raw.jsonl")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
SITES = SITUS_NASIONAL + [s for s in T.SITUS_TAMBAHAN if s not in SITUS_NASIONAL]


def build_queries():
    qs = []
    # 1. kata kunci global (tanpa window) -> tangkap yang paling relevan
    qs.extend(T.KUERI_BERITA)
    # 2. kata kunci inti per jendela waktu -> kedalaman
    for d, n in potong_jendela():
        for k in T.KUERI_BERITA_INTI:
            qs.append(f"{k} after:{(d - timedelta(days=1)).isoformat()} before:{n.isoformat()}")
    # 3. per media
    awal = (jendela_tanggal()[0] - timedelta(days=1)).isoformat()
    for s in SITES:
        for term in T.KUERI_SITUS:
            qs.append(f"{term} site:{s} after:{awal}")
    return qs


def fetch_rss(q):
    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q)
           + "&hl=id&gl=ID&ceid=ID:id")
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=40)
        if r.status_code != 200:
            return q, []
        soup = BeautifulSoup(r.content, "xml")
        items = []
        for it in soup.find_all("item"):
            src = it.find("source")
            items.append({
                "query": q,
                "title": (it.title.text if it.title else "").strip(),
                "gnews_url": (it.link.text if it.link else "").strip(),
                "pub_date": (it.pubDate.text if it.pubDate else "").strip(),
                "source_name": (src.text.strip() if src else ""),
                "source_domain": (src.get("url", "") if src else ""),
            })
        return q, items
    except Exception as e:
        return q, []


def main():
    queries = build_queries()
    print(f"[harvest] {len(queries)} kueri", flush=True)
    seen = set()
    rows = []
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_rss, q): q for q in queries}
        for f in as_completed(futs):
            q, items = f.result()
            done += 1
            new = 0
            for it in items:
                key = it["gnews_url"]
                if key and key not in seen:
                    seen.add(key)
                    rows.append(it)
                    new += 1
            if done % 25 == 0 or new:
                print(f"  [{done}/{len(queries)}] +{new:3d} total={len(rows)}  :: {q[:60]}", flush=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[harvest] selesai: {len(rows)} item unik -> {OUT}")


if __name__ == "__main__":
    main()
