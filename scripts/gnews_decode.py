"""Decode Google News RSS article URLs -> publisher URLs (batchexecute API)."""
import base64, json, re, requests

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def _gn_id(url: str) -> str | None:
    m = re.search(r"news\.google\.com/(?:rss/)?(?:articles|read)/([A-Za-z0-9_\-]+)", url)
    return m.group(1) if m else None


def get_decoding_params(gn_id: str, session: requests.Session):
    r = session.get(f"https://news.google.com/rss/articles/{gn_id}",
                    headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    sig = re.search(r'data-n-a-sg="([^"]+)"', r.text)
    ts = re.search(r'data-n-a-ts="([^"]+)"', r.text)
    if not (sig and ts):
        return None
    return {"signature": sig.group(1), "timestamp": ts.group(1), "gn_id": gn_id}


def decode_batch(params_list, session: requests.Session):
    """params_list: list of dicts from get_decoding_params. Returns list of urls."""
    payload = [
        [
            "Fbv4je",
            json.dumps([
                "garturlreq",
                [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
                 "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
                p["gn_id"], int(p["timestamp"]), p["signature"],
            ]),
            None, "generic",
        ]
        for p in params_list
    ]
    r = session.post(
        "https://news.google.com/_/DotsSplashUi/data/batchexecute",
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8", "User-Agent": UA},
        data={"f.req": json.dumps([payload])}, timeout=60,
    )
    r.raise_for_status()
    out = []
    for line in r.text.split("\n\n")[1].splitlines():
        try:
            arr = json.loads(line)
        except Exception:
            continue
        for item in arr:
            if isinstance(item, list) and len(item) > 2 and item[0] == "wrb.fr":
                try:
                    out.append(json.loads(item[2])[1])
                except Exception:
                    pass
    return out


def decode_urls(gnews_urls, batch_size=8, verbose=False):
    """Returns dict {gnews_url: real_url}."""
    s = requests.Session()
    mapping = {}
    ids = []
    for u in gnews_urls:
        gid = _gn_id(u)
        if gid:
            ids.append((u, gid))
    i = 0
    while i < len(ids):
        chunk = ids[i:i + batch_size]
        params = []
        keep = []
        for u, gid in chunk:
            try:
                p = get_decoding_params(gid, s)
            except Exception:
                p = None
            if p:
                params.append(p); keep.append(u)
        if params:
            try:
                res = decode_batch(params, s)
                for u, real in zip(keep, res):
                    mapping[u] = real
            except Exception as e:
                if verbose:
                    print("batch fail:", e)
        i += batch_size
        if verbose:
            print(f"decoded {len(mapping)}/{len(ids)}", flush=True)
    return mapping


if __name__ == "__main__":
    import sys
    test = ["https://news.google.com/rss/articles/CBMijAFBVV95cUxNVmZGbUh6R2hGTWRjQnhXWFhWdW95R3BIWE9KenA5U05Ueks2UlJwdXBvN2tWME9QVDJuVUpOWkVraFM2d3lEVlBTcHFrcGtZZzg0Q3pOSm91TGRlczI2S0tpaloySm9wMVFIb25LZDh1Z0xGX0E5ZkN6YmJKbnFYT3pSTFlhYnIyYUs0Zg?oc=5"]
    print(decode_urls(test, verbose=True))
