"""Halaman Kelola: panen dari web, validasi sentimen, kurasi klaster SNA, kesimpulan laporan,
pengaturan AI, dan wizard topik baru.

Semua pekerjaan berat (panen, graf SNA, tugas AI) masuk antrean scripts/antrean.py sebagai proses
terpisah. Daftar skrip yang boleh dijalankan ditentukan di sini (PIPA dan tugas AI), bukan oleh
peramban: permintaan hanya memilih nama pipa atau tugas.
"""
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import date, datetime

from flask import abort, jsonify, request

import sumber
import label_ai
import ai_klien
import antrean
from topik import _umum

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KONFIG = os.path.expanduser("~/.config/virgo-sentiment")
DRAF_TOPIK = os.path.join(ROOT, "data", "_bersama", "topik_draf")

# Pipa panen per sumber. login = berkas kredensial di ~/.config/virgo-sentiment/; jeda_jam = jarak minimal
# antar-sesi (Instagram dan Threads mudah menandai sesi yang terlalu sering sebagai spam).
PIPA = {
    "berita": {"judul": "Berita", "platform": "Berita",
               "langkah": ["01_harvest_urls.py", "02_decode_urls.py", "05_harvest_native.py",
                           "03_scrape_articles.py", "06_retry_failed.py", "04_process.py"],
               "berkas": ["articles_clean.csv"], "ket": "Google News, mesin pencari media, lalu ambil isi artikel."},
    "youtube": {"judul": "YouTube", "platform": "YouTube",
                "langkah": ["10_yt_harvest.py", "yt_relevan.py", "11_yt_comments.py"],
                "berkas": ["yt/videos.jsonl", "yt/komentar.jsonl"], "ket": "Video, saring relevansi, lalu komentar. Tanpa login."},
    "x": {"judul": "X", "platform": "X (Twitter)", "login": "x_auth.json",
          "langkah": ["07_x_harvest.py", "09_x_sentimen.py", "08_x_replies.py", "09_x_sentimen.py"],
          "berkas": ["x/tweets_labeled.csv"], "ket": "Tweet, balasan, lalu label. Pakai sesi akun X."},
    "instagram": {"judul": "Instagram (unggahan)", "platform": "Instagram", "login": "ig_auth.json", "jeda_jam": 4,
                  "grup": "ig", "langkah": ["13_ig_harvest.py"], "berkas": ["ig/posts.jsonl"],
                  "ket": "Pelan dan berhenti total bila diminta verifikasi. Akun utama: beri jeda antar-sesi."},
    "instagram_komentar": {"judul": "Instagram (komentar)", "platform": "Instagram", "login": "ig_auth.json",
                           "jeda_jam": 4, "grup": "ig", "langkah": ["14_ig_komentar.py"], "berkas": ["ig/komentar.jsonl"],
                           "ket": "Komentar unggahan yang relevan. Jeda yang sama dengan unggahan Instagram."},
    "threads": {"judul": "Threads", "platform": "Threads", "login": "threads_auth.json", "jeda_jam": 2,
                "grup": "threads", "langkah": ["15_threads_harvest.py"], "berkas": ["threads/posts.jsonl"],
                "ket": "Pelan, berhenti total bila diminta verifikasi."},
    "sna": {"judul": "Graf SNA", "langkah": ["12_sna.py"], "berkas": ["sna.json"],
            "ket": "Bangun ulang graf, klaster, dan profil akun dari data terbaru."},
    "x_qid": {"judul": "Perbarui queryId X", "langkah": ["x_qid.py"], "berkas": [], "global": True,
              "ket": "Jalankan bila panen X gagal setelah X merilis versi baru."},
}
SOSIAL = {"x", "instagram", "instagram_komentar", "threads", "youtube"}


# --------------------------------------------------------------- antrean
def buat_pekerjaan(lajur, jenis, judul, topik, langkah, meta=None):
    os.makedirs(antrean.FOLDER, exist_ok=True)
    p = {"id": datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6], "lajur": lajur, "jenis": jenis,
         "judul": judul, "topik": topik, "langkah": langkah, "status": "antre", "dibuat": time.time(),
         "mulai": None, "selesai": None, "langkah_ke": 0, "pesan": "", "meta": meta or {}}
    antrean.tulis(p)
    subprocess.Popen([sys.executable, os.path.join(ROOT, "scripts", "antrean.py"), "--lajur", lajur], cwd=ROOT,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return p


def _ringkas_pekerjaan(p):
    log = antrean.jalur(p["id"], "log")
    progres, biaya, akhir = None, None, None
    if os.path.exists(log):
        with open(log, "rb") as f:
            f.seek(max(0, os.path.getsize(log) - 6000))
            ekor = f.read().decode("utf-8", "replace")
        for baris in reversed(ekor.splitlines()):
            if progres is None and baris.startswith("##PROGRES "):
                a, _, b = baris[10:].partition("/")
                progres = [int(a or 0), int(b or 0)]
            elif biaya is None and baris.startswith("##BIAYA "):
                biaya = float(baris[8:] or 0)
            elif akhir is None and baris.strip() and not baris.startswith("##"):
                akhir = baris.strip()[:200]
    return {k: p.get(k) for k in ("id", "lajur", "jenis", "judul", "topik", "status", "dibuat", "mulai", "selesai",
                                  "langkah_ke", "pesan", "meta")} | {
        "langkah_n": len(p["langkah"]), "langkah": [l["skrip"].split("/")[-1] for l in p["langkah"]],
        "progres": progres, "biaya": biaya, "baris_akhir": akhir}


def daftar_pekerjaan(topik=None, n=25):
    ps = antrean.semua()
    if topik:
        ps = [p for p in ps if p.get("topik") in (topik, None)]
    return [_ringkas_pekerjaan(p) for p in reversed(ps[-n:] if not topik else ps)][:n]


def _jeda(pipa):
    """Waktu paling cepat pipa dengan jeda boleh dijalankan lagi (epoch) atau None."""
    j = PIPA[pipa].get("jeda_jam")
    if not j:
        return None
    grup = PIPA[pipa].get("grup")
    selesai = [p.get("selesai") or p.get("mulai") or 0 for p in antrean.semua()
               if p.get("meta", {}).get("grup") == grup and p.get("mulai")]
    terakhir = max(selesai, default=0)
    boleh = terakhir + j * 3600
    return boleh if boleh > time.time() else None


def _aktif(jenis_awal):
    return [p for p in antrean.semua() if p["status"] in ("antre", "jalan") and p["jenis"].startswith(jenis_awal)]


# --------------------------------------------------------------- validasi sentimen
def metrik_validasi(item):
    """Kecocokan label aturan dan label AI terhadap label manusia."""
    dinilai = [x for x in item if x.get("manusia", {}).get("s")]
    kelas = list(label_ai.SENTIMEN)

    def ukur(kunci):
        xs = [x for x in dinilai if x.get(kunci, {}).get("s")]
        if not xs:
            return None
        cocok = sum(1 for x in xs if x[kunci]["s"] == x["manusia"]["s"])
        mat = {a: {b: 0 for b in kelas} for a in kelas}             # baris = manusia, kolom = mesin
        for x in xs:
            mat[x["manusia"]["s"]][x[kunci]["s"]] += 1
        per_kelas = {}
        for c in kelas:
            tp = mat[c][c]
            pred = sum(mat[a][c] for a in kelas)
            nyata = sum(mat[c].values())
            per_kelas[c] = {"presisi": tp / pred if pred else None, "recall": tp / nyata if nyata else None, "n": nyata}
        # kappa Cohen: kecocokan di luar kebetulan
        n = len(xs)
        pe = sum((sum(mat[c].values()) / n) * (sum(mat[a][c] for a in kelas) / n) for c in kelas)
        po = cocok / n
        return {"n": n, "akurasi": po, "kappa": (po - pe) / (1 - pe) if pe < 1 else None,
                "matriks": mat, "per_kelas": per_kelas}

    return {"total": len(item), "dinilai": len(dinilai), "aturan": ukur("aturan"), "ai": ukur("ai"),
            "tidak_relevan": sum(1 for x in dinilai if x["manusia"].get("relevan") is False)}


# --------------------------------------------------------------- pemasangan rute
def pasang(app, halaman, ambil_topik):
    """Daftarkan rute halaman Kelola di aplikasi Flask (dipanggil dari app.py)."""

    def topik_atau_404(slug):
        ambil_topik(slug)
        return sumber.topik.muat(slug)

    def galat(pesan, kode=400):
        return jsonify({"galat": pesan}), kode

    # ------------------------------------------------------------- halaman
    @app.route("/<slug>/kelola")
    def halaman_kelola(slug):
        T = topik_atau_404(slug)
        return halaman("kelola.html", slug, "Kelola", buatan_web=slug not in sumber.topik.BUATAN_TANGAN, tanpa_saring=True,
                       penuh_dari=T.JENDELA[0], penuh_sampai=T.JENDELA[1])

    @app.route("/kelola/topik-baru")
    def halaman_topik_baru():
        slug = request.args.get("dari") or sumber.topik.DAFTAR[0]
        ubah = request.args.get("ubah")
        if ubah and (ubah not in sumber.topik.DAFTAR or ubah in sumber.topik.BUATAN_TANGAN):
            abort(404)
        return halaman("topik_baru.html", ubah or slug, "Topik baru", tanpa_saring=True, ubah=ubah,
                       ai_siap=ai_klien.tersedia())

    # ------------------------------------------------------------- antrean
    @app.route("/api/kelola/pekerjaan")
    def api_pekerjaan():
        return jsonify({"pekerjaan": daftar_pekerjaan(request.args.get("topik"))})

    @app.route("/api/kelola/pekerjaan/<id_>/log")
    def api_pekerjaan_log(id_):
        if not re.fullmatch(r"[\w-]{6,60}", id_):
            abort(404)
        p = antrean.jalur(id_, "log")
        dari = int(request.args.get("dari", 0))
        if not os.path.exists(p):
            return jsonify({"teks": "", "ukuran": 0})
        ukuran = os.path.getsize(p)
        dari = dari if 0 <= dari <= ukuran else max(0, ukuran - 20000)
        if not dari and ukuran > 20000:
            dari = ukuran - 20000
        with open(p, "rb") as f:
            f.seek(dari)
            teks = f.read().decode("utf-8", "replace")
        teks = "\n".join(b for b in teks.split("\n") if not b.startswith(("##PROGRES", "##BIAYA")))
        return jsonify({"teks": teks, "ukuran": ukuran})

    @app.route("/api/kelola/pekerjaan/<id_>/batal", methods=["POST"])
    def api_pekerjaan_batal(id_):
        p = antrean.baca(id_) if re.fullmatch(r"[\w-]{6,60}", id_) else None
        if not p:
            abort(404)
        if p["status"] in ("antre", "jalan"):
            open(antrean.jalur(id_, "batal"), "w").close()
            if p["status"] == "antre":
                p.update(status="batal", pesan="dibatalkan sebelum mulai", selesai=time.time())
                antrean.tulis(p)
        return jsonify({"ok": True})

    # ------------------------------------------------------------- panen
    @app.route("/api/<slug>/kelola/panen")
    def api_panen(slug):
        topik_atau_404(slug)
        folder = sumber.topik.folder(slug)
        df = sumber.semua(slug)
        jumlah = df.platform.value_counts().to_dict() if len(df) else {}
        out = []
        for kunci, p in PIPA.items():
            mt = [os.path.getmtime(os.path.join(folder, b)) for b in p["berkas"] if os.path.exists(os.path.join(folder, b))]
            login = p.get("login")
            jalan = [x for x in antrean.semua() if x["status"] in ("antre", "jalan") and x.get("meta", {}).get("pipa") == kunci
                     and (p.get("global") or x.get("topik") == slug)]
            out.append({"kunci": kunci, "judul": p["judul"], "ket": p["ket"], "langkah": p["langkah"],
                        "konten": jumlah.get(p.get("platform")) if p.get("platform") else None,
                        "terakhir": max(mt) if mt else None,
                        "login": None if not login else os.path.exists(os.path.join(KONFIG, login)),
                        "jeda_sampai": _jeda(kunci), "jeda_jam": p.get("jeda_jam"),
                        "aktif": jalan[0]["status"] if jalan else None})
        return jsonify({"pipa": out, "pekerjaan": daftar_pekerjaan(slug)})

    @app.route("/api/<slug>/kelola/panen", methods=["POST"])
    def api_panen_mulai(slug):
        T = topik_atau_404(slug)
        d = request.get_json(silent=True) or {}
        kunci = d.get("pipa")
        if kunci not in PIPA:
            return galat("pipa tidak dikenal")
        p = PIPA[kunci]
        if p.get("login") and not os.path.exists(os.path.join(KONFIG, p["login"])):
            return galat(f"berkas login {p['login']} belum ada di ~/.config/virgo-sentiment/")
        boleh = _jeda(kunci)
        if boleh:
            return galat(f"{p['judul']} baru boleh dijalankan lagi pukul {datetime.fromtimestamp(boleh):%H.%M} "
                         f"(jeda {p['jeda_jam']} jam antar-sesi)")
        if any(x.get("meta", {}).get("pipa") == kunci and x.get("topik") == slug for x in _aktif("panen")):
            return galat(f"{p['judul']} untuk topik ini sudah ada di antrean")
        langkah = [{"skrip": f"scripts/{s}"} for s in p["langkah"]]
        if d.get("sna") and kunci in SOSIAL:
            langkah.append({"skrip": "scripts/12_sna.py"})
        pk = buat_pekerjaan("panen", f"panen:{kunci}", f"{p['judul']} · {T.NAMA}", None if p.get("global") else slug,
                            langkah, {"pipa": kunci, "grup": p.get("grup")})
        return jsonify(_ringkas_pekerjaan(pk))

    # ------------------------------------------------------------- setelan label topik
    @app.route("/api/<slug>/kelola/setelan", methods=["GET", "POST"])
    def api_setelan(slug):
        topik_atau_404(slug)
        if request.method == "POST":
            d = request.get_json(silent=True) or {}
            ubah = {}
            if d.get("label") in ("aturan", "ai"):
                ubah["label"] = d["label"]
            for k in ("buang_tidak_relevan", "laporan_ai"):
                if k in d:
                    ubah[k] = bool(d[k])
            label_ai.simpan_setelan(slug, **ubah)
            if d.get("bangun_sna"):
                buat_pekerjaan("panen", "panen:sna", f"Graf SNA · {slug}", slug, [{"skrip": "scripts/12_sna.py"}],
                               {"pipa": "sna"})
        return jsonify(label_ai.setelan(slug))

    # ------------------------------------------------------------- validasi
    @app.route("/api/<slug>/kelola/validasi")
    def api_validasi(slug):
        topik_atau_404(slug)
        v = label_ai.baca_json(label_ai.berkas(slug, "validasi.json"), {}) or {}
        item = v.get("item", [])
        return jsonify({"dibuat": v.get("dibuat"), "model": v.get("model"), "item": item,
                        "metrik": metrik_validasi(item), "setelan": label_ai.setelan(slug),
                        "aktif": [_ringkas_pekerjaan(p) for p in _aktif("ai:validasi") if p.get("topik") == slug]})

    @app.route("/api/<slug>/kelola/validasi/buat", methods=["POST"])
    def api_validasi_buat(slug):
        T = topik_atau_404(slug)
        n = max(30, min(400, int((request.get_json(silent=True) or {}).get("n", 150))))
        pk = buat_pekerjaan("ai", "ai:validasi", f"Sampel validasi {n} konten · {T.NAMA}", slug,
                            [{"skrip": "scripts/ai_jalan.py", "args": ["validasi", "--n", str(n)]}])
        return jsonify(_ringkas_pekerjaan(pk))

    @app.route("/api/<slug>/kelola/validasi/label", methods=["POST"])
    def api_validasi_label(slug):
        topik_atau_404(slug)
        d = request.get_json(silent=True) or {}
        p = label_ai.berkas(slug, "validasi.json")
        v = label_ai.baca_json(p, {}) or {}
        for x in v.get("item", []):
            if x["h"] == d.get("h"):
                if d.get("hapus"):
                    x.pop("manusia", None)
                else:
                    if d.get("s") not in label_ai.SENTIMEN:
                        return galat("sentimen tidak sah")
                    x["manusia"] = {"s": d["s"], "relevan": d.get("relevan", True) is not False,
                                    "t": time.strftime("%Y-%m-%d %H:%M")}
                    if d.get("e") in label_ai.EMOSI8:
                        x["manusia"]["e"] = d["e"]
                    if d.get("relevan") is False:
                        label_ai.tandai_tidak_relevan(slug, x["id"], x["teks"], "manual")
                    elif d.get("relevan_sebelumnya") is False:
                        label_ai.tandai_tidak_relevan(slug, x["id"], x["teks"], "batal")
                label_ai.tulis_json(p, v)
                return jsonify({"ok": True, "metrik": metrik_validasi(v["item"])})
        return galat("konten tidak ada di sampel", 404)

    # ------------------------------------------------------------- label AI semua konten
    @app.route("/api/<slug>/kelola/label-ai")
    def api_label_ai(slug):
        topik_atau_404(slug)
        df = sumber.semua_mentah(slug)
        sos = df[(df.platform != "Berita") & df.sentimen.isin(["negatif", "netral", "positif"])]
        sos = sos[sos.teks.str.strip().str.len() > 0]                 # teks kosong tidak dilabeli
        sudah = label_ai.muat_label(slug)
        h = sos.teks.map(label_ai.sidik)
        belum = sos[~h.isin(sudah)].drop_duplicates("teks")
        tok_masuk = int(belum.teks.str.len().clip(upper=600).sum() / 3.2) + len(belum) * 12 + (len(belum) // 25 + 1) * 650
        tok_keluar = len(belum) * 22
        return jsonify({"konten": int(len(sos)), "sudah": int(h.isin(sudah).sum()), "belum": int(len(belum)),
                        "perkiraan": ai_klien.perkiraan_biaya(tok_masuk, tok_keluar),
                        "jam_sibuk": ai_klien.jam_sibuk(), "setelan": label_ai.setelan(slug),
                        "aktif": [_ringkas_pekerjaan(p) for p in _aktif("ai:label") if p.get("topik") == slug]})

    @app.route("/api/<slug>/kelola/label-ai", methods=["POST"])
    def api_label_ai_mulai(slug):
        T = topik_atau_404(slug)
        if not ai_klien.tersedia():
            return galat("API key AI belum diatur")
        d = request.get_json(silent=True) or {}
        batas = max(0.05, min(50.0, float(d.get("batas_usd") or ai_klien.setelan()["batas_usd_per_tugas"])))
        langkah = [{"skrip": "scripts/ai_jalan.py", "args": ["label", "--batas-usd", f"{batas:.2f}"]}]
        pk = buat_pekerjaan("ai", "ai:label", f"Label AI · {T.NAMA}", slug, langkah, {"batas_usd": batas})
        return jsonify(_ringkas_pekerjaan(pk))

    # ------------------------------------------------------------- klaster
    @app.route("/api/<slug>/kelola/klaster")
    def api_klaster(slug):
        topik_atau_404(slug)
        import ai_jalan
        folder = sumber.topik.folder(slug)
        if not os.path.exists(os.path.join(folder, "sna.json")):
            return jsonify({"klaster": [], "pesan": "Graf SNA belum dibangun"})
        kurasi = label_ai.baca_json(os.path.join(folder, "sna_narasi.json"), {}) or {}
        draf = label_ai.baca_json(label_ai.berkas(slug, "klaster.json"), {}) or {}
        out = []
        for k in ai_jalan.data_klaster(folder):
            k["contoh"] = k["contoh"][:8]
            k["tersimpan"] = kurasi.get(k["kunci"])
            k["draf"] = draf.get(k["kunci"])
            out.append(k)
        mt_sna = os.path.getmtime(os.path.join(folder, "sna.json"))
        mt_kur = os.path.getmtime(os.path.join(folder, "sna_narasi.json")) if kurasi else 0
        return jsonify({"klaster": out, "perlu_terapkan": mt_kur > mt_sna,
                        "aktif": [_ringkas_pekerjaan(p) for p in _aktif("ai:klaster") + _aktif("panen:sna")
                                  if p.get("topik") == slug]})

    @app.route("/api/<slug>/kelola/klaster/draf", methods=["POST"])
    def api_klaster_draf(slug):
        T = topik_atau_404(slug)
        if not ai_klien.tersedia():
            return galat("API key AI belum diatur")
        k = (request.get_json(silent=True) or {}).get("k")
        args = ["klaster"] + (["--k", str(int(k))] if k else [])
        pk = buat_pekerjaan("ai", "ai:klaster", f"Draf klaster{f' K{k}' if k else ''} · {T.NAMA}", slug,
                            [{"skrip": "scripts/ai_jalan.py", "args": args}])
        return jsonify(_ringkas_pekerjaan(pk))

    @app.route("/api/<slug>/kelola/klaster/simpan", methods=["POST"])
    def api_klaster_simpan(slug):
        topik_atau_404(slug)
        d = request.get_json(silent=True) or {}
        kunci = str(d.get("kunci") or "")
        if not re.fullmatch(r"(x|yt|ig|th):.{1,120}", kunci):
            return galat("kunci klaster tidak sah")
        p = os.path.join(sumber.topik.folder(slug), "sna_narasi.json")
        kurasi = label_ai.baca_json(p, {}) or {}
        if d.get("hapus"):
            kurasi.pop(kunci, None)
        else:
            nama = " ".join(str(d.get("nama", "")).split())[:120]
            butir = [" ".join(str(b).split())[:400] for b in d.get("butir") or [] if str(b).strip()][:8]
            if not nama:
                return galat("nama klaster kosong")
            kurasi[kunci] = {"nama": nama, "kurasi": date.today().isoformat(), "butir": butir,
                             "sumber": d.get("sumber", "manual")}
        label_ai.tulis_json(p, kurasi)
        return jsonify({"ok": True})

    @app.route("/api/<slug>/kelola/klaster/terapkan", methods=["POST"])
    def api_klaster_terapkan(slug):
        T = topik_atau_404(slug)
        pk = buat_pekerjaan("panen", "panen:sna", f"Graf SNA · {T.NAMA}", slug, [{"skrip": "scripts/12_sna.py"}],
                            {"pipa": "sna"})
        return jsonify(_ringkas_pekerjaan(pk))

    # ------------------------------------------------------------- kesimpulan
    def _periode_args(slug, d):
        import laporan
        try:
            return laporan.periode(slug, d.get("dari") or None, d.get("sampai") or None)
        except ValueError as e:
            r = jsonify({"galat": str(e)})
            r.status_code = 400
            abort(r)

    @app.route("/api/<slug>/kelola/kesimpulan")
    def api_kesimpulan(slug):
        T = topik_atau_404(slug)
        import laporan
        d1, d2, penuh = _periode_args(slug, request.args)
        isi = label_ai.baca_json(label_ai.berkas_kesimpulan(slug, d1, d2, penuh), {}) or {}
        analis = ({"kesimpulan": getattr(T, "KESIMPULAN", []), "rekomendasi": getattr(T, "REKOMENDASI", []),
                   "tanggal": getattr(T, "KESIMPULAN_TANGGAL", "")} if penuh and getattr(T, "KESIMPULAN", None) else None)
        return jsonify({"dari": d1, "sampai": d2, "penuh": penuh, "periode": laporan.rentang(d1, d2),
                        "draf": isi.get("draf"), "disetujui": isi.get("disetujui"), "file_topik": analis,
                        "aktif": [_ringkas_pekerjaan(p) for p in _aktif("ai:kesimpulan") if p.get("topik") == slug]})

    @app.route("/api/<slug>/kelola/kesimpulan/draf", methods=["POST"])
    def api_kesimpulan_draf(slug):
        T = topik_atau_404(slug)
        if not ai_klien.tersedia():
            return galat("API key AI belum diatur")
        d1, d2, _ = _periode_args(slug, request.get_json(silent=True) or {})
        pk = buat_pekerjaan("ai", "ai:kesimpulan", f"Draf kesimpulan {d1}–{d2} · {T.NAMA}", slug,
                            [{"skrip": "scripts/ai_jalan.py", "args": ["kesimpulan", "--dari", d1, "--sampai", d2]}],
                            {"dari": d1, "sampai": d2})
        return jsonify(_ringkas_pekerjaan(pk))

    @app.route("/api/<slug>/kelola/kesimpulan/simpan", methods=["POST"])
    def api_kesimpulan_simpan(slug):
        topik_atau_404(slug)
        d = request.get_json(silent=True) or {}
        d1, d2, penuh = _periode_args(slug, d)
        p = label_ai.berkas_kesimpulan(slug, d1, d2, penuh)
        isi = label_ai.baca_json(p, {}) or {"dari": d1, "sampai": d2}
        if d.get("hapus"):
            isi.pop("disetujui", None)
        else:
            ks = [{"judul": " ".join(str(k.get("judul", "")).split())[:120], "isi": str(k.get("isi", "")).strip()[:1500]}
                  for k in d.get("kesimpulan") or [] if str(k.get("judul", "")).strip() and str(k.get("isi", "")).strip()]
            rk = [str(r).strip()[:800] for r in d.get("rekomendasi") or [] if str(r).strip()]
            if not ks:
                return galat("kesimpulan kosong")
            isi["disetujui"] = {"kesimpulan": ks[:10], "rekomendasi": rk[:8], "tanggal": date.today().isoformat()}
        label_ai.tulis_json(p, isi)
        return jsonify({"ok": True})

    # ------------------------------------------------------------- pengaturan AI
    @app.route("/api/kelola/ai", methods=["GET", "POST"])
    def api_ai():
        if request.method == "POST":
            d = request.get_json(silent=True) or {}
            ubah = {}
            if d.get("api_key"):
                if not re.fullmatch(r"[\w\-.]{16,200}", d["api_key"].strip()):
                    return galat("format API key tidak dikenal")
                ubah["api_key"] = d["api_key"].strip()
            for k in ("model", "model_nalar", "base_url"):
                if d.get(k):
                    ubah[k] = str(d[k]).strip()
            if d.get("paralel"):
                ubah["paralel"] = max(1, min(16, int(d["paralel"])))
            if d.get("batas_usd_per_tugas"):
                ubah["batas_usd_per_tugas"] = max(0.05, min(50.0, float(d["batas_usd_per_tugas"])))
            ai_klien.simpan_setelan(ubah)
        s = ai_klien.setelan()
        return jsonify({"tersedia": bool(s["api_key"]), "key": ai_klien.samarkan(s["api_key"]),
                        "penyedia": s.get("penyedia"), "base_url": s["base_url"], "model": s["model"],
                        "model_nalar": s["model_nalar"], "paralel": s.get("paralel"),
                        "batas_usd_per_tugas": s.get("batas_usd_per_tugas"), "saldo": ai_klien.saldo(),
                        "pemakaian": ai_klien.ringkas_pemakaian(30), "harga": ai_klien.HARGA,
                        "jam_sibuk": ai_klien.jam_sibuk(), "lokasi_konfig": ai_klien.CONFIG_PATH.replace(os.path.expanduser("~"), "~")})

    # ------------------------------------------------------------- topik baru & konfigurasi topik JSON
    @app.route("/api/kelola/topik/draf", methods=["POST"])
    def api_topik_draf():
        if not ai_klien.tersedia():
            return galat("API key AI belum diatur")
        b = request.get_json(silent=True) or {}
        brief = {k: " ".join(str(b.get(k, "")).split())[:3000] for k in
                 ("nama", "deskripsi", "wilayah", "pihak", "dari", "sampai", "catatan")}
        if not brief["nama"] or not brief["deskripsi"]:
            return galat("isi nama dan deskripsi topik")
        os.makedirs(DRAF_TOPIK, exist_ok=True)
        id_ = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
        pb = os.path.join(DRAF_TOPIK, f"{id_}-brief.json")
        label_ai.tulis_json(pb, brief)
        pk = buat_pekerjaan("ai", "ai:topik", f"Draf topik · {brief['nama']}", None,
                            [{"skrip": "scripts/ai_jalan.py",
                              "args": ["topik", "--brief", pb, "--keluar", os.path.join(DRAF_TOPIK, f"{id_}.json")]}],
                            {"draf": id_})
        return jsonify({"draf": id_, "pekerjaan": _ringkas_pekerjaan(pk)})

    @app.route("/api/kelola/topik/draf/<id_>")
    def api_topik_draf_ambil(id_):
        if not re.fullmatch(r"[\w-]{6,40}", id_):
            abort(404)
        d = label_ai.baca_json(os.path.join(DRAF_TOPIK, f"{id_}.json"))
        pk = next((p for p in antrean.semua() if p.get("meta", {}).get("draf") == id_), None)
        return jsonify({"siap": bool(d), "isi": d, "pekerjaan": _ringkas_pekerjaan(pk) if pk else None})

    @app.route("/api/kelola/topik", methods=["POST"])
    def api_topik_buat():
        cfg = request.get_json(silent=True) or {}
        cfg = _rapikan_konfig(cfg)
        masalah = _umum.periksa(cfg)
        baru = cfg["slug"] not in sumber.topik.DAFTAR
        if not baru and cfg["slug"] in sumber.topik.BUATAN_TANGAN:
            masalah.append("slug ini dipakai topik buatan tangan")
        if not baru and not request.args.get("ubah"):
            masalah.append("slug sudah dipakai topik lain")
        if masalah:
            return jsonify({"galat": "; ".join(masalah)}), 400
        lama = label_ai.baca_json(os.path.join(_umum.FOLDER, f"{cfg['slug']}.json"), {}) or {}
        cfg["dibuat"] = lama.get("dibuat") or datetime.now().isoformat(timespec="seconds")
        cfg["diubah"] = datetime.now().isoformat(timespec="seconds")
        _umum.simpan(cfg)
        sumber.topik.daftarkan_ulang()
        os.makedirs(sumber.topik.folder(cfg["slug"]), exist_ok=True)
        sumber.konteks.cache_clear()
        return jsonify({"ok": True, "slug": cfg["slug"]})

    @app.route("/api/kelola/topik/uji", methods=["POST"])
    def api_topik_uji():
        """Uji aturan relevansi dan isu terhadap contoh teks, sebelum topik disimpan."""
        d = request.get_json(silent=True) or {}
        cfg = _rapikan_konfig(d.get("konfig") or {})
        cfg.update(slug=cfg["slug"] or "uji", nama=cfg["nama"] or "uji", dari=cfg["dari"] or date.today().isoformat())
        try:
            m = _umum.modul(cfg)
        except Exception as e:
            return galat(f"konfigurasi belum bisa diuji: {e}")
        teks = [t.strip() for t in str(d.get("teks", "")).split("\n") if t.strip()][:200]
        return jsonify({"hasil": [{"teks": t[:300], "relevan": bool(m.relevan(t)),
                                   "isu": [n for n, p in m.NARASI.items() if re.search(p, t, re.I)],
                                   "aktor": [n for n, p in m.AKTOR.items() if re.search(p, t, re.I)]} for t in teks]})

    @app.route("/api/<slug>/kelola/hapus-topik", methods=["POST"])
    def api_hapus_topik(slug):
        """Hapus topik buatan web dari daftar. Konfigurasinya dipindah ke data/_bersama/topik_terhapus/ dan
        folder data/<slug>/ dibiarkan (hapus manual bila memang tidak dipakai)."""
        topik_atau_404(slug)
        if slug in sumber.topik.BUATAN_TANGAN:
            return galat("topik buatan tangan tidak bisa dihapus dari web")
        if any(p.get("topik") == slug and p["status"] in ("antre", "jalan") for p in antrean.semua()):
            return galat("masih ada pekerjaan topik ini di antrean")
        tujuan = os.path.join(ROOT, "data", "_bersama", "topik_terhapus")
        os.makedirs(tujuan, exist_ok=True)
        os.replace(os.path.join(_umum.FOLDER, f"{slug}.json"),
                   os.path.join(tujuan, f"{slug}-{datetime.now():%Y%m%d-%H%M%S}.json"))
        sumber.topik.daftarkan_ulang()
        return jsonify({"ok": True, "berikut": sumber.topik.DAFTAR[0]})

    @app.route("/api/<slug>/kelola/konfigurasi")
    def api_konfigurasi(slug):
        topik_atau_404(slug)
        if slug in sumber.topik.BUATAN_TANGAN:
            return jsonify({"buatan_tangan": True})
        return jsonify({"buatan_tangan": False, "konfig": sumber.topik.muat(slug).KONFIG})


def _rapikan_konfig(c):
    daftar = lambda v: [" ".join(str(x).split()) for x in (v if isinstance(v, list) else str(v or "").split("\n"))
                        if str(x).strip()][:200]
    out = {"slug": str(c.get("slug", "")).strip().lower(), "nama": " ".join(str(c.get("nama", "")).split())[:80],
           "judul": " ".join(str(c.get("judul", "")).split())[:140],
           "judul_laporan": " ".join(str(c.get("judul_laporan", "")).split())[:140],
           "lede": " ".join(str(c.get("lede", "")).split())[:1500],
           "dari": str(c.get("dari", "")).strip(), "sampai": (str(c.get("sampai") or "").strip() or None)}
    for k in ("kueri_berita", "kueri_yt", "kueri_x", "tagar_ig", "kueri_ig", "kueri_threads", "situs_lokal",
              "wajib", "kecuali", "stop"):
        out[k] = daftar(c.get(k))
    out["pasangan"] = [{"jika": daftar(p.get("jika")), "dan": daftar(p.get("dan"))} for p in c.get("pasangan") or []
                       if isinstance(p, dict)][:30]
    out["narasi"] = {" ".join(str(n).split())[:60]: daftar(v) for n, v in (c.get("narasi") or {}).items() if str(n).strip()}
    out["aktor"] = {" ".join(str(n).split())[:60]: daftar(v) for n, v in (c.get("aktor") or {}).items() if str(n).strip()}
    f = c.get("fokus") or {}
    out["fokus"] = ({"nama": " ".join(str(f.get("nama", "")).split())[:60], "ket": " ".join(str(f.get("ket", "")).split())[:300],
                     "narasi": daftar(f.get("narasi"))} if f.get("narasi") else None)
    a = c.get("aturan") or {}
    out["aturan"] = {k: daftar(a.get(k)) for k in ("pihak", "didukung", "abaikan", "samarkan")}
    out["preset"] = [{"label": " ".join(str(p.get("label", "")).split())[:60], "dari": str(p.get("dari", "")),
                      "sampai": str(p.get("sampai", ""))} for p in c.get("preset") or []
                     if isinstance(p, dict) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(p.get("dari", "")))
                     and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(p.get("sampai", "")))][:12]
    out["sumber"] = "wizard"
    return out
