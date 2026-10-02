#!/usr/bin/env python3
"""Klasifikasi tipe akun X: media, institusi, jurnalis, atau publik.

Dipakai untuk memisahkan ARUS BERITA dari SUARA PUBLIK sebelum sentimen
dihitung. Tanpa pemisahan ini, cuitan media yang berupa laporan datar akan
mencemari distribusi sentimen.

Sinyal yang dipakai (berlapis, bukan satu aturan):
  1. handle cocok daftar media nasional/daerah yang sudah diketahui
  2. bio mengandung penanda redaksi/institusi
  3. pola perilaku: volume posting tinggi + hampir semua berisi tautan
"""
import json
import os
import sys
import re
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from konteks import T, D  # noqa: E402


MEDIA_HANDLE = re.compile(
    r"^(kompas|detik|tempo|antara|liputan6|tribun|okezone|republika|suara|"
    r"kumparan|viva|sindo|merdeka|jpnn|beritasatu|katadata|bisnis|medcom|"
    r"inews|tvone|metro_?tv|metrotv|tirto|kbr|rmol|pikiran|solopos|kontan|"
    r"cnn|cnbc|jawapos|surya|radio|elshinta|rri|idntimes|narasi|bbc|dw|voa|"
    r"kabar|berita|news|media|info|redaksi|harian|koran|daily|post|times|"
    r"tvri|kompastv|e100|sonora|prfm|smartfm|trijaya|delta|gen|hard)"
    r"|(news|media|tv|fm|radio|pos|times|daily|update|info|berita)$", re.I)

BIO_MEDIA = re.compile(
    r"\b(akun resmi|official account|portal berita|media online|situs berita|"
    r"kantor berita|surat kabar|harian|koran|redaksi|newsroom|breaking news|"
    r"berita terkini|kabar terkini|stasiun (tv|radio)|radio|televisi|"
    r"news agency|news portal|media siber)\b", re.I)

BIO_INSTITUSI = re.compile(
    r"\b(akun resmi|official)\b.{0,40}\b(kementerian|kemen|badan|direktorat|"
    r"lembaga|pemerintah|pemkot|pemkab|pemprov|polri|polda|polres|tni|"
    r"basarnas|bmkg|knkt|dprd|dpr)\b"
    r"|\b(kementerian|direktorat jenderal|badan nasional|polres|polda|polsek|"
    r"korem|kodim|lanal|lantamal|basarnas|bmkg|knkt|pemkab|pemkot|pemprov)\b", re.I)

BIO_JURNALIS = re.compile(
    r"\b(jurnalis|wartawan|journalist|reporter|redaktur|editor|kontributor|"
    r"pemimpin redaksi|pemred|koresponden|correspondent|news anchor|presenter)\b", re.I)


def tipe_akun(username, bio, n_post, rasio_tautan, followers):
    u = (username or "").strip()
    b = bio or ""
    if BIO_INSTITUSI.search(b):
        return "Institusi/Pemerintah"
    if MEDIA_HANDLE.search(u) or BIO_MEDIA.search(b):
        return "Media"
    if BIO_JURNALIS.search(b):
        return "Jurnalis"
    # perilaku mirip kanal berita: banyak posting & hampir selalu bertaut
    try:
        f = int(followers or 0)
    except Exception:
        f = 0
    if n_post >= 8 and rasio_tautan >= 0.8 and f > 5000:
        return "Media (terdeteksi pola)"
    return "Publik"


def main():
    src = D("x", "tweets.jsonl")
    out = D("x", "akun.csv")
    if not os.path.exists(src):
        print("belum ada data/x/tweets.jsonl")
        return

    agg = defaultdict(lambda: {"n": 0, "tautan": 0, "bio": "", "followers": 0,
                               "nama": "", "verified": "", "lokasi": "",
                               "likes": 0, "rt": 0, "dibuat": ""})
    for line in open(src, encoding="utf-8"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        a = agg[r.get("username", "")]
        a["n"] += 1
        if r.get("urls"):
            a["tautan"] += 1
        a["bio"] = a["bio"] or r.get("user_bio", "")
        a["nama"] = a["nama"] or r.get("nama", "")
        a["lokasi"] = a["lokasi"] or r.get("user_location", "")
        a["verified"] = r.get("verified", "")
        a["dibuat"] = a["dibuat"] or r.get("user_created", "")
        try:
            a["followers"] = max(a["followers"], int(r.get("followers") or 0))
        except Exception:
            pass
        a["likes"] += int(r.get("likes") or 0)
        a["rt"] += int(r.get("retweets") or 0)

    rows = []
    for u, a in agg.items():
        if not u:
            continue
        rasio = a["tautan"] / max(a["n"], 1)
        rows.append({
            "username": u, "nama": a["nama"], "tipe": tipe_akun(u, a["bio"], a["n"], rasio, a["followers"]),
            "posting": a["n"], "followers": a["followers"], "verified": a["verified"],
            "rasio_tautan": round(rasio, 2), "total_like": a["likes"], "total_rt": a["rt"],
            "lokasi": a["lokasi"], "bio": (a["bio"] or "").replace("\n", " ")[:300],
            "akun_dibuat": a["dibuat"],
        })
    rows.sort(key=lambda r: -r["posting"])

    import csv as _csv
    with open(out, "w", encoding="utf-8", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=list(rows[0].keys()), quoting=_csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)

    c = Counter(r["tipe"] for r in rows)
    npost = Counter()
    for r in rows:
        npost[r["tipe"]] += r["posting"]
    print(f"[akun] {len(rows)} akun -> {out}\n")
    print(f"{'TIPE':26s} {'AKUN':>6s} {'POSTING':>8s}")
    for k, v in c.most_common():
        print(f"{k:26s} {v:6d} {npost[k]:8d}")


if __name__ == "__main__":
    main()
