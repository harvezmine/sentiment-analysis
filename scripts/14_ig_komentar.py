#!/usr/bin/env python3
"""Tahap 14: panen komentar + balasan Instagram untuk post yang relevan.

Urutan: post dengan komentar terbanyak lebih dulu — di sanalah percakapan
publiknya, dan kalau sesi terhenti di tengah jalan, yang sudah terkumpul adalah
bagian paling bernilai.

Balasan (child comment) penting untuk SNA: di situ interaksi antar-warganet
terjadi (A membalas B), bukan sekadar warganet -> akun pemilik post.

Output: data/ig/komentar.jsonl + data/ig/komentar_selesai.log (resume-safe)
"""
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sp = importlib.util.spec_from_file_location("ig", os.path.join(ROOT, "scripts", "ig_client.py"))
ig = importlib.util.module_from_spec(sp)
sp.loader.exec_module(ig)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from konteks import D  # noqa: E402

DIR = D("ig")
POSTS = os.path.join(DIR, "posts.jsonl")
OUT = os.path.join(DIR, "komentar.jsonl")
DONE = os.path.join(DIR, "komentar_selesai.log")

MAKS_HAL = 5               # 15 komentar / halaman -> ~75 komentar teratas per post
MAKS_UTAS = 2              # utas balasan yang dibuka per post (terbanyak dulu)
MAKS_HAL_BALASAN = 1
MIN_KOMENTAR = 5           # post dengan komentar lebih sedikit dilewati


def main():
    if not os.path.exists(POSTS):
        print("data/ig/posts.jsonl belum ada — jalankan 13_ig_harvest.py dulu")
        return
    posts = {}
    for line in open(POSTS, encoding="utf-8"):
        try:
            p = json.loads(line)
        except Exception:
            continue
        if p.get("relevan") and p.get("komentar", 0) >= MIN_KOMENTAR:
            posts[p["media_id"]] = p
    selesai = set()
    if os.path.exists(DONE):
        selesai = {l.split("\t")[0] for l in open(DONE, encoding="utf-8")}
    lihat = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                lihat.add(json.loads(line)["komentar_id"])
            except Exception:
                pass
    antre = sorted((p for k, p in posts.items() if k not in selesai),
                   key=lambda p: -p["komentar"])
    print(f"[ig-k] {len(posts)} post relevan, {len(selesai)} sudah, {len(antre)} antre, "
          f"{len(lihat)} komentar tersimpan", flush=True)

    c = ig.IGClient()
    fo = open(OUT, "a", encoding="utf-8")
    fd = open(DONE, "a", encoding="utf-8")

    def tulis(row):
        if row["komentar_id"] in lihat:
            return 0
        lihat.add(row["komentar_id"])
        fo.write(json.dumps(row, ensure_ascii=False) + "\n")
        return 1

    try:
        for i, p in enumerate(antre, 1):
            baru, hal, stop, induk = 0, 0, "maks", []
            min_id = None
            while hal < MAKS_HAL:
                try:
                    j = c.komentar(p["media_id"], p["kode"], min_id)
                except ig.IGBerhenti:
                    raise
                except Exception as e:
                    stop = f"err:{str(e)[:30]}"
                    break
                hal += 1
                for k in j.get("comments") or []:
                    baru += tulis(ig.parse_komentar(k, p))
                    if k.get("child_comment_count"):
                        induk.append(k)
                    for anak in k.get("preview_child_comments") or []:
                        baru += tulis(ig.parse_komentar(anak, p, parent=k))
                min_id = j.get("next_min_id")
                if not j.get("has_more_headload_comments") or not min_id:
                    stop = "habis"
                    break
            # buka utas balasan dengan anak terbanyak
            induk.sort(key=lambda k: -int(k.get("child_comment_count") or 0))
            n_utas = 0
            for k in induk[:MAKS_UTAS]:
                cur_min = cur_max = None
                for _ in range(MAKS_HAL_BALASAN):
                    try:
                        jb = c.balasan(p["media_id"], p["kode"], k["pk"], cur_min, cur_max)
                    except ig.IGBerhenti:
                        raise
                    except Exception:
                        break
                    for anak in jb.get("child_comments") or []:
                        baru += tulis(ig.parse_komentar(anak, p, parent=k))
                    if jb.get("has_more_head_child_comments") and jb.get("next_min_child_cursor"):
                        cur_min, cur_max = jb["next_min_child_cursor"], None
                    elif jb.get("has_more_tail_child_comments") and jb.get("next_max_child_cursor"):
                        cur_min, cur_max = None, jb["next_max_child_cursor"]
                    else:
                        break
                n_utas += 1
            fo.flush()
            fd.write(f"{p['media_id']}\t{hal}\t{baru}\t{stop}\n")
            fd.flush()
            print(f"  [{i}/{len(antre)}] {p['kode']} @{p['username'][:18]:18s} "
                  f"{p['komentar']:>5d} kmt -> +{baru:4d} (h{hal} {stop}, {n_utas} utas) "
                  f"total={len(lihat)}", flush=True)
    except ig.IGBerhenti as e:
        print(f"\n[ig-k] DIHENTIKAN demi keamanan akun: {e}", flush=True)
        sys.exit(2)
    print(f"[ig-k] selesai. komentar unik: {len(lihat)}, {c.n_req} permintaan", flush=True)


if __name__ == "__main__":
    main()
