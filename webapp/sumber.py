"""Lapisan data dashboard multi-topik: satu fungsi pemuat per platform.

Setiap pemuat menerima konteks topik K (folder data, jendela tanggal, modul
topik) sehingga satu proses dashboard bisa melayani banyak topik sekaligus.

Menambah platform baru cukup:
  1. tulis fungsi muat_<platform>(K) yang mengembalikan DataFrame berskema BAKU
  2. daftarkan di PLATFORM di bawah

SKEMA BAKU, kolom minimum yang harus ada:
  platform, id, tanggal, waktu, penulis, tipe_penulis, judul, teks,
  url, engagement, jangkauan, sentimen, emosi, narasi, topik
"""
from __future__ import annotations

import hashlib
import json
import os
import pickle
import re
import sys
import zlib
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import topik  # noqa: E402
from label_teks import klasifikasi  # noqa: E402  (aturan yang sama dengan pipeline)
import label_ai  # noqa: E402  (label AI & koreksi relevansi per topik)

KOLOM = ["platform", "id", "tanggal", "waktu", "jam", "penulis", "tipe_penulis",
         "judul", "teks", "url", "engagement", "jangkauan",
         "sentimen", "emosi", "narasi", "topik", "aktor"]
WIB = timezone(timedelta(hours=7))


class Konteks:
    """Semua yang dibutuhkan pemuat untuk satu topik."""

    def __init__(self, slug):
        self.slug = slug
        self.T = topik.muat(slug)
        self.DATA = topik.folder(slug)
        # jendela peristiwa: data di luar rentang ini hampir pasti salah-parse tanggal
        self.AWAL, self.AKHIR = self.T.JENDELA

    @property
    def panjang_hari(self):
        return (date.fromisoformat(self.AKHIR) - date.fromisoformat(self.AWAL)).days

    @property
    def pekanan(self):
        """Periode panjang diringkas per pekan agar grafik harian tetap terbaca."""
        return self.panjang_hari > 60


@lru_cache(maxsize=None)
def konteks(slug) -> Konteks:
    return Konteks(slug)


def _kosong() -> pd.DataFrame:
    return pd.DataFrame(columns=KOLOM)


# Label per-ID disimpan di memori: panen yang sedang berjalan menulis file
# terus-menerus sehingga cache DataFrame sering dibatalkan, dan tanpa ini
# belasan ribu komentar akan diklasifikasi ulang pada setiap permintaan.
_LABEL: dict = {}

# Cache label di disk (data/<slug>/_cache_label.pkl): pelabelan ulang puluhan ribu konten
# memakan waktu tiap kali dashboard atau generator laporan dinyalakan. Cache sah selama
# aturan label (label_teks.py + NARASI/ATURAN topik) tidak berubah, dan tiap entri dicocokkan
# dengan sidik teksnya sehingga konten yang berubah tetap dilabeli ulang.
_DISK: dict = {}


def _versi_label(K) -> str:
    h = hashlib.md5(open(os.path.join(ROOT, "scripts", "label_teks.py"), "rb").read())
    h.update(json.dumps([K.T.NARASI, getattr(K.T, "ATURAN", None)], sort_keys=True, default=str).encode())
    return h.hexdigest()


def _cache_disk(K) -> dict:
    c = _DISK.get(K.slug)
    if c is None:
        versi, f, lab = _versi_label(K), os.path.join(K.DATA, "_cache_label.pkl"), {}
        try:
            with open(f, "rb") as fh:
                d = pickle.load(fh)
            if d.get("versi") == versi:
                lab = d["lab"]
        except Exception:
            pass
        c = _DISK[K.slug] = {"versi": versi, "lab": lab, "baru": 0, "f": f}
    return c


def _simpan_cache_disk(K):
    c = _DISK.get(K.slug)
    if not c or not c["baru"]:
        return
    try:
        tmp = c["f"] + ".tmp"
        with open(tmp, "wb") as fh:
            pickle.dump({"versi": c["versi"], "lab": c["lab"]}, fh, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, c["f"])
        c["baru"] = 0
    except OSError as e:
        print(f"[sumber] cache label {K.slug} gagal disimpan: {e}")


def _label(K, ids, teks):
    """Sentimen, emosi Plutchik, dan narasi topik dengan aturan label_teks."""
    sen, emo, nar, top = [], [], [], []
    disk = _cache_disk(K)
    for i, t in zip(ids, teks):
        kunci = (K.slug, i)
        lab = _LABEL.get(kunci)
        if lab is None:
            sidik = zlib.crc32(t.encode("utf-8", "replace"))
            ent = disk["lab"].get(i)
            if ent and ent[0] == sidik:
                lab = ent[1]
            else:
                k = klasifikasi(t, narasi=K.T.NARASI, aturan=getattr(K.T, "ATURAN", None))
                lab = (k["sentimen"], k["emosi8"], k["narasi_utama"], k["narasi"])
                disk["lab"][i] = (sidik, lab)
                disk["baru"] += 1
            _LABEL[kunci] = lab
        sen.append(lab[0])
        emo.append(lab[1])
        nar.append(lab[2])
        top.append(lab[3])
    return sen, emo, nar, top


def _rapikan(K, df: pd.DataFrame) -> pd.DataFrame:
    for k in KOLOM:
        if k not in df.columns:
            df[k] = ""
    df = df[KOLOM].copy()
    # penamaan tipe penulis berbeda antar-sumber; disatukan agar tidak muncul ganda
    df["tipe_penulis"] = df["tipe_penulis"].replace({"Pemerintah/Institusi": "Institusi/Pemerintah"})
    df["tanggal"] = df["tanggal"].astype(str).str.slice(0, 10)
    df = df[(df.tanggal >= K.AWAL) & (df.tanggal <= K.AKHIR)]
    for k in ("engagement", "jangkauan"):
        df[k] = pd.to_numeric(df[k], errors="coerce").fillna(0).astype("int64")
    # jam diturunkan dari kolom waktu ("YYYY-MM-DD HH:MM"); -1 bila tak terbaca
    jam = df["waktu"].astype(str).str.extract(r"\s(\d{2}):", expand=False)
    df["jam"] = pd.to_numeric(jam, errors="coerce").fillna(-1).astype(int)
    return df.reset_index(drop=True)


# --------------------------------------------------------------- BERITA
def muat_berita(K) -> pd.DataFrame:
    f = os.path.join(K.DATA, "articles_clean.csv")
    if not os.path.exists(f):
        return _kosong()
    d = pd.read_csv(f, low_memory=False)
    out = pd.DataFrame({
        "platform": "Berita",
        "id": d["id"],
        "tanggal": d["tanggal"],
        "waktu": d["waktu_wib"],
        "penulis": d["media"],
        "tipe_penulis": d["tipe_media"],
        "judul": d["judul"],
        "teks": d["deskripsi"].fillna("").astype(str),
        "url": d["url"],
        "engagement": 0,
        "jangkauan": 0,
        # sentimen berita masih baseline lexicon -> ditandai eksplisit di UI
        "sentimen": d["sentimen_baseline"],
        "emosi": "",
        "narasi": d["topik_utama"],
        "topik": d["topik"],
        "aktor": d["aktor"].fillna("") if "aktor" in d.columns else "",
    })
    return _rapikan(K, out)


# ------------------------------------------------------------------- X
def muat_x(K) -> pd.DataFrame:
    f = os.path.join(K.DATA, "x", "tweets_labeled.csv")
    if not os.path.exists(f):
        f = os.path.join(K.DATA, "x", "tweets.jsonl")
        if not os.path.exists(f):
            return _kosong()
        d = pd.read_json(f, lines=True)
        d["sentimen"] = "belum dilabeli"
        d["narasi"] = "Lainnya"
    else:
        d = pd.read_csv(f, low_memory=False)
        if "relevan" in d.columns:
            d = d[d.relevan == 1]

    tipe = {}
    fa = os.path.join(K.DATA, "x", "akun.csv")
    if os.path.exists(fa):
        a = pd.read_csv(fa)
        tipe = dict(zip(a["username"], a["tipe"]))

    eng = (pd.to_numeric(d.get("likes", 0), errors="coerce").fillna(0)
           + pd.to_numeric(d.get("retweets", 0), errors="coerce").fillna(0)
           + pd.to_numeric(d.get("replies", 0), errors="coerce").fillna(0)
           + pd.to_numeric(d.get("quotes", 0), errors="coerce").fillna(0))
    out = pd.DataFrame({
        "platform": "X (Twitter)",
        "id": d["tweet_id"].astype(str),
        "tanggal": d["tanggal"],
        "waktu": d.get("waktu_wib", ""),
        "penulis": d["username"],
        "tipe_penulis": d["username"].map(lambda u: tipe.get(u, "Publik")),
        "judul": "",
        "teks": d["teks"].fillna("").astype(str),
        "url": d.get("url", ""),
        "engagement": eng,
        "jangkauan": pd.to_numeric(d.get("views", 0), errors="coerce").fillna(0),
        "sentimen": d.get("sentimen", "belum dilabeli"),
        "emosi": d.get("emosi8", "netral"),
        "narasi": d.get("narasi_utama", "Lainnya"),
        "topik": d.get("narasi", ""),
        # untuk X, "aktor" = akun yang di-mention
        "aktor": d.get("mentions", "").fillna("") if hasattr(d.get("mentions", ""), "fillna") else "",
    })
    return _rapikan(K, out)


# ------------------------------------------------------------- YOUTUBE
from tanggal_yt import dari_relatif as _dari_relatif, acuan_file, video_relevan  # noqa: E402


def muat_youtube(K) -> pd.DataFrame:
    dir_yt = os.path.join(K.DATA, "yt")
    fv = os.path.join(dir_yt, "video_detail.jsonl")
    fk = os.path.join(dir_yt, "komentar.jsonl")
    bagian = []

    # --- video sebagai konten
    if os.path.exists(fv):
        d = pd.read_json(fv, lines=True)
        rel = video_relevan(dir_yt)
        if len(d) and rel:
            d = d[d["video_id"].astype(str).map(lambda v: rel.get(v, 1)) == 1]
        if len(d):
            tgl = (d.get("terbit_iso", pd.Series([""] * len(d)))
                   .astype(str).str.slice(0, 10))
            ids = "YTV" + d["video_id"].astype(str)
            judul = d.get("judul", "").fillna("").astype(str)
            sen, emo, nar, top = _label(K, ids, judul)
            bagian.append(pd.DataFrame({
                "platform": "YouTube", "id": ids,
                "tanggal": tgl, "waktu": tgl + " 12:00",
                "penulis": d.get("kanal", ""), "tipe_penulis": "Kanal YouTube",
                "judul": judul, "teks": d.get("deskripsi", "").fillna("").astype(str).str.slice(0, 1200),
                "url": d.get("url", ""),
                "engagement": pd.to_numeric(d.get("suka", 0), errors="coerce").fillna(0),
                "jangkauan": pd.to_numeric(d.get("tayang", 0), errors="coerce").fillna(0),
                "sentimen": sen, "emosi": emo, "narasi": nar, "topik": top, "aktor": "",
            }))

    # --- komentar sebagai konten
    if os.path.exists(fk):
        d = pd.read_json(fk, lines=True)
        rel = video_relevan(dir_yt)
        if len(d) and rel:
            # komentar video yang belakangan dinilai tidak relevan ikut dibuang
            d = d[d["video_id"].astype(str).map(lambda v: rel.get(v, 1)) == 1]
        if len(d):
            # tanggal komentar hanya tersedia sebagai jarak waktu relatif;
            # acuan = waktu file dipanen.
            acuan = acuan_file(fk)
            tgl = d.get("terbit_relatif", pd.Series([""] * len(d))).map(
                lambda t: _dari_relatif(t, acuan))
            ids = "YTK" + d["komentar_id"].astype(str)
            teks = d.get("teks", "").fillna("").astype(str)
            sen, emo, nar, top = _label(K, ids, teks)
            bagian.append(pd.DataFrame({
                "platform": "YouTube", "id": ids,
                "tanggal": tgl, "waktu": tgl + " 12:00",
                "penulis": d.get("penulis", "").astype(str).str.lstrip("@"),
                "tipe_penulis": "Publik",
                "judul": "", "teks": teks,
                "url": d.get("video_url", ""),
                "engagement": pd.to_numeric(d.get("likes", 0), errors="coerce").fillna(0),
                "jangkauan": 0,
                "sentimen": sen, "emosi": emo, "narasi": nar, "topik": top, "aktor": "",
            }))

    if not bagian:
        return _kosong()
    return _rapikan(K, pd.concat(bagian, ignore_index=True))


def muat_threads(K) -> pd.DataFrame:
    dir_th = os.path.join(K.DATA, "threads")
    bagian = []
    induk_relevan = None
    for nama, kode in (("posts.jsonl", "THP"), ("balasan.jsonl", "THB")):
        f = os.path.join(dir_th, nama)
        if not os.path.exists(f):
            continue
        d = pd.read_json(f, lines=True, dtype={"post_id": str, "induk_id": str})
        if not len(d):
            continue
        if kode == "THP":
            d = d[d.get("relevan", 1) == 1]
            induk_relevan = set(d["post_id"].astype(str))
        elif induk_relevan is not None and "induk_id" in d.columns:
            # balasan mewarisi relevansi post induk
            d = d[d["induk_id"].astype(str).isin(induk_relevan)]
            if not len(d):
                continue
        ids = kode + d["post_id"].astype(str)
        teks = d["teks"].fillna("").astype(str)
        sen, emo, nar, top = _label(K, ids, teks)
        bagian.append(pd.DataFrame({
            "platform": "Threads", "id": ids,
            "tanggal": d["tanggal"], "waktu": d["waktu_wib"],
            "penulis": d["username"],
            "tipe_penulis": d["verified"].map(lambda v: "Akun terverifikasi" if v else "Publik"),
            "judul": "", "teks": teks, "url": d["url"],
            "engagement": d["likes"].fillna(0) + d["balasan"].fillna(0)
                          + d["repost"].fillna(0) + d["quote"].fillna(0),
            "jangkauan": 0,
            "sentimen": sen, "emosi": emo, "narasi": nar, "topik": top,
            "aktor": d["mentions"].fillna("").str.replace(";", "; "),
        }))
    if not bagian:
        return _kosong()
    return _rapikan(K, pd.concat(bagian, ignore_index=True))


def muat_instagram(K) -> pd.DataFrame:
    dir_ig = os.path.join(K.DATA, "ig")
    fp = os.path.join(dir_ig, "posts.jsonl")
    fk = os.path.join(dir_ig, "komentar.jsonl")
    bagian = []

    # --- post (caption) sebagai konten; hanya yang lolos filter relevansi
    if os.path.exists(fp):
        d = pd.read_json(fp, lines=True, dtype={"media_id": str})
        if len(d):
            d = d[d.get("relevan", 1) == 1]
            ids = "IGP" + d["media_id"].astype(str)
            cap = d["caption"].fillna("").astype(str)
            sen, emo, nar, top = _label(K, ids, cap)
            bagian.append(pd.DataFrame({
                "platform": "Instagram", "id": ids,
                "tanggal": d["tanggal"], "waktu": d["waktu_wib"],
                "penulis": d["username"],
                "tipe_penulis": d["verified"].map(lambda v: "Akun terverifikasi" if v else "Publik"),
                "judul": cap.str.split("\n").str[0].str.slice(0, 140),
                "teks": cap,
                "url": d["url"],
                "engagement": d["likes"].fillna(0) + d["komentar"].fillna(0),
                "jangkauan": d.get("tayang", 0),
                "sentimen": sen, "emosi": emo, "narasi": nar, "topik": top,
                "aktor": d["mentions"].fillna("").str.replace(";", "; "),
            }))

    # --- komentar + balasan
    if os.path.exists(fk):
        d = pd.read_json(fk, lines=True, dtype={"komentar_id": str, "media_id": str})
        if len(d):
            ids = "IGK" + d["komentar_id"].astype(str)
            teks = d["teks"].fillna("").astype(str)
            sen, emo, nar, top = _label(K, ids, teks)
            bagian.append(pd.DataFrame({
                "platform": "Instagram", "id": ids,
                "tanggal": d["tanggal"], "waktu": d["waktu_wib"],
                "penulis": d["username"], "tipe_penulis": "Publik",
                "judul": "", "teks": teks,
                "url": "https://www.instagram.com/p/" + d["kode"].astype(str) + "/",
                "engagement": d["likes"].fillna(0), "jangkauan": 0,
                "sentimen": sen, "emosi": emo, "narasi": nar, "topik": top,
                "aktor": d["mentions"].fillna("").str.replace(";", "; "),
            }))

    if not bagian:
        return _kosong()
    return _rapikan(K, pd.concat(bagian, ignore_index=True))


# urutan ini = urutan slot warna platform di dashboard
PLATFORM = {
    "Berita": muat_berita,
    "X (Twitter)": muat_x,
    "YouTube": muat_youtube,
    "Instagram": muat_instagram,
    "Threads": muat_threads,
}


def _cap_mtime(slug) -> float:
    """Sidik jari waktu-ubah semua file sumber topik, untuk invalidasi cache. Folder _ai (label AI,
    validasi) dan _rentang (graf per periode) bukan data panen, jadi tidak dihitung."""
    t = 0.0
    for dirpath, dirs, files in os.walk(topik.folder(slug)):
        dirs[:] = [d for d in dirs if d not in ("_ai", "_rentang")]
        for fn in files:
            if fn.endswith((".csv", ".jsonl")):
                try:
                    t = max(t, os.path.getmtime(os.path.join(dirpath, fn)))
                except OSError:
                    pass
    return round(t, 3)


@lru_cache(maxsize=8)
def _semua_mentah(slug: str, _sidik: float) -> pd.DataFrame:
    K = konteks(slug)
    bagian = []
    for nama, fn in PLATFORM.items():
        try:
            d = fn(K)
        except Exception as e:  # satu platform rusak tidak boleh menjatuhkan dashboard
            print(f"[sumber] {slug}/{nama} gagal dimuat: {e}")
            continue
        if len(d):
            bagian.append(d)
    _simpan_cache_disk(K)
    return pd.concat(bagian, ignore_index=True) if bagian else _kosong()


@lru_cache(maxsize=8)
def _semua(slug: str, _sidik: float, _versi_ai: tuple) -> pd.DataFrame:
    # label AI (bila dipakai topik ini) dan konten yang ditandai tidak relevan
    return label_ai.terapkan_df(slug, _semua_mentah(slug, _sidik))


def semua(slug) -> pd.DataFrame:
    return _semua(slug, _cap_mtime(slug), label_ai.versi(slug))


def semua_mentah(slug) -> pd.DataFrame:
    """Data dengan label aturan, tanpa label AI dan tanpa koreksi relevansi (pembanding validasi)."""
    return _semua_mentah(slug, _cap_mtime(slug))


def diperbarui(slug) -> float:
    return _cap_mtime(slug)


def kolom_waktu(K, df, pekanan=None) -> pd.Series:
    """Kunci waktu untuk grafik linimasa: tanggal, atau awal pekan (Senin)
    bila periode panjang (bawaan: panjang jendela topik)."""
    if pekanan is None:
        pekanan = K.pekanan
    if not pekanan or not len(df):
        return df["tanggal"]
    t = pd.to_datetime(df["tanggal"], errors="coerce")
    return (t - pd.to_timedelta(t.dt.weekday, unit="D")).dt.strftime("%Y-%m-%d")


# ------------------------------------------------------------- agregasi
STOPWORD = set("""
yang di ke dari dan atau untuk pada dengan ini itu adalah akan telah sudah
dalam tidak ada juga sebagai oleh karena saat saya kami kita mereka dia
para lebih bisa dapat masih hingga setelah sebelum antara serta agar
bahwa apa siapa kapan mengapa bagaimana ya tak pun lah nya kah per
kepada terhadap tentang secara namun tetapi jika kalau maka sehingga
satu dua tiga orang hari kata ujar tutur sebut jelas terkait berita
https http co com rt amp yg gak ga nya dg utk dr krn sdh tdh nih tuh
""".split())


def kata_teratas(teks_iter, n=60, stop=()):
    """stop: kata topik (mis. nama proyek) yang pasti muncul di mana-mana."""
    c = Counter()
    henti = STOPWORD | set(stop)
    for t in teks_iter:
        for w in re.findall(r"[a-zA-Z][a-zA-Z']{2,}", str(t).lower()):
            if w not in henti and len(w) > 3:
                c[w] += 1
    return c.most_common(n)


def tagar_teratas(df, n=25):
    c = Counter()
    for t in df["teks"].fillna(""):
        for h in re.findall(r"#(\w{3,40})", str(t)):
            c[h.lower()] += 1
    return c.most_common(n)


def ringkas(df: pd.DataFrame) -> dict:
    if not len(df):
        return {"total": 0, "platform": {}, "penulis": 0, "rentang": "-",
                "engagement": 0, "jangkauan": 0}
    return {
        "total": int(len(df)),
        "platform": df.platform.value_counts().to_dict(),
        "penulis": int(df.penulis.nunique()),
        "rentang": f"{df.tanggal.min()} s/d {df.tanggal.max()}",
        "engagement": int(df.engagement.sum()),
        "jangkauan": int(df.jangkauan.sum()),
    }
