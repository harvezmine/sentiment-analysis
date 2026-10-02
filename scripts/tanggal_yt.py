"""Tanggal perkiraan komentar YouTube, dipakai dashboard (webapp/sumber.py) dan SNA.

YouTube tidak memberi tanggal pasti untuk komentar, hanya jarak waktu
("3 hari yang lalu"); acuannya adalah waktu file komentar dipanen.
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone

WIB = timezone(timedelta(hours=7))
_REL = re.compile(r"(\d+)\s*(detik|menit|jam|hari|minggu|bulan|tahun)", re.I)
_SATUAN_HARI = {"detik": 0, "menit": 0, "jam": 0, "hari": 1,
                "minggu": 7, "bulan": 30, "tahun": 365}


def acuan_file(path):
    """Waktu file dipanen (mtime) sebagai acuan tanggal relatif."""
    return datetime.fromtimestamp(os.path.getmtime(path), WIB) if os.path.exists(path) else None


def dari_relatif(teks_rel, acuan):
    """'3 hari yang lalu' -> 'YYYY-MM-DD' perkiraan; '' bila tak terbaca."""
    m = _REL.search(str(teks_rel or ""))
    if not m or acuan is None:
        return ""
    n, satuan = int(m.group(1)), m.group(2).lower()
    return (acuan - timedelta(days=n * _SATUAN_HARI.get(satuan, 0))).strftime("%Y-%m-%d")


def video_relevan(dir_yt):
    """{video_id: 0|1} dari yt_relevan.py; kosong = semua dianggap relevan."""
    f = os.path.join(dir_yt, "relevansi.json")
    if not os.path.exists(f):
        return {}
    try:
        return json.load(open(f, encoding="utf-8"))
    except Exception:
        return {}
