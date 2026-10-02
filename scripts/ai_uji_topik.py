#!/usr/bin/env python3
"""Uji pembanding: seberapa dekat konfigurasi topik buatan AI dengan topik yang disusun manual
(virgo, masela, tangguh), diukur pada data yang sudah dipanen.

Dua alur dibandingkan:
  A  draf langsung dari gambaran topik (alur awal wizard)
  B  riset judul nyata → draf → uji otomatis → perbaikan (scripts/ai_topik.py)

Ukuran (patokan = keputusan aturan manual yang dipakai saat panen):
  relevansi   kecocokan aturan relevan() dengan keputusan manual pada judul berita yang terjaring Google News
              (lolos/tidak lolos saringan judul), video YouTube, dan tweet: presisi, recall, F1
  jangkauan   porsi artikel relevan yang bisa ditemukan kueri berita konfigurasi itu (perkiraan: semua kata
              kueri muncul di judul/deskripsi), dan porsi video relevan untuk kueri YouTube
  isu         porsi konten relevan yang tertandai minimal satu isu

    python3 scripts/ai_uji_topik.py                 # pakai draf tersimpan bila ada
    python3 scripts/ai_uji_topik.py --ulang --topik virgo
"""
import argparse
import json
import os
import random
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

import ai_klien  # noqa: E402
import ai_topik  # noqa: E402
import ai_tugas  # noqa: E402
import topik  # noqa: E402
from topik import _umum  # noqa: E402

FOLDER = os.path.join(ROOT, "data", "_bersama", "evaluasi")

# Gambaran seperti yang diketik pengguna di wizard: inti peristiwa, wilayah, pihak; tanpa hasil riset manual.
BRIEF = {
    "virgo": {"nama": "KM Virgo Transport 8",
              "deskripsi": "Kapal feri KM Virgo Transport 8 rute Surabaya–Banjarmasin terbalik dan tenggelam di Laut Jawa "
                           "dini hari 13 September 2026 dengan sekitar 243 orang di dalamnya. Banyak penumpang hilang dan "
                           "operasi pencarian berlangsung berminggu-minggu. Pantau percakapan publik tentang pencarian "
                           "korban, penyebab kecelakaan, dan tanggung jawab operator serta regulator.",
              "wilayah": "Laut Jawa, Surabaya, Banjarmasin, Kalimantan Selatan",
              "pihak": "Basarnas, Kementerian Perhubungan, Syahbandar, operator kapal, Polri, TNI AL",
              "dari": "2026-09-12", "sampai": "2026-09-30", "catatan": ""},
    "masela": {"nama": "INPEX Masela",
               "deskripsi": "Proyek LNG Abadi di Blok Masela, Kepulauan Tanimbar, yang dioperasikan INPEX memicu rangkaian "
                            "aksi sepanjang 2026: tuntutan hak tanah adat dan ganti rugi lahan, kompensasi nelayan, tenaga "
                            "kerja lokal, hingga desakan mencabut status Proyek Strategis Nasional. Pantau seluruh "
                            "percakapan tentang proyek ini, dengan aksi warga sebagai sorotan.",
               "wilayah": "Kepulauan Tanimbar, Maluku",
               "pihak": "INPEX, SKK Migas, Kementerian ESDM, Presiden, Pemprov Maluku, Pemkab Kepulauan Tanimbar, "
                        "masyarakat adat, nelayan",
               "dari": "2026-01-01", "sampai": "", "catatan": ""},
    "tangguh": {"nama": "bp Tangguh",
                "deskripsi": "Proyek bp Tangguh (lapangan Ubadari) di Teluk Bintuni dan Fakfak, Papua Barat. Februari 2026 "
                             "kapal seismik bp dihadang kapal nelayan dan dipasangi sasi adat oleh masyarakat Arguni. Isu: "
                             "keresahan nelayan soal radius aman dan ruang laut saat pemasangan platform jacket Ubadari "
                             "(Juni 2026), tuntutan kompensasi dan hak adat (LMA, petuanan Arguni), serta tuntutan PI 10% "
                             "dan dana bagi hasil Teluk Bintuni (Mei 2026).",
                "wilayah": "Teluk Bintuni, Fakfak, Arguni, Papua Barat",
                "pihak": "bp, SKK Migas, Kementerian ESDM, LMA, Raja Petuanan Arguni, Pemkab Fakfak, Pemkab Teluk Bintuni, nelayan",
                "dari": "2026-01-01", "sampai": "", "catatan": ""},
}


def _norm(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


def pool(slug, maks_x=3000):
    """Data berlabel keputusan manual: [(teks, label 0/1)] per jenis."""
    F = topik.folder(slug)
    out = {}
    lolos = {_norm(json.loads(l)["title"]) for l in open(os.path.join(F, "urls_decoded.jsonl"), encoding="utf-8")}
    judul = {}
    for l in open(os.path.join(F, "urls_raw.jsonl"), encoding="utf-8"):
        r = json.loads(l)
        judul[_norm(r["title"])] = 1 if _norm(r["title"]) in lolos else 0
    out["berita"] = [(t, v) for t, v in judul.items()]
    rel = json.load(open(os.path.join(F, "yt", "relevansi.json"), encoding="utf-8"))
    out["youtube"] = []
    for l in open(os.path.join(F, "yt", "videos.jsonl"), encoding="utf-8"):
        v = json.loads(l)
        if str(v.get("video_id")) in rel:
            out["youtube"].append((f"{v.get('judul', '')} {(v.get('deskripsi') or '')[:300]}", int(rel[str(v['video_id'])])))
    xs = [json.loads(l) for l in open(os.path.join(F, "x", "tweets_labeled.jsonl"), encoding="utf-8")]
    xs = [x for x in xs if x.get("tipe") == "posting"]
    random.Random(1).shuffle(xs)
    out["x"] = [(x.get("teks", ""), 1 if str(x.get("relevan")) == "1" else 0) for x in xs[:maks_x]]
    return out


def ukur_relevan(fn, data):
    tp = fp = fn_ = 0
    for t, v in data:
        a = 1 if fn(t) else 0
        tp += a and v
        fp += a and not v
        fn_ += (not a) and v
    p, r = (tp / (tp + fp) if tp + fp else 0), (tp / (tp + fn_) if tp + fn_ else 0)
    return {"presisi": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0, "n": len(data),
            "relevan": sum(v for _, v in data)}


cocok_kueri = ai_topik.cocok_kueri


def jangkauan(kueri, teks):
    rendah = [t.lower() for t in teks]
    return sum(1 for t in rendah if any(cocok_kueri(q, t) for q in kueri)) / max(1, len(rendah))


def cakupan_isu(narasi_rx, teks):
    rx = [re.compile(p, re.I) for p in narasi_rx if p]
    return sum(1 for t in teks if any(r.search(t) for r in rx)) / max(1, len(teks))


def evaluasi(slug, T, data, nama):
    F = topik.folder(slug)
    art = pd.read_csv(os.path.join(F, "articles_clean.csv"), low_memory=False)
    teks_art = (art.judul.fillna("") + " " + art.deskripsi.fillna("")).tolist()
    vid_rel = [t for t, v in data["youtube"] if v]
    x_rel = [t for t, v in data["x"] if v][:1500]
    import label_teks
    narasi = list((T.NARASI or label_teks.NARASI).values())
    narasi = [p.pattern if hasattr(p, "pattern") else p for p in narasi]
    narasi_b = [p.pattern if hasattr(p, "pattern") else p for p in (getattr(T, "TOPIK_BERITA", None) or {}).values()] or narasi
    return {
        "nama": nama, "kueri_berita": len(T.KUERI_BERITA), "kueri_yt": len(T.KUERI_YT), "isu": len(T.NARASI or {}),
        "aktor": len(T.AKTOR),
        "relevan": {k: ukur_relevan(T.relevan, v) for k, v in data.items()},
        "jangkauan_berita": jangkauan(T.KUERI_BERITA, teks_art), "jangkauan_yt": jangkauan(T.KUERI_YT, vid_rel),
        "isu_berita": cakupan_isu(narasi_b, teks_art), "isu_sosial": cakupan_isu(narasi, x_rel),
        # porsi terbesar satu isu: mendekati 100% berarti ada isu yang menandai hampir semua konten (kata terlalu umum)
        "isu_maks": max([cakupan_isu([p], teks_art) for p in narasi_b] or [0]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topik", default="virgo,masela,tangguh")
    ap.add_argument("--ulang", action="store_true")
    a = ap.parse_args()
    os.makedirs(FOLDER, exist_ok=True)
    ringkas = {}
    for slug in a.topik.split(","):
        brief = BRIEF[slug]
        p = os.path.join(FOLDER, f"topik_{slug}.json")
        simpan = {} if a.ulang or not os.path.exists(p) else json.load(open(p, encoding="utf-8"))
        if "A" not in simpan:
            print(f"[{slug}] alur A: draf langsung")
            simpan["A"] = {"draf": ai_tugas.draf_topik(brief)}
            json.dump(simpan, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if "B" not in simpan:
            print(f"[{slug}] alur B: riset → draf → uji → perbaiki")
            simpan["B"] = ai_topik.susun(brief, log=lambda *m: print("   ", *m), putaran=2)
        json.dump(simpan, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        data = pool(slug)
        print(f"[{slug}] data patokan: berita {len(data['berita'])} judul ({sum(v for _, v in data['berita'])} lolos), "
              f"YouTube {len(data['youtube'])} ({sum(v for _, v in data['youtube'])} relevan), X {len(data['x'])}")
        hasil = [evaluasi(slug, topik.muat(slug), data, "manual")]
        for alur in ("A", "B"):
            cfg = {**simpan[alur]["draf"], "slug": f"uji_{slug}", "nama": brief["nama"], "dari": brief["dari"],
                   "sampai": brief["sampai"] or None}
            hasil.append(evaluasi(slug, _umum.modul(cfg), data, f"AI {alur}"))
        ringkas[slug] = hasil
        if "B" in simpan and simpan["B"].get("uji"):
            u = simpan["B"]["uji"]
            print(f"[{slug}] uji otomatis alur B: F1 {u['awal']['f1']:.0%} → {u['akhir']['f1']:.0%}, "
                  f"cakupan isu {u['awal']['cakupan_isu']:.0%} → {u['akhir']['cakupan_isu']:.0%}, "
                  f"jangkauan kueri {u['awal'].get('jangkauan', 0):.0%} → {u['akhir'].get('jangkauan', 0):.0%}")
    ph = os.path.join(FOLDER, "hasil_topik.json")
    lama = json.load(open(ph, encoding="utf-8")) if os.path.exists(ph) else {}
    json.dump({**lama, **ringkas}, open(ph, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{'topik':8} {'konfig':7} | {'F1 berita':>9} {'F1 YT':>6} {'F1 X':>6} | {'R berita':>8} {'R YT':>6} {'R X':>6} | "
          f"{'jangk.B':>7} {'jangk.YT':>8} | {'isu B':>6} {'isu S':>6} {'maks':>5} | kueri isu aktor")
    for slug, hs in ringkas.items():
        for h in hs:
            r = h["relevan"]
            print(f"{slug:8} {h['nama']:7} | {r['berita']['f1']:9.0%} {r['youtube']['f1']:6.0%} {r['x']['f1']:6.0%} | "
                  f"{r['berita']['recall']:8.0%} {r['youtube']['recall']:6.0%} {r['x']['recall']:6.0%} | "
                  f"{h['jangkauan_berita']:7.0%} {h['jangkauan_yt']:8.0%} | {h['isu_berita']:6.0%} {h['isu_sosial']:6.0%} "
                  f"{h.get('isu_maks', 0):5.0%} | "
                  f"{h['kueri_berita']:>5} {h['isu']:>3} {h['aktor']:>5}")
    print(f"\nbiaya AI proses ini: ${ai_klien.pengeluaran()['usd']:.4f}")


if __name__ == "__main__":
    main()
