"""Klien Threads (threads.com) berbasis cookie sesi web.

Sesi Instagram pertama terputus setelah ~22 permintaan dari `requests` Python,
kemungkinan besar karena sidik jari TLS-nya jelas bukan peramban. Klien ini
karena itu:
  - memakai curl_cffi dengan impersonasi Chrome (TLS + HTTP/2 seperti peramban)
  - jeda acak 12–25 detik antar-permintaan, istirahat 2–5 menit tiap ~20
    permintaan, dan batas permintaan per jalankan (MAKS_REQ)
  - berhenti total (ThreadsBerhenti) pada tanda login/checkpoint/rate-limit
    pertama — tidak mencoba ulang otomatis

Kredensial di luar folder proyek: ~/.config/virgo-sentiment/threads_auth.json
  {"sessionid", "csrftoken", "ds_user_id", "mid", "ig_did"}

Doc ID GraphQL diambil dari bundle JS threads.com (lihat DOC). Bila Threads
merilis versi baru dan query ditolak, jalankan ulang pencarian doc ID.
"""
import json
import os
import random
import re
import time
from datetime import datetime, timedelta, timezone

from curl_cffi import requests

AUTH_PATH = os.environ.get("THREADS_AUTH_PATH") or os.path.expanduser(
    "~/.config/virgo-sentiment/threads_auth.json")
WIB = timezone(timedelta(hours=7))
APP_ID = "238260118697367"           # app id klien web threads.com

DOC = {
    "cari": "39269977565926803",       # BarcelonaSearchResultsQuery
    "cari_lanjut": "39309682601963393",  # BarcelonaSearchResultsRefetchableQuery
}

JEDA_MIN, JEDA_MAKS = 12.0, 25.0
ISTIRAHAT_TIAP = 20
ISTIRAHAT = (120, 300)
MAKS_REQ = int(os.environ.get("THREADS_MAKS_REQ", "180"))


class ThreadsBerhenti(Exception):
    """Sesi tidak sah / diminta verifikasi / dibatasi. Jangan diulang otomatis."""


class ThreadsClient:
    def __init__(self):
        a = json.load(open(AUTH_PATH, encoding="utf-8"))
        self.a = a
        self.s = requests.Session(impersonate="chrome")
        for k, v in a.items():
            self.s.cookies.set(k, v, domain=".threads.com")
        self.n_req = 0
        self._terakhir = 0.0
        self.token = None

    # ------------------------------------------------------------ ritme
    def _jeda(self):
        if self.n_req >= MAKS_REQ:
            raise ThreadsBerhenti(f"batas {MAKS_REQ} permintaan per jalankan tercapai")
        if self.n_req and self.n_req % ISTIRAHAT_TIAP == 0:
            t = random.uniform(*ISTIRAHAT)
            print(f"    [threads] istirahat {t / 60:.1f} menit", flush=True)
            time.sleep(t)
        tunggu = random.uniform(JEDA_MIN, JEDA_MAKS) - (time.time() - self._terakhir)
        if tunggu > 0:
            time.sleep(tunggu)

    def _periksa(self, r):
        teks = r.text[:3000].lower()
        if r.status_code in (301, 302, 401, 403) or "checkpoint_required" in teks \
                or "challenge_required" in teks or "login_required" in teks:
            raise ThreadsBerhenti(f"HTTP {r.status_code}: {r.text[:160]}")
        if r.status_code == 429 or "rate limit" in teks or "please wait a few minutes" in teks:
            raise ThreadsBerhenti("rate-limit — hentikan beberapa jam")

    def halaman(self, url):
        """GET halaman HTML (search / post). Sekaligus memperbarui token."""
        self._jeda()
        r = self.s.get(url, timeout=40, allow_redirects=False,
                       headers={"accept": "text/html,application/xhtml+xml",
                                "sec-fetch-mode": "navigate", "sec-fetch-dest": "document"})
        self._terakhir = time.time()
        self.n_req += 1
        self._periksa(r)
        if "/login" in r.text[:5000] and '"is_logged_in":false' in r.text:
            raise ThreadsBerhenti("halaman meminta login")
        self._ambil_token(r.text)
        return r.text

    def _ambil_token(self, html):
        dtsg = re.search(r'"DTSGInitialData",\[\],\{"token":"([^"]+)"', html)
        lsd = re.search(r'"LSD",\[\],\{"token":"([^"]+)"', html)
        aktor = re.search(r'"actorID":"(\d+)"', html)
        if dtsg and lsd:
            self.token = {
                "fb_dtsg": dtsg.group(1), "lsd": lsd.group(1),
                "av": aktor.group(1) if aktor else "0",
                "jazoest": "2" + str(sum(ord(c) for c in dtsg.group(1))),
            }

    def graphql(self, doc_id, nama, variabel, referer):
        if not self.token:
            raise RuntimeError("token belum ada — panggil halaman() dulu")
        self._jeda()
        data = {
            "av": self.token["av"], "__user": "0", "__a": "1", "__comet_req": "29",
            "fb_dtsg": self.token["fb_dtsg"], "jazoest": self.token["jazoest"],
            "lsd": self.token["lsd"], "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": nama, "variables": json.dumps(variabel),
            "server_timestamps": "true", "doc_id": doc_id,
        }
        r = self.s.post("https://www.threads.com/graphql/query", data=data, timeout=40,
                        allow_redirects=False, headers={
                            "x-fb-lsd": self.token["lsd"], "x-csrftoken": self.a["csrftoken"],
                            "x-ig-app-id": APP_ID, "x-fb-friendly-name": nama,
                            "x-asbd-id": "359341", "origin": "https://www.threads.com",
                            "referer": referer, "sec-fetch-site": "same-origin",
                            "sec-fetch-mode": "cors", "sec-fetch-dest": "empty"})
        self._terakhir = time.time()
        self.n_req += 1
        self._periksa(r)
        teks = r.text
        if teks.startswith("for (;;);"):
            teks = teks[9:]
        j = json.loads(teks)
        if j.get("errors") and not j.get("data"):
            raise RuntimeError(f"graphql: {str(j['errors'])[:200]}")
        return j


# ---------------------------------------------------------------- parser
def blok_json(html):
    """Semua blok <script type=application/json data-sjs> yang memuat post:
    hasil pencarian (thread_items) atau balasan di halaman post (direct_replies)."""
    for b in re.findall(r'<script type="application/json"[^>]*data-sjs>(.*?)</script>', html, re.S):
        if "thread_items" in b or "direct_replies" in b:
            try:
                yield json.loads(b)
            except Exception:
                pass


def telusuri(o, kunci):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == kunci:
                yield v
            yield from telusuri(v, kunci)
    elif isinstance(o, list):
        for v in o:
            yield from telusuri(v, kunci)


def post_pencarian(html_atau_json):
    """(daftar post, page_info) dari halaman pencarian atau respons GraphQL."""
    sumber = list(blok_json(html_atau_json)) if isinstance(html_atau_json, str) else [html_atau_json]
    posts, info = [], {}
    for b in sumber:
        for sr in telusuri(b, "searchResults"):
            info = sr.get("page_info") or info
            for e in sr.get("edges") or []:
                for it in ((e.get("node") or {}).get("thread") or {}).get("thread_items") or []:
                    if it.get("post"):
                        posts.append(it["post"])
    return posts, info


def balasan_dari_html(html):
    """Balasan langsung yang di-prefetch di halaman post (±15 teratas)."""
    out = []
    for b in blok_json(html):
        for dr in telusuri(b, "direct_replies"):
            for e in (dr or {}).get("edges") or []:
                for pe in (((e.get("node") or {}).get("posts")) or {}).get("edges") or []:
                    if (pe.get("node") or {}).get("pk"):
                        out.append(pe["node"])
    return out


def variabel_cari(html):
    """Variabel query pencarian yang dipakai halaman (berisi relay provider)."""
    m = re.search(r'"queryID":"\d+","variables":(\{"meta_place_id".*?\}),"queryName":"BarcelonaSearchResultsQuery"', html)
    return json.loads(m.group(1)) if m else None


def parse_post(p, sumber=""):
    u = p.get("user") or {}
    t = p.get("taken_at")
    w = datetime.fromtimestamp(int(t), WIB) if t else None
    info = p.get("text_post_app_info") or {}
    teks = (p.get("caption") or {}).get("text") or ""
    balas_ke = ((info.get("reply_to_author") or {}).get("username")) or ""
    return {
        "post_id": str(p.get("pk") or p.get("id")),
        "kode": p.get("code"),
        "url": f"https://www.threads.com/@{u.get('username')}/post/{p.get('code')}",
        "tanggal": w.strftime("%Y-%m-%d") if w else "",
        "waktu_wib": w.strftime("%Y-%m-%d %H:%M") if w else "",
        "username": u.get("username", ""),
        "user_id": str(u.get("pk") or u.get("id") or ""),
        "verified": bool(u.get("is_verified")),
        "teks": teks,
        "likes": int(p.get("like_count") or 0),
        "balasan": int(info.get("direct_reply_count") or 0),
        "repost": int(info.get("repost_count") or 0),
        "quote": int(info.get("quote_count") or 0),
        "is_reply": bool(info.get("is_reply")),
        "balas_ke": balas_ke,
        "mentions": ";".join(sorted(set(re.findall(r"@([\w.]{2,30})", teks)))),
        "sumber": sumber,
    }
