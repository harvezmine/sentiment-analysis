"""Penyusunan konfigurasi topik baru dengan riset, uji otomatis, dan perbaikan (wizard Topik baru).

Model bahasa tidak tahu peristiwa yang terjadi setelah batas pengetahuannya, jadi draf yang hanya
berdasar gambaran singkat sering salah nama, tempat, dan istilah. Alurnya:

  1. riset    AI membuat kueri awal dari gambaran topik; judul berita (Google News RSS, sesuai periode)
              dan judul video YouTube diambil tanpa login
  2. draf     AI menyusun konfigurasi berdasarkan gambaran DAN judul-judul nyata tadi
  3. uji      AI menilai relevansi tiap judul riset; hasilnya dibandingkan dengan aturan relevansi draf
              (presisi, recall, judul yang terlewat dan salah tangkap) dan cakupan isu
  4. perbaiki AI memperbaiki istilah wajib, pasangan, pengecualian, dan kata kunci isu dari contoh yang
              salah; diuji ulang, versi yang lebih baik dipakai

Semua langkah mencetak progres; biaya tipikal 0,10–0,20 USD per topik (separuhnya di luar jam sibuk),
hampir seluruhnya dari mode berpikir pada draf dan perbaikan.
"""
import json
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

import ai_klien
import ai_tugas
from topik import _umum

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


# --------------------------------------------------------------- 1. riset
def kueri_riset(brief):
    d = ai_klien.obrolan([
        {"role": "system", "content": "Kamu menyiapkan pencarian awal untuk memahami sebuah topik berita di Indonesia. "
                                      "Jawab hanya JSON."},
        {"role": "user", "content": "Topik:\n" + json.dumps(brief, ensure_ascii=False) +
         '\n\nBuat kueri pencarian singkat (bahasa Indonesia) untuk menemukan berita dan video tentang topik ini. '
         'Dua kueri berita pertama harus luas: hanya nama utama topik (nama proyek, kapal, perusahaan beserta lokasinya), '
         '1–3 kata, supaya hasil tidak sempit. Sisanya 2–4 kata, masing-masing satu isu atau pihak dari gambaran; jangan '
         'menggabungkan beberapa isu dalam satu kueri. Tambahkan juga 2–4 nama tempat atau istilah dari topik ini yang '
         'mungkin punya arti lain (nama tempat wisata, kata sifat, nama umum), masing-masing satu kata atau nama saja, '
         'supaya konten lain yang memakai nama sama ikut terlihat. '
         'JSON: {"berita": [6–8 kueri], "youtube": [3–4 kueri], "ambigu": [2–4 nama]}'}],
        tugas="topik")
    return ([str(q) for q in d.get("berita", [])][:8], [str(q) for q in d.get("youtube", [])][:4],
            [str(q) for q in d.get("ambigu", [])][:4])


def ambil_berita(kueri, dari=None, sampai=None, maks=100):
    q = kueri
    if dari:
        q += f" after:{(date.fromisoformat(dari) - timedelta(days=1)).isoformat()}"
    if sampai:
        q += f" before:{(date.fromisoformat(sampai) + timedelta(days=1)).isoformat()}"
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q) + "&hl=id&gl=ID&ceid=ID:id"
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        soup = BeautifulSoup(r.content, "xml")
    except Exception:
        return []
    out = []
    for it in soup.find_all("item")[:maks]:
        judul = (it.title.text if it.title else "").strip()
        src = it.find("source")
        media = src.text.strip() if src else ""
        if media and judul.endswith(" - " + media):
            judul = judul[: -len(media) - 3]
        out.append({"sumber": "Berita", "judul": judul, "media": media,
                    "tanggal": (it.pubDate.text if it.pubDate else "")[:16]})
    return out


def ambil_youtube(kueri, maks=20):
    # params=None = urutan relevansi; bawaan klien ("CAIS…") hanya urut tanggal unggah dan sering kosong
    try:
        import yt_client as yt
        j = yt.YTClient().cari(kueri, params=None)
        vids = yt.parse_hasil_cari(j)
    except Exception as e:
        print(f"[riset] YouTube gagal untuk {kueri!r}: {e}", flush=True)
        return []
    return [{"sumber": "YouTube", "judul": v.get("judul", ""), "media": v.get("kanal", ""),
             "deskripsi": (v.get("deskripsi") or "")[:200]} for v in vids[:maks]]


def jendela(dari, sampai, maks=6):
    """Periode panjang dipecah per jendela (maks 6) karena RSS Google News hanya memberi ±100 hasil per kueri."""
    if not dari:
        return [(None, sampai)]
    a = date.fromisoformat(dari)
    z = date.fromisoformat(sampai) if sampai else date.today()
    hari = (z - a).days
    if hari <= 45:
        return [(dari, sampai)]
    n = min(maks, hari // 30 + 1)
    langkah = hari / n
    batas = [a + timedelta(days=round(i * langkah)) for i in range(n)] + [z]
    return [(batas[i].isoformat(), (batas[i + 1] - timedelta(days=1 if i + 1 < n else 0)).isoformat()) for i in range(n)]


def riset(brief, log=print):
    kb, ky, ka = kueri_riset(brief)
    log(f"[riset] kueri berita: {kb} · YouTube: {ky} · nama ambigu: {ka}")
    dari, sampai = brief.get("dari"), brief.get("sampai") or None
    # dua kueri luas dicari per jendela waktu, kueri isu cukup sekali untuk seluruh periode
    tugas = [(q, d, s) for q in kb[:2] for d, s in jendela(dari, sampai)] + [(q, dari, sampai) for q in kb[2:]]
    hasil = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for xs in ex.map(lambda t: ambil_berita(*t), tugas):
            hasil += xs
        for xs in ex.map(ambil_youtube, ky):
            hasil += xs
        # nama ambigu tanpa konteks dan tanpa batas tanggal: memunculkan konten lain dengan nama sama
        # (mis. "Ubadari" juga air terjun wisata) supaya uji bisa menghitung salah tangkapnya
        for xs in ex.map(lambda q: ambil_youtube(q, maks=15), ka):
            hasil += xs
        for xs in ex.map(lambda q: ambil_berita(q, maks=25), ka):
            hasil += xs
    lihat, out = set(), []
    for x in hasil:
        k = re.sub(r"\W+", " ", x["judul"].lower()).strip()
        if k and k not in lihat:
            lihat.add(k)
            out.append(x)
    log(f"[riset] {len(out)} judul unik ({sum(1 for x in out if x['sumber'] == 'Berita')} berita, "
        f"{sum(1 for x in out if x['sumber'] == 'YouTube')} YouTube)")
    return out


# --------------------------------------------------------------- 3. uji
def cocok_kueri(kueri, teks_rendah):
    """Perkiraan apakah teks (huruf kecil) bisa ditemukan kueri: semua frasa bertanda petik dan semua kata ada."""
    q = kueri.lower()
    frasa = re.findall(r'"([^"]+)"', q)
    sisa = re.sub(r'"[^"]+"|\b(after|before|site):\S+', " ", q)
    kata = [w for w in re.findall(r"[\w#]+", sisa) if len(w) > 1]
    return all(f in teks_rendah for f in frasa) and all(re.search(rf"(?<!\w){re.escape(w.lstrip('#'))}", teks_rendah) for w in kata)


def nilai_relevansi(item, brief):
    """AI menilai apakah tiap judul membahas topik ini: {indeks: 1/0}."""
    sistem = ("Kamu menilai relevansi judul berita dan video terhadap satu topik pemantauan. Relevan = judul itu "
              "membahas peristiwa, pihak, atau isu topik ini secara langsung. Tidak relevan = membahas hal lain yang "
              "kebetulan memakai kata yang sama (tempat, perusahaan, atau peristiwa lain). Jawab hanya JSON: "
              '{"hasil": [{"id": 1, "r": true}]}')
    topik = json.dumps({k: brief.get(k) for k in ("nama", "deskripsi", "wilayah", "pihak", "dari", "sampai")},
                       ensure_ascii=False)
    paket = [list(range(i, min(i + 40, len(item)))) for i in range(0, len(item), 40)]

    def kirim(idx):
        baris = "\n".join(f"[{k + 1}] ({item[i]['sumber']}) {item[i]['judul']}" for k, i in enumerate(idx))
        d = ai_klien.obrolan([{"role": "system", "content": sistem},
                              {"role": "user", "content": f"Topik:\n{topik}\n\nJudul:\n{baris}"}], tugas="topik")
        out = {}
        for e in d.get("hasil", []):
            try:
                out[idx[int(e["id"]) - 1]] = 0 if e.get("r") is False else 1
            except (KeyError, ValueError, IndexError, TypeError):
                continue
        return out

    hasil, _ = ai_klien.paralel(kirim, paket, n=4)
    nilai = {}
    for h in hasil:
        nilai.update(h or {})
    return nilai


def uji(cfg, item, nilai):
    """Bandingkan aturan relevansi draf dengan penilaian AI atas judul riset; cakupan isu pada judul relevan."""
    m = _umum.modul({**cfg, "slug": cfg.get("slug") or "uji", "nama": cfg.get("nama") or "uji",
                     "dari": cfg.get("dari") or date.today().isoformat()})
    tp = fp = fn = tn = 0
    terlewat, salah, tanpa_isu, tak_terjangkau = [], [], [], []
    nar = [re.compile(p, re.I) for p in m.NARASI.values()]
    kueri = (cfg.get("kueri_berita") or []) + (cfg.get("kueri_yt") or [])
    for i, x in enumerate(item):
        if i not in nilai:
            continue
        teks = f"{x['judul']} {x.get('deskripsi', '')}"
        aturan, ai = m.relevan(teks), nilai[i]
        if aturan and ai:
            tp += 1
        elif aturan and not ai:
            fp += 1
            salah.append(x["judul"])
        elif ai and not aturan:
            fn += 1
            terlewat.append(x["judul"])
        else:
            tn += 1
        if ai and not any(r.search(teks) for r in nar):
            tanpa_isu.append(x["judul"])
        if ai and not any(cocok_kueri(q, teks.lower()) for q in kueri):
            tak_terjangkau.append(x["judul"])
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    relevan_ai = tp + fn
    umum = isu_terlalu_umum(cfg, [f"{x['judul']} {x.get('deskripsi', '')}" for i, x in enumerate(item) if nilai.get(i)])
    return {"presisi": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0, "dinilai": tp + fp + fn + tn,
            "relevan_ai": relevan_ai, "cakupan_isu": 1 - len(tanpa_isu) / relevan_ai if relevan_ai else 0,
            # jangkauan = judul relevan yang memuat semua kata salah satu kueri (perkiraan bawah: mesin pencari
            # juga membaca isi artikel)
            "jangkauan": 1 - len(tak_terjangkau) / relevan_ai if relevan_ai else 0,
            "terlewat": terlewat[:25], "salah_tangkap": salah[:25], "tanpa_isu": tanpa_isu[:25],
            "tak_terjangkau": tak_terjangkau[:25],
            "n_terlewat": fn, "n_salah_tangkap": fp, "n_tanpa_isu": len(tanpa_isu), "n_tak_terjangkau": len(tak_terjangkau),
            "isu_terlalu_umum": umum}


def isu_terlalu_umum(cfg, teks, batas=0.45):
    """Isu yang menandai hampir semua konten relevan biasanya memuat kata terlalu umum (nama tempat, "nelayan",
    "warga"): cakupan isu naik tetapi pembagian isu jadi tidak bermakna. Kembalikan isu dengan porsi > batas
    beserta kata yang paling sering cocok."""
    if not teks:
        return []
    out = []
    for nama, kata in (cfg.get("narasi") or {}).items():
        rx = _umum.pola(kata, minimal=3)
        if not rx:
            continue
        porsi = sum(1 for t in teks if re.search(rx, t, re.I)) / len(teks)
        if porsi <= batas:
            continue
        hitung = []
        for k in kata:
            rk = _umum.pola([k], minimal=3)
            if rk:
                hitung.append((sum(1 for t in teks if re.search(rk, t, re.I)) / len(teks), k))
        out.append({"isu": nama, "porsi": round(porsi, 3), "kata": [k for _, k in sorted(hitung, reverse=True)[:4]]})
    return out


# --------------------------------------------------------------- 4. perbaiki
def perbaiki(cfg, hasil, brief):
    """AI memperbaiki aturan relevansi dan kata kunci isu dari contoh yang salah; mengembalikan cfg baru."""
    bagian = {k: cfg.get(k) for k in ("wajib", "pasangan", "kecuali", "narasi", "kueri_berita")}
    sistem = ("Kamu memperbaiki aturan relevansi berbasis kata kunci untuk pemantauan percakapan publik. Aturan: konten "
              "relevan bila memuat salah satu istilah 'wajib', atau memuat istilah 'jika' dan istilah 'dan' dari satu "
              "'pasangan' tanpa frasa 'kecuali'. Istilah dicocokkan sebagai kata utuh tanpa membedakan huruf besar. "
              "Perbaiki supaya judul yang terlewat ikut terjaring dan judul yang salah tangkap tidak, tanpa membuat "
              "aturan terlalu luas. Tambahkan kata kunci isu yang pendek (1–2 kata) supaya judul tanpa isu ikut "
              "tertandai, tetapi jangan memakai kata yang umum di seluruh topik (nama tempat, nama perusahaan, "
              "'warga', 'nelayan', 'adat', 'migas') sebagai kata isu sendirian, dan ganti kata seperti itu pada isu "
              "yang dilaporkan terlalu umum dengan frasa yang lebih khas. Paling banyak 15 kata per isu. Bila banyak judul relevan tidak memuat semua kata dari kueri mana pun, tambahkan kueri berita "
              "pendek (nama utama saja, atau 2–3 kata tanpa tanda petik) di 'kueri_tambahan', paling banyak 8. "
              "Pertahankan istilah lama yang masih benar. Jawab hanya JSON dengan kunci wajib, pasangan, kecuali, "
              "narasi (bentuk sama dengan masukan), dan kueri_tambahan (daftar, boleh kosong).")
    pengguna = (f"Topik: {json.dumps(brief, ensure_ascii=False)}\n\nAturan sekarang:\n{json.dumps(bagian, ensure_ascii=False)}\n\n"
                f"Judul relevan yang TERLEWAT:\n" + "\n".join(f"- {t}" for t in hasil["terlewat"]) +
                f"\n\nJudul tidak relevan yang SALAH TANGKAP:\n" + "\n".join(f"- {t}" for t in hasil["salah_tangkap"]) +
                f"\n\nJudul relevan yang belum tertandai isu apa pun:\n" + "\n".join(f"- {t}" for t in hasil["tanpa_isu"]) +
                f"\n\nJudul relevan yang tidak terjangkau kueri berita mana pun:\n" +
                "\n".join(f"- {t}" for t in hasil.get("tak_terjangkau", [])) +
                f"\n\nIsu yang terlalu umum (menandai sebagian besar judul relevan) dan kata pemicunya:\n" +
                "\n".join(f"- {u['isu']} ({u['porsi']:.0%}): {', '.join(u['kata'])}" for u in hasil.get("isu_terlalu_umum", [])))
    d = ai_klien.obrolan([{"role": "system", "content": sistem}, {"role": "user", "content": pengguna}],
                         tugas="topik", berpikir="high", maks_token=32000)
    baru = dict(cfg)
    for k in ("wajib", "pasangan", "kecuali", "narasi"):
        if d.get(k):
            baru[k] = d[k]
    lama = cfg.get("kueri_berita") or []
    tambah = [str(q).strip() for q in (d.get("kueri_tambahan") or []) if str(q).strip()][:8]
    baru["kueri_berita"] = lama + [q for q in tambah if q.lower() not in {x.lower() for x in lama}]
    return baru


# --------------------------------------------------------------- alur lengkap
ANGKA = re.compile(r"^(rp\s?)?\d[\d.,]*\s?(%|persen|ribu|rb|juta|miliar|triliun)?$", re.I)


def rapikan_narasi(cfg, brief=None, maks=20):
    """Buang kata isu yang sebenarnya nama topik (istilah wajib, istilah ambigu di pasangan, stop, nama aktor,
    wilayah) atau angka: kata seperti itu menandai hampir semua konten sehingga pembagian isu tidak bermakna."""
    larang = set()
    for k in (cfg.get("wajib") or []) + (cfg.get("stop") or []):
        larang.add(str(k).lower().strip('"# '))
    for p in cfg.get("pasangan") or []:
        larang.update(str(k).lower().strip('"# ') for k in p.get("jika") or [])
    for nama, var in (cfg.get("aktor") or {}).items():
        larang.update(str(k).lower() for k in [nama, *var])
    if brief:
        larang.update(w.strip().lower() for w in re.split(r"[,;/]", brief.get("wilayah") or "") if w.strip())
    baru = {}
    for isu, kata in (cfg.get("narasi") or {}).items():
        lihat, bersih = set(), []
        for k in kata if isinstance(kata, list) else [kata]:
            k = " ".join(str(k).lower().split())
            if len(k) < 3 or k in larang or k in lihat or ANGKA.match(k):
                continue
            lihat.add(k)
            bersih.append(k)
        if bersih:
            baru[isu] = bersih[:maks]
    return {**cfg, "narasi": baru}


def skor(h):
    """Pembanding antarversi: relevansi paling penting, lalu cakupan isu dan jangkauan kueri."""
    lebih = sum(u["porsi"] - 0.45 for u in h.get("isu_terlalu_umum", []))
    return h["f1"] + 0.5 * h["cakupan_isu"] + 0.25 * h.get("jangkauan", 0) - 0.5 * lebih


def susun(brief, log=print, putaran=1):
    """Riset → draf → uji → perbaiki (berulang `putaran` kali). Mengembalikan
    {"draf", "riset": [...], "uji": {"awal", "akhir"}, "kueri_riset"}."""
    t0 = time.time()
    item = riset(brief, log)
    log("##PROGRES 1/5")
    # contoh untuk draf: sebagian besar judul awal, ditambah judul terakhir (hasil nama ambigu) agar 'kecuali' terisi
    pilih = item if len(item) <= 160 else item[:130] + item[-30:]
    contoh = [f"({x['sumber']}) {x['judul']}" for x in pilih]
    draf = ai_tugas.draf_topik(brief, contoh_judul=contoh)
    log("[draf] konfigurasi awal tersusun")
    log("##PROGRES 2/5")
    nilai = nilai_relevansi(item, brief)
    cfg = rapikan_narasi({**draf, "dari": brief.get("dari"), "sampai": brief.get("sampai") or None,
                          "nama": brief.get("nama")}, brief)
    awal = uji(cfg, item, nilai)
    log(f"[uji] awal: presisi {awal['presisi']:.0%}, recall {awal['recall']:.0%}, cakupan isu {awal['cakupan_isu']:.0%}, "
        f"jangkauan kueri {awal['jangkauan']:.0%} "
        f"({awal['relevan_ai']} dari {awal['dinilai']} judul dinilai relevan)")
    log("##PROGRES 3/5")
    terbaik, hasil_terbaik = cfg, awal
    for i in range(putaran):
        if (hasil_terbaik["f1"] >= 0.97 and hasil_terbaik["cakupan_isu"] >= 0.9 and hasil_terbaik["jangkauan"] >= 0.8
                and not hasil_terbaik["isu_terlalu_umum"]):
            break
        try:
            calon = rapikan_narasi(perbaiki(terbaik, hasil_terbaik, brief), brief)
        except ai_klien.AIError as e:
            log(f"[perbaiki {i + 1}] gagal ({e}); memakai draf terbaik sejauh ini")
            break
        h = uji(calon, item, nilai)
        log(f"[perbaiki {i + 1}] presisi {h['presisi']:.0%}, recall {h['recall']:.0%}, cakupan isu {h['cakupan_isu']:.0%}, "
            f"jangkauan kueri {h['jangkauan']:.0%}")
        if skor(h) > skor(hasil_terbaik):
            terbaik, hasil_terbaik = calon, h
        log(f"##PROGRES {min(4, 3 + i + 1)}/5")
    log("##PROGRES 5/5")
    log(f"[topik] selesai dalam {time.time() - t0:.0f} dtk")
    draf_akhir = {k: v for k, v in terbaik.items() if k not in ("dari", "sampai", "nama")}
    return {"draf": draf_akhir, "riset": item[:200], "uji": {"awal": awal, "akhir": hasil_terbaik}}
