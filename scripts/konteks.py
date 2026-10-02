"""Konteks topik untuk skrip pipeline.

Topik dipilih lewat argumen --topik <slug> atau variabel lingkungan TOPIK:
    TOPIK=masela python3 scripts/10_yt_harvest.py
    python3 scripts/10_yt_harvest.py --topik masela

Skrip cukup:  from konteks import T, D, DATA
  T     modul topik (topik/<slug>.py): kueri, jendela, filter relevansi, narasi
  D()   path di dalam folder data topik:  D("yt", "videos.jsonl")
  DATA  folder data topik (data/<slug>/)
"""
import os
import sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import topik as _topik  # noqa: E402


def _slug():
    for i, a in enumerate(sys.argv):
        if a.startswith("--topik="):
            return a.split("=", 1)[1]
        if a == "--topik" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return os.environ.get("TOPIK", _topik.BAWAAN)


SLUG = _slug()
T = _topik.muat(SLUG)
DATA = _topik.folder(SLUG)
os.makedirs(DATA, exist_ok=True)


def D(*p):
    return os.path.join(DATA, *p)


def jendela_tanggal():
    """(awal, akhir) sebagai objek date."""
    a, z = T.JENDELA
    return date.fromisoformat(a), date.fromisoformat(z)


def potong_jendela(maks_harian=45):
    """Pecahan waktu untuk kueri berjendela: harian bila periode pendek,
    pekanan bila panjang (agar jumlah kueri tidak meledak untuk topik
    berbulan-bulan). Menghasilkan pasangan (mulai, sampai-eksklusif)."""
    a, z = jendela_tanggal()
    langkah = 1 if (z - a).days <= maks_harian else 7
    d = a
    while d <= z:
        n = min(d + timedelta(days=langkah), z + timedelta(days=1))
        yield d, n
        d = n


print(f"[topik] {SLUG} · {T.NAMA} · {T.JENDELA[0]} s/d {T.JENDELA[1]} · data/{SLUG}/",
      file=sys.stderr, flush=True)
