#!/usr/bin/env python3
"""Uji kualitas klasifikasi terhadap sampel berlabel manual (data/_bersama/evaluasi/sampel_<slug>.json,
kunci "emas": {"s": sentimen, "r": relevan}). Membandingkan label aturan (label_teks) dengan varian AI.

    python3 scripts/ai_evaluasi.py                                   # varian bawaan, semua topik bersampel
    python3 scripts/ai_evaluasi.py --varian v1,v2,v2-nalar,v2-pro --topik virgo,masela

Varian: v1 = instruksi awal; v2 = rubrik selaras dashboard + contoh; akhiran -nalar = mode berpikir "low";
-pro = deepseek-v4-pro. Jawaban AI di-cache, jadi menjalankan ulang varian yang sama tidak dibayar lagi.
Hasil: data/_bersama/evaluasi/hasil_klasifikasi.json
"""
import argparse
import glob
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, ROOT)

import ai_klien  # noqa: E402
import ai_tugas  # noqa: E402
import topik  # noqa: E402

FOLDER = os.path.join(ROOT, "data", "_bersama", "evaluasi")
KELAS = ("negatif", "netral", "positif")
VARIAN = {
    "v1": {"versi": "v1"},
    "v2": {"versi": "v2"},
    "v3": {"versi": "v2"},          # rubrik v2 setelah perbaikan dari analisis kesalahan (nama baru agar tercatat terpisah)
    "v3-pro": {"versi": "v2", "model": "deepseek-v4-pro"},
    "v2-nalar": {"versi": "v2", "berpikir": "low"},
    "v2-pro": {"versi": "v2", "model": "deepseek-v4-pro"},
    "v2-pro-nalar": {"versi": "v2", "model": "deepseek-v4-pro", "berpikir": "low"},
}


def ukur(pasang):
    """pasang = [(emas, tebakan)] untuk sentimen. Akurasi, F1 makro, kappa, matriks."""
    n = len(pasang)
    if not n:
        return None
    mat = {a: {b: 0 for b in KELAS} for a in KELAS}
    for e, t in pasang:
        mat[e][t] += 1
    po = sum(mat[c][c] for c in KELAS) / n
    pe = sum((sum(mat[c].values()) / n) * (sum(mat[a][c] for a in KELAS) / n) for c in KELAS)
    f1 = []
    for c in KELAS:
        tp, pred, nyata = mat[c][c], sum(mat[a][c] for a in KELAS), sum(mat[c].values())
        p, r = (tp / pred if pred else 0), (tp / nyata if nyata else 0)
        f1.append(2 * p * r / (p + r) if p + r else 0)
    return {"n": n, "akurasi": po, "f1_makro": sum(f1) / 3, "kappa": (po - pe) / (1 - pe) if pe < 1 else 0, "matriks": mat}


def ukur_relevan(pasang):
    """pasang = [(emas_r, tebakan_r)]: akurasi dan seberapa banyak konten tidak relevan yang tertangkap."""
    if not pasang:
        return None
    tp = sum(1 for e, t in pasang if e == 0 and t == 0)
    fp = sum(1 for e, t in pasang if e == 1 and t == 0)
    fn = sum(1 for e, t in pasang if e == 0 and t == 1)
    return {"akurasi": sum(1 for e, t in pasang if e == t) / len(pasang),
            "tangkap_tidak_relevan": tp / (tp + fn) if tp + fn else None,
            "salah_buang": fp / max(1, sum(1 for e, _ in pasang if e == 1))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--varian", default="v1,v2")
    ap.add_argument("--topik", default="")
    a = ap.parse_args()
    sampel = {}
    for f in sorted(glob.glob(os.path.join(FOLDER, "sampel_*.json"))):
        slug = os.path.basename(f)[7:-5]
        if a.topik and slug not in a.topik.split(","):
            continue
        d = [x for x in json.load(open(f, encoding="utf-8")) if x.get("emas")]
        if d:
            sampel[slug] = d
    hasil = {"dibuat": time.strftime("%Y-%m-%d %H:%M"), "n": {k: len(v) for k, v in sampel.items()}, "varian": {}}

    def catat(nama, tebak, biaya=0.0, detik=0.0):
        semua, rel, per = [], [], {}
        for slug, d in sampel.items():
            ps = [(x["emas"]["s"], tebak[slug][x["h"]]["s"]) for x in d if x["h"] in tebak[slug]]
            per[slug] = ukur(ps)
            semua += ps
            rel += [(x["emas"]["r"], tebak[slug][x["h"]].get("r", 1)) for x in d if x["h"] in tebak[slug]]
        hasil["varian"][nama] = {"semua": ukur(semua), "per_topik": per, "relevan": ukur_relevan(rel),
                                 "biaya_usd": round(biaya, 4), "detik": round(detik, 1)}

    # label aturan sebagai pembanding (tidak menilai relevansi: semua dianggap relevan)
    catat("aturan", {slug: {x["h"]: {"s": x["aturan"], "r": 1} for x in d} for slug, d in sampel.items()})

    for nama in [v for v in a.varian.split(",") if v]:
        cfg = VARIAN[nama]
        sebelum, t0 = ai_klien.pengeluaran()["usd"], time.time()
        tebak = {}
        for slug, d in sampel.items():
            T = topik.muat(slug)
            item = [{"id": x["h"], "teks": x["teks"], "platform": x["platform"]} for x in d]
            lab, galat = ai_tugas.label_konten(item, T, topik=f"evaluasi:{slug}", **cfg)
            if galat:
                print(f"  {nama}/{slug}: {len(galat)} paket gagal ({galat[0][1]})")
            tebak[slug] = lab
        catat(nama, tebak, ai_klien.pengeluaran()["usd"] - sebelum, time.time() - t0)

    os.makedirs(FOLDER, exist_ok=True)
    lama = {}
    p = os.path.join(FOLDER, "hasil_klasifikasi.json")
    if os.path.exists(p):
        lama = json.load(open(p, encoding="utf-8")).get("varian", {})
    hasil["varian"] = {**lama, **hasil["varian"]}
    json.dump(hasil, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"\n{'varian':14} {'akurasi':>8} {'F1 makro':>9} {'kappa':>6} | " +
          " ".join(f"{s:>8}" for s in sampel) + f" | {'relevan':>8} {'tangkap TR':>10} {'salah buang':>11} | {'biaya':>8} {'detik':>6}")
    for nama, h in hasil["varian"].items():
        s, r = h["semua"], h["relevan"]
        print(f"{nama:14} {s['akurasi']:8.1%} {s['f1_makro']:9.3f} {s['kappa']:6.3f} | " +
              " ".join(f"{(h['per_topik'].get(t) or {}).get('akurasi', 0):8.1%}" for t in sampel) +
              f" | {r['akurasi']:8.1%} {(r['tangkap_tidak_relevan'] or 0):10.1%} {r['salah_buang']:11.1%} | "
              f"${h['biaya_usd']:7.4f} {h['detik']:6.1f}")


if __name__ == "__main__":
    main()
