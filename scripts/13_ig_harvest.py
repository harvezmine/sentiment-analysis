#!/usr/bin/env python3
"""Tahap 13: panen post Instagram tentang KM Virgo Transport 8.

Tiga jalur:
  1. tagar      : tab 'top' dan 'recent' per tagar
  2. kata kunci : pencarian /fbsearch/web/top_serp (IG kini mendukung
                  pencarian kata kunci, menjangkau post tanpa tagar)
  3. snowball   : tagar lain yang mengandung 'virgo' dan muncul di caption
                  post relevan otomatis ikut ditelusuri pada putaran berikut

Tagar lebar (#basarnas, #kapaltenggelam) ikut menarik insiden lain; setiap post
diberi kolom `relevan` oleh ig_client.relevan() dan dashboard hanya memakai
yang relevan.

Output: data/ig/posts.jsonl (resume-safe) + data/ig/queries.log
"""
import importlib.util
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sp = importlib.util.spec_from_file_location("ig", os.path.join(ROOT, "scripts", "ig_client.py"))
ig = importlib.util.module_from_spec(sp)
sp.loader.exec_module(ig)
from konteks import T, D  # noqa: E402

DIR = D("ig")
OUT = os.path.join(DIR, "posts.jsonl")
QLOG = os.path.join(DIR, "queries.log")
os.makedirs(DIR, exist_ok=True)

TGL_AWAL = T.JENDELA[0]

TAGAR_SPESIFIK = T.TAGAR_IG
# tagar lebar: banyak topik lain, hanya tab top + filter relevansi
TAGAR_LEBAR = T.TAGAR_IG_LEBAR
KUERI = T.KUERI_IG

MAKS_HAL_TOP = 8
MAKS_HAL_RECENT = 40        # recent berhenti sendiri saat melewati TGL_AWAL
MAKS_HAL_CARI = 8


class Panen:
    def __init__(self):
        self.c = ig.IGClient()
        self.lihat = set()
        if os.path.exists(OUT):
            for line in open(OUT, encoding="utf-8"):
                try:
                    self.lihat.add(json.loads(line)["media_id"])
                except Exception:
                    pass
        self.selesai = set()
        if os.path.exists(QLOG):
            for line in open(QLOG, encoding="utf-8"):
                self.selesai.add(line.split("\t")[0])
        self.fo = open(OUT, "a", encoding="utf-8")
        self.fq = open(QLOG, "a", encoding="utf-8")

    def simpan(self, medias, sumber):
        baru, lama = 0, 0
        for m in medias:
            p = ig.parse_media(m)
            if p["tanggal"] and p["tanggal"] < TGL_AWAL:
                lama += 1
                continue
            if p["media_id"] in self.lihat:
                continue
            self.lihat.add(p["media_id"])
            p["relevan"] = T.relevan(p["caption"])
            p["sumber"] = sumber
            self.fo.write(json.dumps(p, ensure_ascii=False) + "\n")
            baru += 1
        self.fo.flush()
        return baru, lama

    def catat(self, kunci, hal, baru, stop, info=""):
        self.fq.write(f"{kunci}\t{hal}\t{baru}\t{stop}\t{info}\n")
        self.fq.flush()
        print(f"  +{baru:4d} (h{hal:2d} {stop:8s}) total={len(self.lihat):5d} :: {kunci} {info}",
              flush=True)

    # ------------------------------------------------------------ tagar
    def tagar(self, tag, tab, maks):
        kunci = f"#{tag}|{tab}"
        if kunci in self.selesai:
            return
        baru_total, hal, stop, info = 0, 0, "maks", ""
        max_id = page = nmi = None
        if tab == "top":
            # halaman pertama tab top datang dari web_info, sekaligus media_count
            try:
                j = self.c.tag_info(tag)
            except ig.IGBerhenti:
                raise
            except Exception as e:
                self.catat(kunci, 0, 0, "err", str(e)[:60])
                return
            d = j.get("data") or {}
            info = f"[{d.get('media_count', '?')} post]"
            top = d.get("top") or {}
            b, _ = self.simpan(ig.media_dari_bagian(top.get("sections")), kunci)
            baru_total += b
            hal = 1
            if not top.get("more_available"):
                self.catat(kunci, hal, baru_total, "habis", info)
                return
            max_id, page, nmi = top.get("next_max_id"), top.get("next_page"), top.get("next_media_ids")
        while hal < maks:
            try:
                j = self.c.tag_bagian(tag, tab, max_id, page, nmi)
            except ig.IGBerhenti:
                raise
            except Exception as e:
                stop = f"err:{str(e)[:40]}"
                break
            medias = ig.media_dari_bagian(j.get("sections"))
            b, lama = self.simpan(medias, kunci)
            baru_total += b
            hal += 1
            if tab == "recent" and medias and lama == len(medias):
                stop = "lewat"      # seluruh halaman sudah sebelum kejadian
                break
            if not j.get("more_available"):
                stop = "habis"
                break
            max_id, page, nmi = j.get("next_max_id"), j.get("next_page"), j.get("next_media_ids")
        self.catat(kunci, hal, baru_total, stop, info)

    # ------------------------------------------------------------ kata kunci
    def kata_kunci(self, q):
        kunci = f"q:{q}"
        if kunci in self.selesai:
            return
        baru_total, hal, stop = 0, 0, "maks"
        nxt = rank = None
        while hal < MAKS_HAL_CARI:
            try:
                j = self.c.cari(q, nxt, rank)
            except ig.IGBerhenti:
                raise
            except Exception as e:
                stop = f"err:{str(e)[:40]}"
                break
            g = j.get("media_grid") or {}
            b, _ = self.simpan(ig.media_dari_bagian(g.get("sections")), kunci)
            baru_total += b
            hal += 1
            rank = g.get("rank_token") or j.get("rank_token") or rank
            nxt = g.get("next_max_id")
            if not g.get("has_more") or not nxt:
                stop = "habis"
                break
        self.catat(kunci, hal, baru_total, stop)

    def tagar_snowball(self, sudah):
        """Tagar ber-'virgo' yang muncul >=2x di caption post relevan."""
        c = Counter()
        for line in open(OUT, encoding="utf-8"):
            try:
                p = json.loads(line)
            except Exception:
                continue
            if not p.get("relevan"):
                continue
            for h in (p.get("hashtags") or "").split(";"):
                if "virgo" in h and h not in sudah:
                    c[h] += 1
        return [h for h, n in c.most_common(15) if n >= 2]


def main():
    p = Panen()
    print(f"[ig] sudah punya {len(p.lihat)} post, {len(p.selesai)} kueri selesai", flush=True)
    try:
        for t in TAGAR_SPESIFIK:
            p.tagar(t, "top", MAKS_HAL_TOP)
            p.tagar(t, "recent", MAKS_HAL_RECENT)
        for q in KUERI:
            p.kata_kunci(q)
        for t in TAGAR_LEBAR:
            p.tagar(t, "top", MAKS_HAL_TOP)
        tambahan = p.tagar_snowball(set(TAGAR_SPESIFIK) | set(TAGAR_LEBAR))
        if tambahan:
            print(f"[ig] snowball: {', '.join('#' + t for t in tambahan)}", flush=True)
        for t in tambahan:
            p.tagar(t, "top", MAKS_HAL_TOP)
            p.tagar(t, "recent", MAKS_HAL_RECENT)
    except ig.IGBerhenti as e:
        print(f"\n[ig] DIHENTIKAN demi keamanan akun: {e}", flush=True)
        print("[ig] buka instagram.com di peramban, selesaikan verifikasi bila ada, "
              "lalu perbarui cookie sebelum menjalankan ulang.", flush=True)
        sys.exit(2)
    n_rel = sum(1 for line in open(OUT, encoding="utf-8") if '"relevan": 1' in line)
    print(f"[ig] selesai. post unik: {len(p.lihat)} (relevan {n_rel}), "
          f"{p.c.n_req} permintaan", flush=True)


if __name__ == "__main__":
    main()
