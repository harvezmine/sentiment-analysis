#!/usr/bin/env python3
"""Klien YouTube InnerTube — endpoint internal yang dipakai web youtube.com.

Tanpa API key Google dan tanpa kuota harian. Konfigurasi klien (ytcfg) diambil
langsung dari HTML youtube.com setiap kali dijalankan, sehingga tidak ada nilai
yang di-hardcode dan basi saat YouTube merilis versi baru.

Catatan: YouTube menghapus jumlah dislike dari seluruh antarmukanya sejak
Desember 2021, jadi angka itu memang tidak tersedia di sini.
"""
import json
import re
import time
import random

import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
BASE = "https://www.youtube.com/youtubei/v1"


def walk(obj):
    """Telusuri seluruh pohon JSON dalam URUTAN DOKUMEN, hasilkan tiap dict.

    Urutan penting: token continuation "halaman berikutnya" selalu item
    terakhir pada daftar komentar, sedangkan token di atasnya adalah pembuka
    balasan. Penelusuran berbasis stack (LIFO) akan membalik urutan itu dan
    membuat paginasi berhenti di halaman pertama.
    """
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)


def teks(node):
    """Rangkai simpul teks YouTube (simpleText / runs) menjadi string."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if "simpleText" in node:
            return node["simpleText"]
        if "runs" in node:
            return "".join(r.get("text", "") for r in node["runs"])
        if "content" in node and isinstance(node["content"], str):
            return node["content"]
    return ""


def angka(s):
    """'1,2 rb', '3.4K', '1.234' -> int. Mengembalikan 0 bila gagal."""
    if s is None:
        return 0
    if isinstance(s, (int, float)):
        return int(s)
    s = str(s).strip().lower().replace("\xa0", " ")
    m = re.search(r"([\d.,]+)\s*(rb|jt|k|m|b|t)?", s)
    if not m:
        return 0
    n = m.group(1)
    # format Indonesia: titik = ribuan, koma = desimal
    if "," in n and "." in n:
        n = n.replace(".", "").replace(",", ".")
    elif "," in n:
        n = n.replace(",", ".") if len(n.split(",")[-1]) <= 2 else n.replace(",", "")
    else:
        if n.count(".") > 1 or (("." in n) and len(n.split(".")[-1]) == 3):
            n = n.replace(".", "")
    try:
        v = float(n)
    except ValueError:
        return 0
    faktor = {"rb": 1e3, "k": 1e3, "jt": 1e6, "m": 1e6, "b": 1e9, "t": 1e12}
    return int(v * faktor.get(m.group(2) or "", 1))


class YTClient:
    def __init__(self, lang="id", region="ID"):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": UA,
            "Accept-Language": f"{lang}-{region},{lang};q=0.9,en;q=0.8",
            "Content-Type": "application/json",
            "Origin": "https://www.youtube.com",
            "Referer": "https://www.youtube.com/",
        })
        self.lang, self.region = lang, region
        self._muat_cfg()

    def _muat_cfg(self):
        r = self.s.get("https://www.youtube.com/?persist_gl=1&gl=" + self.region, timeout=40)
        r.raise_for_status()
        html = r.text
        key = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html)
        ver = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', html)
        name = re.search(r'"INNERTUBE_CLIENT_NAME":"?([^",]+)"?', html)
        if not key or not ver:
            raise RuntimeError("gagal membaca ytcfg dari halaman YouTube")
        self.key = key.group(1)
        self.ctx = {
            "client": {
                "clientName": (name.group(1) if name else "WEB"),
                "clientVersion": ver.group(1),
                "hl": self.lang, "gl": self.region,
                "userAgent": UA,
            }
        }
        vis = re.search(r'"visitorData":"([^"]+)"', html)
        if vis:
            self.ctx["client"]["visitorData"] = vis.group(1)
            self.s.headers["X-Goog-Visitor-Id"] = vis.group(1)
        self.s.headers["X-Youtube-Client-Name"] = "1"
        self.s.headers["X-Youtube-Client-Version"] = self.key and ver.group(1)

    def panggil(self, endpoint, badan, retries=3):
        url = f"{BASE}/{endpoint}?key={self.key}&prettyPrint=false"
        isi = {"context": self.ctx}
        isi.update(badan)
        akhir = None
        for i in range(retries):
            try:
                r = self.s.post(url, json=isi, timeout=45)
                if r.status_code == 200:
                    return r.json()
                akhir = (r.status_code, r.text[:160])
                if r.status_code in (429, 503):
                    time.sleep(30 + i * 30)
                else:
                    time.sleep(3 + i * 4)
            except Exception as e:
                akhir = ("EXC", str(e)[:160])
                time.sleep(4 + i * 4)
        raise RuntimeError(f"{endpoint} gagal: {akhir}")

    # ------------------------------------------------------------ search
    # params terurut relevansi/tanggal; 'CAISBAgCEAE' = urut tanggal unggah, tipe video
    def cari(self, kueri, params="CAISBAgCEAE%3D", continuation=None):
        if continuation:
            return self.panggil("search", {"continuation": continuation})
        badan = {"query": kueri}
        if params:
            badan["params"] = requests.utils.unquote(params)
        return self.panggil("search", badan)

    def next(self, video_id=None, continuation=None):
        if continuation:
            return self.panggil("next", {"continuation": continuation})
        return self.panggil("next", {"videoId": video_id})

    def player(self, video_id):
        return self.panggil("player", {"videoId": video_id,
                                       "contentCheckOk": True, "racyCheckOk": True})


# ------------------------------------------------------------- parsing
def lanjutan(obj):
    """Ambil token continuation pertama yang ditemukan."""
    for d in walk(obj):
        cir = d.get("continuationItemRenderer")
        if isinstance(cir, dict):
            ep = cir.get("continuationEndpoint") or {}
            cmd = ep.get("continuationCommand") or {}
            if cmd.get("token"):
                return cmd["token"]
            btn = ((cir.get("button") or {}).get("buttonRenderer") or {})
            cmd2 = ((btn.get("command") or {}).get("continuationCommand") or {})
            if cmd2.get("token"):
                return cmd2["token"]
    return None


def parse_video(vr):
    """videoRenderer -> dict ringkas."""
    vid = vr.get("videoId")
    if not vid:
        return None
    pemilik = teks(vr.get("ownerText") or vr.get("longBylineText") or vr.get("shortBylineText"))
    kanal_id = ""
    for d in walk(vr.get("ownerText") or vr.get("longBylineText") or {}):
        if d.get("browseId", "").startswith("UC"):
            kanal_id = d["browseId"]
            break
    deskripsi = ""
    for k in ("detailedMetadataSnippets", "descriptionSnippet"):
        if k in vr:
            n = vr[k]
            if isinstance(n, list) and n:
                deskripsi = teks(n[0].get("snippetText", n[0]))
            else:
                deskripsi = teks(n)
            if deskripsi:
                break
    # viewCountText memakai format Indonesia ("2.146 x ditonton"); shortViewCountText
    # sudah dibulatkan ("2,1 rb"), jadi yang panjang selalu didahulukan.
    tayang = angka(teks(vr.get("viewCountText"))) or angka(teks(vr.get("shortViewCountText")))
    badge = json.dumps(vr.get("badges", [])) + json.dumps(vr.get("thumbnailOverlays", []))
    langsung = "LIVE" in badge or "UPCOMING" in badge
    return {
        "video_id": vid,
        "judul": teks(vr.get("title")),
        "kanal": pemilik,
        "kanal_id": kanal_id,
        "deskripsi": deskripsi,
        "tayang": tayang,
        "terbit_relatif": teks(vr.get("publishedTimeText")),
        "durasi": teks(vr.get("lengthText")),
        # siaran langsung memakai live chat, bukan komentar — ditandai agar
        # tahap panen komentar bisa melewatinya
        "langsung": int(langsung),
        "url": f"https://www.youtube.com/watch?v={vid}",
    }


def parse_hasil_cari(j):
    out, lihat = [], set()
    for d in walk(j):
        vr = d.get("videoRenderer")
        if isinstance(vr, dict):
            v = parse_video(vr)
            if v and v["video_id"] not in lihat:
                lihat.add(v["video_id"])
                out.append(v)
    return out


def parse_komentar(j):
    """Ambil komentar dari dua bentuk respons YouTube: commentEntityPayload
    (format baru, di frameworkUpdates) dan commentRenderer (format lama)."""
    out = []
    # --- format baru
    for d in walk(j):
        p = d.get("commentEntityPayload")
        if not isinstance(p, dict):
            continue
        prop = p.get("properties") or {}
        aut = p.get("author") or {}
        tb = p.get("toolbar") or {}
        isi = (prop.get("content") or {})
        out.append({
            "komentar_id": prop.get("commentId", ""),
            "teks": isi.get("content", "") if isinstance(isi, dict) else str(isi),
            "penulis": aut.get("displayName", ""),
            "penulis_id": aut.get("channelId", ""),
            "terbit_relatif": prop.get("publishedTime", ""),
            "likes": angka(tb.get("likeCountNotliked") or tb.get("likeCountLiked") or 0),
            "jml_balasan": angka(tb.get("replyCount") or 0),
            "level": int(prop.get("replyLevel", 0) or 0),
        })
    if out:
        return out
    # --- format lama
    for d in walk(j):
        cr = d.get("commentRenderer")
        if not isinstance(cr, dict):
            continue
        out.append({
            "komentar_id": cr.get("commentId", ""),
            "teks": teks(cr.get("contentText")),
            "penulis": teks(cr.get("authorText")),
            "penulis_id": (((cr.get("authorEndpoint") or {}).get("browseEndpoint") or {})
                           .get("browseId", "")),
            "terbit_relatif": teks(cr.get("publishedTimeText")),
            "likes": angka(cr.get("voteCount")),
            "jml_balasan": angka(teks(cr.get("replyCount"))) if cr.get("replyCount") else 0,
            "level": 0,
        })
    return out


def parse_detail_video(j_next, j_player=None):
    """Gabungkan hasil next + player menjadi metadata video."""
    hasil = {"suka": 0, "tayang": 0, "judul": "", "kanal": "", "kanal_id": "",
             "terbit": "", "deskripsi": "", "subscriber": ""}
    for d in walk(j_next):
        vpr = d.get("videoPrimaryInfoRenderer")
        if isinstance(vpr, dict):
            hasil["judul"] = teks(vpr.get("title")) or hasil["judul"]
            hasil["tayang"] = angka(teks(((vpr.get("viewCount") or {})
                                          .get("videoViewCountRenderer") or {}).get("viewCount"))) \
                or hasil["tayang"]
            hasil["terbit"] = teks(vpr.get("dateText")) or hasil["terbit"]
    # Jumlah suka ada di likeButtonViewModel; 'title' memuat angka ringkas
    # ("1,2 rb") sedangkan accessibilityText memuat angka penuh.
    for d in walk(j_next):
        lbv = d.get("likeButtonViewModel")
        if not isinstance(lbv, dict):
            continue
        for e in walk(lbv):
            bvm = e.get("buttonViewModel")
            if isinstance(bvm, dict) and bvm.get("iconName") in ("LIKE", "LIKE_FILLED"):
                n = angka(bvm.get("accessibilityText") or "") or angka(bvm.get("title") or "")
                if n:
                    hasil["suka"] = max(hasil["suka"], n)
        vsr = d.get("videoSecondaryInfoRenderer")
        if isinstance(vsr, dict):
            hasil["kanal"] = teks((vsr.get("owner") or {}).get("videoOwnerRenderer", {}).get("title")) \
                or hasil["kanal"]
            hasil["subscriber"] = teks((vsr.get("owner") or {})
                                       .get("videoOwnerRenderer", {})
                                       .get("subscriberCountText")) or hasil["subscriber"]
            hasil["deskripsi"] = (teks(vsr.get("attributedDescription"))
                                  or teks(vsr.get("description")) or hasil["deskripsi"])
    if j_player:
        vd = (j_player.get("videoDetails") or {})
        hasil["judul"] = hasil["judul"] or vd.get("title", "")
        hasil["kanal"] = hasil["kanal"] or vd.get("author", "")
        hasil["kanal_id"] = vd.get("channelId", "") or hasil["kanal_id"]
        hasil["deskripsi"] = hasil["deskripsi"] or vd.get("shortDescription", "")
        hasil["tayang"] = hasil["tayang"] or angka(vd.get("viewCount"))
        mf = ((j_player.get("microformat") or {}).get("playerMicroformatRenderer") or {})
        hasil["terbit_iso"] = mf.get("publishDate", "") or mf.get("uploadDate", "")
    return hasil


if __name__ == "__main__":
    c = YTClient()
    print("ytcfg ok — client:", c.ctx["client"]["clientName"],
          c.ctx["client"]["clientVersion"])
    j = c.cari('"Virgo Transport 8"')
    vids = parse_hasil_cari(j)
    print(f"hasil pencarian: {len(vids)} video")
    for v in vids[:5]:
        print(f"  {v['tayang']:>9,} tayangan | {v['kanal'][:24]:24s} | {v['judul'][:60]}")
    print("continuation:", "ada" if lanjutan(j) else "tidak ada")
