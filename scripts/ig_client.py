"""Klien Instagram berbasis cookie sesi web.

Sesi pertama di-logout Instagram setelah ~22 permintaan dari `requests`
Python (jeda 6–10 dtk). Penyebab paling mungkin: sidik jari TLS/HTTP2 yang
jelas bukan peramban. Versi ini karena itu:
  - curl_cffi dengan impersonasi Chrome (TLS + HTTP/2 + User-Agent konsisten)
  - mengirim cookie peramban lengkap (sessionid, csrftoken, ds_user_id, mid, ig_did)
  - jeda acak 12–25 dtk, istirahat 2–5 menit tiap 20 permintaan, batas
    permintaan per jalankan (IG_MAKS_REQ, bawaan 120)
  - login_required / checkpoint / challenge / rate-limit -> BERHENTI TOTAL
    (IGBerhenti), tidak dicoba ulang otomatis

Kredensial di luar folder proyek: ~/.config/virgo-sentiment/ig_auth.json
"""
import json
import os
import random
import re
import time
from datetime import datetime, timedelta, timezone

from curl_cffi import requests

AUTH_PATH = os.environ.get("IG_AUTH_PATH") or os.path.expanduser(
    "~/.config/virgo-sentiment/ig_auth.json")

APP_ID = "936619743392459"          # app id klien web instagram.com
WIB = timezone(timedelta(hours=7))

JEDA_MIN, JEDA_MAKS = 12.0, 25.0
ISTIRAHAT_TIAP = 20
ISTIRAHAT = (120, 300)
MAKS_REQ = int(os.environ.get("IG_MAKS_REQ", "120"))


class IGBerhenti(Exception):
    """Sesi tidak lagi sah atau akun diminta verifikasi. Jangan diulang."""


class IGClient:
    def __init__(self):
        a = json.load(open(AUTH_PATH, encoding="utf-8"))
        # User-Agent TIDAK diisi manual: harus sama dengan versi Chrome yang ditiru
        self.s = requests.Session(impersonate="chrome")
        self.s.headers.update({
            "x-ig-app-id": APP_ID,
            "x-csrftoken": a["csrftoken"],
            "x-requested-with": "XMLHttpRequest",
            "x-asbd-id": "359341",
            "accept": "*/*",
            "referer": "https://www.instagram.com/",
            # tanpa header sec-fetch, endpoint komentar membalas halaman HTML
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
        })
        for k in ("sessionid", "csrftoken", "ds_user_id", "mid", "ig_did"):
            if a.get(k):
                self.s.cookies.set(k, a[k], domain=".instagram.com")
        self._terakhir = 0.0
        self.n_req = 0

    # ------------------------------------------------------------ transport
    def _jeda(self):
        if self.n_req >= MAKS_REQ:
            raise IGBerhenti(f"batas {MAKS_REQ} permintaan per jalankan tercapai (bukan blokir)")
        if self.n_req and self.n_req % ISTIRAHAT_TIAP == 0:
            t = random.uniform(*ISTIRAHAT)
            print(f"    [ig] istirahat {t / 60:.1f} menit", flush=True)
            time.sleep(t)
        tunggu = random.uniform(JEDA_MIN, JEDA_MAKS) - (time.time() - self._terakhir)
        if tunggu > 0:
            time.sleep(tunggu)

    def _minta(self, metode, url, **kw):
        # satu percobaan ulang hanya untuk galat jaringan; tanda bahaya apa pun
        # dari Instagram langsung menghentikan panen
        for coba in range(2):
            self._jeda()
            try:
                r = self.s.request(metode, url, timeout=40, allow_redirects=False, **kw)
            except requests.RequestsError as e:
                self._terakhir = time.time()
                if coba == 1:
                    raise
                print(f"    [ig] jaringan: {str(e)[:60]} (ulang sekali)", flush=True)
                continue
            self._terakhir = time.time()
            self.n_req += 1
            teks = r.text[:800].lower()
            if r.status_code in (301, 302, 401, 403) or "login_required" in teks \
                    or "checkpoint_required" in teks or "challenge_required" in teks:
                raise IGBerhenti(f"HTTP {r.status_code}: {r.text[:160]}")
            if r.status_code == 429 or "please wait a few minutes" in teks or "feedback_required" in teks:
                raise IGBerhenti("rate-limit / feedback_required: hentikan beberapa jam")
            if "json" not in r.headers.get("content-type", ""):
                raise RuntimeError(f"bukan JSON (HTTP {r.status_code})")
            j = r.json()
            if j.get("status") == "fail":
                raise RuntimeError(f"status fail: {str(j.get('message'))[:120]}")
            return j
        raise RuntimeError("gagal setelah 2 percobaan")

    # ------------------------------------------------------------ endpoint
    def tag_info(self, tag):
        return self._minta("GET", "https://www.instagram.com/api/v1/tags/web_info/",
                           params={"tag_name": tag})

    def tag_bagian(self, tag, tab, max_id=None, page=None, next_media_ids=None):
        """tab = 'top' | 'recent'. Mengembalikan dict dengan sections + kursor."""
        data = {"tab": tab, "include_persistent": "0", "surface": "grid"}
        if max_id:
            data["max_id"] = max_id
        if page is not None:
            data["page"] = str(page)
        if next_media_ids:
            data["next_media_ids"] = json.dumps(next_media_ids)
        self.s.headers["referer"] = f"https://www.instagram.com/explore/tags/{tag}/"
        return self._minta("POST", f"https://www.instagram.com/api/v1/tags/{tag}/sections/",
                           data=data)

    def cari(self, kueri, next_max_id=None, rank_token=None):
        params = {"query": kueri}
        if next_max_id:
            params["next_max_id"] = next_max_id
        if rank_token:
            params["rank_token"] = rank_token
        self.s.headers["referer"] = "https://www.instagram.com/explore/search/"
        return self._minta("GET", "https://www.instagram.com/api/v1/fbsearch/web/top_serp/",
                           params=params)

    def komentar(self, media_pk, kode, min_id=None):
        params = {"can_support_threading": "true", "permalink_enabled": "false"}
        if min_id:
            params["min_id"] = min_id
        self.s.headers["referer"] = f"https://www.instagram.com/p/{kode}/"
        return self._minta("GET", f"https://www.instagram.com/api/v1/media/{media_pk}/comments/",
                           params=params)

    def balasan(self, media_pk, kode, komentar_pk, min_id=None, max_id=None):
        """Balasan berpaginasi dua arah: min_id (head) atau max_id (tail)."""
        params = {}
        if min_id:
            params["min_id"] = min_id
        if max_id:
            params["max_id"] = max_id
        self.s.headers["referer"] = f"https://www.instagram.com/p/{kode}/"
        return self._minta(
            "GET",
            f"https://www.instagram.com/api/v1/media/{media_pk}/comments/{komentar_pk}/child_comments/",
            params=params)


# ---------------------------------------------------------------- parser
def media_dari_bagian(sections):
    """Ratakan struktur 'sections' (grid tagar / hasil cari) jadi list media."""
    out = []
    for sec in sections or []:
        lc = sec.get("layout_content") or {}
        for it in (lc.get("medias") or []) + (lc.get("fill_items") or []):
            m = it.get("media", it)
            if isinstance(m, dict) and m.get("pk"):
                out.append(m)
        ob = lc.get("one_by_two_item") or {}
        for it in (ob.get("clips") or {}).get("items") or []:
            m = it.get("media", it)
            if isinstance(m, dict) and m.get("pk"):
                out.append(m)
    return out


def _wib(ts):
    try:
        return datetime.fromtimestamp(int(ts), WIB)
    except Exception:
        return None


def parse_media(m):
    cap = (m.get("caption") or {}).get("text") or ""
    u = m.get("user") or {}
    t = _wib(m.get("taken_at"))
    tipe = {1: "foto", 2: "video", 8: "carousel"}.get(m.get("media_type"), str(m.get("media_type")))
    if m.get("product_type") == "clips":
        tipe = "reels"
    kolab = [c.get("username") for c in (m.get("coauthor_producers") or []) if c.get("username")]
    return {
        "media_id": str(m.get("pk")),
        "kode": m.get("code"),
        "url": f"https://www.instagram.com/p/{m.get('code')}/",
        "tanggal": t.strftime("%Y-%m-%d") if t else "",
        "waktu_wib": t.strftime("%Y-%m-%d %H:%M") if t else "",
        "username": u.get("username", ""),
        "nama": u.get("full_name", ""),
        "user_id": str(u.get("pk", "")),
        "verified": bool(u.get("is_verified")),
        "caption": cap,
        "hashtags": ";".join(sorted({h.lower() for h in re.findall(r"#(\w{2,60})", cap)})),
        "mentions": ";".join(sorted({x for x in re.findall(r"@([\w.]{2,30})", cap)})),
        "kolaborator": ";".join(kolab),
        "likes": int(m.get("like_count") or 0),
        "komentar": int(m.get("comment_count") or 0),
        "tayang": int(m.get("play_count") or m.get("ig_play_count") or m.get("view_count") or 0),
        "tipe": tipe,
        "lokasi": ((m.get("location") or {}).get("name") or ""),
    }


def parse_komentar(c, media, parent=None):
    u = c.get("user") or {}
    t = _wib(c.get("created_at"))
    teks = c.get("text") or ""
    return {
        "komentar_id": str(c.get("pk")),
        "media_id": media["media_id"],
        "kode": media["kode"],
        "pemilik_post": media["username"],
        "parent_id": str(parent["pk"]) if parent else "",
        "balas_ke": ((parent or {}).get("user") or {}).get("username", "") if parent else "",
        "level": 1 if parent else 0,
        "tanggal": t.strftime("%Y-%m-%d") if t else "",
        "waktu_wib": t.strftime("%Y-%m-%d %H:%M") if t else "",
        "username": u.get("username", ""),
        "user_id": str(u.get("pk", "")),
        "verified": bool(u.get("is_verified")),
        "teks": teks,
        "mentions": ";".join(sorted({x for x in re.findall(r"@([\w.]{2,30})", teks)})),
        "likes": int(c.get("comment_like_count") or 0),
        "jml_balasan": int(c.get("child_comment_count") or 0),
    }
