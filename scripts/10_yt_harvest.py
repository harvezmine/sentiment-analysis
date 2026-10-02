#!/usr/bin/env python3
"""Tahap 10: panen video YouTube tentang KM Virgo Transport 8.

Memakai InnerTube (lihat scripts/yt_client.py) sehingga tidak butuh API key
maupun kuota harian. Tiap kueri ditelusuri dua kali: urut relevansi dan urut
tanggal unggah, karena keduanya memberi hasil yang berbeda.

Output: data/yt/videos.jsonl (resume-safe) + data/yt/queries.log
"""
import importlib.util
import json
import os
import sys
import random
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from konteks import T, D  # noqa: E402

sp = importlib.util.spec_from_file_location("yt", os.path.join(ROOT, "scripts", "yt_client.py"))
yt = importlib.util.module_from_spec(sp)
sp.loader.exec_module(yt)

OUT = D("yt", "videos.jsonl")
QLOG = D("yt", "queries.log")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

KUERI = T.KUERI_YT

# params InnerTube: urutan hasil pencarian
URUT = {
    "relevansi": None,               # bawaan
    "terbaru": "CAISBAgCEAE=",       # urut tanggal unggah, hanya tipe video
}
MAKS_HALAMAN = 6                     # ~20 video per halaman


def main():
    lihat = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                lihat.add(json.loads(line)["video_id"])
            except Exception:
                pass
    selesai = set()
    if os.path.exists(QLOG):
        for line in open(QLOG, encoding="utf-8"):
            selesai.add(line.split("\t")[0])
    print(f"[yt] sudah punya {len(lihat)} video, {len(selesai)} kueri selesai", flush=True)

    c = yt.YTClient()
    fo = open(OUT, "a", encoding="utf-8")
    fq = open(QLOG, "a", encoding="utf-8")
    jobs = [(q, nama, par) for q in KUERI for nama, par in URUT.items()]

    for i, (q, nama, par) in enumerate(jobs, 1):
        kunci = f"{q}|{nama}"
        if kunci in selesai:
            continue
        cont, halaman, baru = None, 0, 0
        stop = "maks"
        for _ in range(MAKS_HALAMAN):
            try:
                j = c.cari(q, params=par, continuation=cont) if not cont else c.cari(q, continuation=cont)
            except Exception as e:
                stop = f"err:{str(e)[:50]}"
                break
            vids = yt.parse_hasil_cari(j)
            for v in vids:
                if v["video_id"] in lihat:
                    continue
                lihat.add(v["video_id"])
                v["kueri"] = q
                v["urut"] = nama
                fo.write(json.dumps(v, ensure_ascii=False) + "\n")
                baru += 1
            fo.flush()
            halaman += 1
            cont = yt.lanjutan(j)
            if not cont:
                stop = "habis"
                break
            if not vids:
                stop = "kosong"
                break
            time.sleep(1.6 + random.random() * 1.4)
        fq.write(f"{kunci}\t{halaman}\t{baru}\t{stop}\n")
        fq.flush()
        print(f"  [{i}/{len(jobs)}] +{baru:3d} (h{halaman} {stop:10s}) total={len(lihat)} "
              f":: {q[:44]} [{nama}]", flush=True)
        time.sleep(1.2 + random.random())

    fo.close()
    fq.close()
    print(f"[yt] selesai. video unik: {len(lihat)}")


if __name__ == "__main__":
    main()
