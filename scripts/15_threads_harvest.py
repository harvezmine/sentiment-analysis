#!/usr/bin/env python3
"""Tahap 15: panen Threads — post dari pencarian + balasan post teratas.

Dua fase, keduanya resume-safe:
  1. cari    : tiap kueri x tab (Top, Terbaru): halaman HTML (±19 post
               ter-prefetch) lalu paginasi GraphQL 10 post per halaman
  2. balasan : post relevan dengan balasan terbanyak dibuka satu per satu;
               halaman post memuat ±10–15 balasan teratas yang ter-prefetch

Ritme mengikuti threads_client (12–25 dtk, istirahat tiap 20 permintaan,
batas per jalankan). Fase 2 memakai sisa kuota fase 1, jadi bila kuota habis
jalankan ulang besok — yang sudah selesai tidak diulang.

Output: data/threads/posts.jsonl, data/threads/balasan.jsonl (+ log resume)
"""
import importlib.util
import json
import os
import sys
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import threads_client as th  # noqa: E402
from konteks import T, D  # noqa: E402

sp = importlib.util.spec_from_file_location("ig", os.path.join(ROOT, "scripts", "ig_client.py"))
ig = importlib.util.module_from_spec(sp)
sp.loader.exec_module(ig)      # dipakai untuk filter relevansi yang sama dengan Instagram

DIR = D("threads")
POSTS = os.path.join(DIR, "posts.jsonl")
BALASAN = os.path.join(DIR, "balasan.jsonl")
QLOG = os.path.join(DIR, "queries.log")
BLOG = os.path.join(DIR, "balasan_selesai.log")
os.makedirs(DIR, exist_ok=True)

TGL_AWAL = T.JENDELA[0]
KUERI = T.KUERI_THREADS
TAB = {"top": "", "terbaru": "&filter=recent"}
MAKS_HAL = 3                  # halaman GraphQL tambahan per kueri-tab
MAKS_POST_BALASAN = 60
MIN_BALASAN = 5


def _muat_id(path, kunci):
    out = set()
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                out.add(json.loads(line)[kunci])
            except Exception:
                pass
    return out


def _muat_log(path):
    return {l.split("\t")[0] for l in open(path, encoding="utf-8")} if os.path.exists(path) else set()


def fase_cari(c, lihat, fo, fq, selesai):
    for q in KUERI:
        for tab, filt in TAB.items():
            kunci = f"{q}|{tab}"
            if kunci in selesai:
                continue
            url = f"https://www.threads.com/search?q={quote(q)}&serp_type=default{filt}"
            baru, rel, hal, stop = 0, 0, 0, "maks"
            try:
                html = c.halaman(url)
                posts, info = th.post_pencarian(html)
                var = th.variabel_cari(html)
                if var and tab == "terbaru":
                    var["recent"] = 1      # parameter URL belum tentu dikenali
                while True:
                    for p in posts:
                        r = th.parse_post(p, sumber=kunci)
                        if r["post_id"] in lihat or (r["tanggal"] and r["tanggal"] < TGL_AWAL):
                            continue
                        lihat.add(r["post_id"])
                        r["relevan"] = T.relevan(r["teks"])
                        rel += r["relevan"]
                        fo.write(json.dumps(r, ensure_ascii=False) + "\n")
                        baru += 1
                    fo.flush()
                    if not info.get("has_next_page") or not var:
                        stop = "habis"
                        break
                    if hal >= MAKS_HAL:
                        break
                    var.update({"after": info.get("end_cursor"), "first": 10, "before": None,
                                "last": None, "pinned_ids": None})
                    j = c.graphql(th.DOC["cari_lanjut"], "BarcelonaSearchResultsRefetchableQuery",
                                  var, url)
                    posts, info = th.post_pencarian(j)
                    hal += 1
            except th.ThreadsBerhenti:
                raise
            except Exception as e:
                stop = f"err:{str(e)[:40]}"
            fq.write(f"{kunci}\t{hal}\t{baru}\t{rel}\t{stop}\n")
            fq.flush()
            print(f"  +{baru:3d} (relevan {rel:3d}, h{hal} {stop}) total={len(lihat):4d} "
                  f"req={c.n_req:3d} :: {q} [{tab}]", flush=True)


def fase_balasan(c):
    posts = {}
    for line in open(POSTS, encoding="utf-8"):
        try:
            p = json.loads(line)
        except Exception:
            continue
        if p.get("relevan") and not p.get("is_reply") and p.get("balasan", 0) >= MIN_BALASAN:
            posts[p["post_id"]] = p
    selesai = _muat_log(BLOG)
    lihat = _muat_id(BALASAN, "post_id")
    antre = sorted((p for k, p in posts.items() if k not in selesai),
                   key=lambda p: -p["balasan"])[:MAKS_POST_BALASAN]
    print(f"[threads] fase balasan: {len(posts)} post relevan ber-balasan, "
          f"{len(selesai)} selesai, {len(antre)} antre", flush=True)
    fo = open(BALASAN, "a", encoding="utf-8")
    fd = open(BLOG, "a", encoding="utf-8")
    for i, p in enumerate(antre, 1):
        try:
            html = c.halaman(p["url"])
        except th.ThreadsBerhenti:
            raise
        except Exception as e:
            print(f"  [{i}] gagal {p['kode']}: {str(e)[:60]}", flush=True)
            continue
        baru = 0
        for b in th.balasan_dari_html(html):
            r = th.parse_post(b, sumber="balasan")
            if r["post_id"] in lihat or r["post_id"] == p["post_id"]:
                continue
            lihat.add(r["post_id"])
            r["induk_id"] = p["post_id"]
            r["pemilik_induk"] = p["username"]
            r["balas_ke"] = r["balas_ke"] or p["username"]
            fo.write(json.dumps(r, ensure_ascii=False) + "\n")
            baru += 1
        fo.flush()
        fd.write(f"{p['post_id']}\t{baru}\n")
        fd.flush()
        print(f"  [{i}/{len(antre)}] @{p['username'][:18]:18s} {p['balasan']:>5} balasan -> "
              f"+{baru:3d} total={len(lihat)} req={c.n_req}", flush=True)


def main():
    c = th.ThreadsClient()
    lihat = _muat_id(POSTS, "post_id")
    selesai = _muat_log(QLOG)
    print(f"[threads] sudah punya {len(lihat)} post, {len(selesai)} kueri selesai, "
          f"batas {th.MAKS_REQ} permintaan", flush=True)
    fo = open(POSTS, "a", encoding="utf-8")
    fq = open(QLOG, "a", encoding="utf-8")
    try:
        fase_cari(c, lihat, fo, fq, selesai)
        fo.close()
        fase_balasan(c)
    except th.ThreadsBerhenti as e:
        print(f"\n[threads] DIHENTIKAN demi keamanan akun: {e}", flush=True)
        print("[threads] data yang sudah terkumpul aman; jalankan ulang nanti untuk melanjutkan.",
              flush=True)
        sys.exit(2)
    n_rel = sum(1 for l in open(POSTS, encoding="utf-8") if '"relevan": 1' in l)
    print(f"[threads] selesai. post {len(lihat)} (relevan {n_rel}), "
          f"balasan {len(_muat_id(BALASAN, 'post_id'))}, {c.n_req} permintaan", flush=True)


if __name__ == "__main__":
    main()
