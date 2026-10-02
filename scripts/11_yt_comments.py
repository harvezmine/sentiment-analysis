#!/usr/bin/env python3
"""Tahap 11: panen komentar (beserta balasan) dan metrik video YouTube.

Untuk tiap video: ambil detail (jumlah suka, tayangan, tanggal terbit) lalu
telusuri komentar dengan continuation. Token balasan yang muncul di tiap
halaman ikut ditelusuri, sehingga percakapan bertingkat ikut terjaring.

Catatan: siaran langsung dilewati — kolomnya berisi live chat, bukan komentar,
dan YouTube tidak menyimpannya sebagai komentar setelah siaran berakhir.

Output: data/yt/komentar.jsonl, data/yt/video_detail.jsonl, data/yt/videos.log
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

SRC = D("yt", "videos.jsonl")
OUT = D("yt", "komentar.jsonl")
DET = D("yt", "video_detail.jsonl")
VLOG = D("yt", "videos.log")

MAKS_HALAMAN = 8       # halaman komentar per video (~20 komentar/halaman)
MAKS_BALASAN = 3       # token balasan yang ditelusuri per halaman
MAKS_VIDEO = 600


def semua_lanjutan(obj):
    """Semua token continuation pada satu respons, sesuai urutan kemunculan."""
    token = []
    for d in yt.walk(obj):
        cir = d.get("continuationItemRenderer")
        if not isinstance(cir, dict):
            continue
        t = (((cir.get("continuationEndpoint") or {}).get("continuationCommand") or {})
             .get("token"))
        if not t:
            btn = (cir.get("button") or {}).get("buttonRenderer") or {}
            t = ((btn.get("command") or {}).get("continuationCommand") or {}).get("token")
        if t and t not in token:
            token.append(t)
    return token


def main():
    if not os.path.exists(SRC):
        print("[yt-komentar] data/yt/videos.jsonl belum ada — jalankan tahap 10 dulu")
        return

    # peta relevansi dari scripts/yt_relevan.py — mencegah insiden kapal lain
    # ikut terpanen komentarnya (satu video kapal pesiar 6,2 jt tayangan
    # sempat lolos dan mendominasi seluruh metrik)
    frel = D("yt", "relevansi.json")
    relevan = json.load(open(frel, encoding="utf-8")) if os.path.exists(frel) else {}
    if not relevan:
        # topik baru: peta belum dibuat 12_yt_relevan -> hitung dari filter topik
        for line in open(SRC, encoding="utf-8"):
            try:
                v = json.loads(line)
            except Exception:
                continue
            relevan[v["video_id"]] = T.relevan(f"{v.get('judul', '')} {v.get('deskripsi', '')}")

    video = []
    lihat_v = set()
    for line in open(SRC, encoding="utf-8"):
        try:
            v = json.loads(line)
        except Exception:
            continue
        if v["video_id"] in lihat_v or v.get("langsung"):
            continue
        if relevan and not relevan.get(v["video_id"], 1):
            continue
        lihat_v.add(v["video_id"])
        video.append(v)
    video.sort(key=lambda v: -int(v.get("tayang") or 0))
    video = video[:MAKS_VIDEO]

    selesai = set()
    if os.path.exists(VLOG):
        for line in open(VLOG, encoding="utf-8"):
            selesai.add(line.split("\t")[0])
    lihat_k = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                lihat_k.add(json.loads(line)["komentar_id"])
            except Exception:
                pass
    print(f"[yt-komentar] {len(video)} video non-live; {len(selesai)} sudah diproses, "
          f"{len(lihat_k)} komentar tersimpan", flush=True)

    c = yt.YTClient()
    fo = open(OUT, "a", encoding="utf-8")
    fd = open(DET, "a", encoding="utf-8")
    fl = open(VLOG, "a", encoding="utf-8")

    for i, v in enumerate(video, 1):
        vid = v["video_id"]
        if vid in selesai:
            continue
        try:
            n = c.next(video_id=vid)
        except Exception as e:
            fl.write(f"{vid}\t0\t0\terr:{str(e)[:50]}\n")
            fl.flush()
            continue

        try:
            det = yt.parse_detail_video(n, c.player(vid))
        except Exception:
            det = yt.parse_detail_video(n)
        det.update({"video_id": vid, "url": v["url"],
                    "judul": det.get("judul") or v.get("judul", ""),
                    "kanal": det.get("kanal") or v.get("kanal", ""),
                    "kueri": v.get("kueri", "")})
        fd.write(json.dumps(det, ensure_ascii=False) + "\n")
        fd.flush()

        cont = yt.lanjutan(n)
        halaman, baru = 0, 0
        stop = "maks"
        while cont and halaman < MAKS_HALAMAN:
            try:
                k = c.next(continuation=cont)
            except Exception as e:
                stop = f"err:{str(e)[:40]}"
                break
            for x in yt.parse_komentar(k):
                kid = x.get("komentar_id") or ""
                if not kid or kid in lihat_k:
                    continue
                lihat_k.add(kid)
                x.update({"video_id": vid, "video_judul": det.get("judul", ""),
                          "kanal": det.get("kanal", ""), "video_url": v["url"]})
                fo.write(json.dumps(x, ensure_ascii=False) + "\n")
                baru += 1
            fo.flush()
            halaman += 1

            token = semua_lanjutan(k)
            if not token:
                stop = "habis"
                break
            # token terakhir = halaman berikutnya; sisanya = pembuka balasan
            lanjut = token[-1]
            for tb in token[:-1][:MAKS_BALASAN]:
                try:
                    kb = c.next(continuation=tb)
                except Exception:
                    continue
                for x in yt.parse_komentar(kb):
                    kid = x.get("komentar_id") or ""
                    if not kid or kid in lihat_k:
                        continue
                    lihat_k.add(kid)
                    x.update({"video_id": vid, "video_judul": det.get("judul", ""),
                              "kanal": det.get("kanal", ""), "video_url": v["url"],
                              "balasan": 1})
                    fo.write(json.dumps(x, ensure_ascii=False) + "\n")
                    baru += 1
                fo.flush()
                time.sleep(0.9 + random.random() * 0.7)
            cont = lanjut if lanjut != cont else None
            time.sleep(1.1 + random.random() * 0.9)

        fl.write(f"{vid}\t{halaman}\t{baru}\t{stop}\n")
        fl.flush()
        print(f"  [{i}/{len(video)}] {vid} suka={det.get('suka', 0):>6} "
              f"tayang={det.get('tayang', 0):>9,} +{baru:4d} komentar ({stop}) "
              f"total={len(lihat_k)} :: {det.get('judul', '')[:42]}", flush=True)
        time.sleep(0.8 + random.random() * 0.8)

    fo.close()
    fd.close()
    fl.close()
    print(f"[yt-komentar] selesai. komentar unik: {len(lihat_k)}")


if __name__ == "__main__":
    main()
