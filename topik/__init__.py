"""Registri topik Analisa Sentimen.

Satu topik = satu modul di folder ini (virgo.py, masela.py, ...). Modul itu
memuat SEMUA yang spesifik topik; pipeline di scripts/ dan dashboard hanya
membaca dari sini. Data tiap topik disimpan terpisah di data/<slug>/.

Menjalankan pipeline untuk satu topik:
    TOPIK=masela python3 scripts/10_yt_harvest.py
    python3 scripts/10_yt_harvest.py --topik masela

Menambah topik baru: salin masela.py, ubah isinya, tambahkan slug ke DAFTAR.

Kontrak isi modul topik (atribut yang dibaca pipeline & dashboard)
---------------------------------------------------------------------------
Identitas   SLUG, NAMA, JUDUL, ATAS, LEDE, STATUS ("berjalan" | "selesai")
Waktu       JENDELA = (awal, akhir) "YYYY-MM-DD"; PRESET = [(label, awal, akhir)]
Berita      KUERI_BERITA, KUERI_BERITA_INTI (dipecah per jendela waktu),
            KUERI_SITUS (istilah untuk kueri site:), SITUS_TAMBAHAN (media lokal),
            KUERI_NATIVE (mesin pencari internal media), JUDUL_KUAT, JUDUL_LONGGAR
YouTube     KUERI_YT
X/IG/Th     KUERI_X, KUERI_X_HARIAN, TAGAR_IG, TAGAR_IG_LEBAR, KUERI_IG,
            KUERI_THREADS (boleh kosong: platform belum dipanen)
Filter      relevan(teks) -> 0/1; opsional relevan_x(teks, kueri)
Analisis    NARASI (dict nama -> regex; None = narasi bawaan label_teks),
            TOPIK_BERITA, AKTOR (dict nama -> regex), STOP (kata khas topik
            yang disembunyikan dari awan kata & kata khas klaster),
            opsional ATURAN = {"pihak", "didukung", "abaikan"} (regex sasaran kritik,
            sasaran dukungan, kata evaluatif yang netral di topik ini; tanpa ini =
            aturan Virgo), opsional ISTILAH = {"nada_positif",
            "kantong_positif", "emosi": {emosi8: nama tampil}} untuk wawasan SNA
Laporan     opsional KESIMPULAN = [{"judul", "isi"}], REKOMENDASI = [str],
            KESIMPULAN_TANGGAL (dipakai scripts/laporan.py)
Dashboard   KET_PLATFORM (dict platform -> keterangan), CATATAN_LINIMASA,
            opsional FOKUS = {"nama", "ket", "narasi": [nama narasi]} untuk lensa
            sorotan (filter + panel porsi) di dashboard
"""
import importlib
import os
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# urutan tampil di pemilih topik: topik terbaru dulu. Topik buatan tangan = modul .py di folder ini;
# topik dari wizard halaman Kelola = berkas <slug>.json (lihat topik/_umum.py), otomatis terdaftar.
BUATAN_TANGAN = ["tangguh", "masela", "virgo"]
DAFTAR = []
BAWAAN = "virgo"


def daftarkan_ulang():
    """Segarkan DAFTAR (di tempat, agar semua yang sudah mengimpornya ikut melihat topik baru)."""
    from topik import _umum
    DAFTAR[:] = [s for s in _umum.daftar_json() if s not in BUATAN_TANGAN] + BUATAN_TANGAN
    return DAFTAR

# Media nasional untuk kueri site: Google News, dipakai semua topik.
SITUS_NASIONAL = [
    "detik.com", "kompas.com", "cnnindonesia.com", "tempo.co", "antaranews.com",
    "liputan6.com", "tribunnews.com", "okezone.com", "republika.co.id", "suara.com",
    "kumparan.com", "viva.co.id", "sindonews.com", "merdeka.com", "jpnn.com",
    "beritasatu.com", "katadata.co.id", "bisnis.com", "medcom.id", "inews.id",
    "tvonenews.com", "metrotvnews.com", "tirto.id", "kbr.id", "rmol.id",
    "pikiran-rakyat.com", "kontan.co.id", "cnbcindonesia.com", "kompas.tv",
    "jawapos.com", "timesindonesia.co.id", "gatra.com", "validnews.id", "idntimes.com",
    "narasi.tv", "thejakartapost.com", "jakartaglobe.id", "voaindonesia.com", "bbc.com",
    "mediaindonesia.com", "koran-jakarta.com", "investor.id", "fajar.co.id",
    "wartaekonomi.co.id", "genpi.co", "tribratanews.polri.go.id", "mongabay.co.id",
]


def muat(slug):
    if slug not in DAFTAR:
        daftarkan_ulang()
    if slug not in DAFTAR:
        raise KeyError(f"topik '{slug}' tidak dikenal; pilihan: {', '.join(DAFTAR)}")
    if slug not in BUATAN_TANGAN:
        from topik import _umum
        return _umum.muat(slug)
    return importlib.import_module(f"topik.{slug}")


def semua():
    return [muat(s) for s in DAFTAR]


def folder(slug):
    """Folder data topik: data/<slug>/"""
    return os.path.join(ROOT, "data", slug)


def hari_ini():
    return date.today().isoformat()


def relevan_x(T, teks, kueri=""):
    """Relevansi tweet: pakai aturan khusus topik bila ada, selain itu relevan()."""
    if hasattr(T, "relevan_x"):
        return T.relevan_x(teks, kueri)
    return T.relevan(teks)


daftarkan_ulang()
