#!/usr/bin/env python3
"""Klien AI Analisa Sentimen: API kompatibel OpenAI, bawaan DeepSeek.

Konfigurasi di luar repo, ~/.config/virgo-sentiment/ai.json (izin 600), atau variabel lingkungan
AI_API_KEY / AI_BASE_URL / AI_MODEL / AI_MODEL_NALAR (lokasi berkas: AI_CONFIG_PATH). Contoh:

    {"penyedia": "deepseek", "base_url": "https://api.deepseek.com", "api_key": "sk-...",
     "model": "deepseek-flash", "model_nalar": "deepseek-flash", "paralel": 6, "batas_usd_per_tugas": 2}

  model        dipakai untuk klasifikasi massal (tanpa mode berpikir, suhu 0)
  model_nalar  dipakai untuk tugas yang butuh penalaran (nama klaster, kesimpulan, draf topik)

Yang ditangani di sini:
  - keluaran JSON (response_format json_object) yang diurai dan diperiksa
  - percobaan ulang dengan jeda bertambah untuk 429, 5xx, dan gangguan jaringan
  - cache jawaban di data/_bersama/ai_cache.sqlite: permintaan yang sama persis tidak dibayar dua kali
  - catatan pemakaian per panggilan (token, perkiraan biaya, durasi) di data/_bersama/ai_pemakaian.jsonl
  - batas biaya per proses (atur_batas): tugas berhenti sebelum melewati anggaran
  - cek saldo akun

    python3 scripts/ai_klien.py --cek        # konfigurasi (key disamarkan), saldo, satu panggilan uji
"""
import argparse
import hashlib
import json
import os
import random
import re
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.environ.get("AI_CONFIG_PATH") or os.path.expanduser("~/.config/virgo-sentiment/ai.json")
BERSAMA = os.path.join(ROOT, "data", "_bersama")
LOG_PEMAKAIAN = os.path.join(BERSAMA, "ai_pemakaian.jsonl")
CACHE_DB = os.path.join(BERSAMA, "ai_cache.sqlite")

BAWAAN = {"penyedia": "deepseek", "base_url": "https://api.deepseek.com", "api_key": "",
          "model": "deepseek-flash", "model_nalar": "deepseek-flash", "paralel": 6,
          "batas_usd_per_tugas": 2.0}

# Harga per sejuta token (USD), dari api-docs.deepseek.com/quick_start/pricing (Oktober 2026).
# Jam sibuk: Senin–Jumat 01–04 dan 06–10 UTC (08–11 dan 13–17 WIB); di luar itu separuh harga.
HARGA = {
    "deepseek-flash": {"hit": 0.006, "miss": 0.30, "out": 1.20},
    "deepseek-v4-pro": {"hit": 0.044, "miss": 1.32, "out": 3.96},
}
HARGA_LAIN = HARGA["deepseek-flash"]       # model tak dikenal: perkiraan memakai harga flash


class AIError(Exception):
    pass


class AITidakSiap(AIError):
    """Key belum diatur."""


class AIBatasBiaya(AIError):
    """Anggaran tugas ini habis."""


# --------------------------------------------------------------- konfigurasi
def setelan():
    s = dict(BAWAAN)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            s.update(json.load(f))
    except FileNotFoundError:
        pass
    for kunci, env in (("api_key", "AI_API_KEY"), ("base_url", "AI_BASE_URL"), ("model", "AI_MODEL"),
                       ("model_nalar", "AI_MODEL_NALAR")):
        if os.environ.get(env):
            s[kunci] = os.environ[env]
    s["base_url"] = s["base_url"].rstrip("/")
    return s


def simpan_setelan(baru):
    """Gabungkan perubahan ke ai.json (izin 600). Key kosong tidak menimpa key lama."""
    s = {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            s = json.load(f)
    except FileNotFoundError:
        pass
    for k, v in baru.items():
        if k == "api_key" and not v:
            continue
        s[k] = v
    os.makedirs(os.path.dirname(CONFIG_PATH), mode=0o700, exist_ok=True)
    fd = os.open(CONFIG_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1, ensure_ascii=False)
    os.chmod(CONFIG_PATH, 0o600)


def tersedia():
    return bool(setelan().get("api_key"))


def samarkan(key):
    return f"{key[:3]}…{key[-4:]}" if key and len(key) > 10 else ("(belum diatur)" if not key else "…")


# --------------------------------------------------------------- harga & biaya
def jam_sibuk(t=None):
    d = datetime.fromtimestamp(t or time.time(), tz=timezone.utc)
    return d.weekday() < 5 and (1 <= d.hour < 4 or 6 <= d.hour < 10)


def harga(model, t=None):
    h = HARGA.get(model, HARGA_LAIN)
    f = 1.0 if jam_sibuk(t) else 0.5
    return {k: v * f for k, v in h.items()}


def biaya(usage, model, t=None):
    h = harga(model, t)
    hit = usage.get("prompt_cache_hit_tokens", (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)) or 0
    miss = usage.get("prompt_cache_miss_tokens", max(0, usage.get("prompt_tokens", 0) - hit)) or 0
    out = usage.get("completion_tokens", 0) or 0
    return (hit * h["hit"] + miss * h["miss"] + out * h["out"]) / 1e6


def perkiraan_biaya(token_masuk, token_keluar, model=None):
    """Perkiraan kasar (tanpa diskon cache): harga jam sibuk dan di luar jam sibuk."""
    h = HARGA.get(model or setelan()["model"], HARGA_LAIN)
    sibuk = (token_masuk * h["miss"] + token_keluar * h["out"]) / 1e6
    return {"sibuk": sibuk, "luar_sibuk": sibuk / 2}


# --------------------------------------------------------------- anggaran per proses
_KUNCI = threading.Lock()
_PENGELUARAN = {"usd": 0.0, "batas": None, "panggilan": 0, "token_masuk": 0, "token_keluar": 0}


def atur_batas(usd):
    with _KUNCI:
        _PENGELUARAN["batas"] = usd


def pengeluaran():
    with _KUNCI:
        return dict(_PENGELUARAN)


def _catat(entri):
    with _KUNCI:
        _PENGELUARAN["usd"] += entri["biaya_usd"]
        _PENGELUARAN["panggilan"] += 1
        _PENGELUARAN["token_masuk"] += entri["token_masuk"]
        _PENGELUARAN["token_keluar"] += entri["token_keluar"]
        os.makedirs(BERSAMA, exist_ok=True)
        with open(LOG_PEMAKAIAN, "a", encoding="utf-8") as f:
            f.write(json.dumps(entri, ensure_ascii=False) + "\n")


def _cek_batas():
    with _KUNCI:
        b = _PENGELUARAN["batas"]
        if b is not None and _PENGELUARAN["usd"] >= b:
            raise AIBatasBiaya(f"anggaran tugas ${b:.2f} habis (terpakai ${_PENGELUARAN['usd']:.4f})")


# --------------------------------------------------------------- cache jawaban
_DB_KUNCI = threading.Lock()
_DB = None


def _db():
    global _DB
    if _DB is None:
        os.makedirs(BERSAMA, exist_ok=True)
        _DB = sqlite3.connect(CACHE_DB, check_same_thread=False, timeout=30)
        _DB.execute("CREATE TABLE IF NOT EXISTS jawab (kunci TEXT PRIMARY KEY, isi TEXT, dibuat REAL)")
        _DB.commit()
    return _DB


def _cache_ambil(kunci):
    with _DB_KUNCI:
        r = _db().execute("SELECT isi FROM jawab WHERE kunci = ?", (kunci,)).fetchone()
    return r[0] if r else None


def _cache_simpan(kunci, isi):
    with _DB_KUNCI:
        _db().execute("INSERT OR REPLACE INTO jawab VALUES (?, ?, ?)", (kunci, isi, time.time()))
        _db().commit()


# --------------------------------------------------------------- panggilan
def _urai_json(isi):
    t = (isi or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, re.S)
        if m:
            return json.loads(m.group(0))
        raise


def obrolan(pesan, *, tugas, topik=None, json_keluar=True, berpikir=False, model=None, suhu=0.0,
            maks_token=None, cache=True, timeout=None, percobaan=5):
    """Satu panggilan chat completion. pesan = [{"role", "content"}].
    berpikir: False (mode berpikir dimatikan, suhu dipakai) atau "low"/"high"/"max".
    Mengembalikan dict (json_keluar) atau str."""
    s = setelan()
    if not s["api_key"]:
        raise AITidakSiap(f"API key belum diatur ({CONFIG_PATH})")
    model = model or (s["model_nalar"] if berpikir else s["model"])
    body = {"model": model, "messages": pesan}
    if json_keluar:
        body["response_format"] = {"type": "json_object"}
    if berpikir:
        body["reasoning_effort"] = berpikir
    else:
        body["thinking"] = {"type": "disabled"}
        body["temperature"] = suhu
    if maks_token:
        body["max_tokens"] = maks_token
    kunci = hashlib.sha256(json.dumps([s["base_url"], body], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if cache:
        lama = _cache_ambil(kunci)
        if lama is not None:
            return _urai_json(lama) if json_keluar else lama
    _cek_batas()

    url = s["base_url"] + "/chat/completions"
    hdr = {"Authorization": f"Bearer {s['api_key']}", "Content-Type": "application/json"}
    timeout = timeout or (300 if berpikir else 120)
    galat = None
    for i in range(percobaan):
        t0 = time.time()
        try:
            r = requests.post(url, headers=hdr, json=body, timeout=timeout)
        except requests.RequestException as e:
            galat = f"jaringan: {e}"
        else:
            if r.status_code == 200:
                d = r.json()
                isi = d["choices"][0]["message"].get("content") or ""
                terpotong = d["choices"][0].get("finish_reason") == "length"
                u = d.get("usage") or {}
                _catat({"t": round(time.time(), 1), "tugas": tugas, "topik": topik, "model": d.get("model", model),
                        "token_masuk": u.get("prompt_tokens", 0), "token_keluar": u.get("completion_tokens", 0),
                        "cache_hit": u.get("prompt_cache_hit_tokens", 0),
                        "token_nalar": (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
                        "biaya_usd": round(biaya(u, model), 6), "durasi": round(time.time() - t0, 2)})
                if json_keluar:
                    try:
                        hasil = _urai_json(isi)
                    except (json.JSONDecodeError, ValueError):
                        if terpotong:
                            # batas token habis (mode berpikir ikut memakai batas keluaran): ulangi dengan batas lebih besar
                            body["max_tokens"] = min(64000, int(body.get("max_tokens") or 8000) * 2)
                            galat = "jawaban terpotong karena batas token"
                        else:
                            galat = "jawaban bukan JSON yang sah"
                        continue
                    if cache:
                        _cache_simpan(kunci, isi)
                    return hasil
                if cache:
                    _cache_simpan(kunci, isi)
                return isi
            if r.status_code in (400, 401, 402, 403, 422):
                pesan_api = r.text[:300]
                if r.status_code == 401:
                    raise AITidakSiap("API key ditolak (401). Periksa key di halaman Kelola › AI.")
                if r.status_code == 402:
                    raise AIError("Saldo DeepSeek habis (402). Isi ulang saldo di platform.deepseek.com.")
                raise AIError(f"permintaan ditolak {r.status_code}: {pesan_api}")
            galat = f"HTTP {r.status_code}"
            tunggu = r.headers.get("Retry-After")
            if tunggu and tunggu.isdigit():
                time.sleep(min(int(tunggu), 60))
                continue
        time.sleep(min(60, 2 ** (i + 1)) + random.random())
    raise AIError(f"gagal setelah {percobaan} percobaan ({galat})")


def paralel(fungsi, daftar, n=None, progres=None):
    """Jalankan fungsi(item) untuk tiap item secara paralel; progres(selesai, total) dipanggil tiap item.
    Galat AIBatasBiaya/AITidakSiap menghentikan semuanya; galat lain dicatat per item."""
    n = n or int(setelan().get("paralel", 6))
    hasil, galat = [None] * len(daftar), []
    with ThreadPoolExecutor(max_workers=max(1, n)) as ex:
        fut = {ex.submit(fungsi, x): i for i, x in enumerate(daftar)}
        selesai = 0
        for f in as_completed(fut):
            i = fut[f]
            try:
                hasil[i] = f.result()
            except (AIBatasBiaya, AITidakSiap):
                for g in fut:
                    g.cancel()
                raise
            except Exception as e:
                galat.append((i, str(e)))
            selesai += 1
            if progres:
                progres(selesai, len(daftar))
    return hasil, galat


# --------------------------------------------------------------- akun & pemakaian
def saldo():
    s = setelan()
    if not s["api_key"]:
        return None
    try:
        r = requests.get(s["base_url"] + "/user/balance", headers={"Authorization": f"Bearer {s['api_key']}"},
                         timeout=20)
        if r.status_code != 200:
            return {"galat": f"HTTP {r.status_code}"}
        d = r.json()
        info = (d.get("balance_infos") or [{}])[0]
        return {"tersedia": d.get("is_available"), "mata_uang": info.get("currency"),
                "total": float(info.get("total_balance") or 0)}
    except requests.RequestException as e:
        return {"galat": str(e)}


def ringkas_pemakaian(hari=30):
    """Total biaya dan token per hari dan per tugas dari catatan pemakaian."""
    batas = time.time() - hari * 86400
    per_hari, per_tugas, total = {}, {}, {"usd": 0.0, "panggilan": 0, "token": 0}
    try:
        f = open(LOG_PEMAKAIAN, encoding="utf-8")
    except FileNotFoundError:
        return {"per_hari": [], "per_tugas": [], "total": total}
    with f:
        for baris in f:
            try:
                e = json.loads(baris)
            except json.JSONDecodeError:
                continue
            if e.get("t", 0) < batas:
                continue
            tgl = datetime.fromtimestamp(e["t"]).strftime("%Y-%m-%d")
            tok = e.get("token_masuk", 0) + e.get("token_keluar", 0)
            for wadah, k in ((per_hari, tgl), (per_tugas, e.get("tugas", "-"))):
                w = wadah.setdefault(k, {"usd": 0.0, "panggilan": 0, "token": 0})
                w["usd"] += e.get("biaya_usd", 0)
                w["panggilan"] += 1
                w["token"] += tok
            total["usd"] += e.get("biaya_usd", 0)
            total["panggilan"] += 1
            total["token"] += tok
    return {"per_hari": sorted(({"tanggal": k, **v} for k, v in per_hari.items()), key=lambda x: x["tanggal"]),
            "per_tugas": sorted(({"tugas": k, **v} for k, v in per_tugas.items()), key=lambda x: -x["usd"]),
            "total": total}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Cek konfigurasi dan koneksi AI")
    ap.add_argument("--cek", action="store_true")
    a = ap.parse_args()
    s = setelan()
    print(f"penyedia {s['penyedia']} · {s['base_url']} · model {s['model']} / {s['model_nalar']} · key {samarkan(s['api_key'])}")
    if not s["api_key"]:
        sys.exit("API key belum diatur")
    print("saldo:", saldo())
    if a.cek:
        print("uji:", obrolan([{"role": "user", "content": 'Balas json {"ok": true}'}], tugas="uji", cache=False))
        print("pengeluaran proses ini:", pengeluaran())
