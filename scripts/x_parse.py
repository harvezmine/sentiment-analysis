#!/usr/bin/env python3
"""Parser response GraphQL X (SearchTimeline / TweetDetail / UserTweets).

Dipakai untuk mengubah dump JSON mentah dari network interception
menjadi baris tweet yang rapi. Tahan terhadap perubahan struktur:
menelusuri seluruh pohon JSON mencari objek bertipe Tweet/TweetWithVisibilityResults.
"""
import json, re, os, sys, html
from datetime import datetime, timezone, timedelta

WIB = timezone(timedelta(hours=7))


def walk(o):
    """Yield semua dict di dalam struktur JSON."""
    stack = [o]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            yield x
            stack.extend(x.values())
        elif isinstance(x, list):
            stack.extend(x)


def _legacy(t):
    if "legacy" in t and isinstance(t["legacy"], dict):
        return t["legacy"]
    return t


def _user_of(t):
    ur = (t.get("core", {}) or {}).get("user_results", {}) or {}
    res = ur.get("result", {}) or {}
    leg = res.get("legacy", {}) or {}
    core = res.get("core", {}) or {}
    avatar = res.get("avatar", {}) or {}
    return {
        "user_id": res.get("rest_id", ""),
        "username": core.get("screen_name") or leg.get("screen_name", ""),
        "name": core.get("name") or leg.get("name", ""),
        "user_created": core.get("created_at") or leg.get("created_at", ""),
        "followers": leg.get("followers_count", (res.get("relationship_counts", {}) or {}).get("followers", "")),
        "following": leg.get("friends_count", (res.get("relationship_counts", {}) or {}).get("following", "")),
        "user_tweets": leg.get("statuses_count", ""),
        "user_desc": (res.get("profile_bio", {}) or {}).get("description") or leg.get("description", ""),
        "user_location": ((res.get("location", {}) or {}).get("location")
                          if isinstance(res.get("location"), dict) else leg.get("location", "")),
        "verified": res.get("is_blue_verified", leg.get("verified", "")),
        "avatar": (avatar.get("image_url") or leg.get("profile_image_url_https", "")),
    }


def parse_tweet(t):
    """t = objek dengan __typename Tweet / TweetWithVisibilityResults."""
    if t.get("__typename") == "TweetWithVisibilityResults":
        t = t.get("tweet", t)
    if t.get("__typename") not in ("Tweet", None) and "rest_id" not in t:
        return None
    leg = _legacy(t)
    rest_id = t.get("rest_id") or leg.get("id_str")
    if not rest_id:
        return None
    note = (((t.get("note_tweet", {}) or {}).get("note_tweet_results", {}) or {})
            .get("result", {}) or {})
    text = note.get("text") or leg.get("full_text") or leg.get("text") or ""
    text = html.unescape(text)
    ents = note.get("entity_set") or leg.get("entities", {}) or {}
    views = (t.get("views", {}) or {}).get("count", "")
    created = leg.get("created_at", "")
    try:
        dt = datetime.strptime(created, "%a %b %d %H:%M:%S %z %Y").astimezone(WIB)
        tgl, waktu = dt.strftime("%Y-%m-%d"), dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        tgl = waktu = ""
    u = _user_of(t)
    media = (ents.get("media") or (leg.get("extended_entities", {}) or {}).get("media") or [])
    return {
        "tweet_id": rest_id,
        "tanggal": tgl, "waktu_wib": waktu, "created_at": created,
        "username": u["username"], "nama": u["name"], "user_id": u["user_id"],
        "followers": u["followers"], "following": u["following"],
        "user_tweets": u["user_tweets"], "verified": u["verified"],
        "user_bio": u["user_desc"], "user_location": u["user_location"],
        "user_created": u["user_created"],
        "teks": text,
        "lang": leg.get("lang", ""),
        "likes": leg.get("favorite_count", 0),
        "retweets": leg.get("retweet_count", 0),
        "replies": leg.get("reply_count", 0),
        "quotes": leg.get("quote_count", 0),
        "bookmarks": leg.get("bookmark_count", 0),
        "views": views,
        "is_retweet": bool(leg.get("retweeted_status_result")),
        "is_quote": bool(leg.get("is_quote_status")),
        "reply_to_user": leg.get("in_reply_to_screen_name", ""),
        "reply_to_tweet": leg.get("in_reply_to_status_id_str", ""),
        "conversation_id": leg.get("conversation_id_str", ""),
        "hashtags": "; ".join(h.get("text", "") for h in ents.get("hashtags", [])),
        "mentions": "; ".join(m.get("screen_name", "") for m in ents.get("user_mentions", [])),
        "urls": "; ".join(x.get("expanded_url", "") for x in ents.get("urls", [])),
        "media_type": "; ".join(m.get("type", "") for m in media),
        "media_url": "; ".join(m.get("media_url_https", "") for m in media),
        "source": re.sub(r"<[^>]+>", "", t.get("source", "") or ""),
        "url": f"https://x.com/{u['username']}/status/{rest_id}" if u["username"] else "",
    }


def parse_blob(obj):
    """Ambil semua tweet unik dari satu response JSON."""
    out, seen = [], set()
    for d in walk(obj):
        tn = d.get("__typename")
        if tn in ("Tweet", "TweetWithVisibilityResults"):
            r = parse_tweet(d)
            if r and r["tweet_id"] not in seen:
                seen.add(r["tweet_id"]); out.append(r)
    return out


def parse_files(paths):
    all_rows, seen = [], set()
    for p in paths:
        try:
            obj = json.load(open(p, encoding="utf-8"))
        except Exception as e:
            print(f"  skip {p}: {e}"); continue
        for r in parse_blob(obj):
            if r["tweet_id"] not in seen:
                seen.add(r["tweet_id"]); all_rows.append(r)
    return all_rows


if __name__ == "__main__":
    import glob
    files = sys.argv[1:] or sorted(glob.glob("data/x/raw/*.json"))
    rows = parse_files(files)
    print(f"{len(rows)} tweet unik dari {len(files)} file")
    with open("data/x/tweets.jsonl", "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
