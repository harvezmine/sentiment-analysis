"""Label AI dan koreksi manual per topik, dipakai bersama oleh dashboard (webapp/sumber.py), graf SNA
(12_sna.py), dan laporan PDF supaya angkanya selalu sama.

Semua berkas ada di data/<slug>/_ai/ (tidak masuk git):
  setelan.json        {"label": "aturan" | "ai", "buang_tidak_relevan": false}
  label.jsonl         label AI per teks: {"h": sidik teks, "s": sentimen, "e": emosi8, "st": stance,
                      "r": 1|0 relevan, "m": model, "t": waktu}
  tidak_relevan.jsonl konten yang ditandai tidak relevan: {"id", "h", "sumber": "manual"|"ai", "t"}
  validasi.json       sampel validasi sentimen (lihat webapp/kelola.py)
  klaster.json        draf nama & catatan klaster dari AI
  kesimpulan/         draf dan versi disetujui kesimpulan laporan per periode

Teks dikenali dari sidiknya (md5 teks yang spasinya dirapikan), jadi label AI berlaku di semua tempat
teks yang sama muncul (komentar YouTube di dashboard dan di graf SNA, misalnya).

Label AI hanya dipakai bila setelan topik "label" = "ai". Narasi/isu tetap dari aturan kata kunci topik.
"""
import hashlib
import json
import os
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SENTIMEN = ("negatif", "netral", "positif")
EMOSI8 = ("senang", "percaya", "takut", "terkejut", "sedih", "jijik", "marah", "antisipasi", "netral")
STANCE = ("kritik", "dukungan", "netral")
_KUNCI = threading.Lock()
_CACHE = {}


def folder(slug):
    return os.path.join(ROOT, "data", slug, "_ai")


def berkas(slug, nama):
    return os.path.join(folder(slug), nama)


def sidik(teks):
    return hashlib.md5(" ".join(str(teks or "").split()).encode("utf-8", "replace")).hexdigest()


def _mtime(p):
    try:
        return os.path.getmtime(p)
    except OSError:
        return 0.0


# --------------------------------------------------------------- setelan
def setelan(slug):
    try:
        with open(berkas(slug, "setelan.json"), encoding="utf-8") as f:
            s = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        s = {}
    return {"label": s.get("label", "aturan"), "buang_tidak_relevan": bool(s.get("buang_tidak_relevan", False)),
            "laporan_ai": bool(s.get("laporan_ai", True))}


def simpan_setelan(slug, **ubah):
    s = setelan(slug)
    s.update({k: v for k, v in ubah.items() if k in s})
    os.makedirs(folder(slug), exist_ok=True)
    tulis_json(berkas(slug, "setelan.json"), s)
    return s


def tulis_json(p, isi):
    """Tulis atomik (berkas sementara lalu ganti) agar pembaca tidak pernah melihat berkas setengah jadi."""
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = f"{p}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(isi, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def baca_json(p, bawaan=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return bawaan


# --------------------------------------------------------------- label AI
def muat_label(slug):
    """{sidik: {"s", "e", "st", "r"}}; entri terakhir untuk sidik yang sama menang."""
    p = berkas(slug, "label.jsonl")
    m = _mtime(p)
    with _KUNCI:
        c = _CACHE.get(("label", slug))
        if c and c[0] == m:
            return c[1]
    lab = {}
    if m:
        with open(p, encoding="utf-8") as f:
            for baris in f:
                try:
                    e = json.loads(baris)
                    lab[e["h"]] = e
                except (json.JSONDecodeError, KeyError):
                    continue
    with _KUNCI:
        _CACHE[("label", slug)] = (m, lab)
    return lab


def tambah_label(slug, entri):
    """entri: [{"h", "s", "e", "st", "r", "m"}]; ditambahkan ke label.jsonl."""
    if not entri:
        return
    os.makedirs(folder(slug), exist_ok=True)
    t = round(time.time(), 1)
    with _KUNCI, open(berkas(slug, "label.jsonl"), "a", encoding="utf-8") as f:
        for e in entri:
            f.write(json.dumps({**e, "t": t}, ensure_ascii=False) + "\n")


def muat_tidak_relevan(slug):
    """(set id, set sidik) konten yang ditandai tidak relevan; tanda terakhir per id menang
    (sumber "batal" membatalkan tanda sebelumnya)."""
    p = berkas(slug, "tidak_relevan.jsonl")
    m = _mtime(p)
    with _KUNCI:
        c = _CACHE.get(("tr", slug))
        if c and c[0] == m:
            return c[1]
    akhir = {}
    if m:
        with open(p, encoding="utf-8") as f:
            for baris in f:
                try:
                    e = json.loads(baris)
                    akhir[e["id"]] = e
                except (json.JSONDecodeError, KeyError):
                    continue
    aktif = [e for e in akhir.values() if e.get("sumber") != "batal"]
    hasil = ({e["id"] for e in aktif}, {e["h"] for e in aktif if e.get("h")})
    with _KUNCI:
        _CACHE[("tr", slug)] = (m, hasil)
    return hasil


def tandai_tidak_relevan(slug, id_, teks, sumber="manual"):
    os.makedirs(folder(slug), exist_ok=True)
    with _KUNCI, open(berkas(slug, "tidak_relevan.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": str(id_), "h": sidik(teks) if sumber != "batal" else "",
                            "sumber": sumber, "t": round(time.time(), 1)}, ensure_ascii=False) + "\n")


def berkas_kesimpulan(slug, d1, d2, penuh):
    """Kesimpulan seluruh periode disimpan sebagai 'penuh' (akhir jendela topik yang berjalan bergeser
    tiap hari); periode lain memakai tanggalnya."""
    return berkas(slug, os.path.join("kesimpulan", "penuh.json" if penuh else f"{d1}_{d2}.json"))


def versi(slug):
    """Sidik setelan + label + tanda relevansi, untuk kunci cache data dashboard."""
    return (_mtime(berkas(slug, "setelan.json")), _mtime(berkas(slug, "label.jsonl")),
            _mtime(berkas(slug, "tidak_relevan.jsonl")))


def aktif(slug):
    return setelan(slug)["label"] == "ai"


# --------------------------------------------------------------- penerapan
def terapkan_df(slug, df):
    """Ganti sentimen & emosi konten media sosial dengan label AI (bila setelan topik memakai AI) dan
    buang konten yang ditandai tidak relevan. df = DataFrame gabungan dari webapp/sumber.py."""
    if not len(df):
        return df
    s = setelan(slug)
    ids, sidik_tr = muat_tidak_relevan(slug)
    pakai_ai = s["label"] == "ai"
    lab = muat_label(slug) if (pakai_ai or s["buang_tidak_relevan"]) else {}
    if not (pakai_ai or ids or s["buang_tidak_relevan"]):
        return df
    df = df.copy()
    sos = df.platform != "Berita"
    h = df.loc[sos, "teks"].map(sidik)
    buang = df.id.astype(str).isin(ids)
    if sidik_tr:
        buang |= sos & df.index.isin(h[h.isin(sidik_tr)].index)
    if s["buang_tidak_relevan"] and lab:
        tidak = h.map(lambda x: lab.get(x, {}).get("r", 1) == 0)
        buang |= sos & df.index.isin(tidak[tidak].index)
    if pakai_ai and lab:
        ada = h[h.isin(lab.keys())]
        df.loc[ada.index, "sentimen"] = ada.map(lambda x: lab[x]["s"])
        df.loc[ada.index, "emosi"] = ada.map(lambda x: lab[x]["e"])
    return df[~buang].reset_index(drop=True)


def terapkan(slug, teks, lab):
    """Untuk satu interaksi graf SNA: lab = {"sentimen", "emosi8", ...}. Mengembalikan None bila konten
    harus dibuang (tidak relevan), selain itu lab dengan label AI bila aktif."""
    s = setelan(slug)
    h = sidik(teks)
    _, sidik_tr = muat_tidak_relevan(slug)
    if h in sidik_tr:
        return None
    if s["label"] != "ai" and not s["buang_tidak_relevan"]:
        return lab
    e = muat_label(slug).get(h)
    if not e:
        return lab
    if s["buang_tidak_relevan"] and e.get("r", 1) == 0:
        return None
    if s["label"] == "ai":
        lab = {**lab, "sentimen": e["s"], "emosi8": e["e"]}
    return lab
