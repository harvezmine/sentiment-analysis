#!/usr/bin/env python3
"""Tahap 3: scrape isi artikel dari URL publisher.
Strategi ekstraksi berlapis: JSON-LD NewsArticle -> selector khas media ID -> heuristik <p>.
Output: data/articles.jsonl (append + resume-safe), raw HTML tidak disimpan.
"""
import json, os, re, sys, threading, time, random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from konteks import T, D  # noqa: E402

IN = D("urls_decoded.jsonl")
OUT = D("articles.jsonl")
FAIL = D("failed.jsonl")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

# paksa halaman penuh (anti-paginasi)
FULLPAGE = {
    "detik.com": "?single=1", "news.detik.com": "?single=1", "finance.detik.com": "?single=1",
    "kompas.com": "?page=all", "regional.kompas.com": "?page=all", "nasional.kompas.com": "?page=all",
    "money.kompas.com": "?page=all", "megapolitan.kompas.com": "?page=all",
    "tribunnews.com": "?page=all", "suara.com": "?page=all",
}

CONTENT_SELECTORS = [
    "div.detail__body-text", "div.detail-text", "div.read__content", "div.article-content",
    "div.detail-konten", "div.detail_text", "div#detikdetailtext", "div.itp_bodycontent",
    "div.content-text", "div.entry-content", "div.post-content", "div.article__content",
    "div.article-body", "div.body-content", "div.detail-desc", "div.txt_conten",
    "div.baca", "div.isi-berita", "div.content_detail", "div.detailsclear",
    "article .content", "div[itemprop='articleBody']", "div.article__body", "section.detail-text",
    "div.news-content", "div.post-body", "div.td-post-content", "div.single-content",
    "div.detail-artikel", "div.detail_konten", "div.wrap__article-detail-content",
    "div.read-page--content", "div.article-page", "div.paragraph", "main article",
]

JUNK = re.compile(
    r"baca juga|simak juga|lihat juga|artikel ini telah tayang|saksikan juga|"
    r"tonton juga|ikuti (berita|kami)|advertisement|adsense|scroll to continue|"
    r"gabung (di|ke) (kanal|grup)|copyright|hak cipta|editor\s*:|reporter\s*:|"
    r"^\s*(baca|video|foto|infografis)\s*:|halaman selanjutnya|klik di sini|"
    r"dapatkan (update|berita)|whatsapp channel|telegram|download aplikasi", re.I)

lock = threading.Lock()
domain_last = defaultdict(float)
domain_lock = threading.Lock()


def throttle(dom, gap=0.8):
    with domain_lock:
        wait = domain_last[dom] + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        domain_last[dom] = time.time()


def jsonld_articles(soup):
    for tag in soup.find_all("script", type=lambda t: t and "ld+json" in t):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except Exception:
            continue
        stack = [data]
        while stack:
            d = stack.pop()
            if isinstance(d, list):
                stack.extend(d)
            elif isinstance(d, dict):
                if "@graph" in d:
                    stack.extend(d["@graph"] if isinstance(d["@graph"], list) else [d["@graph"]])
                t = d.get("@type")
                types = t if isinstance(t, list) else [t]
                if any(str(x).lower() in ("newsarticle", "article", "reportagenewsarticle",
                                          "blogposting", "liveblogposting") for x in types):
                    yield d


def clean_text(txt):
    lines = [re.sub(r"\s+", " ", l).strip() for l in txt.split("\n")]
    keep = [l for l in lines if l and len(l) > 25 and not JUNK.search(l)]
    return "\n".join(keep)


def extract_from_soup(soup):
    # buang elemen pengganggu
    for sel in ["script", "style", "noscript", "iframe", "figure", "figcaption",
                "aside", "nav", "footer", "header", "form",
                ".baca-juga", ".read-also", ".linksisip", ".para_caption",
                ".detail__body-tag", ".tag", ".related", ".share", ".breadcrumb",
                ".advertisement", ".ads", "[class*='baca-juga']", "[class*='read-also']"]:
        for el in soup.select(sel):
            el.decompose()
    best = ""
    for sel in CONTENT_SELECTORS:
        for node in soup.select(sel):
            ps = node.find_all("p")
            txt = "\n".join(p.get_text(" ", strip=True) for p in ps) if ps else node.get_text("\n", strip=True)
            txt = clean_text(txt)
            if len(txt) > len(best):
                best = txt
        if len(best) > 600:
            break
    if len(best) < 250:  # heuristik terakhir: semua <p> panjang di halaman
        ps = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        txt = clean_text("\n".join(ps))
        if len(txt) > len(best):
            best = txt
    return best


def meta(soup, *names):
    for n in names:
        for attr in ("property", "name", "itemprop"):
            el = soup.find("meta", attrs={attr: n})
            if el and el.get("content"):
                return el["content"].strip()
    return ""


def scrape(rec, session):
    url = rec["url"]
    dom = urlparse(url).netloc.replace("www.", "")
    base = dom
    suffix = FULLPAGE.get(base) or FULLPAGE.get(".".join(base.split(".")[-2:]), "")
    target = url + suffix if suffix and "?" not in url else url
    throttle(dom)
    r = session.get(target, headers=HDRS, timeout=35, allow_redirects=True)
    if r.status_code != 200 or len(r.content) < 500:
        raise RuntimeError(f"HTTP {r.status_code}")
    soup = BeautifulSoup(r.content, "lxml")

    ld = next(iter(jsonld_articles(soup)), {}) or {}
    body = ""
    if isinstance(ld.get("articleBody"), str):
        body = clean_text(ld["articleBody"].replace("\\n", "\n"))
    body_dom = extract_from_soup(BeautifulSoup(r.content, "lxml"))
    if len(body_dom) > len(body):
        body = body_dom

    def author_of(a):
        if isinstance(a, dict):
            return a.get("name", "")
        if isinstance(a, list):
            return ", ".join(filter(None, (author_of(x) for x in a)))
        return str(a or "")

    title = (ld.get("headline") or meta(soup, "og:title", "twitter:title")
             or (soup.title.get_text(strip=True) if soup.title else "") or rec.get("title", ""))
    published = (ld.get("datePublished") or meta(soup, "article:published_time", "datePublished",
                                                "publishdate", "pubdate", "og:updated_time") or "")
    modified = ld.get("dateModified") or meta(soup, "article:modified_time", "dateModified") or ""
    author = author_of(ld.get("author")) or meta(soup, "author", "article:author", "og:article:author")
    desc = meta(soup, "og:description", "description", "twitter:description")
    section = (meta(soup, "article:section", "articleSection")
               or (ld.get("articleSection") if isinstance(ld.get("articleSection"), str) else ""))
    kw = meta(soup, "keywords", "news_keywords", "article:tag")

    return {
        "url": r.url, "source_url": url, "domain": dom,
        "source_name": rec.get("source_name", ""),
        "title": re.sub(r"\s+", " ", title).strip(),
        "published": published, "modified": modified,
        "author": author[:300], "section": section, "keywords": kw[:500],
        "description": desc, "content": body,
        "n_chars": len(body), "n_words": len(body.split()),
        "gnews_pubdate": rec.get("pub_date", ""),
        "match": rec.get("match", ""), "query": rec.get("query", ""),
        "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def main():
    # URL dari Google News (tahap 2) + mesin pencari internal media (tahap 5)
    rows, lihat = [], set()
    for f in (IN, D("urls_native.jsonl")):
        if not os.path.exists(f):
            continue
        for l in open(f, encoding="utf-8"):
            try:
                r = json.loads(l)
            except Exception:
                continue
            if r.get("url") and r["url"] not in lihat:
                lihat.add(r["url"])
                rows.append(r)
    done = set()
    if os.path.exists(OUT):
        for l in open(OUT, encoding="utf-8"):
            try:
                done.add(json.loads(l)["source_url"])
            except Exception:
                pass
    todo = [r for r in rows if r["url"] not in done]
    print(f"[scrape] total={len(rows)} sudah={len(done)} todo={len(todo)}", flush=True)

    fo = open(OUT, "a", encoding="utf-8")
    ff = open(FAIL, "a", encoding="utf-8")
    cnt = {"ok": 0, "fail": 0, "n": 0}
    local = threading.local()

    def work(rec):
        if not hasattr(local, "s"):
            local.s = requests.Session()
        try:
            art = scrape(rec, local.s)
            if art["n_chars"] < 120:
                raise RuntimeError("konten terlalu pendek")
            with lock:
                fo.write(json.dumps(art, ensure_ascii=False) + "\n"); fo.flush()
                cnt["ok"] += 1
        except Exception as e:
            with lock:
                ff.write(json.dumps({"url": rec["url"], "err": str(e)[:200]}, ensure_ascii=False) + "\n")
                cnt["fail"] += 1
        with lock:
            cnt["n"] += 1
            if cnt["n"] % 100 == 0:
                print(f"  {cnt['n']}/{len(todo)} ok={cnt['ok']} fail={cnt['fail']}", flush=True)

    with ThreadPoolExecutor(max_workers=16) as ex:
        list(as_completed([ex.submit(work, r) for r in todo]))
    fo.close(); ff.close()
    print(f"[scrape] selesai ok={cnt['ok']} fail={cnt['fail']} -> {OUT}")


if __name__ == "__main__":
    main()
