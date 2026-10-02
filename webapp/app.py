#!/usr/bin/env python3
"""Analisa Sentimen: dashboard multi-topik (KM Virgo, INPEX Masela, ...).

Jalankan:  python3 webapp/app.py   lalu buka http://127.0.0.1:8080
Server:    gunicorn --chdir webapp -w 2 -t 300 -b 0.0.0.0:8080 app:app
           (DASHBOARD_USER + DASHBOARD_PASS mengaktifkan login; HOST/PORT untuk app.run)
  /                      buka topik terakhir yang dilihat (satu dashboard, pemilih topik di bilah atas)
  /<topik>/              ringkasan satu topik (mis. /masela/)
  /api/<topik>/<data>    agregat JSON untuk grafik

Semua grafik dirender di sisi klien dengan Chart.js; Python hanya menyiapkan
agregat sebagai JSON. Tidak ada dependensi selain Flask + pandas.
"""
import hmac
import json
import os
import re
import sys
from datetime import date

from flask import Flask, Response, abort, jsonify, make_response, redirect, render_template, request, send_file

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sumber  # noqa: E402
from label_teks import penanda  # noqa: E402  (sumber sudah menambah scripts/ ke path)

app = Flask(__name__)
app.jinja_env.globals["PLATFORM"] = list(sumber.PLATFORM.keys())

# Saat dipasang daring: isi DASHBOARD_USER dan DASHBOARD_PASS agar semua halaman, API, dan unduhan
# laporan meminta login (HTTP Basic). Data berisi nama akun dan unggahan pengguna media sosial.
_LOGIN = (os.environ.get("DASHBOARD_USER", ""), os.environ.get("DASHBOARD_PASS", ""))


@app.before_request
def _wajib_login():
    if not all(_LOGIN):
        return None
    a = request.authorization
    if a and hmac.compare_digest(a.username or "", _LOGIN[0]) and hmac.compare_digest(a.password or "", _LOGIN[1]):
        return None
    return Response("Login diperlukan.", 401, {"WWW-Authenticate": 'Basic realm="Analisa Sentimen", charset="UTF-8"'})

URUTAN_EMOSI = ["sedih", "antisipasi", "marah", "jijik", "percaya", "senang",
                "takut", "terkejut"]
# palet sentimen diverging merah-abu-biru, tervalidasi untuk buta warna
WARNA_SENTIMEN = {"negatif": "#e66767", "netral": "#5a5954",
                  "positif": "#3987e5", "belum dilabeli": "#3a3a36"}


def _filter(df):
    """Terapkan filter platform / tanggal / tipe penulis dari query string."""
    p = request.args.get("platform", "")
    if p and p != "semua":
        df = df[df.platform == p]
    t = request.args.get("tipe", "")
    if t and t != "semua":
        df = df[df.tipe_penulis == t]
    d1, d2 = request.args.get("dari", ""), request.args.get("sampai", "")
    if d1:
        df = df[df.tanggal >= d1]
    if d2:
        df = df[df.tanggal <= d2]
    if request.args.get("fokus") == "1":
        df = df[_maske_fokus(df)]
    return df


def _pola_fokus():
    """Regex narasi lensa fokus topik aktif (topik.FOKUS), None bila tidak ada."""
    slug = (request.view_args or {}).get("slug")
    F = getattr(sumber.topik.muat(slug), "FOKUS", None) if slug in sumber.topik.DAFTAR else None
    return "|".join(re.escape(n) for n in F["narasi"]) if F else None


def _maske_fokus(df):
    pola = _pola_fokus()
    if not pola:
        return df.index == df.index
    return df.topik.fillna("").str.contains(pola, regex=True)


# ------------------------------------------------------------- halaman
def _topik(slug):
    if slug not in sumber.topik.DAFTAR:
        sumber.topik.daftarkan_ulang()          # topik baru yang dibuat worker/proses lain
    if slug not in sumber.topik.DAFTAR:
        abort(404)
    return sumber.topik.muat(slug)


_BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def _periode(awal, akhir):
    """'2026-01-01','2026-09-30' -> '1 Jan – 30 Sep 2026'"""
    (ya, ma, da), (yz, mz, dz) = (map(int, awal.split("-")), map(int, akhir.split("-")))
    kiri = f"{da} {_BULAN[ma - 1]}" + ("" if ya == yz else f" {ya}")
    return f"{kiri} – {dz} {_BULAN[mz - 1]} {yz}"


def _topik_semua():
    """Info ringkas semua topik untuk pemilih topik di bilah atas. Jumlah konten
    dimuat peramban lewat /api/<slug>/status saat pemilih dibuka, agar membuka satu
    topik tidak memaksa server memuat data topik lain."""
    sumber.topik.daftarkan_ulang()
    return [{"slug": t.SLUG, "nama": t.NAMA, "judul": t.JUDUL, "status": t.STATUS,
             "periode": _periode(*t.JENDELA)} for t in sumber.topik.semua()]


_TGL = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _rentang_url(T):
    """Periode dari ?dari=&sampai= (dipotong ke jendela topik), atau None bila tidak ada/tidak sah."""
    d1, d2 = request.args.get("dari", ""), request.args.get("sampai", "")
    if not (_TGL.match(d1) and _TGL.match(d2)):
        return None
    d1, d2 = max(d1, T.JENDELA[0]), min(d2, T.JENDELA[1])
    return (d1, d2) if d1 <= d2 else None


def _per_pekan(slug):
    """Grafik waktu per pekan atau per hari: ?per= dari halaman, selain itu bawaan topik."""
    per = request.args.get("per", "")
    return per == "pekan" if per in ("pekan", "hari") else sumber.konteks(slug).pekanan


def _halaman(template, slug, judul, **kw):
    T = _topik(slug)
    rng = _rentang_url(T)
    f_dari, f_sampai = rng or T.JENDELA
    # halaman yang dibuka dengan periode di URL (mis. untuk laporan) memilih per hari/pekan
    # sesuai panjang periode itu; selain itu mengikuti panjang jendela topik
    pekanan = ((date.fromisoformat(f_sampai) - date.fromisoformat(f_dari)).days > 60) if rng \
        else sumber.konteks(slug).pekanan
    import ai_klien
    import label_ai
    info = {"slug": slug, "awal": T.JENDELA[0], "akhir": T.JENDELA[1],
            "preset": [list(p) for p in T.PRESET], "per": "pekan" if pekanan else "hari",
            "ai": ai_klien.tersedia(), "laporan_ai": label_ai.setelan(slug)["laporan_ai"]}
    # sumber label sentimen topik ini dan hasil validasinya (Kelola › Validasi sentimen)
    v = label_ai.baca_json(label_ai.berkas(slug, "validasi.json"), {}) or {}
    dinilai = [x for x in v.get("item", []) if x.get("manusia", {}).get("s")]
    kunci_label = "ai" if label_ai.aktif(slug) else "aturan"
    cocok = [x for x in dinilai if x.get(kunci_label, {}).get("s")]
    label_info = {"sumber": kunci_label, "n": len(cocok),
                  "akurasi": (sum(x[kunci_label]["s"] == x["manusia"]["s"] for x in cocok) / len(cocok)) if cocok else None}
    resp = make_response(render_template(
        template, judul=judul, T=T, slug=slug, topik_semua=_topik_semua(), label_info=label_info,
        topik_info=json.dumps(info, ensure_ascii=False), f_dari=f_dari, f_sampai=f_sampai,
        cetak=request.args.get("cetak") == "1",
        per="per pekan" if pekanan else "harian", pekanan=pekanan, **kw))
    # halaman awal membuka topik terakhir yang dilihat
    resp.set_cookie("topik", slug, max_age=365 * 86400, samesite="Lax")
    return resp


@app.route("/")
def halaman_awal():
    """Satu dashboard untuk semua topik: buka topik terakhir yang dilihat,
    selain itu topik terbaru (urutan pertama di topik.DAFTAR)."""
    slug = request.cookies.get("topik")
    if slug not in sumber.topik.DAFTAR:
        slug = sumber.topik.DAFTAR[0]
    return redirect(f"/{slug}/")


@app.route("/<slug>/")
def halaman_ringkasan(slug):
    return _halaman("index.html", slug, "Ringkasan")


@app.route("/<slug>/platform/<nama>")
def halaman_platform(slug, nama):
    return _halaman("platform.html", slug, nama, platform=nama)


@app.route("/<slug>/jelajah")
def halaman_jelajah(slug):
    return _halaman("jelajah.html", slug, "Jelajah Data")


@app.route("/<slug>/metode")
def halaman_metode(slug):
    return _halaman("metode.html", slug, "Metodologi & Batasan")


# tautan lama (sebelum multi-topik) tetap berfungsi: semuanya milik topik Virgo
@app.route("/sna")
def lama_sna():
    return redirect("/virgo/#sna")


@app.route("/platform/<nama>")
def lama_platform(nama):
    return redirect(f"/virgo/platform/{nama}")


@app.route("/jelajah")
def lama_jelajah():
    return redirect("/virgo/jelajah")


@app.route("/metode")
def lama_metode():
    return redirect("/virgo/metode")


def _waktu_indo(ts):
    from datetime import datetime
    if not ts:
        return "belum ada data"
    t = datetime.fromtimestamp(ts)
    bulan = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    return f"{t.day} {bulan[t.month - 1]}, {t:%H.%M}"


def _folder_sna(slug):
    """Folder graf SNA: graf periode ?dari=&sampai= bila sudah dibuat (oleh laporan per periode),
    selain itu graf seluruh periode."""
    T = _topik(slug)
    rng = _rentang_url(T)
    if rng and rng != tuple(T.JENDELA):
        d = os.path.join(sumber.topik.folder(slug), "_rentang", f"{rng[0]}_{rng[1]}")
        if os.path.exists(os.path.join(d, "sna.json")):
            return d
    return sumber.topik.folder(slug)


@app.route("/api/<slug>/sna")
def api_sna(slug):
    """Graf sosial + graf media-aktor hasil scripts/12_sna.py. Filter platform
    diterapkan di peramban agar pergantian filter tidak mengunduh ulang graf."""
    f = os.path.join(_folder_sna(slug), "sna.json")
    if not os.path.exists(f):
        return jsonify({"sosial": None, "berita": None, "pesan": "jalankan scripts/12_sna.py"})
    with open(f, encoding="utf-8") as fh:
        return app.response_class(fh.read(), mimetype="application/json")


_KUNCI_LAPORAN = __import__("threading").Lock()


@app.route("/<slug>/laporan.pdf")
def unduh_laporan(slug):
    """Buat laporan PDF topik ini (scripts/laporan.py) dan kirim sebagai unduhan.
    Laporan dibuat satu per satu: tiap pembuatan membuka Chrome tanpa jendela ±1 menit."""
    _topik(slug)
    from laporan import buat_laporan
    with _KUNCI_LAPORAN:
        # ?baru=1 memaksa cetak ulang; selain itu PDF terakhir dipakai bila data belum berubah
        rng = _rentang_url(sumber.topik.muat(slug))
        ai = request.args.get("ai")
        path = buat_laporan(slug, url=request.host_url, log=lambda *a: app.logger.info(" ".join(map(str, a))),
                            pakai_tersimpan=request.args.get("baru") != "1",
                            dari=rng[0] if rng else None, sampai=rng[1] if rng else None,
                            ai=None if ai is None else ai == "1")
    return send_file(path, mimetype="application/pdf", as_attachment=True,
                     download_name=os.path.basename(path))


@app.route("/api/<slug>/sna-teks")
def api_sna_teks(slug):
    """Isi unggahan per sisi graf (urutan sama dengan sna.json), untuk pencarian isi
    dan daftar unggahan di peta. Dipisah karena hanya diunduh saat dibutuhkan."""
    f = os.path.join(_folder_sna(slug), "sna_teks.json")
    if not os.path.exists(f):
        return jsonify({"sosial": [], "berita": []})
    with open(f, encoding="utf-8") as fh:
        return app.response_class(fh.read(), mimetype="application/json")


# id berawalan kode ini adalah komentar/balasan; selebihnya unggahan utama
_KOMENTAR = ("YTK", "IGK", "THB")


@app.route("/api/<slug>/contoh-sentimen")
def api_contoh_sentimen(slug):
    """Contoh nyata tiap sentimen — posting dan komentar terpisah — lengkap
    dengan penanda yang membuatnya dilabeli begitu. Dipilih dari engagement
    tertinggi agar yang tampil adalah konten yang benar-benar banyak dilihat.
    Berita dikecualikan: sentimennya masih baseline lexicon."""
    T = sumber.konteks(slug).T
    df = _filter(sumber.semua(slug))
    df = df[(df.platform != "Berita") & (df.teks.fillna("").str.len() >= 40)]
    df = df.assign(jenis=df.id.astype(str).str.startswith(_KOMENTAR).map(
        {True: "komentar", False: "posting"}))
    per = int(request.args.get("n", 4))
    out = {}
    for sen in ("negatif", "netral", "positif"):
        out[sen] = {}
        for jenis in ("posting", "komentar"):
            sub = df[(df.sentimen == sen) & (df.jenis == jenis)].sort_values(
                "engagement", ascending=False)
            pilih, lihat = [], set()
            for r in sub.head(60).itertuples():
                kunci = re.sub(r"\W+", " ", str(r.teks).lower())[:80]
                if kunci in lihat:
                    continue
                lihat.add(kunci)
                pilih.append({
                    "platform": r.platform, "penulis": r.penulis, "tanggal": r.tanggal,
                    "teks": str(r.teks)[:320], "url": r.url, "engagement": int(r.engagement),
                    "emosi": r.emosi, "penanda": penanda(str(r.teks), narasi=T.NARASI,
                                                    aturan=getattr(T, "ATURAN", None)),
                })
                if len(pilih) == per:
                    break
            out[sen][jenis] = pilih
        out[sen]["jumlah"] = int((df.sentimen == sen).sum())
    return jsonify(out)


@app.route("/api/<slug>/fokus")
def api_fokus(slug):
    """Lensa sorotan: porsi konten fokus (mis. demo & tuntutannya) dibanding
    seluruh percakapan, per periode, per platform, dan per narasi. Filter
    fokus sengaja diabaikan di sini agar perbandingannya utuh."""
    T = _topik(slug)
    F = getattr(T, "FOKUS", None)
    if not F:
        return jsonify({"ada": False})
    args = request.args.to_dict()
    args.pop("fokus", None)
    df = sumber.semua(slug)
    p = args.get("platform", "")
    if p and p != "semua":
        df = df[df.platform == p]
    if args.get("tipe") and args["tipe"] != "semua":
        df = df[df.tipe_penulis == args["tipe"]]
    if args.get("dari"):
        df = df[df.tanggal >= args["dari"]]
    if args.get("sampai"):
        df = df[df.tanggal <= args["sampai"]]
    if not len(df):
        return jsonify({"ada": True, "nama": F["nama"], "narasi": F["narasi"], "label": [], "seri": [],
                        "total": {"konten": 0, "fokus": 0, "persen": 0}, "per_platform": {}, "per_narasi": []})
    df = df.assign(tanggal=sumber.kolom_waktu(sumber.konteks(slug), df, _per_pekan(slug)), fokus=_maske_fokus(df))
    label = sorted(df.tanggal.unique())

    def seri(d, nama):
        g = d.groupby("tanggal").agg(n=("id", "count"), f=("fokus", "sum"))
        return {"nama": nama,
                # pekan dengan < 10 konten tidak diberi porsi: 1 dari 2 konten = 50% hanya bising
                "persen": [round(100 * float(g.f.get(t, 0)) / g.n[t], 1) if t in g.index and g.n[t] >= 10 else None
                           for t in label],
                "fokus": [int(g.f.get(t, 0)) for t in label],
                "total": [int(g.n.get(t, 0)) for t in label]}
    hasil = [seri(df, "Semua platform")]
    per_platform = {}
    for pl, d in df.groupby("platform"):
        hasil.append(seri(d, pl))
        per_platform[pl] = {"konten": int(len(d)), "fokus": int(d.fokus.sum()),
                            "persen": round(100 * float(d.fokus.sum()) / len(d), 1)}
    from collections import Counter
    c = Counter()
    for t in df[df.fokus].topik.fillna(""):
        for n in str(t).split("; "):
            if n in F["narasi"]:
                c[n] += 1
    return jsonify({
        "ada": True, "nama": F["nama"], "ket": F.get("ket", ""), "narasi": F["narasi"],
        "label": label, "seri": hasil,
        "total": {"konten": int(len(df)), "fokus": int(df.fokus.sum()),
                  "persen": round(100 * float(df.fokus.sum()) / len(df), 1)},
        "per_platform": per_platform,
        "per_narasi": [{"nama": n, "n": int(c.get(n, 0))} for n in F["narasi"]],
    })


@app.route("/api/<slug>/emosi")
def api_emosi(slug):
    """Distribusi 8 emosi Plutchik (media sosial saja; berita tidak dilabeli emosi)."""
    df = _filter(sumber.semua(slug))
    netral = int((df.emosi == "netral").sum())
    df = df[df.emosi.isin(URUTAN_EMOSI)]
    vc = df.emosi.value_counts()
    total = int(vc.sum()) or 1
    label = [e for e in URUTAN_EMOSI if e in vc.index]
    label.sort(key=lambda e: -int(vc[e]))
    return jsonify({"label": label, "data": [int(vc[e]) for e in label],
                    "persen": [round(100 * int(vc[e]) / total, 1) for e in label],
                    "netral": netral})


# ---------------------------------------------------------------- API
@app.route("/api/<slug>/status")
def api_status(slug):
    """Untuk bilah atas: kapan data terakhir berubah dan berapa isinya."""
    df = sumber.semua(slug)
    return jsonify({"diperbarui": _waktu_indo(sumber.diperbarui(slug)),
                    "total": int(len(df)),
                    "platform": {k: int(v) for k, v in df.platform.value_counts().items()}})


@app.route("/api/<slug>/ringkasan")
def api_ringkasan(slug):
    df = _filter(sumber.semua(slug))
    r = sumber.ringkas(df)
    r["opsi_tipe"] = sorted(x for x in df.tipe_penulis.dropna().unique() if x)
    return jsonify(r)


@app.route("/api/<slug>/linimasa")
def api_linimasa(slug):
    df = _filter(sumber.semua(slug))
    df = df.assign(tanggal=sumber.kolom_waktu(sumber.konteks(slug), df, _per_pekan(slug)))
    if not len(df):
        return jsonify({"label": [], "seri": []})
    piv = df.pivot_table(index="tanggal", columns="platform",
                         values="id", aggfunc="count").fillna(0).sort_index()
    return jsonify({
        "label": list(piv.index),
        "seri": [{"nama": c, "data": [int(v) for v in piv[c]]} for c in piv.columns],
    })


def _sosial(df):
    """Grafik sentimen memakai media sosial saja: sentimen berita masih baseline
    lexicon (94% negatif karena kata musibah), tidak sebanding dengan aturan
    media sosial. Berita tetap tampil bila filter platform = Berita."""
    if request.args.get("platform", "") == "Berita":
        return df
    return df[df.platform != "Berita"]


@app.route("/api/<slug>/sentimen")
def api_sentimen(slug):
    df = _sosial(_filter(sumber.semua(slug)))
    df = df.assign(tanggal=sumber.kolom_waktu(sumber.konteks(slug), df, _per_pekan(slug)))
    if not len(df):
        return jsonify({"label": [], "data": [], "warna": [], "harian": {}})
    vc = df.sentimen.fillna("belum dilabeli").value_counts()
    piv = (df.pivot_table(index="tanggal", columns="sentimen",
                          values="id", aggfunc="count").fillna(0).sort_index())
    return jsonify({
        "label": list(vc.index),
        "data": [int(v) for v in vc.values],
        "warna": [WARNA_SENTIMEN.get(k, "#58a6ff") for k in vc.index],
        "harian": {
            "label": list(piv.index),
            "seri": [{"nama": c, "data": [int(v) for v in piv[c]],
                      "warna": WARNA_SENTIMEN.get(c, "#58a6ff")} for c in piv.columns],
        },
    })


@app.route("/api/<slug>/narasi")
def api_narasi(slug):
    df = _filter(sumber.semua(slug))
    from collections import Counter
    c = Counter()
    for s in df.topik.fillna(""):
        for t in str(s).split("; "):
            if t:
                c[t] += 1
    if not c:
        c = Counter(df.narasi.fillna("Lainnya"))
    top = c.most_common(14)
    return jsonify({"label": [k for k, _ in top], "data": [v for _, v in top]})


@app.route("/api/<slug>/penulis")
def api_penulis(slug):
    df = _filter(sumber.semua(slug))
    if not len(df):
        return jsonify({"volume": [], "engagement": [], "tipe": {}})
    vol = df.penulis.value_counts().head(15)
    eng = (df.groupby("penulis").engagement.sum()
             .sort_values(ascending=False).head(15))
    tipe = df.tipe_penulis.fillna("-").value_counts()
    return jsonify({
        "volume": [{"nama": k, "nilai": int(v)} for k, v in vol.items()],
        "engagement": [{"nama": k, "nilai": int(v)} for k, v in eng.items() if v > 0],
        "tipe": {"label": list(tipe.index), "data": [int(v) for v in tipe.values]},
    })


@app.route("/api/<slug>/kata")
def api_kata(slug):
    df = _filter(sumber.semua(slug))
    teks = df.teks
    if (df.platform == "Berita").all() and len(df):
        teks = df.judul.fillna("") + " " + df.teks.fillna("")
    return jsonify({
        "kata": [{"t": k, "n": v} for k, v in sumber.kata_teratas(teks, 70, stop=_topik(slug).STOP)],
        "tagar": [{"t": k, "n": v} for k, v in sumber.tagar_teratas(df, 25)],
    })


@app.route("/api/<slug>/jam")
def api_jam(slug):
    """Pola jam unggah: matriks tanggal x jam untuk heatmap."""
    df = _filter(sumber.semua(slug))
    df = df.assign(tanggal=sumber.kolom_waktu(sumber.konteks(slug), df, _per_pekan(slug)))
    df = df[df.jam >= 0]
    if not len(df):
        return jsonify({"tanggal": [], "sel": [], "maks": 0, "per_jam": [0] * 24})
    piv = df.pivot_table(index="tanggal", columns="jam", values="id",
                         aggfunc="count").fillna(0)
    for j in range(24):
        if j not in piv.columns:
            piv[j] = 0
    piv = piv[sorted(piv.columns)].sort_index()
    sel = []
    for iy, tgl in enumerate(piv.index):
        for j in range(24):
            n = int(piv.loc[tgl, j])
            if n:
                sel.append({"x": j, "y": iy, "v": n})
    per_jam = [int(piv[j].sum()) for j in range(24)]
    return jsonify({"tanggal": list(piv.index), "sel": sel,
                    "maks": int(max((s["v"] for s in sel), default=0)),
                    "per_jam": per_jam})


@app.route("/api/<slug>/kumulatif")
def api_kumulatif(slug):
    df = _filter(sumber.semua(slug))
    df = df.assign(tanggal=sumber.kolom_waktu(sumber.konteks(slug), df, _per_pekan(slug)))
    if not len(df):
        return jsonify({"label": [], "seri": []})
    piv = df.pivot_table(index="tanggal", columns="platform", values="id",
                         aggfunc="count").fillna(0).sort_index().cumsum()
    return jsonify({"label": list(piv.index),
                    "seri": [{"nama": c, "data": [int(v) for v in piv[c]]}
                             for c in piv.columns]})


@app.route("/api/<slug>/aktor")
def api_aktor(slug):
    """Entitas/aktor yang disebut di dalam konten."""
    df = _filter(sumber.semua(slug))
    from collections import Counter
    c = Counter()
    for s in df.aktor.fillna(""):
        for a in str(s).split("; "):
            a = a.strip()
            if a:
                c[a] += 1
    top = c.most_common(16)
    return jsonify({"label": [k for k, _ in top], "data": [v for _, v in top]})


@app.route("/api/<slug>/narasi-harian")
def api_narasi_harian(slug):
    """Pergeseran narasi dari hari ke hari (area bertumpuk, 8 teratas)."""
    df = _filter(sumber.semua(slug))
    df = df.assign(tanggal=sumber.kolom_waktu(sumber.konteks(slug), df, _per_pekan(slug)))
    if not len(df):
        return jsonify({"label": [], "seri": []})
    from collections import Counter
    c = Counter()
    for s in df.topik.fillna(""):
        for t in str(s).split("; "):
            if t:
                c[t] += 1
    atas = [k for k, _ in c.most_common(8)]
    tgl = sorted(df.tanggal.unique())
    seri = []
    for nama in atas:
        m = df.topik.fillna("").str.contains(re.escape(nama), regex=True)
        g = df[m].groupby("tanggal").size()
        seri.append({"nama": nama, "data": [int(g.get(t, 0)) for t in tgl]})
    return jsonify({"label": tgl, "seri": seri})


@app.route("/api/<slug>/sentimen-tipe")
def api_sentimen_tipe(slug):
    """Sentimen dipecah per tipe penulis: memperlihatkan bias arus berita."""
    df = _sosial(_filter(sumber.semua(slug)))
    if not len(df):
        return jsonify({"label": [], "seri": []})
    piv = (df.pivot_table(index="tipe_penulis", columns="sentimen",
                          values="id", aggfunc="count").fillna(0))
    piv = piv.loc[piv.sum(axis=1).sort_values(ascending=False).index]
    return jsonify({
        "label": list(piv.index),
        "seri": [{"nama": c, "data": [int(v) for v in piv[c]],
                  "warna": WARNA_SENTIMEN.get(c, "#58a6ff")} for c in piv.columns],
    })


@app.route("/api/<slug>/engagement")
def api_engagement(slug):
    """Sebaran engagement: memperlihatkan apakah percakapan digerakkan sedikit
    konten viral atau merata."""
    df = _filter(sumber.semua(slug))
    df = df[df.engagement > 0]
    if not len(df):
        return jsonify({"label": [], "data": [], "konsentrasi": []})
    batas = [1, 10, 50, 100, 500, 1000, 5000, 10**9]
    nama = ["1–9", "10–49", "50–99", "100–499", "500–999", "1rb–4,9rb", "≥5rb"]
    jml, bawah = [], 1
    for i, b in enumerate(batas[1:]):
        jml.append(int(((df.engagement >= bawah) & (df.engagement < b)).sum()))
        bawah = b
    urut = df.engagement.sort_values(ascending=False).values
    total = urut.sum()
    konsentrasi = []
    for p in (1, 5, 10, 25, 50, 100):
        n = max(1, int(len(urut) * p / 100))
        konsentrasi.append({"persen": p,
                            "share": round(float(urut[:n].sum()) / float(total) * 100, 1)})
    return jsonify({"label": nama, "data": jml, "konsentrasi": konsentrasi})


@app.route("/api/<slug>/konten")
def api_konten(slug):
    df = _filter(sumber.semua(slug))
    urut = request.args.get("urut", "engagement")
    if urut == "terbaru":
        df = df.sort_values("waktu", ascending=False)
    else:
        df = df.sort_values("engagement", ascending=False)
    cari = request.args.get("cari", "").strip()
    if cari:
        m = (df.judul.fillna("").str.contains(cari, case=False, regex=False)
             | df.teks.fillna("").str.contains(cari, case=False, regex=False))
        df = df[m]
    hal = int(request.args.get("hal", 1))
    per = 50
    total = len(df)
    df = df.iloc[(hal - 1) * per: hal * per]
    kolom = ["platform", "tanggal", "penulis", "tipe_penulis", "judul",
             "teks", "url", "engagement", "jangkauan", "sentimen", "narasi"]
    baris = df[kolom].fillna("").to_dict("records")
    for b in baris:
        b["teks"] = str(b["teks"])[:400]
    return jsonify({"total": total, "hal": hal, "per": per, "baris": baris})


# halaman Kelola: panen dari web, validasi sentimen, klaster, kesimpulan, AI, topik baru
import kelola  # noqa: E402
kelola.pasang(app, _halaman, _topik)


if __name__ == "__main__":
    host, port = os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", 8080))
    print(f"Dashboard: http://{host}:{port}" + ("  (login aktif)" if all(_LOGIN) else ""))
    app.run(host=host, port=port, debug=False)
