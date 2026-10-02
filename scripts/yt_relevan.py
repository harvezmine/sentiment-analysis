#!/usr/bin/env python3
"""Tandai relevansi video YouTube terhadap peristiwa KM Virgo Transport 8.

Pencarian YouTube memakai kueri longgar, sehingga ikut menarik insiden kapal
lain. Satu video kapal pesiar tenggelam dengan 6,2 juta tayangan misalnya
sempat masuk dan langsung mendominasi seluruh metrik. Filter ini memisahkannya.

Output: data/yt/relevansi.json  {video_id: 1|0}
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from konteks import T, D  # noqa: E402

SRC = D("yt", "videos.jsonl")
OUT = D("yt", "relevansi.json")

def relevan(judul, deskripsi):
    """Relevansi video menurut filter topik aktif (topik/<slug>.py)."""
    return T.relevan(f"{judul} {deskripsi}")


def main():
    if not os.path.exists(SRC):
        print("data/yt/videos.jsonl belum ada")
        return
    peta, buang = {}, []
    for line in open(SRC, encoding="utf-8"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        n = relevan(r.get("judul", ""), r.get("deskripsi", ""))
        peta[r["video_id"]] = n
        if not n:
            buang.append(r)
    json.dump(peta, open(OUT, "w", encoding="utf-8"))
    ya = sum(peta.values())
    print(f"[relevansi] {len(peta)} video -> relevan {ya}, dibuang {len(peta) - ya}")
    print(f"[relevansi] peta ditulis ke {OUT}\n")
    buang.sort(key=lambda r: -int(r.get("tayang") or 0))
    print("video yang dibuang (tayangan tertinggi):")
    for r in buang[:12]:
        print(f"  {int(r.get('tayang') or 0):>10,} | {r.get('kanal', '')[:20]:20s} | {r.get('judul', '')[:58]}")


if __name__ == "__main__":
    main()
