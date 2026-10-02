#!/usr/bin/env python3
"""Tahap 6: coba ulang URL yang gagal di tahap 3.
Varian yang dicoba: URL polos (tanpa suffix paginasi), versi AMP, dan header berbeda.
Memakai curl_cffi dengan sidik TLS Chrome bila tersedia: beberapa media (mis. RRI)
menolak sidik TLS python-requests dengan HTTP 403 walau header-nya menyerupai peramban.
"""
import json, os, re, sys, threading, importlib.util
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
try:
    from curl_cffi import requests as creq      # sidik TLS Chrome
except ImportError:
    creq = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from konteks import T, D  # noqa: E402

spec = importlib.util.spec_from_file_location("s3", os.path.join(ROOT, "scripts", "03_scrape_articles.py"))
s3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(s3)

FAIL = D("failed.jsonl")
OUT = D("articles.jsonl")
STILL = D("failed_final.jsonl")

ALT_HDRS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}

lock = threading.Lock()


def variants(u):
    base = re.sub(r"[?#].*$", "", u)
    out = [base]
    if base.endswith("/"):
        out.append(base.rstrip("/"))
    out.append(base + ("&" if "?" in base else "?") + "amp=1")
    out.append(base.rstrip("/") + "/amp")
    return out


def try_one(rec, s):
    for v in variants(rec["url"]):
        try:
            # dengan curl_cffi, User-Agent dibiarkan milik profil Chrome agar sidiknya konsisten
            hdr = {k: v_ for k, v_ in ALT_HDRS.items() if k != "User-Agent"} if creq else ALT_HDRS
            r = s.get(v, headers=hdr, timeout=35)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.content, "lxml")
            ld = next(iter(s3.jsonld_articles(soup)), {}) or {}
            body = s3.clean_text(ld.get("articleBody", "") or "")
            dom_body = s3.extract_from_soup(BeautifulSoup(r.content, "lxml"))
            if len(dom_body) > len(body):
                body = dom_body
            if len(body) < 150:
                continue
            title = (ld.get("headline") or s3.meta(soup, "og:title")
                     or (soup.title.get_text(strip=True) if soup.title else ""))
            return {
                "url": r.url, "source_url": rec["url"],
                "domain": re.sub(r"^www\.", "", r.url.split("/")[2]),
                "source_name": "", "title": re.sub(r"\s+", " ", title).strip(),
                "published": ld.get("datePublished") or s3.meta(soup, "article:published_time", "publishdate"),
                "modified": ld.get("dateModified") or "",
                "author": "", "section": s3.meta(soup, "article:section"),
                "keywords": s3.meta(soup, "keywords", "news_keywords"),
                "description": s3.meta(soup, "og:description", "description"),
                "content": body, "n_chars": len(body), "n_words": len(body.split()),
                "gnews_pubdate": "", "match": "retry", "query": "retry",
                "scraped_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
            }
        except Exception:
            continue
    return None


def main():
    if not os.path.exists(FAIL):
        print("tidak ada file gagal"); return
    recs, seen = [], set()
    for l in open(FAIL, encoding="utf-8"):
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r["url"] not in seen:
            seen.add(r["url"]); recs.append(r)
    done = set()
    for l in open(OUT, encoding="utf-8"):
        try:
            done.add(json.loads(l)["source_url"])
        except Exception:
            pass
    recs = [r for r in recs if r["url"] not in done]
    print(f"[retry] {len(recs)} URL gagal akan dicoba ulang")

    fo = open(OUT, "a", encoding="utf-8"); fs = open(STILL, "w", encoding="utf-8")
    cnt = {"ok": 0, "n": 0}
    local = threading.local()

    def work(r):
        if not hasattr(local, "s"):
            local.s = creq.Session(impersonate="chrome") if creq else requests.Session()
        a = try_one(r, local.s)
        with lock:
            cnt["n"] += 1
            if a:
                fo.write(json.dumps(a, ensure_ascii=False) + "\n"); fo.flush(); cnt["ok"] += 1
            else:
                fs.write(json.dumps(r, ensure_ascii=False) + "\n")
            if cnt["n"] % 100 == 0:
                print(f"  {cnt['n']}/{len(recs)} pulih={cnt['ok']}", flush=True)

    with ThreadPoolExecutor(max_workers=4 if creq else 12) as ex:
        list(as_completed([ex.submit(work, r) for r in recs]))
    fo.close(); fs.close()
    print(f"[retry] pulih {cnt['ok']} dari {len(recs)}")


if __name__ == "__main__":
    main()
