#!/usr/bin/env python3
"""Temukan queryId GraphQL X langsung dari bundle JavaScript aplikasi web.

queryId berubah tiap rilis X, jadi jangan di-hardcode. Script ini menambang
pasangan {queryId, operationName} dari seluruh bundle dan menyimpannya ke
data/x/query_ids.json.
"""
import importlib.util
import json
import os
import re

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "_bersama", "x_query_ids.json")

PAT = re.compile(r'queryId\s*:\s*"([A-Za-z0-9_\-]{10,})"\s*,\s*operationName\s*:\s*"(\w+)"')
PAT2 = re.compile(r'operationName\s*:\s*"(\w+)"\s*,\s*queryId\s*:\s*"([A-Za-z0-9_\-]{10,})"')

PENTING = ("SearchTimeline", "TweetDetail", "UserTweets", "UserByScreenName",
           "UserTweetsAndReplies", "Retweeters", "Favoriters", "UsersByRestIds")


def _client():
    """Pakai XClient yang sudah ada supaya kredensial hanya dibaca di satu tempat."""
    sp = importlib.util.spec_from_file_location("xc", os.path.join(ROOT, "scripts", "x_client.py"))
    xc = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(xc)
    return xc.XClient()


def main():
    c = _client()
    s = c.s  # sesi yang sudah membawa cookie + header browser
    html = s.get("https://x.com/home", timeout=45).text
    urls = sorted(set(re.findall(
        r'https://abs\.twimg\.com/responsive-web/client-web[^"\'\s]+\.js', html)))
    print(f"[qid] {len(urls)} bundle ditemukan", flush=True)

    found = {}
    for i, u in enumerate(urls, 1):
        try:
            t = s.get(u, timeout=45).text
        except Exception:
            continue
        for m in PAT.finditer(t):
            found[m.group(2)] = m.group(1)
        for m in PAT2.finditer(t):
            found[m.group(1)] = m.group(2)
        if i % 25 == 0:
            print(f"  {i}/{len(urls)} -> {len(found)} operasi", flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(found, open(OUT, "w", encoding="utf-8"),
              indent=1, ensure_ascii=False, sort_keys=True)
    print(f"[qid] {len(found)} operasi -> {OUT}")
    for k in PENTING:
        print(f"   {k:24s} {found.get(k, '- TIDAK DITEMUKAN -')}")


if __name__ == "__main__":
    main()
