#!/usr/bin/env python3
"""Antrean pekerjaan halaman Kelola: panen, olah, dan tugas AI dijalankan sebagai proses terpisah dari
dashboard, satu per satu per lajur, jadi tetap berjalan walau dashboard dimuat ulang.

Pekerjaan = berkas data/_bersama/pekerjaan/<id>.json:
  {"id", "lajur": "panen"|"ai", "jenis", "judul", "topik", "langkah": [{"skrip", "args"}],
   "status": "antre"|"jalan"|"selesai"|"gagal"|"batal", "dibuat", "mulai", "selesai", "langkah_ke", "pid", "pesan"}
dengan log di <id>.log. Pembatalan: berkas <id>.batal (proses yang berjalan dihentikan).

Lajur "panen" berisi semua panen dan pengolahan data, sehingga Instagram dan Threads tidak pernah
berjalan bersamaan dan file data tidak ditulis dua proses sekaligus. Lajur "ai" untuk tugas AI.

    python3 scripts/antrean.py --lajur panen      # dijalankan otomatis oleh dashboard; keluar bila antrean kosong
"""
import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.path.join(ROOT, "data", "_bersama", "pekerjaan")


def jalur(id_, ext="json"):
    return os.path.join(FOLDER, f"{id_}.{ext}")


def baca(id_):
    try:
        with open(jalur(id_), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def tulis(p):
    tmp = jalur(p["id"]) + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=1)
    os.replace(tmp, jalur(p["id"]))


def semua():
    if not os.path.isdir(FOLDER):
        return []
    out = []
    for fn in os.listdir(FOLDER):
        if fn.endswith(".json"):
            p = baca(fn[:-5])
            if p:
                out.append(p)
    return sorted(out, key=lambda p: p["dibuat"])


def _hidup(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False


def bereskan(lajur):
    """Pekerjaan berstatus 'jalan' yang prosesnya sudah tidak ada (mis. laptop mati) ditandai terputus."""
    for p in semua():
        if p["lajur"] == lajur and p["status"] == "jalan" and not _hidup(p.get("pid_antrean")):
            p.update(status="gagal", pesan="terputus (proses antrean berhenti)", selesai=time.time())
            tulis(p)


def jalankan(p, log):
    p.update(status="jalan", mulai=time.time(), pid_antrean=os.getpid())
    tulis(p)
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    if p.get("topik"):
        env["TOPIK"] = p["topik"]
    for i, l in enumerate(p["langkah"]):
        if os.path.exists(jalur(p["id"], "batal")):
            p.update(status="batal", pesan="dibatalkan sebelum langkah berikutnya")
            return
        p.update(langkah_ke=i)
        tulis(p)
        log.write(f"\n===== [{i + 1}/{len(p['langkah'])}] {l['skrip']} {' '.join(l.get('args', []))} · "
                  f"{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        log.flush()
        proc = subprocess.Popen([sys.executable, os.path.join(ROOT, l["skrip"]), *l.get("args", [])],
                                cwd=ROOT, env={**env, **l.get("env", {})}, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
        p["pid"] = proc.pid
        tulis(p)
        while proc.poll() is None:
            if os.path.exists(jalur(p["id"], "batal")):
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(15)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                log.write("\n[antrean] dibatalkan\n")
                p.update(status="batal", pesan=f"dibatalkan saat {l['skrip']}")
                return
            time.sleep(1)
        if proc.returncode != 0:
            p.update(status="gagal", pesan=f"{l['skrip']} keluar dengan kode {proc.returncode}")
            return
    p.update(status="selesai", pesan="")


def main(lajur):
    os.makedirs(FOLDER, exist_ok=True)
    kunci = open(os.path.join(FOLDER, f"lajur-{lajur}.lock"), "w")
    try:
        fcntl.flock(kunci, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return                                  # antrean lajur ini sudah dijalankan proses lain
    bereskan(lajur)
    while True:
        antre = [p for p in semua() if p["lajur"] == lajur and p["status"] == "antre"]
        if not antre:
            break
        p = antre[0]
        if os.path.exists(jalur(p["id"], "batal")):
            p.update(status="batal", pesan="dibatalkan sebelum mulai", selesai=time.time())
            tulis(p)
            continue
        with open(jalur(p["id"], "log"), "a", encoding="utf-8") as log:
            try:
                jalankan(p, log)
            except Exception as e:                       # galat antrean sendiri, bukan skrip
                p.update(status="gagal", pesan=f"galat antrean: {e}")
            p["selesai"] = time.time()
            tulis(p)
            log.write(f"\n[antrean] {p['status']} · {time.strftime('%Y-%m-%d %H:%M:%S')}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lajur", required=True, choices=["panen", "ai"])
    main(ap.parse_args().lajur)
