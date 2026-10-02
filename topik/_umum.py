"""Topik yang dibuat dari halaman Kelola (wizard topik baru).

Konfigurasinya disimpan sebagai data di topik/<slug>.json, bukan kode, lalu diubah di sini menjadi
modul topik dengan kontrak yang sama dengan topik buatan tangan (lihat topik/__init__.py). Semua daftar
kata dari JSON di-escape sebelum menjadi regex, jadi isi JSON tidak pernah dijalankan sebagai kode.

Bentuk JSON (semua daftar boleh kosong kecuali kueri_berita, narasi, dan wajib/pasangan):
  slug, nama, judul, judul_laporan, lede, dari, sampai (null = pemantauan berjalan sampai hari ini),
  kueri_berita, kueri_yt, kueri_x, tagar_ig, kueri_ig, kueri_threads, situs_lokal,
  wajib            istilah yang cukup sendiri untuk menyatakan relevan
  pasangan         [{"jika": [istilah ambigu], "dan": [konteks]}]: relevan bila keduanya muncul
  kecuali          frasa topik lain; konten yang hanya cocok lewat pasangan dan memuat frasa ini dibuang
  narasi           {nama isu: [kata/frasa]}
  aktor            {nama aktor: [variasi penyebutan]}
  fokus            {"nama", "ket", "narasi": [nama isu]} atau null
  aturan           {"pihak", "didukung", "abaikan", "samarkan"}: daftar kata untuk aturan sentimen
  stop             kata nama topik yang disembunyikan dari awan kata
  preset           [{"label", "dari", "sampai"}]
"""
import json
import os
import re
import types
from datetime import date

FOLDER = os.path.dirname(os.path.abspath(__file__))
SLUG_SAH = re.compile(r"^[a-z][a-z0-9_]{1,30}$")
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September",
         "Oktober", "November", "Desember"]


def _bersih(daftar):
    out = []
    for k in daftar or []:
        k = " ".join(str(k).split()).strip()
        if k and k.lower() not in (x.lower() for x in out):
            out.append(k)
    return out


def pola(kata, minimal=1):
    """Daftar istilah -> regex: cocok sebagai kata utuh, tanpa membedakan huruf besar. Istilah beberapa kata
    juga cocok tanpa spasi atau dengan garis bawah, jadi "blok masela" menangkap tagar #BlokMasela.
    minimal: panjang istilah terpendek yang dipakai (isu dan aktor: 3, agar singkatan seperti "ma" tidak
    menangkap kata lain)."""
    kata = [k.lower().lstrip("#") for k in _bersih(kata) if len(k.strip().lstrip("#")) >= minimal]
    if not kata:
        return None
    alt = "|".join(re.escape(k).replace(r"\ ", " ").replace(" ", r"[\s_]*") for k in sorted(kata, key=len, reverse=True))
    return rf"(?<!\w)(?:{alt})(?!\w)"


def _periode(a, z):
    ya, ma, _ = map(int, a.split("-"))
    yz, mz, _ = map(int, z.split("-"))
    if (ya, ma) == (yz, mz):
        return f"{BULAN[ma - 1]} {ya}"
    return f"{BULAN[ma - 1]}{'' if ya == yz else ' ' + str(ya)}–{BULAN[mz - 1]} {yz}"


def periksa(cfg):
    """Daftar masalah konfigurasi (kosong = sah)."""
    m = []
    if not SLUG_SAH.match(str(cfg.get("slug", ""))):
        m.append("slug harus huruf kecil, angka, atau garis bawah, 2–31 karakter, diawali huruf")
    if not str(cfg.get("nama", "")).strip():
        m.append("nama topik kosong")
    for k in ("dari",) + (("sampai",) if cfg.get("sampai") else ()):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(cfg.get(k) or "")):
            m.append(f"tanggal {k} harus YYYY-MM-DD")
    if cfg.get("sampai") and str(cfg.get("sampai")) < str(cfg.get("dari")):
        m.append("tanggal akhir sebelum tanggal awal")
    if not _bersih(cfg.get("kueri_berita")) and not _bersih(cfg.get("kueri_yt")):
        m.append("isi minimal kueri berita atau kueri YouTube")
    if not _bersih(cfg.get("wajib")) and not any(_bersih(p.get("jika")) and _bersih(p.get("dan"))
                                                 for p in cfg.get("pasangan") or []):
        m.append("isi minimal satu istilah wajib atau satu pasangan untuk menyaring relevansi")
    if not any(_bersih(v) for v in (cfg.get("narasi") or {}).values()):
        m.append("isi minimal satu isu (narasi) beserta kata kuncinya")
    return m


def modul(cfg, path=None):
    """Modul topik dari konfigurasi JSON."""
    slug = cfg["slug"]
    m = types.ModuleType(f"topik.{slug}")
    m.__file__ = path or os.path.join(FOLDER, f"{slug}.json")
    m.__doc__ = f"Topik {cfg['nama']} (dibuat dari halaman Kelola)."
    dari = cfg["dari"]
    akhir = cfg.get("sampai") or date.today().isoformat()
    m.SLUG, m.NAMA = slug, cfg["nama"]
    m.JUDUL = cfg.get("judul") or cfg["nama"]
    m.JUDUL_LAPORAN = cfg.get("judul_laporan") or m.JUDUL
    m.LEDE = cfg.get("lede") or ""
    m.STATUS = "selesai" if cfg.get("sampai") and cfg["sampai"] < date.today().isoformat() else "berjalan"
    m.JENDELA = (dari, akhir)
    m.ATAS = f"Laporan percakapan publik · {_periode(dari, akhir)}"
    m.PRESET = [("Seluruh periode", dari, akhir)] + [
        (p["label"], p["dari"], p["sampai"]) for p in cfg.get("preset") or []
        if p.get("label") and p.get("dari") and p.get("sampai")]

    kb = _bersih(cfg.get("kueri_berita"))
    wajib = _bersih(cfg.get("wajib"))
    m.KUERI_BERITA = kb
    m.KUERI_BERITA_INTI = kb[:3]
    m.KUERI_SITUS = [f'"{w}"' for w in wajib[:2]] or kb[:2]
    m.SITUS_TAMBAHAN = [re.sub(r"^https?://|/.*$", "", s) for s in _bersih(cfg.get("situs_lokal"))]
    m.KUERI_NATIVE = [k.strip('"') for k in kb[:6]]
    m.KUERI_YT = _bersih(cfg.get("kueri_yt"))
    m.KUERI_X = _bersih(cfg.get("kueri_x"))
    m.KUERI_X_HARIAN = m.KUERI_X[:2]
    m.TAGAR_IG = [t.lstrip("#").lower() for t in _bersih(cfg.get("tagar_ig"))]
    m.TAGAR_IG_LEBAR = []
    m.KUERI_IG = _bersih(cfg.get("kueri_ig")) or [k.strip('"') for k in kb[:5]]
    m.KUERI_THREADS = _bersih(cfg.get("kueri_threads"))

    # relevansi: istilah wajib, atau pasangan istilah ambigu + konteks (tanpa frasa pengecualian)
    rx_wajib = re.compile(pola(wajib), re.I) if wajib else None
    pasangan = [(re.compile(pola(p["jika"]), re.I), re.compile(pola(p["dan"]), re.I))
                for p in cfg.get("pasangan") or [] if _bersih(p.get("jika")) and _bersih(p.get("dan"))]
    kecuali = pola(cfg.get("kecuali"))
    rx_kecuali = re.compile(kecuali, re.I) if kecuali else None

    def relevan(teks):
        teks = teks or ""
        if rx_wajib and rx_wajib.search(teks):
            return 1
        if rx_kecuali and rx_kecuali.search(teks):
            return 0
        return int(any(a.search(teks) and b.search(teks) for a, b in pasangan))

    m.relevan = relevan
    m.JUDUL_KUAT = pola(wajib) or r"(?!x)x"
    longgar = [f"(?:{pola(p['jika'])}).{{0,60}}(?:{pola(p['dan'])})|(?:{pola(p['dan'])}).{{0,60}}(?:{pola(p['jika'])})"
               for p in cfg.get("pasangan") or [] if _bersih(p.get("jika")) and _bersih(p.get("dan"))]
    m.JUDUL_LONGGAR = "|".join(longgar) or r"(?!x)x"

    m.NARASI = {n: pola(k, 3) for n, k in (cfg.get("narasi") or {}).items() if pola(k, 3)}
    m.TOPIK_BERITA = dict(m.NARASI)
    m.AKTOR = {n: pola(k or [n], 3) for n, k in (cfg.get("aktor") or {}).items() if pola(k or [n], 3)}
    m.STOP = {w.lower() for w in _bersih(cfg.get("stop"))}
    fk = cfg.get("fokus") or {}
    narasi_fokus = [n for n in fk.get("narasi") or [] if n in m.NARASI]
    m.FOKUS = ({"nama": fk.get("nama") or "Fokus", "ket": fk.get("ket") or "konten yang menyentuh isu sorotan",
                "narasi": narasi_fokus} if narasi_fokus else None)
    aturan = {k: pola((cfg.get("aturan") or {}).get(k)) for k in ("pihak", "didukung", "abaikan", "samarkan")}
    m.ATURAN = {k: v for k, v in aturan.items() if v}
    m.ISTILAH = {"nada_positif": "suportif", "kantong_positif": "dukungan"}
    m.KET_PLATFORM = {
        "Berita": "Artikel media daring dari Google News dan mesin pencari internal media.",
        "X (Twitter)": "Tweet dari kata kunci dan tagar topik beserta balasannya.",
        "YouTube": "Video yang membahas topik ini beserta komentar dan balasannya.",
        "Instagram": "Unggahan dari tagar dan kata kunci topik beserta komentar yang berhasil dikumpulkan.",
        "Threads": "Unggahan dan balasan dari pencarian kata kunci.",
    }
    m.CATATAN_LINIMASA = "Jumlah konten per waktu untuk tiap platform."
    m.KONFIG = cfg
    return m


def daftar_json():
    """Slug topik JSON, terbaru dulu."""
    hasil = []
    for fn in os.listdir(FOLDER):
        if fn.endswith(".json") and not fn.startswith("_"):
            try:
                with open(os.path.join(FOLDER, fn), encoding="utf-8") as f:
                    hasil.append((json.load(f).get("dibuat", ""), fn[:-5]))
            except (OSError, json.JSONDecodeError):
                continue
    return [s for _, s in sorted(hasil, reverse=True)]


_CACHE = {}


def muat(slug):
    p = os.path.join(FOLDER, f"{slug}.json")
    mt = os.path.getmtime(p)
    c = _CACHE.get(slug)
    if c and c[0] == mt:
        return c[1]
    with open(p, encoding="utf-8") as f:
        m = modul(json.load(f), p)
    _CACHE[slug] = (mt, m)
    return m


def simpan(cfg):
    """Tulis topik/<slug>.json (atomik)."""
    p = os.path.join(FOLDER, f"{cfg['slug']}.json")
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)
    return p
