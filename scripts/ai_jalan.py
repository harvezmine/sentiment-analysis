#!/usr/bin/env python3
"""Pelaksana tugas AI (dipanggil antrean halaman Kelola, bisa juga dari terminal).

    TOPIK=masela python3 scripts/ai_jalan.py label [--batas-usd 1.5]     # label AI semua konten media sosial yang belum
    TOPIK=masela python3 scripts/ai_jalan.py validasi --n 150             # sampel validasi + label AI-nya
    TOPIK=masela python3 scripts/ai_jalan.py klaster [--k 1,3]            # draf nama & catatan klaster (graf seluruh periode)
    TOPIK=masela python3 scripts/ai_jalan.py kesimpulan --dari 2026-07-01 --sampai 2026-07-31
    python3 scripts/ai_jalan.py topik --brief brief.json --keluar draf.json

Baris "##PROGRES a/b" dan "##BIAYA x" di keluaran dibaca halaman Kelola untuk bilah progres.
"""
import argparse
import json
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "webapp"))
sys.path.insert(0, ROOT)

import ai_klien  # noqa: E402
import ai_tugas  # noqa: E402
import label_ai  # noqa: E402


def lapor(a, b):
    print(f"##PROGRES {a}/{b}", flush=True)


def lapor_biaya():
    print(f"##BIAYA {ai_klien.pengeluaran()['usd']:.4f}", flush=True)


def _topik():
    import topik
    slug = os.environ.get("TOPIK")
    if not slug:
        sys.exit("TOPIK belum diisi")
    return slug, topik.muat(slug)


def _konten_sosial(slug):
    """Konten media sosial periode topik, dengan label aturan (bukan label AI) untuk pembanding."""
    import sumber
    df = sumber.semua_mentah(slug)                                  # label aturan, tanpa label AI
    return df[(df.platform != "Berita") & df.sentimen.isin(["negatif", "netral", "positif"])]


# --------------------------------------------------------------- label semua konten
def tugas_label(a):
    slug, T = _topik()
    ai_klien.atur_batas(a.batas_usd)
    sos = _konten_sosial(slug)
    sudah = label_ai.muat_label(slug)
    sos = sos.assign(h=sos.teks.map(label_ai.sidik))
    belum = sos[~sos.h.isin(sudah)].drop_duplicates("h")
    belum = belum[belum.teks.str.strip().str.len() > 0]
    print(f"[label] {len(sos)} konten media sosial, {len(sos) - len(belum)} sudah berlabel AI, {len(belum)} akan dilabeli")
    n, selesai = len(belum), 0
    lapor(0, n)
    model = ai_klien.setelan()["model"]
    # simpan per potongan: bila dibatalkan atau anggaran habis, hasil yang sudah ada tidak hilang
    for i in range(0, n, 500):
        bagian = belum.iloc[i:i + 500]
        item = [{"id": r.h, "teks": r.teks, "platform": r.platform} for r in bagian.itertuples()]
        try:
            hasil, galat = ai_tugas.label_konten(item, T, topik=slug,
                                                 progres=lambda x, _y: lapor(selesai + x, n))
        except ai_klien.AIBatasBiaya as e:
            print(f"[label] berhenti: {e}")
            break
        label_ai.tambah_label(slug, [{"h": h, **v, "m": model} for h, v in hasil.items()])
        selesai += len(bagian)
        lapor(selesai, n)
        lapor_biaya()
        if galat:
            print(f"[label] {len(galat)} paket gagal di potongan ini: {galat[0][1]}")
    p = ai_klien.pengeluaran()
    print(f"[label] selesai: {len(label_ai.muat_label(slug))} teks berlabel AI · biaya ${p['usd']:.4f} "
          f"({p['panggilan']} panggilan)")


# --------------------------------------------------------------- sampel validasi
def tugas_validasi(a):
    slug, T = _topik()
    ai_klien.atur_batas(a.batas_usd)
    sos = _konten_sosial(slug)
    sos = sos[sos.teks.str.strip().str.len() >= 20].drop_duplicates("teks")
    rnd = random.Random(a.seed)
    # bertingkat per label aturan agar konten negatif dan positif cukup terwakili
    per = max(1, a.n // 3)
    ambil = []
    for s in ("negatif", "netral", "positif"):
        g = sos[sos.sentimen == s]
        idx = list(g.index)
        rnd.shuffle(idx)
        ambil += idx[:per]
    sisa = [i for i in sos.index if i not in set(ambil)]
    rnd.shuffle(sisa)
    ambil += sisa[:max(0, a.n - len(ambil))]
    sampel = sos.loc[ambil].sample(frac=1, random_state=a.seed)
    item = [{"id": str(r.id), "platform": r.platform, "teks": r.teks, "penulis": r.penulis, "tanggal": r.tanggal,
             "h": label_ai.sidik(r.teks), "aturan": {"s": r.sentimen, "e": r.emosi}} for r in sampel.itertuples()]
    print(f"[validasi] sampel {len(item)} konten")
    lapor(0, len(item))
    if ai_klien.tersedia():
        hasil, galat = ai_tugas.label_konten([{"id": x["id"], "teks": x["teks"], "platform": x["platform"]} for x in item],
                                             T, topik=slug, progres=lapor)
        for x in item:
            if x["id"] in hasil:
                x["ai"] = hasil[x["id"]]
        label_ai.tambah_label(slug, [{"h": x["h"], **x["ai"], "m": ai_klien.setelan()["model"]} for x in item if x.get("ai")])
        lapor_biaya()
    lama = label_ai.baca_json(label_ai.berkas(slug, "validasi.json"), {}) or {}
    # label manusia dari sampel lama tetap dipakai bila teksnya sama
    manusia = {x["h"]: x["manusia"] for x in lama.get("item", []) if x.get("manusia")}
    for x in item:
        if x["h"] in manusia:
            x["manusia"] = manusia[x["h"]]
    label_ai.tulis_json(label_ai.berkas(slug, "validasi.json"),
                        {"dibuat": time.strftime("%Y-%m-%d %H:%M"), "model": ai_klien.setelan()["model"], "item": item})
    lapor(len(item), len(item))
    print(f"[validasi] tersimpan · biaya ${ai_klien.pengeluaran()['usd']:.4f}")


# --------------------------------------------------------------- klaster SNA
def data_klaster(folder, maks=10, hanya=None):
    """Bahan untuk nama_klaster dari sna.json + sna_teks.json di folder graf."""
    so = (json.load(open(os.path.join(folder, "sna.json"), encoding="utf-8")).get("sosial") or {})
    try:
        teks = json.load(open(os.path.join(folder, "sna_teks.json"), encoding="utf-8")).get("sosial") or []
    except FileNotFoundError:
        teks = []
    simpul, sisi = so.get("simpul", []), so.get("sisi", [])
    out = []
    for c in (so.get("klaster") or [])[:maks]:
        if hanya and c["k"] + 1 not in hanya:
            continue
        anggota = {i for i, n in enumerate(simpul) if n.get("k") == c["k"]}
        es = sorted([(i, e) for i, e in enumerate(sisi) if e["a"] in anggota and e["b"] in anggota],
                    key=lambda t: -t[1].get("w", 1))
        contoh = []
        for i, e in es:
            tt = teks[i] if i < len(teks) else []
            if tt:
                contoh.append({"oleh": simpul[e["a"]]["l"], "ke": simpul[e["b"]]["l"], "teks": tt[0], "s": e.get("s", "")})
            if len(contoh) >= 30:
                break
        for x in c.get("contoh", []):                    # unggahan paling disukai di klaster
            contoh.insert(0, {"oleh": x.get("oleh"), "ke": "", "teks": x.get("t", ""), "suka": x.get("l", 0), "s": x.get("s", "")})
        plat = {"x": "X", "yt": "YouTube", "ig": "Instagram", "th": "Threads"}
        out.append({
            "no": c["k"] + 1, "kunci": (c.get("tokoh_id") or [None])[0], "nama_sekarang": c.get("nama") or c.get("nama_auto"),
            "kurasi": bool(c.get("nama")), "simpul": c["simpul"], "interaksi": c["interaksi"],
            "platform": ", ".join(f"{plat.get(p, p)} {v}" for p, v in (c.get("platform") or {}).items()),
            "sentimen": ", ".join(f"{k} {v}%" for k, v in (c.get("sentimen") or {}).items()),
            "emosi": ", ".join(c.get("emosi_utama") or []), "isu": c.get("narasi") or [], "kata": c.get("kata") or [],
            "tokoh": c.get("tokoh") or [], "contoh": contoh[:32]})
    return out


def namai(bahan, T, slug):
    hasil, galat = ai_klien.paralel(lambda d: ai_tugas.nama_klaster(d, T, topik=slug), bahan, n=4,
                                    progres=lapor)
    return {d["no"]: h for d, h in zip(bahan, hasil) if h}, galat


def tugas_klaster(a):
    slug, T = _topik()
    ai_klien.atur_batas(a.batas_usd)
    import topik
    hanya = {int(x) for x in a.k.split(",")} if a.k else None
    bahan = data_klaster(topik.folder(slug), hanya=hanya)
    print(f"[klaster] {len(bahan)} klaster")
    lapor(0, len(bahan))
    hasil, galat = namai(bahan, T, slug)
    p = label_ai.berkas(slug, "klaster.json")
    draf = label_ai.baca_json(p, {}) or {}
    for d in bahan:
        if d["no"] in hasil and d["kunci"]:
            draf[d["kunci"]] = {**hasil[d["no"]], "no": d["no"], "dibuat": time.strftime("%Y-%m-%d %H:%M")}
    label_ai.tulis_json(p, draf)
    lapor_biaya()
    for i, g in galat:
        print(f"[klaster] K{bahan[i]['no']} gagal: {g}")
    print(f"[klaster] {len(hasil)} draf tersimpan · biaya ${ai_klien.pengeluaran()['usd']:.4f}")


def namai_rentang(folder, T, slug, log=print):
    """Nama & catatan klaster untuk graf satu periode (laporan per rentang): ditulis langsung ke sna.json
    periode itu dan disimpan di klaster_ai.json agar tidak dibayar ulang."""
    p = os.path.join(folder, "sna.json")
    d = json.load(open(p, encoding="utf-8"))
    so = d.get("sosial") or {}
    simpan = label_ai.baca_json(os.path.join(folder, "klaster_ai.json"), {}) or {}
    bahan = [x for x in data_klaster(folder) if x["kunci"] not in simpan]
    if bahan:
        log(f"[laporan] menulis nama {len(bahan)} klaster dengan AI")
        hasil, _ = namai(bahan, T, slug)
        for x in bahan:
            if x["no"] in hasil:
                simpan[x["kunci"]] = hasil[x["no"]]
        label_ai.tulis_json(os.path.join(folder, "klaster_ai.json"), simpan)
    ganti = {}
    for c in so.get("klaster", []):
        h = simpan.get((c.get("tokoh_id") or [None])[0])
        if h and not c.get("nama"):
            ganti[c.get("nama_auto")] = h["nama"]
            c["nama"], c["butir"], c["kurasi"] = h["nama"], h["butir"], "ai"
    for w in so.get("wawasan", []):
        for lama, baru in ganti.items():
            if lama:
                w["judul"] = w.get("judul", "").replace(lama, baru)
                w["isi"] = w.get("isi", "").replace(lama, baru)
    label_ai.tulis_json(p, d)
    return len(ganti)


# --------------------------------------------------------------- kesimpulan
def tugas_kesimpulan(a):
    slug, T = _topik()
    ai_klien.atur_batas(a.batas_usd)
    import laporan
    d1, d2, penuh = laporan.periode(slug, a.dari, a.sampai)
    if not penuh:
        laporan.siapkan_sna(slug, d1, d2)
    lapor(0, 2)
    F = laporan.fakta(slug, d1, d2)
    fakta = ai_tugas.fakta_ringkas(F)
    lapor(1, 2)
    hasil = ai_tugas.kesimpulan(fakta, T, topik=slug)
    p = label_ai.berkas_kesimpulan(slug, d1, d2, penuh)
    lama = label_ai.baca_json(p, {}) or {}
    lama["draf"] = {**hasil, "dibuat": time.strftime("%Y-%m-%d %H:%M"), "model": ai_klien.setelan()["model_nalar"]}
    lama.setdefault("dari", d1)
    lama.setdefault("sampai", d2)
    label_ai.tulis_json(p, lama)
    lapor(2, 2)
    lapor_biaya()
    if hasil["angka_tak_dikenal"]:
        print(f"[kesimpulan] periksa angka yang tidak ditemukan di data: {hasil['angka_tak_dikenal']}")
    print(f"[kesimpulan] draf {len(hasil['kesimpulan'])} poin tersimpan · biaya ${ai_klien.pengeluaran()['usd']:.4f}")


# --------------------------------------------------------------- draf topik
def tugas_topik(a):
    """Riset judul berita/YouTube → draf → uji aturan terhadap penilaian AI → perbaiki (lihat ai_topik.susun)."""
    import ai_topik
    ai_klien.atur_batas(a.batas_usd)
    brief = json.load(open(a.brief, encoding="utf-8"))
    lapor(0, 5)
    h = ai_topik.susun(brief, log=lambda t: print(t, flush=True), putaran=2)
    d = h["draf"]
    label_ai.tulis_json(a.keluar, {"brief": brief, "draf": d, "uji": h["uji"], "riset": h["riset"],
                                   "dibuat": time.strftime("%Y-%m-%d %H:%M")})
    lapor_biaya()
    print(f"[topik] draf tersimpan: {len(d.get('kueri_berita', []))} kueri berita, {len(d.get('narasi', {}))} isu, "
          f"{len(d.get('aktor', {}))} aktor · biaya ${ai_klien.pengeluaran()['usd']:.4f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Tugas AI Analisa Sentimen")
    sub = ap.add_subparsers(dest="tugas", required=True)
    bawaan = ai_klien.setelan().get("batas_usd_per_tugas", 2.0)
    for nama in ("label", "validasi", "klaster", "kesimpulan", "topik"):
        p = sub.add_parser(nama)
        p.add_argument("--batas-usd", type=float, default=bawaan)
    sub.choices["validasi"].add_argument("--n", type=int, default=150)
    sub.choices["validasi"].add_argument("--seed", type=int, default=7)
    sub.choices["klaster"].add_argument("--k", default="")
    sub.choices["kesimpulan"].add_argument("--dari")
    sub.choices["kesimpulan"].add_argument("--sampai")
    sub.choices["topik"].add_argument("--brief", required=True)
    sub.choices["topik"].add_argument("--keluar", required=True)
    a = ap.parse_args()
    if a.tugas != "validasi" and not ai_klien.tersedia():
        sys.exit("API key AI belum diatur (halaman Kelola › AI)")
    try:
        {"label": tugas_label, "validasi": tugas_validasi, "klaster": tugas_klaster,
         "kesimpulan": tugas_kesimpulan, "topik": tugas_topik}[a.tugas](a)
    except ai_klien.AIError as e:
        print(f"[ai] gagal: {e}")
        sys.exit(2)
