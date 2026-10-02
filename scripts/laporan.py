#!/usr/bin/env python3
"""Generator laporan PDF per topik: sampul, daftar isi, header/footer bernomor, tangkapan
grafik dashboard, penjelasan dari data, dan kesimpulan.

    python3 scripts/laporan.py --topik masela                       # seluruh periode topik
    python3 scripts/laporan.py --topik masela --dari 2026-07-01 --sampai 2026-07-31
    python3 scripts/laporan.py --topik virgo --keluar ~/Desktop/virgo.pdf

Dari kode:
    from laporan import buat_laporan
    path = buat_laporan("masela")                                   # menyalakan server dashboard sementara
    path = buat_laporan("masela", url="http://127.0.0.1:8080/", dari="2026-07-01", sampai="2026-07-31")

Alur: (1) hitung fakta dari data yang sama dengan dashboard (webapp/sumber.py), dibatasi ke
periode laporan; (2) untuk periode selain seluruh jendela topik, bangun graf SNA periode itu
(scripts/12_sna.py ke data/<slug>/_rentang/); (3) buka dashboard bertema cetak dengan periode
yang sama di Chrome tanpa jendela dan tangkap panel grafik serta graf SNA; (4) susun HTML dari
templat webapp/templates/laporan/; (5) cetak sampul, daftar isi, dan isi ke PDF lalu gabungkan.

Kesimpulan dan rekomendasi analis (KESIMPULAN/REKOMENDASI di file topik) ditulis untuk seluruh
periode, jadi hanya dipakai pada laporan seluruh periode; laporan periode lain memakai kesimpulan
yang disusun dari data periode itu.
"""
import argparse
import base64
import html
import io
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from collections import Counter
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "webapp"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402
import sumber  # noqa: E402  (data yang sama persis dengan dashboard)
import label_ai  # noqa: E402

TEMPLAT = os.path.join(ROOT, "webapp", "templates", "laporan")
FOLDER_KELUAR = os.path.join(ROOT, "laporan")
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September",
         "Oktober", "November", "Desember"]
BLN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
EMOSI_NAMA = {"senang": "senang", "percaya": "percaya", "takut": "takut", "terkejut": "terkejut",
              "sedih": "sedih", "jijik": "muak", "marah": "marah", "antisipasi": "antisipasi"}


# --------------------------------------------------------------- format angka & tanggal
def ang(n):
    return f"{int(round(n)):,}".replace(",", ".")


def pct(x, d=1):
    s = f"{x:.{d}f}".replace(".", ",")
    return (s[:-2] if s.endswith(",0") else s) + "%"


def tgl(t, pendek=False):
    try:
        y, m, d = map(int, str(t)[:10].split("-"))
    except ValueError:
        return str(t)
    return f"{d} {(BLN if pendek else BULAN)[m - 1]}" + ("" if pendek else f" {y}")


def tgl_bulan(t):
    """'2026-07-13' -> '13 Juli' (tanpa tahun, untuk kalimat)."""
    try:
        y, m, d = map(int, str(t)[:10].split("-"))
    except ValueError:
        return str(t)
    return f"{d} {BULAN[m - 1]}"


def _waktu_indo(ts):
    if not ts:
        return "-"
    d = datetime.fromtimestamp(ts)
    return f"{d.day} {BULAN[d.month - 1]} {d.year} pukul {d:%H.%M}"


def koma(teks):
    """Desimal gaya Indonesia pada teks yang dibuat di luar laporan (wawasan SNA)."""
    return re.sub(r"(?<=\d)\.(?=\d)", ",", str(teks))


def rentang(a, z):
    """'2026-07-01','2026-07-31' -> '1–31 Juli 2026'; beda bulan -> '1 Januari – 1 Oktober 2026'."""
    try:
        (ya, ma, da), (yz, mz, dz) = (map(int, str(a)[:10].split("-")), map(int, str(z)[:10].split("-")))
    except ValueError:
        return f"{a} – {z}"
    if (ya, ma, da) == (yz, mz, dz):
        return tgl(a)
    if ya == yz and ma == mz:
        return f"{da}–{dz} {BULAN[mz - 1]} {yz}"
    if ya == yz:
        return f"{da} {BULAN[ma - 1]} – {dz} {BULAN[mz - 1]} {yz}"
    return f"{tgl(a)} – {tgl(z)}"


def daftar(xs, kata="dan"):
    """Daftar gaya PUEBI: 'a dan b', 'a, b, dan c'."""
    xs = [x for x in xs if x]
    if len(xs) <= 1:
        return "".join(xs)
    if len(xs) == 2:
        return f"{xs[0]} {kata} {xs[1]}"
    return ", ".join(xs[:-1]) + f", {kata} " + xs[-1]


def np_(p):
    """Nama platform untuk tabel: 'X (Twitter)' -> 'X'."""
    return "X" if p == "X (Twitter)" else p


def plat_kal(p):
    """Nama platform di tengah kalimat."""
    return {"X (Twitter)": "X", "Berita": "berita"}.get(p, p)


def kutip(isu):
    return f"“{isu}”"


def kira(p):
    """Porsi dalam kata, mis. 74 -> 'sekitar tiga perempat'; None bila terlalu kecil."""
    for batas, kata in ((90, "hampir seluruh"), (80, "sebagian besar"), (70, "sekitar tiga perempat"),
                        (60, "sekitar dua pertiga"), (52, "lebih dari separuh"), (45, "sekitar separuh"),
                        (40, "hampir separuh"), (30, "sekitar sepertiga"), (22, "sekitar seperempat")):
        if p >= batas:
            return kata
    return None


def besar(n):
    """Angka besar untuk kalimat: 5462017 -> '5,5 juta'."""
    if n >= 1e6:
        s = f"{n / 1e6:.1f}".replace(".", ",")
        return (s[:-2] if s.endswith(",0") else s) + " juta"
    return ang(n)


def kali(r):
    return (f"{r:.1f}".replace(".", ",").replace(",0", "") if r < 1.95 else str(round(r))) + " kali"


def lama_kata(jam):
    if jam is None:
        return ""
    if jam < 1:
        return f"{max(1, round(jam * 60))} menit"
    if jam < 48:
        return f"{jam:.1f}".replace(".", ",").replace(",0", "") + " jam"
    return f"{round(jam / 24)} hari"


def potong(t, n):
    t = str(t or "")
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def kapital(s):
    return s[:1].upper() + s[1:] if s else s


def hitung_multi(kolom):
    c = Counter()
    for s in kolom.fillna(""):
        for x in str(s).split("; "):
            x = x.strip()
            if x and x != "Lainnya":
                c[x] += 1
    return c


# --------------------------------------------------------------- periode laporan
def periode(slug, dari=None, sampai=None):
    """(awal, akhir, penuh): periode laporan dipotong ke jendela topik; penuh = seluruh jendela."""
    T = sumber.topik.muat(slug)
    a, z = T.JENDELA
    d1, d2 = max(dari or a, a), min(sampai or z, z)
    if d1 > d2:
        raise ValueError(f"periode {dari}–{sampai} di luar jendela topik {a}–{z}")
    return d1, d2, (d1, d2) == (a, z)


def folder_sna(slug, d1, d2, penuh):
    return sumber.topik.folder(slug) if penuh else os.path.join(sumber.topik.folder(slug), "_rentang", f"{d1}_{d2}")


def siapkan_sna(slug, d1, d2, log=print):
    """Graf SNA untuk periode laporan. Periode penuh memakai graf dashboard; periode lain dibangun
    sekali dengan scripts/12_sna.py lalu dipakai ulang selama data dan aturan belum berubah."""
    folder = folder_sna(slug, d1, d2, False)
    f = os.path.join(folder, "sna.json")
    T = sumber.topik.muat(slug)
    acuan = max(sumber.diperbarui(slug), os.path.getmtime(T.__file__),
                os.path.getmtime(os.path.join(ROOT, "scripts", "12_sna.py")),
                os.path.getmtime(os.path.join(ROOT, "scripts", "label_teks.py")))
    if os.path.exists(f) and os.path.getmtime(f) > acuan:
        return folder
    log(f"[laporan] membangun graf SNA {rentang(d1, d2)}")
    env = {**os.environ, "TOPIK": slug, "SNA_DARI": d1, "SNA_SAMPAI": d2, "SNA_KELUAR": folder}
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "12_sna.py")], env=env,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"12_sna.py gagal untuk {d1}–{d2}:\n{r.stderr[-1500:]}")
    return folder


# --------------------------------------------------------------- fakta dari data
def fakta(slug, dari=None, sampai=None):
    """Semua angka dan teks penjelasan untuk laporan, dihitung dari data dashboard pada periode laporan."""
    d1, d2, penuh = periode(slug, dari, sampai)
    K = sumber.konteks(slug)
    T = K.T
    df = sumber.semua(slug)
    df = df[(df.tanggal >= d1) & (df.tanggal <= d2)].copy()
    if not len(df):
        raise RuntimeError(f"topik '{slug}' tidak punya data pada {rentang(d1, d2)}")
    pekanan = K.pekanan if penuh else (date.fromisoformat(d2) - date.fromisoformat(d1)).days > 60
    waktu = lambda x: sumber.kolom_waktu(K, x, pekanan)
    sos = df[(df.platform != "Berita") & (df.sentimen.isin(["negatif", "netral", "positif"]))]
    total = len(df)
    sekarang = datetime.now()
    F = {"slug": slug, "T": T, "total": total, "pekanan": pekanan, "per": "pekan" if pekanan else "hari",
         "dari": d1, "sampai": d2, "penuh": penuh, "periode": rentang(d1, d2),
         "judul": getattr(T, "JUDUL_LAPORAN", T.JUDUL),
         # kalimat "Halaman ini ..." milik dashboard, bukan laporan
         "lede": re.sub(r"\s*Halaman ini [^.]*\.", "", T.LEDE).strip(),
         "diperbarui": _waktu_indo(sumber.diperbarui(slug)),
         "dibuat": f"{sekarang.day} {BULAN[sekarang.month - 1]} {sekarang.year}",
         "label_ai": label_ai.aktif(slug),
         "penulis": int(df.penulis.nunique()), "engagement": int(df.engagement.sum()),
         "jangkauan": int(df.jangkauan.sum())}

    # --- platform
    plat = []
    for p in sumber.PLATFORM:
        n = int((df.platform == p).sum())
        if n:
            plat.append({"nama": p, "n": n, "pct": 100 * n / total})
    F["platform"] = plat
    F["platform_kosong"] = [p for p in sumber.PLATFORM if not (df.platform == p).sum()]

    # --- dinamika waktu: puncak dan isi tiap puncak
    per = waktu(df)
    vol = per.value_counts().sort_index()
    puncak = []
    for label, n in vol.sort_values(ascending=False).head(3).items():
        sub = df[per == label]
        nar = hitung_multi(sub.topik).most_common(2)
        ber = sub[sub.platform == "Berita"]
        judul = []
        for n_, _ in nar:                    # satu judul untuk tiap isu teratas periode itu
            cocok = ber[ber.topik.fillna("").str.contains(re.escape(n_))]
            if len(cocok):
                j = html.unescape(str(cocok.sort_values("tanggal").judul.iloc[0]))
                if j not in judul:
                    judul.append(j)
        if not judul and len(ber):
            judul = [html.unescape(str(ber.judul.iloc[0]))]
        puncak.append({"label": label, "n": int(n), "narasi": [k for k, _ in nar],
                       "plat": sub.platform.value_counts().index[0], "judul": judul})
    F["puncak"] = puncak

    # --- sentimen & emosi (media sosial)
    F["n_sosial"] = int(len(sos))
    if len(sos):
        s = sos.sentimen.value_counts(normalize=True) * 100
        F["sentimen"] = {k: float(s.get(k, 0)) for k in ("negatif", "netral", "positif")}
        sp = []
        for p, g in sos.groupby("platform"):
            if len(g) >= 30:
                v = g.sentimen.value_counts(normalize=True) * 100
                sp.append({"nama": p, "n": len(g), "neg": float(v.get("negatif", 0)),
                           "pos": float(v.get("positif", 0)), "net": float(v.get("netral", 0))})
        F["sentimen_platform"] = sorted(sp, key=lambda x: -x["n"])
        emo = sos.emosi[sos.emosi.isin(EMOSI_NAMA)].value_counts()
        F["emosi"] = [{"nama": EMOSI_NAMA[k], "pct": 100 * v / len(sos)} for k, v in emo.head(4).items()]
        F["emosi_netral"] = 100 * (1 - emo.sum() / len(sos))
    else:
        F["sentimen"], F["sentimen_platform"], F["emosi"], F["emosi_netral"] = {}, [], [], 100

    # --- isu, lensa fokus, aktor
    nar = hitung_multi(df.topik)
    F["narasi"] = [{"nama": k, "n": v, "pct": 100 * v / total} for k, v in nar.most_common(10)]
    fok = getattr(T, "FOKUS", None)
    if fok:
        pola = "|".join(re.escape(n) for n in fok["narasi"])
        m = df.topik.fillna("").str.contains(pola, regex=True)
        fp = []
        for p in sumber.PLATFORM:
            g = m[df.platform == p]
            if len(g):
                fp.append({"nama": p, "n": int(g.sum()), "dari": len(g), "pct": 100 * g.mean()})
        F["fokus"] = {"nama": fok["nama"], "ket": fok["ket"], "narasi": fok["narasi"],
                      "n": int(m.sum()), "pct": 100 * m.mean(), "platform": fp}
    else:
        F["fokus"] = None
    akt = hitung_multi(df.aktor)
    F["aktor"] = [{"nama": k, "n": v} for k, v in akt.most_common(10)]

    # --- sumber & penulis
    ber = df[df.platform == "Berita"]
    F["media"] = [{"nama": k, "n": int(v)} for k, v in ber.penulis.value_counts().head(8).items()] if len(ber) else []
    sos_all = df[df.platform != "Berita"]
    eng = (sos_all.groupby(["penulis", "platform"]).engagement.sum().sort_values(ascending=False).head(8))
    F["akun"] = [{"nama": k[0], "platform": k[1], "eng": int(v)} for k, v in eng.items() if v > 0]
    top = sos_all.engagement.sort_values(ascending=False)
    F["konsentrasi"] = (100 * top.head(max(1, len(top) // 100)).sum() / top.sum()) if top.sum() else 0

    # --- graf SNA periode ini
    fsna = folder_sna(slug, d1, d2, penuh)
    F["sna"] = baca_sna(fsna)
    fa = os.path.join(fsna, "sna_akun.json")
    akun_sna = json.load(open(fa, encoding="utf-8")) if os.path.exists(fa) else {}
    fs = os.path.join(fsna, "sna.json")
    node_ids = {n["id"] for n in (json.load(open(fs, encoding="utf-8")).get("sosial") or {}).get("simpul", [])} \
        if os.path.exists(fs) else set()
    F["neg"] = profil_sentimen(df, "negatif", akun_sna, node_ids, waktu)
    F["pos"] = profil_sentimen(df, "positif", akun_sna, node_ids, waktu)
    F["koordinasi"] = indikator_koordinasi(df, slug, T)

    F["teks"] = narasi_otomatis(F)
    # Sumber kesimpulan, berurutan: versi yang disetujui di halaman Kelola untuk periode ini, catatan analis
    # di file topik (ditulis untuk seluruh periode), lalu ringkasan dari data. Draf AI dipasang buat_laporan.
    setuju = (label_ai.baca_json(label_ai.berkas_kesimpulan(slug, d1, d2, penuh), {}) or {}).get("disetujui")
    if setuju:
        F["kesimpulan"], F["rekomendasi"] = setuju["kesimpulan"], setuju.get("rekomendasi", [])
        F["kesimpulan_tanggal"], F["analis"], F["sumber_kesimpulan"] = _tgl_teks(setuju.get("tanggal")), True, "disetujui"
    elif penuh and getattr(T, "KESIMPULAN", None):
        F["kesimpulan"], F["rekomendasi"] = T.KESIMPULAN, getattr(T, "REKOMENDASI", [])
        F["kesimpulan_tanggal"], F["analis"], F["sumber_kesimpulan"] = getattr(T, "KESIMPULAN_TANGGAL", ""), True, "topik"
    else:
        F["kesimpulan"], F["rekomendasi"], F["kesimpulan_tanggal"], F["analis"] = \
            kesimpulan_otomatis(F), [], "", False
        F["sumber_kesimpulan"] = "otomatis"
    return F


def _tgl_teks(iso):
    return tgl(iso) if iso else ""


def pasang_kesimpulan_ai(F, log=print):
    """Ganti kesimpulan otomatis dengan draf AI (dibuat sekali per periode lalu dipakai ulang selama datanya
    belum berubah). Hanya bila belum ada versi disetujui atau catatan analis."""
    if F.get("sumber_kesimpulan") != "otomatis":
        return False
    import ai_klien
    import ai_tugas
    if not ai_klien.tersedia():
        return False
    slug, d1, d2 = F["slug"], F["dari"], F["sampai"]
    p = label_ai.berkas_kesimpulan(slug, d1, d2, F["penuh"])
    isi = label_ai.baca_json(p, {}) or {"dari": d1, "sampai": d2}
    draf = isi.get("draf")
    if not draf or os.path.getmtime(p) < sumber.diperbarui(slug):
        log("[laporan] menulis kesimpulan dengan AI")
        try:
            draf = ai_tugas.kesimpulan(ai_tugas.fakta_ringkas(F), F["T"], topik=slug)
        except Exception as e:
            log(f"[laporan] kesimpulan AI gagal, memakai ringkasan dari data: {e}")
            return False
        isi["draf"] = {**draf, "dibuat": time.strftime("%Y-%m-%d %H:%M"), "model": ai_klien.setelan()["model_nalar"]}
        label_ai.tulis_json(p, isi)
    F["kesimpulan"], F["rekomendasi"], F["sumber_kesimpulan"] = draf["kesimpulan"], draf.get("rekomendasi", []), "ai"
    return True


KODE_PLAT = {"X (Twitter)": "x", "YouTube": "yt", "Instagram": "ig", "Threads": "th"}
NAMA_KODE = {"x": "X", "yt": "YouTube", "ig": "Instagram", "th": "Threads"}


def _id_sna(platform, penulis, ada):
    """ID node SNA untuk akun (komentator YouTube berlabel '@nama' di SNA, tanpa '@' di dashboard)."""
    k = KODE_PLAT.get(platform)
    if not k:
        return None
    for cand in (f"{k}:{penulis}", f"{k}:@{penulis}"):
        if cand in ada:
            return cand
    return None


def _nama_id(nid):
    p, _, nama = str(nid).partition(":")
    return nama, NAMA_KODE.get(p, p)


def _bersih(t, n=260):
    t = re.sub(r"\s+", " ", html.unescape(str(t or ""))).strip()
    return t if len(t) <= n else t[:n - 1].rstrip() + "…"


# akun otomatis (asisten AI, pengumpul utas) yang membalas atas permintaan pengguna lain
AKUN_BOT = {"grok", "askperplexity", "threadreaderapp", "readwiseio", "pikaso_me"}


def profil_sentimen(df, sen, akun_sna, node_ids, waktu):
    """Konten dan akun penyebar satu sentimen di media sosial, plus relasi SNA tiap akun."""
    sos = df[(df.platform != "Berita") & df.sentimen.isin(["negatif", "netral", "positif"])
             & ~df.penulis.astype(str).str.lower().isin(AKUN_BOT)]
    x = sos[sos.sentimen == sen]
    if not len(x):
        return None
    out = {"n": len(x), "pct": 100 * len(x) / len(sos)}
    out["platform"] = [{"nama": p, "n": int(n), "pct": 100 * n / len(x)} for p, n in x.platform.value_counts().items()]
    out["narasi"] = [{"nama": k, "n": v, "pct": 100 * v / len(x)} for k, v in hitung_multi(x.topik).most_common(6)]
    out["puncak"] = [{"label": k, "n": int(v)} for k, v in waktu(x).value_counts().head(3).items()]
    top = x.sort_values("engagement", ascending=False).head(8)
    out["konten"] = [{"penulis": r.penulis, "platform": r.platform, "tanggal": r.tanggal, "teks": _bersih(r.teks),
                      "eng": int(r.engagement), "narasi": r.narasi, "url": r.url, "tipe": r.tipe_penulis}
                     for r in top.itertuples()]
    # akun penyebar: volume konten bernada ini, lalu engagement-nya
    total = sos.groupby(["penulis", "platform"]).size()
    agg = (x.groupby(["penulis", "platform"])
             .agg(n=("id", "size"), eng=("engagement", "sum"), tipe=("tipe_penulis", "first"))
             .sort_values(["n", "eng"], ascending=False))
    akun = []
    for (penulis, plat), r in agg.head(12).iterrows():
        mine = x[(x.penulis == penulis) & (x.platform == plat)]
        nid = _id_sna(plat, penulis, akun_sna)
        rel = akun_sna.get(nid, {}) if nid else {}
        akun.append({
            "nama": penulis, "platform": plat, "tipe": r.tipe, "n": int(r.n), "eng": int(r.eng),
            "porsi": 100 * r.n / max(int(total.get((penulis, plat), r.n)), 1),
            "narasi": (hitung_multi(mine.topik).most_common(1) or [("", 0)])[0][0],
            "contoh": _bersih(mine.sort_values("engagement", ascending=False).teks.iloc[0], 180),
            "id": nid, "di_peta": bool(nid and nid in node_ids),
            "klaster": rel.get("k"),
            "sasaran": [{"nama": _nama_id(i)[0], "n": c} for i, c in rel.get("sasaran", {}).get(sen, [])[:3]],
            "dari": [{"nama": _nama_id(i)[0], "n": c} for i, c in rel.get("dari", {}).get(sen, [])[:3]],
        })
    out["akun"] = akun
    out["ego"] = [a for a in akun if a["di_peta"]][:3]
    # akun yang paling sering menerima interaksi bernada ini (kanal/akun tempat konten itu berkumpul)
    sasaran = sorted(((nid, d["in"].get(sen, 0)) for nid, d in akun_sna.items()), key=lambda t: -t[1])[:8]
    out["sasaran"] = [{"nama": _nama_id(i)[0], "platform": _nama_id(i)[1], "n": n,
                       "porsi": 100 * n / max(sum(akun_sna[i]["in"].values()), 1)} for i, n in sasaran if n]
    return out


_URL = re.compile(r"https?://\S+")
_MENTION = re.compile(r"@[\w.]+")


def _x_meta(slug):
    """username X -> (tanggal akun dibuat, followers), dari data mentah."""
    meta = {}
    for nama in ("tweets.jsonl", "replies.jsonl"):
        f = os.path.join(sumber.topik.folder(slug), "x", nama)
        if not os.path.exists(f):
            continue
        for l in open(f, encoding="utf-8"):
            try:
                r = json.loads(l)
            except Exception:
                continue
            u = r.get("username")
            if u and u not in meta and r.get("user_created"):
                try:
                    dibuat = datetime.strptime(r["user_created"], "%a %b %d %H:%M:%S %z %Y").date().isoformat()
                except ValueError:
                    continue
                meta[u] = (dibuat, int(r.get("followers") or 0))
    return meta


def indikator_koordinasi(df, slug, T):
    """Pola perilaku yang lazim pada amplifikasi terorganisasi. Indikator, bukan vonis."""
    # deskripsi video YouTube berisi templat kanal media ("Download aplikasi..."), bukan amplifikasi
    sos = df[(df.platform != "Berita") & ~df.id.astype(str).str.startswith("YTV")].copy()
    if not len(sos):
        return None
    out = {}
    # 1. teks kembar: isi sama (setelah tautan, mention, tanda baca dibuang) dari >= 3 akun berbeda
    norm = (sos.teks.fillna("").map(html.unescape).str.lower()
            .map(lambda t: _MENTION.sub(" ", _URL.sub(" ", t)))
            .str.replace(r"[^a-z0-9À-ɏ ]+", " ", regex=True)
            .str.replace(r"\s+", " ", regex=True).str.strip())
    sos["norm"] = norm
    kembar = []
    umum = re.compile(r"^(innalillahi|inna lillahi|innalilahi|innalillah|inalillahi|turut berduka|berduka|aamiin|amiin|"
                      r"amin|semoga|alhamdulillah|ya allah|al fatihah|alfatihah|rip|mantap|terima kasih|makasih)")
    kandidat = sos[(sos.norm.str.len() >= 35) & (sos.norm.str.count(" ") >= 5) & ~sos.norm.str.match(umum)]
    for t, grp in kandidat.groupby("norm"):
        n_akun = grp.penulis.nunique()
        if n_akun < 3:
            continue
        jam = None
        w = pd.to_datetime(grp[grp.platform != "YouTube"].waktu, errors="coerce").dropna()
        if len(w) >= 2:
            jam = (w.max() - w.min()).total_seconds() / 3600
        kembar.append({"teks": _bersih(grp.teks.iloc[0], 200), "akun": n_akun, "unggahan": len(grp),
                       "sentimen": grp.sentimen.value_counts().index[0],
                       "platform": ", ".join(np_(p) for p in grp.platform.unique()),
                       "dari": grp.tanggal.min(), "sampai": grp.tanggal.max(), "jam": jam,
                       "contoh_akun": list(grp.penulis.value_counts().index[:8])})
    out["kembar"] = sorted(kembar, key=lambda k: (-k["akun"], -k["unggahan"]))[:10]
    out["kembar_total"] = len(kembar)
    out["kembar_unggahan"] = sum(k["unggahan"] for k in kembar)
    # 2. mention massal: satu unggahan menandai >= 6 akun di badan teks. Deretan @ di awal balasan
    #    ditambahkan otomatis oleh X untuk semua peserta utas, jadi tidak dihitung.
    badan = sos.teks.fillna("").str.replace(r"^(\s*@[\w.]+)+", "", regex=True)
    massal = sos[badan.str.count(r"@[\w.]+") >= 6]
    out["massal_n"] = len(massal)
    out["massal_pengirim"] = int(massal.penulis.nunique())
    out["massal_akun"] = [{"nama": k[0], "platform": k[1], "n": int(v)}
                          for k, v in massal.groupby(["penulis", "platform"]).size().sort_values(ascending=False).head(8).items()]
    ditag = Counter(m.lower() for t in badan[massal.index] for m in _MENTION.findall(t))
    out["massal_ditag"] = [{"nama": k, "n": v} for k, v in ditag.most_common(8)]
    # balasan dalam utas panjang: banyak akun berbeda membawa deretan mention otomatis yang sama
    awal = sos.teks.fillna("").str.extract(r"^((?:\s*@[\w.]+){6,})")[0].dropna()
    out["utas_n"] = len(awal)
    out["utas_ditag"] = [{"nama": k, "n": v} for k, v in
                         Counter(m.lower() for t in awal for m in _MENTION.findall(t)).most_common(6)]
    # 3. akun satu nada: volume tinggi dan hampir semua unggahannya bernada sama
    lab = sos[sos.sentimen.isin(["negatif", "positif"])]
    vol = sos.groupby(["penulis", "platform"]).size()
    batas = max(5, int(vol.quantile(0.99)))
    satu = []
    for (p_, pl), n in vol[vol >= batas].items():
        mine = lab[(lab.penulis == p_) & (lab.platform == pl)]
        if not len(mine):
            continue
        dom = mine.sentimen.value_counts()
        porsi = 100 * dom.iloc[0] / n
        if porsi >= 60:
            satu.append({"nama": p_, "platform": pl, "n": int(n), "nada": dom.index[0], "porsi": porsi})
    out["satu_nada"] = sorted(satu, key=lambda a: (-a["porsi"], -a["n"]))[:12]
    out["satu_nada_total"] = len(satu)
    out["satu_nada_batas"] = batas
    # 4. akun X baru (dibuat <= 180 hari sebelum awal peristiwa atau sesudahnya) yang aktif membahas topik ini
    meta = _x_meta(slug)
    awal = (datetime.fromisoformat(T.JENDELA[0]) - pd.Timedelta(days=180)).date().isoformat()
    xs = sos[sos.platform == "X (Twitter)"]
    baru = []
    for u, grp in xs.groupby("penulis"):
        m = meta.get(u)
        if m and m[0] >= awal and len(grp) >= 2:
            baru.append({"nama": u, "dibuat": m[0], "followers": m[1], "n": len(grp),
                         "nada": grp.sentimen.value_counts().index[0]})
    out["akun_baru"] = sorted(baru, key=lambda a: -a["n"])[:12]
    out["akun_baru_total"] = len(baru)
    out["akun_baru_sejak"] = awal
    return out


def baca_sna(folder):
    f = os.path.join(folder, "sna.json")
    if not os.path.exists(f):
        return None
    d = json.load(open(f, encoding="utf-8"))
    so, be = d.get("sosial") or {}, d.get("berita") or {}
    out = {"statistik": so.get("statistik", {}),
           "wawasan": [{**w, "judul": koma(w.get("judul", "")), "isi": koma(w.get("isi", ""))}
                       for w in so.get("wawasan", [])],
           "dibuat": d.get("dibuat", ""), "klaster": []}
    for c in (so.get("klaster") or [])[:10]:
        out["klaster"].append({
            "no": c["k"] + 1, "nama": c.get("nama") or c.get("nama_auto"),
            "kurasi": bool(c.get("nama")), "butir": c.get("butir") or [],
            "simpul": c["simpul"], "interaksi": c["interaksi"], "sentimen": c["sentimen"],
            "platform": ", ".join(f"{ {'x': 'X', 'yt': 'YouTube', 'ig': 'Instagram', 'th': 'Threads'}.get(p, p) } {ang(v)}"
                                  for p, v in (c.get("platform") or {}).items()),
            "tokoh": [t.lstrip("@") for t in c.get("tokoh", [])[:3]], "isu": (c.get("narasi") or [])[:2]})
    out["kurasi"] = any(k["kurasi"] for k in out["klaster"])
    if be.get("simpul"):
        akt = sorted([n for n in be["simpul"] if n["p"] == "aktor"], key=lambda n: -n["i"])[:8]
        med = sorted([n for n in be["simpul"] if n["p"] == "media"], key=lambda n: -n["o"])[:8]
        out["berita"] = {"aktor": [(n["l"], n["i"]) for n in akt], "media": [(n["l"], n["o"]) for n in med],
                         "simpul": len(be["simpul"]), "sisi": len(be.get("sisi", []))}
    return out


# --------------------------------------------------------------- teks penjelasan
def _label_waktu(label, pekanan, pendek=False):
    if pekanan:
        return f"pekan {tgl_bulan(label)}" if pendek else f"pekan yang dimulai {tgl(label)}"
    return tgl_bulan(label) if pendek else tgl(label)


def narasi_otomatis(F):
    """Paragraf pembuka tiap bagian, disusun dari angka periode laporan. Gaya: kalimat pendek,
    angka seperlunya, porsi besar dalam kata ('sekitar dua pertiga'), tanpa tafsir berlebihan."""
    t = {}
    T = F["T"]
    plat = sorted(F["platform"], key=lambda p: -p["n"])
    p1 = plat[0]
    kal = [f"Selama {F['periode']} tercatat {ang(F['total'])} konten tentang {T.NAMA} dari "
           f"{ang(F['penulis'])} akun dan media."]
    lain = daftar([f"{plat_kal(p['nama'])} ({ang(p['n'])})" for p in plat[1:3]])
    k = kira(p1["pct"])
    awal = ("Hampir seluruh konten" if k == "hampir seluruh" else f"{kapital(k)} di antaranya") if k \
        else "Konten terbanyak"
    kal.append(f"{awal} berasal dari {plat_kal(p1['nama'])} ({ang(p1['n'])} konten)"
               + (f", disusul {lain}." if lain else "."))
    kal.append(f"Seluruh konten ini mengumpulkan {besar(F['engagement'])} engagement"
               + (f" dan {besar(F['jangkauan'])} tayangan." if F["jangkauan"] else "."))
    t["ringkasan"] = " ".join(kal)

    if F["puncak"]:
        p0, pk = F["puncak"][0], F["pekanan"]
        kal = [f"Percakapan paling ramai terjadi pada {_label_waktu(p0['label'], pk)} dengan {ang(p0['n'])} "
               f"konten, terutama dari {plat_kal(p0['plat'])}."]
        if p0["narasi"]:
            kal.append(f"Isu yang paling banyak dibahas saat itu adalah {daftar([kutip(n) for n in p0['narasi']])}.")
        if len(F["puncak"]) > 1:
            kal.append("Puncak berikutnya terjadi pada " + daftar(
                [f"{_label_waktu(p['label'], pk, True)} ({ang(p['n'])} konten)" for p in F["puncak"][1:]]) + ".")
        t["waktu"] = " ".join(kal)

    s = F["sentimen"]
    if s:
        kal = [f"Dari {ang(F['n_sosial'])} konten media sosial, {pct(s['negatif'], 0)} bernada negatif dan "
               f"{pct(s['positif'], 0)} positif; sisanya netral."]
        if s["negatif"] and s["positif"]:
            r = s["positif"] / s["negatif"]
            if r >= 1.15:
                kal.append(f"Konten positif sekitar {kali(r)} lebih banyak daripada konten negatif.")
            elif r <= 1 / 1.15:
                kal.append(f"Konten negatif sekitar {kali(1 / r)} lebih banyak daripada konten positif.")
            else:
                kal.append("Jumlah konten positif dan negatif hampir seimbang.")
        sp = F["sentimen_platform"]
        if len(sp) > 1:
            ng, ps = max(sp, key=lambda x: x["neg"]), max(sp, key=lambda x: x["pos"])
            if ng["nama"] != ps["nama"]:
                kal.append(f"{plat_kal(ng['nama'])} menjadi platform paling kritis ({pct(ng['neg'], 0)} negatif), "
                           f"sedangkan {plat_kal(ps['nama'])} paling positif ({pct(ps['pos'], 0)} positif).")
            else:
                kal.append(f"{plat_kal(ng['nama'])} memiliki porsi negatif ({pct(ng['neg'], 0)}) sekaligus "
                           f"positif ({pct(ng['pos'], 0)}) tertinggi.")
        t["sentimen"] = " ".join(kal)
        e = F["emosi"]
        if e:
            kal = f"Emosi yang paling sering muncul adalah {e[0]['nama']} ({pct(e[0]['pct'], 0)})"
            if len(e) > 1:
                kal += f" dan {e[1]['nama']} ({pct(e[1]['pct'], 0)})"
            if len(e) > 2:
                kal += f", disusul {e[2]['nama']} ({pct(e[2]['pct'], 0)})"
            k = kira(F["emosi_netral"])
            awal = "Hampir seluruh konten" if k == "hampir seluruh" else (f"{kapital(k)} konten" if k else "Sebagian konten")
            t["emosi"] = kal + f". {awal} ({pct(F['emosi_netral'], 0)}) tidak menunjukkan emosi yang jelas."

    x = F["narasi"]
    if x:
        kal = f"Isu yang paling banyak dibicarakan adalah {kutip(x[0]['nama'])} ({pct(x[0]['pct'], 0)} konten)"
        if len(x) > 1:
            kal += ", disusul " + daftar([f"{kutip(n['nama'])} ({pct(n['pct'], 0)})" for n in x[1:3]])
        t["narasi"] = kal + ". Satu konten bisa membahas lebih dari satu isu."
    fk = F["fokus"]
    if fk and fk["n"]:
        kal = f"{kapital(fk['nama'])} mencakup {ang(fk['n'])} konten ({pct(fk['pct'], 0)} dari seluruh konten)."
        ber = next((p for p in fk["platform"] if p["nama"] == "Berita"), None)
        so = [p for p in fk["platform"] if p["nama"] != "Berita" and p["dari"] >= 30]
        if ber and so and ber["pct"] > 2 * max(p["pct"] for p in so):
            lo, hi = min(p["pct"] for p in so), max(p["pct"] for p in so)
            rng = f"{pct(lo, 0)[:-1]}–{pct(hi, 0)}" if round(lo) != round(hi) else pct(hi, 0)
            kal += f" Isu-isu ini jauh lebih sering muncul di berita ({pct(ber['pct'], 0)}) daripada di media sosial ({rng})."
        else:
            tp = max(fk["platform"], key=lambda p: p["pct"])
            kal += f" Porsi tertinggi ada di {plat_kal(tp['nama'])} ({pct(tp['pct'], 0)})."
        t["fokus"] = kal
    if F["aktor"]:
        t["aktor"] = ("Pihak yang paling sering disebut adalah "
                      + daftar([f"{re.sub(r'\s*\(.*?\)', '', a['nama'])} ({ang(a['n'])} konten)" for a in F["aktor"][:3]]) + ".")

    kal = []
    if F["media"]:
        kal.append("Media yang paling banyak memberitakan topik ini adalah "
                   + daftar([f"{m['nama']} ({ang(m['n'])} artikel)" for m in F["media"][:3]]) + ".")
    if F["akun"]:
        kal.append("Di media sosial, engagement terbesar dikumpulkan oleh "
                   + daftar([f"{a['nama']} ({np_(a['platform'])})" for a in F["akun"][:3]]) + ".")
    if F["konsentrasi"]:
        c = F["konsentrasi"]
        tingkat = "sangat terpusat" if c >= 50 else ("cukup terpusat" if c >= 25 else "relatif merata")
        kal.append(f"Perhatian publik {tingkat}: 1% konten teratas mengumpulkan {pct(c, 0)} dari total "
                   f"engagement media sosial.")
    if kal:
        t["sumber"] = " ".join(kal)

    sna = F["sna"]
    if sna and sna["statistik"]:
        st = sna["statistik"]
        t["sna"] = (f"Graf SNA berisi {ang(st.get('akun_total', 0))} akun (node) yang terhubung oleh "
                    f"{ang(st.get('interaksi_total', 0))} interaksi (edge), yaitu komentar, balasan, dan mention. "
                    f"Algoritma Louvain mengelompokkan akun-akun ini ke dalam {ang(st.get('komunitas', 0))} klaster.")
    if sna and sna.get("berita"):
        b = sna["berita"]
        t["peta_berita"] = (f"Graf pemberitaan menghubungkan {ang(b['simpul'])} media dan aktor. Aktor yang paling "
                            f"sering diberitakan adalah {daftar([a for a, _ in b['aktor'][:4]])}.")

    for k, nama in (("neg", "negatif"), ("pos", "positif")):
        P = F.get(k)
        if not P:
            continue
        kal = [f"Sebanyak {ang(P['n'])} konten media sosial ({pct(P['pct'], 0)}) bernada {nama}."]
        p1 = P["platform"][0]
        kk = kira(p1["pct"])
        if kk:
            kal.append(("Hampir seluruhnya" if kk == "hampir seluruh" else f"{kapital(kk)} di antaranya")
                       + f" berasal dari {plat_kal(p1['nama'])} ({ang(p1['n'])}).")
        nar = P["narasi"]
        if nar:
            kal.append(f"Isu yang paling sering muncul di konten {nama} adalah {kutip(nar[0]['nama'])} "
                       f"({ang(nar[0]['n'])} konten)" + (f", disusul {kutip(nar[1]['nama'])} ({ang(nar[1]['n'])})"
                                                         if len(nar) > 1 else "") + ".")
        if P["akun"]:
            kal.append(f"Akun yang paling banyak mengunggah konten {nama} adalah "
                       + daftar([f"{a['nama']} ({a['n']} konten)" for a in P["akun"][:3]]) + ".")
        if P["puncak"]:
            pk = P["puncak"][0]
            kal.append(f"Volume tertinggi terjadi pada {_label_waktu(pk['label'], F['pekanan'])} "
                       f"({ang(pk['n'])} konten).")
        t[k] = " ".join(kal)

    ko = F.get("koordinasi")
    if ko:
        bag = []
        if ko["kembar_total"] == 1:
            bag.append(f"satu kelompok teks identik yang diunggah tiga akun atau lebih ({ang(ko['kembar_unggahan'])} unggahan)")
        elif ko["kembar_total"]:
            bag.append(f"{ang(ko['kembar_total'])} kelompok teks identik yang masing-masing diunggah tiga akun "
                       f"atau lebih ({ang(ko['kembar_unggahan'])} unggahan)")
        if ko["massal_n"]:
            bag.append(f"{ang(ko['massal_n'])} unggahan yang menandai enam akun atau lebih sekaligus")
        if ko["satu_nada_total"]:
            bag.append(f"{ang(ko['satu_nada_total'])} akun bervolume tinggi yang hampir selalu bernada sama")
        if ko["akun_baru_total"]:
            bag.append(f"{ang(ko['akun_baru_total'])} akun X baru yang langsung aktif membahas topik ini")
        if bag:
            kal = "Pada periode ini terdapat " + daftar(bag) + "."
            if ko["kembar"]:
                k0 = ko["kembar"][0]
                kapan = f"pada {tgl(k0['dari'])}" if k0["dari"] == k0["sampai"] else \
                    (f"antara {k0['dari'][8:].lstrip('0')} dan {tgl(k0['sampai'])}" if k0["dari"][:7] == k0["sampai"][:7]
                     else f"antara {tgl_bulan(k0['dari'])} dan {tgl(k0['sampai'])}")
                kal += (f" {'Kelompok terbesar' if ko['kembar_total'] > 1 else 'Teks itu'} diunggah {k0['akun']} akun"
                        + (f" dalam {lama_kata(k0['jam'])}" if k0["jam"] is not None and k0["jam"] < 48 else "")
                        + f" {kapan}: “{potong(k0['teks'], 120)}”")
                kal += "" if kal.endswith(("…”", ".”")) else "."
            t["koordinasi"] = kal
        else:
            t["koordinasi"] = ("Pada periode ini tidak ditemukan teks identik dari banyak akun, mention massal, akun "
                               "satu nada, maupun akun X baru yang menonjol.")
    return t


def kalimat(teks):
    """Pecah paragraf menjadi kalimat (batas: tanda akhir kalimat lalu huruf kapital atau kutip)."""
    return [k for k in re.split(r"(?<=[.!?”])\s+(?=[A-Z“])", teks or "") if k]


def kesimpulan_otomatis(F):
    """Kesimpulan laporan periode non-penuh: poin-poin dari data periode itu. 'ringkas' adalah versi
    pendek (kalimat utuh) untuk kotak temuan utama di ringkasan eksekutif."""
    t, out = F["teks"], []
    pilih = lambda teks, *i: " ".join(k for j, k in enumerate(kalimat(teks)) if j in i)
    if F["puncak"]:
        out.append({"judul": f"Puncak percakapan pada {_label_waktu(F['puncak'][0]['label'], F['pekanan'])}",
                    "isi": t["waktu"], "ringkas": pilih(t["waktu"], 0, 1)})
    s = F["sentimen"]
    if s:
        if s["positif"] >= 1.15 * s["negatif"]:
            judul = "Konten positif lebih banyak daripada konten negatif"
        elif s["negatif"] >= 1.15 * s["positif"]:
            judul = "Konten negatif lebih banyak daripada konten positif"
        else:
            judul = "Konten positif dan negatif hampir seimbang"
        out.append({"judul": judul, "isi": t["sentimen"], "ringkas": pilih(t["sentimen"], 0, 1)})
    if F["narasi"]:
        out.append({"judul": f"Isu terbesar: {F['narasi'][0]['nama']}",
                    "isi": t["narasi"] + (" " + t["fokus"] if t.get("fokus") else ""),
                    "ringkas": pilih(t["narasi"], 0)})
    if t.get("neg"):
        k = kalimat(t["neg"])
        out.append({"judul": "Penyebar konten negatif", "isi": t["neg"],
                    "ringkas": " ".join([k[0]] + [x for x in k if x.startswith("Akun yang")])})
    if t.get("pos"):
        k = kalimat(t["pos"])
        out.append({"judul": "Penyebar konten positif", "isi": t["pos"],
                    "ringkas": " ".join([k[0]] + [x for x in k if x.startswith("Akun yang")])})
    ko = F.get("koordinasi")
    if t.get("koordinasi"):
        ada = ko and (ko["kembar_total"] or ko["massal_n"] or ko["satu_nada_total"] or ko["akun_baru_total"])
        out.append({"judul": "Pola unggahan seragam dan akun baru" if ada else "Tidak ada pola amplifikasi yang menonjol",
                    "isi": t["koordinasi"], "ringkas": pilih(t["koordinasi"], 0)})
    sna = F["sna"]
    if sna and sna["wawasan"]:
        out.append({"judul": "Akun yang paling banyak menerima interaksi", "isi": sna["wawasan"][0]["isi"]})
    return out


# --------------------------------------------------------------- tangkapan dashboard
PANEL = [
    ("linimasa", ".panel:has(#g-linimasa)"), ("kumulatif", ".panel:has(#g-kumulatif)"),
    ("jam", ".panel:has(#g-jam)"),
    ("sen_ringkas", ".panel:has(#sen-ringkas)"), ("sentimen_waktu", ".panel:has(#g-sentimen-harian)"),
    ("sentimen_tipe", ".panel:has(#g-sentimen-tipe)"), ("emosi", ".panel:has(#g-emosi)"),
    ("fokus", "#panel-fokus"), ("narasi", ".panel:has(#g-narasi)"), ("aktor", ".panel:has(#g-aktor)"),
    ("narasi_waktu", ".panel:has(#g-narasi-harian)"), ("tipe", ".panel:has(#g-tipe)"),
    ("produktif", ".panel:has(#g-penulis-volume)"), ("engagement", ".panel:has(#g-penulis-eng)"),
    ("konsentrasi", ".panel:has(#konsentrasi)"), ("kata", ".panel:has(#awan-kata)"),
    ("tagar", ".panel:has(#awan-tagar)"), ("klaster_sent", ".panel:has(#g-klaster-sent)"),
    ("klaster_emo", ".panel:has(#sna-emo-matriks)"), ("peran", ".panel:has(#sna-peran)"),
]
# bilah atas dan filter tidak ikut tertangkap; judul dan keterangan panel diganti keterangan gambar
# di laporan, jadi disembunyikan agar tidak tertulis dua kali
CSS_TANGKAP = """
header.bilah, .subnav, .saring { display: none !important; }
html { scroll-behavior: auto !important; }
.sna-zoom, .sna-tip { display: none !important; }
.kisi { align-items: start !important; }
.kisi > .panel > h2, .kisi > .panel > p.ket { display: none !important; }
"""


def _gbr(data, jenis="png"):
    """Gambar tangkapan: data URI + ukuran piksel (atribut width/height agar tata letak stabil)."""
    from PIL import Image
    w, h = Image.open(io.BytesIO(data)).size
    return {"src": f"data:image/{jenis};base64," + base64.b64encode(data).decode(), "w": w, "h": h}


# Animasi Chart.js dimatikan setelah skrip dashboard berjalan (aplikasi.js mengatur durasinya)
# tetapi sebelum grafik dibuat dari data API, sehingga grafik langsung jadi tanpa menunggu.
SKRIP_TANPA_ANIMASI = """
window.addEventListener('DOMContentLoaded', () => {
  try { Chart.defaults.animation = false; } catch (e) {}
});
"""
# siap = graf SNA tergambar, tiap kanvas grafik yang tampak sudah punya Chart, dan kerangka
# "Memuat" sudah diganti isi
SIAP = """() => {
  if (typeof S === 'undefined' || !S.g || typeof Chart === 'undefined') return false;
  if (document.querySelector('.memuat.kerangka')) return false;
  const kanvas = [...document.querySelectorAll('.panel canvas[id^="g-"]')].filter(c => c.offsetParent !== null);
  return kanvas.every(c => Chart.getChart(c));
}"""
SATU_BINGKAI = "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"

SNA_SENTIMEN = """(sen) => { S.f = snaFilterAwal(); if (sen) S.f.sent = new Set([sen]);
  S.pilih = null; S.sorotK = null; snaSinkronKontrol(); snaTerapkan(true); }"""
SNA_EGO = """(id) => { const n = S.g.simpul.find(x => x.id === id);
  if (!n || !n.tampak) return false; snaPilih(n.idx, true); return true; }"""


def tangkap(F, url, browser, log=print, ego=None):
    """Tangkap panel dashboard bertema cetak (resolusi 2x) untuk periode laporan, memakai Chrome
    yang sudah terbuka. ego = {"negatif": [id node], "positif": [...]}: akun yang dibuatkan ego-network."""
    gambar = {}
    # dashboard yang dipasang dengan login (DASHBOARD_USER/PASS) juga meminta login ke Chrome penangkap
    login = (os.environ.get("DASHBOARD_USER", ""), os.environ.get("DASHBOARD_PASS", ""))
    ctx = browser.new_context(viewport={"width": 1440, "height": 2600}, device_scale_factor=2, locale="id-ID",
                              **({"http_credentials": {"username": login[0], "password": login[1]}} if all(login) else {}))
    ctx.add_init_script(SKRIP_TANPA_ANIMASI)
    pg = ctx.new_page()
    q = "cetak=1" + ("" if F["penuh"] else f"&dari={F['dari']}&sampai={F['sampai']}")
    pg.goto(f"{url}{F['slug']}/?{q}", wait_until="domcontentloaded", timeout=180000)
    pg.add_style_tag(content=CSS_TANGKAP)
    try:
        pg.wait_for_function(SIAP, timeout=60000, polling=150)
    except Exception:
        log("[laporan] peringatan: sebagian panel belum siap setelah 60 dtk, lanjut menangkap")
    pg.evaluate(SATU_BINGKAI)
    for nama, sel in PANEL:
        el = pg.query_selector(sel)
        if el and el.is_visible():
            gambar[nama] = _gbr(el.screenshot())
    log(f"[laporan] {len(gambar)} panel tertangkap")
    # graf SNA: tiga pewarnaan, graf khusus satu sentimen + ego-network, dan graf pemberitaan
    wadah = pg.query_selector(".sna-wadah")
    if wadah and pg.evaluate("() => !!(S.g && S.g.vis && S.g.vis.length)"):
        wadah.scroll_into_view_if_needed()
        for mode in ("sentimen", "emosi", "klaster"):
            pg.click(f'#sna-tab button[data-mode="{mode}"]')
            pg.evaluate(SATU_BINGKAI)
            # graf berisi ribuan titik berwarna: JPEG jauh lebih kecil dari PNG
            gambar[f"sna_{mode}"] = _gbr(wadah.screenshot(type="jpeg", quality=86), "jpeg")
        pg.click('#sna-tab button[data-mode="sentimen"]')
        for sen in ("negatif", "positif"):
            pg.evaluate(SNA_SENTIMEN, sen)
            pg.evaluate(SATU_BINGKAI)
            gambar[f"sna_{sen}"] = _gbr(wadah.screenshot(type="jpeg", quality=86), "jpeg")
            for i, nid in enumerate((ego or {}).get(sen, [])):
                if pg.evaluate(SNA_EGO, nid):
                    pg.evaluate(SATU_BINGKAI)
                    gambar[f"ego_{sen}_{i}"] = _gbr(wadah.screenshot(type="jpeg", quality=86), "jpeg")
        pg.evaluate(SNA_SENTIMEN, None)
        if pg.evaluate("() => !!(S.gab && S.gab.simpul.some(n => n.grp === 'berita'))"):
            pg.evaluate("() => { S.f.plat = new Set(['berita']); snaSinkronKontrol(); snaTerapkan(true); }")
            pg.evaluate(SATU_BINGKAI)
            gambar["sna_berita"] = _gbr(wadah.screenshot(type="jpeg", quality=86), "jpeg")
        log("[laporan] graf SNA tertangkap")
    ctx.close()
    return gambar


# --------------------------------------------------------------- render HTML & PDF
def bagian_laporan(F):
    """Daftar bagian laporan (id, judul) sesuai isi periode ini. Judul harus sama persis dengan
    <h1> di isi.html: nomor halaman daftar isi dibaca dari bookmark PDF berdasarkan judul ini."""
    b = [("ringkasan", "Ringkasan eksekutif"), ("latar", "Latar belakang dan metodologi"),
         ("waktu", "Tren volume percakapan"), ("sentimen", "Sentimen dan emosi"), ("narasi", "Isu dan aktor")]
    if F["sna"] and F["sna"]["statistik"]:
        b.append(("sna", "Social network analysis (SNA)"))
    b.append(("sumber", "Akun dan media berpengaruh"))
    if F["neg"]:
        b.append(("negatif", "Sentimen negatif: konten dan akun penyebar"))
    if F["pos"]:
        b.append(("positif", "Sentimen positif: konten dan akun penyebar"))
    if F["koordinasi"]:
        b.append(("koordinasi", "Indikator amplifikasi terkoordinasi"))
    b.append(("kesimpulan", "Kesimpulan dan rekomendasi" if F["rekomendasi"] else "Kesimpulan"))
    return b


def _font_tertanam():
    """Plus Jakarta Sans (font variabel) sebagai data URI: Chrome tanpa jendela tidak selalu
    sempat memuat Google Fonts sebelum mencetak, dan laporan harus bisa dibuat luring."""
    f = os.path.join(ROOT, "webapp", "static", "fonts", "plus-jakarta-sans-variabel.woff2")
    if not os.path.exists(f):
        return ""
    b64 = base64.b64encode(open(f, "rb").read()).decode()
    return ("@font-face{font-family:'Plus Jakarta Sans';font-style:normal;font-weight:200 800;"
            f"font-display:block;src:url(data:font/woff2;base64,{b64}) format('woff2');}}\n")


def render(F, gambar, halaman=None):
    """HTML sampul, daftar isi, dan isi laporan; halaman = {bagian: nomor} untuk daftar isi."""
    import jinja2
    from markupsafe import Markup
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLAT), autoescape=True)
    env.filters.update(ang=ang, pct=pct, tgl=tgl, lama=lama_kata)
    css = _font_tertanam() + open(os.path.join(ROOT, "webapp", "static", "laporan.css"), encoding="utf-8").read()
    bagian = [{"id": k, "judul": j, "no": f"{i + 1:02d}", "hal": (halaman or {}).get(k, "")}
              for i, (k, j) in enumerate(bagian_laporan(F))]
    no = {b["id"]: b["no"] for b in bagian}
    # CSS adalah milik proyek: jangan di-escape
    konteks = dict(F=F, g=gambar, css=Markup(css), bagian=bagian, no=no)
    return {n: env.get_template(f"{n}.html").render(**konteks) for n in ("sampul", "daftar", "isi")}


def _header_footer(F):
    gaya = ("font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;font-size:7.5pt;color:#8a877f;"
            "width:100%;padding:0 17mm;display:flex;justify-content:space-between;align-items:center;"
            "-webkit-print-color-adjust:exact;")
    kepala = (f'<div style="{gaya}"><span><b style="color:#45443f">{html.escape(F["T"].NAMA)}</b></span>'
              f'<span>Laporan percakapan publik · {F["periode"]}</span></div>')
    kaki = (f'<div style="{gaya}"><div style="flex:1;display:flex;justify-content:space-between;'
            f'border-top:0.5pt solid #e4e1d9;padding-top:2mm;">'
            f'<span>Data per {F["diperbarui"]}</span>'
            f'<span>Halaman <span class="pageNumber"></span> dari <span class="totalPages"></span></span></div></div>')
    kaki_daftar = kaki.split('<span>Halaman')[0] + '<span>Daftar isi</span></div></div>'
    return kepala, kaki, kaki_daftar


def _nomor_dari_outline(pdf_bytes, bagian):
    """Halaman awal tiap bagian dari bookmark PDF yang dibuat Chrome dari judul <h1>."""
    from pypdf import PdfReader
    r = PdfReader(io.BytesIO(pdf_bytes))
    judul = {j.lower(): k for k, j in bagian}
    hal = {}

    def jelajah(item):
        for it in item:
            if isinstance(it, list):
                jelajah(it)
                continue
            k = judul.get(re.sub(r"\s+", " ", it.title or "").strip().lower())
            if k and k not in hal:
                hal[k] = r.get_destination_page_number(it) + 1
    try:
        jelajah(r.outline)
    except Exception:
        return {}
    return hal


def _nomor_halaman(pdf_bytes, bagian):
    """Cadangan: halaman tempat tiap bagian dimulai (penanda 'Bagian 0N' di judul bab)."""
    from pypdf import PdfReader
    r = PdfReader(io.BytesIO(pdf_bytes))
    hal = {}
    for i, page in enumerate(r.pages):
        teks = re.sub(r"\s+", " ", page.extract_text() or "").lower()
        for j, (k, _) in enumerate(bagian):
            if k not in hal and f"bagian {j + 1:02d}" in teks:
                hal[k] = i + 1
    return hal


def _pdf(b, html_, header=None, footer=None, margin=None):
    pg = b.new_page()
    pg.set_content(html_, wait_until="load", timeout=120000)       # font & gambar tertanam: tanpa jaringan
    pg.evaluate("document.fonts.ready")
    opsi = dict(format="A4", print_background=True, prefer_css_page_size=True, outline=True, tagged=True)
    if header is not None:
        opsi.update(display_header_footer=True, header_template=header, footer_template=footer,
                    margin=margin)
    data = pg.pdf(**opsi)
    pg.close()
    return data


def _buka_chrome(p, log=print):
    """Google Chrome bila terpasang (hasil sama dengan di laptop); selain itu Chromium bawaan Playwright,
    misalnya di server Linux setelah `playwright install chromium`. LAPORAN_CHROME="" memaksa Chromium."""
    kanal = os.environ.get("LAPORAN_CHROME", "chrome")
    if kanal:
        try:
            return p.chromium.launch(channel=kanal, headless=True)
        except Exception:
            log(f"[laporan] Chrome '{kanal}' tidak ditemukan, memakai Chromium bawaan Playwright")
    return p.chromium.launch(headless=True)


def _server_sementara(log=print):
    """Nyalakan dashboard di port bebas (thread daemon) dan kembalikan URL-nya."""
    import app as aplikasi
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    th = threading.Thread(target=lambda: aplikasi.app.run(host="127.0.0.1", port=port, threaded=True,
                                                          use_reloader=False), daemon=True)
    th.start()
    url = f"http://127.0.0.1:{port}/"
    for _ in range(60):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            break
        except OSError:
            time.sleep(0.5)
    log(f"[laporan] server dashboard sementara: {url}")
    return url


def _nama_berkas(slug, d1, d2, ai=False):
    return f"{slug}-laporan-{d1}_{d2}" + ("-ai" if ai else "")


def laporan_tersimpan(slug, dari=None, sampai=None, ai=False):
    """PDF terakhir topik dan periode ini bila masih mutakhir, selain itu None. Mutakhir = dibuat setelah
    perubahan terakhir pada data, graf SNA, file topik (kesimpulan), aturan label, dan desain laporan;
    jadi mengunduh ulang tanpa perubahan apa pun tidak mencetak ulang."""
    import glob
    d1, d2, penuh = periode(slug, dari, sampai)
    pola = _nama_berkas(slug, d1, d2, ai) + "-[0-9]*.pdf"
    ada = sorted(glob.glob(os.path.join(FOLDER_KELUAR, pola)), key=os.path.getmtime)
    if not ada:
        return None
    terakhir = ada[-1]
    T = sumber.topik.muat(slug)
    acuan = [sumber.diperbarui(slug), os.path.getmtime(T.__file__), os.path.getmtime(__file__),
             os.path.getmtime(os.path.join(ROOT, "scripts", "label_teks.py")),
             os.path.getmtime(os.path.join(ROOT, "webapp", "static", "laporan.css"))]
    fsna = folder_sna(slug, d1, d2, penuh)
    acuan += [t for t in label_ai.versi(slug) if t]
    for f in [os.path.join(fsna, "sna.json"), os.path.join(sumber.topik.folder(slug), "sna_narasi.json"),
              label_ai.berkas_kesimpulan(slug, d1, d2, penuh)] + \
            [os.path.join(TEMPLAT, n) for n in os.listdir(TEMPLAT)]:
        if os.path.exists(f):
            acuan.append(os.path.getmtime(f))
    return terakhir if os.path.getmtime(terakhir) > max(acuan) else None


def pakai_ai(slug, ai=None, d1=None, d2=None, penuh=True):
    """AI dipakai laporan bila diminta (ai=True/False) atau, bila tidak ditentukan, menurut setelan topik
    (Kelola › Validasi) dan selama API key tersedia. Hanya True bila AI memang akan menulis sesuatu: nama
    klaster graf periode (bukan seluruh periode) atau kesimpulan yang belum disetujui dan tanpa catatan analis."""
    import ai_klien
    if not ai_klien.tersedia() or not (label_ai.setelan(slug)["laporan_ai"] if ai is None else bool(ai)):
        return False
    if not penuh:
        return True
    setuju = (label_ai.baca_json(label_ai.berkas_kesimpulan(slug, d1, d2, penuh), {}) or {}).get("disetujui")
    return not setuju and not getattr(sumber.topik.muat(slug), "KESIMPULAN", None)


def buat_laporan(slug, keluar=None, url=None, log=print, pakai_tersimpan=False, dari=None, sampai=None, ai=None):
    """Buat laporan PDF untuk satu topik; kembalikan path berkasnya.

    slug        : topik (lihat topik.DAFTAR)
    keluar      : path PDF tujuan; bawaan laporan/<slug>-laporan-<dari>_<sampai>-YYYYMMDD-HHMM.pdf
    url         : URL dashboard yang sudah berjalan (mis. "http://127.0.0.1:8080/");
                  bila kosong, server sementara dinyalakan otomatis
    pakai_tersimpan : kembalikan PDF terakhir periode ini bila masih mutakhir (lihat laporan_tersimpan)
    dari, sampai: periode laporan 'YYYY-MM-DD' (bawaan: seluruh jendela topik)
    ai          : True/False memaksa pemakaian AI untuk nama klaster periode dan kesimpulan yang belum
                  disetujui; None = menurut setelan topik
    """
    d1, d2, penuh = periode(slug, dari, sampai)
    ai = pakai_ai(slug, ai, d1, d2, penuh)
    if pakai_tersimpan and not keluar:
        lama = laporan_tersimpan(slug, d1, d2, ai)
        if lama:
            log(f"[laporan] memakai laporan tersimpan yang masih mutakhir: {lama}")
            return lama
    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader, PdfWriter
    t0 = time.time()
    lap = lambda pesan: log(f"{pesan} ({time.time() - t0:.0f} dtk)")
    if not penuh:
        folder = siapkan_sna(slug, d1, d2, log)
        if ai:
            import ai_jalan
            try:
                ai_jalan.namai_rentang(folder, sumber.topik.muat(slug), slug, log)
            except Exception as e:
                log(f"[laporan] nama klaster AI gagal, memakai nama otomatis: {e}")
        lap("[laporan] graf SNA periode siap")
    F = fakta(slug, d1, d2)
    if ai:
        pasang_kesimpulan_ai(F, log)
    lap(f"[laporan] fakta {slug} {F['periode']} dihitung")
    url = url or _server_sementara(log)
    if not url.endswith("/"):
        url += "/"
    kepala, kaki, kaki_daftar = _header_footer(F)
    margin = {"top": "22mm", "bottom": "20mm", "left": "17mm", "right": "17mm"}
    with sync_playwright() as p:
        b = _buka_chrome(p, log)                                # satu Chrome untuk tangkap & cetak
        ego = {sen: [a["id"] for a in (F[k] or {}).get("ego", [])] for sen, k in (("negatif", "neg"), ("positif", "pos"))}
        gambar = tangkap(F, url, b, log, ego)
        lap("[laporan] grafik dashboard tertangkap")
        html_ = render(F, gambar)
        sampul = _pdf(b, html_["sampul"])
        # isi dicetak sekali; nomor halaman tiap bagian dibaca dari bookmark-nya, lalu daftar isi
        # (satu halaman) dicetak terpisah dengan nomor itu
        isi = _pdf(b, html_["isi"], kepala, kaki, margin)
        bg = bagian_laporan(F)
        hal = _nomor_dari_outline(isi, bg) or _nomor_halaman(isi, bg)
        daftar_ = _pdf(b, render(F, gambar, hal)["daftar"], kepala, kaki_daftar, margin)
        b.close()
    lap("[laporan] PDF dicetak")

    w = PdfWriter()
    for data, outline in ((sampul, False), (daftar_, False), (isi, True)):
        w.append(PdfReader(io.BytesIO(data)), import_outline=outline)   # bookmark bab ikut tersalin
    # label halaman = nomor di footer: sampul & daftar isi "i, ii", isi mulai dari 1
    n_depan = len(PdfReader(io.BytesIO(sampul)).pages) + len(PdfReader(io.BytesIO(daftar_)).pages)
    w.set_page_label(0, n_depan - 1, style="/r")
    w.set_page_label(n_depan, len(w.pages) - 1, style="/D", start=1)
    w.add_metadata({"/Title": f"Laporan Percakapan Publik: {F['judul']} ({F['periode']})",
                    "/Author": "Analisa Sentimen", "/Subject": f"Percakapan publik {F['periode']}",
                    "/Creator": "scripts/laporan.py"})
    if not keluar:
        os.makedirs(FOLDER_KELUAR, exist_ok=True)
        keluar = os.path.join(FOLDER_KELUAR, f"{_nama_berkas(slug, d1, d2, ai)}-{datetime.now():%Y%m%d-%H%M}.pdf")
    keluar = os.path.expanduser(keluar)
    os.makedirs(os.path.dirname(os.path.abspath(keluar)), exist_ok=True)
    with open(keluar, "wb") as fh:
        w.write(fh)
    log(f"[laporan] selesai: {keluar} ({len(w.pages)} halaman, {os.path.getsize(keluar) / 1e6:.1f} MB, "
        f"{time.time() - t0:.0f} dtk)")
    return keluar


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Buat laporan PDF satu topik")
    ap.add_argument("--topik", required=True, help=f"slug topik: {', '.join(sumber.topik.DAFTAR)}")
    ap.add_argument("--dari", help="awal periode laporan, YYYY-MM-DD (bawaan: awal jendela topik)")
    ap.add_argument("--sampai", help="akhir periode laporan, YYYY-MM-DD (bawaan: akhir jendela topik)")
    ap.add_argument("--keluar", help="path PDF tujuan")
    ap.add_argument("--url", help="URL dashboard yang sudah berjalan (opsional)")
    ap.add_argument("--cache", action="store_true", help="pakai PDF terakhir bila data belum berubah")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--ai", dest="ai", action="store_true", default=None,
                   help="pakai AI untuk nama klaster periode dan kesimpulan yang belum disetujui")
    g.add_argument("--tanpa-ai", dest="ai", action="store_false")
    a = ap.parse_args()
    buat_laporan(a.topik, a.keluar, a.url, pakai_tersimpan=a.cache, dari=a.dari, sampai=a.sampai, ai=a.ai)
