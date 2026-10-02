#!/usr/bin/env python3
"""Tahap 5 (suplemen): panen URL dari mesin pencari internal tiap media.
Menangkap artikel yang tidak muncul / tidak terindeks di Google News RSS.
Output: data/urls_native.jsonl (skema sama dgn urls_decoded.jsonl, URL sudah asli)
"""
import json, os, re, sys, time, threading
from urllib.parse import urljoin, urlparse, quote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from konteks import T, D  # noqa: E402

OUT = D("urls_native.jsonl")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Accept-Language": "id-ID,id;q=0.9"}

QUERIES = T.KUERI_NATIVE

# (nama, template url, jumlah halaman, pola url artikel yang valid)
ENGINES = [
    ("detikcom", "https://www.detik.com/search/searchall?query={q}&page={p}&result_type=latest", 20,
     r"^https?://[a-z]+\.detik\.com/[^/]+/d-\d+"),
    ("Kompas.com", "https://search.kompas.com/search/?q={q}&page={p}", 20,
     r"^https?://[a-z]+\.kompas\.com/read/"),
    ("Tribunnews.com", "https://www.tribunnews.com/search?q={q}&page={p}", 20,
     r"^https?://(www|[a-z]+)\.tribunnews\.com/\w+/\d{4}/\d{2}/\d{2}/"),
    ("Liputan6.com", "https://www.liputan6.com/search?q={q}&page={p}", 15,
     r"^https?://www\.liputan6\.com/[^/]+/read/\d+"),
    ("Suara.com", "https://www.suara.com/search?q={q}&page={p}", 15,
     r"^https?://(www|[a-z]+)\.suara\.com/\w+/\d{4}/\d{2}/\d{2}/"),
    ("Merdeka", "https://www.merdeka.com/pencarian/?q={q}&page={p}", 15,
     r"^https?://www\.merdeka\.com/[^/]+/.+\.html"),
    ("JPNN.com", "https://www.jpnn.com/search?q={q}&page={p}", 15,
     r"^https?://www\.jpnn\.com/news/"),
    ("Sindonews", "https://search.sindonews.com/search?q={q}&page={p}", 15,
     r"^https?://[a-z]+\.sindonews\.com/(read|berita)/\d+"),
    ("VIVA.co.id", "https://www.viva.co.id/search?q={q}&page={p}", 15,
     r"^https?://www\.viva\.co\.id/\w+/.+-\d+"),
    ("ANTARA News", "https://www.antaranews.com/search?q={q}&page={p}", 15,
     r"^https?://(www|[a-z]+)\.antaranews\.com/berita/\d+"),
    ("Republika", "https://www.republika.co.id/search/{q}?page={p}", 10,
     r"^https?://\w+\.republika\.co\.id/berita/"),
    ("okezone", "https://search.okezone.com/searchword/{q}/news/{p}", 10,
     r"^https?://\w+\.okezone\.com/read/\d{4}/"),
    ("Tempo.co", "https://www.tempo.co/search?q={q}&page={p}", 15,
     r"^https?://www\.tempo\.co/\w+/"),
    ("Kumparan", "https://kumparan.com/search?q={q}&type=story&page={p}", 10,
     r"^https?://kumparan\.com/[^/]+/[^/]+-\w{10,}"),
    ("Medcom.id", "https://www.medcom.id/search?q={q}&page={p}", 10,
     r"^https?://www\.medcom\.id/\w+/"),
    ("iNews.ID", "https://www.inews.id/search?q={q}&page={p}", 10,
     r"^https?://www\.inews\.id/\w+/"),
    ("Beritasatu", "https://www.beritasatu.com/search?q={q}&page={p}", 10,
     r"^https?://www\.beritasatu\.com/\w+/\d+/"),
    ("tvOneNews", "https://www.tvonenews.com/search?q={q}&page={p}", 10,
     r"^https?://www\.tvonenews\.com/\w+/\d+-"),
    ("Kontan", "https://www.kontan.co.id/search/?search={q}&page={p}", 10,
     r"^https?://\w+\.kontan\.co\.id/news/"),
    ("Bisnis.com", "https://search.bisnis.com/?q={q}&page={p}", 10,
     r"^https?://\w+\.bisnis\.com/read/"),
]

lock = threading.Lock()
rows, seen = [], set()


def harvest(name, tmpl, pages, pat, q):
    rx = re.compile(pat)
    found = 0
    s = requests.Session()
    for p in range(1, pages + 1):
        url = tmpl.format(q=quote_plus(q), p=p)
        try:
            r = s.get(url, headers=HDRS, timeout=30)
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.content, "lxml")
            links = set()
            for a in soup.find_all("a", href=True):
                h = urljoin(url, a["href"]).split("#")[0]
                h = re.sub(r"\?.*$", "", h)
                if rx.match(h):
                    links.add((h, a.get_text(" ", strip=True)[:250]))
            if not links:
                break
            new = 0
            with lock:
                for h, t in links:
                    if h not in seen:
                        seen.add(h)
                        rows.append({"url": h, "title": t, "source_name": name,
                                     "query": f"native:{q}", "pub_date": "", "match": "native"})
                        new += 1
            found += new
            if new == 0 and p > 3:
                break
            time.sleep(0.7)
        except Exception:
            break
    return name, q, found


def main():
    prev = set()
    for f in ("urls_decoded.jsonl",):
        p = D(f)
        if os.path.exists(p):
            for l in open(p, encoding="utf-8"):
                try:
                    prev.add(re.sub(r"[?#].*$", "", json.loads(l)["url"]).rstrip("/").lower())
                except Exception:
                    pass
    print(f"[native] sudah punya {len(prev)} URL dari Google News")

    tasks = [(n, t, pg, pt, q) for (n, t, pg, pt) in ENGINES for q in QUERIES]
    with ThreadPoolExecutor(max_workers=10) as ex:
        for f in as_completed([ex.submit(harvest, *t) for t in tasks]):
            n, q, c = f.result()
            if c:
                print(f"  +{c:4d}  {n:16s} :: {q}", flush=True)

    fresh = [r for r in rows
             if re.sub(r"[?#].*$", "", r["url"]).rstrip("/").lower() not in prev]
    with open(OUT, "w", encoding="utf-8") as fh:
        for r in fresh:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[native] {len(rows)} URL ditemukan, {len(fresh)} baru -> {OUT}")


if __name__ == "__main__":
    main()
