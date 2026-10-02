#!/usr/bin/env python3
"""Tahap 4: bersihkan, deduplikasi, dan perkaya dataset artikel.

Menambahkan: tanggal ternormalisasi (WIB), tipe media, topik, aktor yang disebut,
dan skor sentimen baseline berbasis lexicon InSet.
Topik dan aktor diambil dari modul topik aktif (T.TOPIK_BERITA, T.AKTOR),
relevansi dari T.relevan().
Output: data/<topik>/articles_clean.csv / .jsonl  + ringkasan_*.csv
"""
import json, os, re, csv, sys, unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = lambda *p: os.path.join(ROOT, *p)        # path di akar proyek (leksikon)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from konteks import T, D  # noqa: E402   D = folder data topik
WIB = timezone(timedelta(hours=7))

# ----------------------------------------------------------------- lexicon
def load_lex():
    lex = {}
    for f, sign in ((R("lexicon", "inset_positive.tsv"), 1), (R("lexicon", "inset_negative.tsv"), 1)):
        if not os.path.exists(f):
            continue
        with open(f, encoding="utf-8") as fh:
            next(fh, None)
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 2:
                    try:
                        lex[parts[0].strip().lower()] = int(parts[1])
                    except ValueError:
                        pass
    return lex

LEX = load_lex()

# kata domain-spesifik: berita musibah penuh kata negatif "netral-faktual";
# bobot tambahan untuk nada evaluatif (kritik/tuntutan/kelalaian) vs sekadar laporan.
NEG_EVAL = re.compile(
    r"\b(lalai|kelalaian|abai|mengabaikan|kecewa|kecam|mengecam|kritik|mengkritik|protes|"
    r"desak|mendesak|tuntut|menuntut|marah|geram|murka|sorot|menyoroti|buruk|amburadul|"
    r"semrawut|kacau|carut.?marut|bobrok|gagal|kegagalan|lambat|lamban|lelet|telat|"
    r"terlambat|tidak becus|tak becus|janggal|mencurigakan|diduga\s+langgar|melanggar|"
    r"pelanggaran|manipulasi|dimanipulasi|korupsi|pungli|kongkalikong|tutup.?tutupi|"
    r"tidak transparan|tak transparan|minim|kurang|langgar aturan|overload|kelebihan muatan|"
    r"tidak laik|tak laik|kadaluarsa|uzur|tua|karat|bobrok|nekat|serampangan|"
    r"dipertanyakan|ironi|miris|memprihatinkan|tragis|petaka|bencana kemanusiaan|"
    r"copot|pecat|mundur|tanggung jawab siapa|siapa yang bertanggung jawab)\b", re.I)
POS_EVAL = re.compile(
    r"\b(apresiasi|mengapresiasi|terima kasih|berterima kasih|bangga|salut|sigap|"
    r"cepat tanggap|responsif|gerak cepat|optimal|maksimal|berhasil|sukses|"
    r"selamat|diselamatkan|terselamatkan|ditemukan selamat|harapan|bersyukur|syukur|"
    r"lega|solidaritas|gotong royong|bantuan|membantu|peduli|kepedulian|dukungan|"
    r"mendukung|santunan|kompensasi|pulih|pemulihan|transparan|akuntabel|profesional|"
    r"heroik|pahlawan|relawan|donasi|empati|doa|mendoakan)\b", re.I)

TOPICS = T.TOPIK_BERITA
ACTORS = T.AKTOR

NASIONAL = {
    "detik.com", "kompas.com", "kompas.id", "kompas.tv", "cnnindonesia.com", "cnbcindonesia.com",
    "tempo.co", "antaranews.com", "liputan6.com", "tribunnews.com", "okezone.com",
    "republika.co.id", "suara.com", "kumparan.com", "viva.co.id", "sindonews.com",
    "merdeka.com", "jpnn.com", "beritasatu.com", "katadata.co.id", "bisnis.com",
    "medcom.id", "inews.id", "tvonenews.com", "metrotvnews.com", "tirto.id", "kbr.id",
    "mediaindonesia.com", "kontan.co.id", "jawapos.com", "rri.co.id", "idntimes.com",
    "narasi.tv", "koran-jakarta.com", "investor.id", "gatra.com", "validnews.id",
    "rmol.id", "wartaekonomi.co.id", "inilah.com", "fajar.co.id", "timesindonesia.co.id",
}
INTERNASIONAL = {"bbc.com", "dw.com", "voaindonesia.com", "reuters.com", "apnews.com",
                 "channelnewsasia.com", "straitstimes.com", "thejakartapost.com",
                 "jakartaglobe.id", "aljazeera.com", "scmp.com", "abc.net.au", "rfi.fr",
                 "benarnews.org", "arabnews.com", "kyodonews.net", "nhk.or.jp"}


def media_type(dom):
    d = dom.lower().replace("www.", "")
    root = ".".join(d.split(".")[-3:]) if d.endswith((".co.id", ".go.id", ".or.id", ".web.id")) else ".".join(d.split(".")[-2:])
    if ".go.id" in d or "polri.go.id" in d:
        return "Pemerintah/Institusi"
    if root in INTERNASIONAL or d in INTERNASIONAL:
        return "Internasional"
    if root in NASIONAL or d in NASIONAL or any(d.endswith(n) for n in NASIONAL):
        return "Nasional"
    return "Daerah/Lainnya"


def parse_dt(s):
    """Parse aneka format tanggal yang dipakai media Indonesia -> datetime WIB."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if not s:
        return None
    # ISO 8601 (paling umum di JSON-LD / meta tag)
    iso = s.replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(iso)
        return (d.replace(tzinfo=WIB) if d.tzinfo is None else d).astimezone(WIB)
    except Exception:
        pass
    # RFC 2822 (pubDate RSS)
    try:
        from email.utils import parsedate_to_datetime
        d = parsedate_to_datetime(s)
        return (d.replace(tzinfo=WIB) if d.tzinfo is None else d).astimezone(WIB)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
                "%Y/%m/%d %H:%M:%S", "%d-%m-%Y %H:%M", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(s[:len(fmt) + 8].strip(), fmt).replace(tzinfo=WIB)
        except Exception:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, da = int(m[1]), int(m[2]), int(m[3])
        if 2000 <= y <= 2100 and 1 <= mo <= 12 and 1 <= da <= 31:
            try:
                return datetime(y, mo, da, tzinfo=WIB)
            except ValueError:
                return None
    return None


def norm_title(t):
    t = unicodedata.normalize("NFKD", t.lower())
    t = re.sub(r"\s*[-–|]\s*[^-–|]{0,40}$", "", t)   # buang " - Nama Media"
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def sentiment(text):
    """Skor baseline: lexicon InSet + penimbang nada evaluatif. Bukan ground truth."""
    words = re.findall(r"[a-zA-Z']+", text.lower())
    lex_score = sum(LEX.get(w, 0) for w in words)
    n = max(len(words), 1)
    neg_ev = len(NEG_EVAL.findall(text))
    pos_ev = len(POS_EVAL.findall(text))
    score = (lex_score / n) * 10 + (pos_ev - neg_ev) * 0.35
    if score > 0.45:
        label = "positif"
    elif score < -0.45:
        label = "negatif"
    else:
        label = "netral"
    return round(score, 3), label, pos_ev, neg_ev


def artikel_judul_saja(sudah):
    """Artikel yang isinya gagal diambil (mis. RRI di balik verifikasi Cloudflare) tetap
    dihitung dari metadata Google News: judul, media, tanggal. Ditandai hanya_judul
    agar dashboard dan pembaca tahu isinya tidak tersedia."""
    f = D("failed_final.jsonl")
    if not os.path.exists(f):
        return []
    meta = {}
    for nama in ("urls_decoded.jsonl", "urls_native.jsonl"):
        p = D(nama)
        if os.path.exists(p):
            for l in open(p, encoding="utf-8"):
                try:
                    x = json.loads(l)
                except Exception:
                    continue
                if x.get("url"):
                    meta.setdefault(x["url"], x)
    out = []
    for l in open(f, encoding="utf-8"):
        try:
            u = json.loads(l)["url"]
        except Exception:
            continue
        m = meta.get(u)
        if not m or u in sudah or not m.get("title"):
            continue
        judul = re.sub(r"\s+[-–|]\s+[^-–|]{2,45}$", "", m["title"]).strip()
        out.append({"url": u, "source_url": u, "domain": re.sub(r"^www\.", "", u.split("/")[2]),
                    "source_name": m.get("source_name") or "", "title": judul, "published": "",
                    "gnews_pubdate": m.get("pub_date", ""), "description": "", "content": "",
                    "n_chars": 0, "n_words": 0, "hanya_judul": True})
    print(f"[process] + {len(out)} artikel hanya-judul (isi gagal diambil)")
    return out


def main():
    src = D("articles.jsonl")
    rows = []
    for l in open(src, encoding="utf-8"):
        try:
            rows.append(json.loads(l))
        except Exception:
            pass
    print(f"[process] baca {len(rows)} artikel")
    rows += artikel_judul_saja({r.get("source_url") or r.get("url") for r in rows})

    # --- filter relevansi berbasis isi
    keep = []
    for r in rows:
        blob = f"{r.get('title','')} {r.get('description','')} {r.get('content','')}"
        if T.relevan(blob):
            keep.append(r)
    print(f"[process] relevan: {len(keep)} (buang {len(rows)-len(keep)})")

    # --- dedupe judul-domain & judul global near-dup
    seen_t, out = set(), []
    for r in sorted(keep, key=lambda x: -x.get("n_chars", 0)):
        k = (r["domain"], norm_title(r["title"]))
        k2 = norm_title(r["title"])
        if k in seen_t or (len(k2) > 30 and k2 in seen_t):
            continue
        seen_t.add(k); seen_t.add(k2)
        out.append(r)
    print(f"[process] setelah dedupe: {len(out)}")

    # satu media, satu nama: artikel dari mesin pencari media sering tanpa source_name dan
    # jatuh ke nama domain ("gardapapua.com" di samping "Garda Papua"); pakai nama terbanyak
    nama_dom = {}
    for r in out:
        if r.get("source_name"):
            nama_dom.setdefault(r["domain"], Counter())[r["source_name"]] += 1
    nama_dom = {d: c.most_common(1)[0][0] for d, c in nama_dom.items()}

    recs = []
    for r in out:
        d = parse_dt(r.get("published")) or parse_dt(r.get("gnews_pubdate", ""))
        blob = f"{r.get('title','')}. {r.get('description','')}. {r.get('content','')}"
        topics = [t for t, rx in TOPICS.items() if re.search(rx, blob, re.I)]
        actors = [a for a, rx in ACTORS.items() if re.search(rx, blob, re.I)]
        sc, lab, pe, ne = sentiment(blob)
        recs.append({
            "id": f"NEWS{len(recs)+1:05d}",
            "tanggal": d.strftime("%Y-%m-%d") if d else "",
            "waktu_wib": d.strftime("%Y-%m-%d %H:%M") if d else "",
            "jam": d.hour if d else "",
            "media": r.get("source_name") or nama_dom.get(r["domain"]) or r["domain"],
            "domain": r["domain"],
            "tipe_media": media_type(r["domain"]),
            "judul": r["title"],
            "url": r["url"],
            "penulis": r.get("author", ""),
            "rubrik": r.get("section", ""),
            "keywords": r.get("keywords", ""),
            "deskripsi": r.get("description", ""),
            "isi": r.get("content", ""),
            "jml_kata": r.get("n_words", 0),
            "topik": "; ".join(topics),
            "topik_utama": topics[0] if topics else "Lainnya",
            "aktor": "; ".join(actors),
            "skor_sentimen": sc,
            "sentimen_baseline": lab,
            "hanya_judul": bool(r.get("hanya_judul")),
            "n_frasa_positif": pe,
            "n_frasa_negatif": ne,
        })

    df = pd.DataFrame(recs).sort_values("waktu_wib")
    df.to_csv(D("articles_clean.csv"), index=False, quoting=csv.QUOTE_ALL)
    df.to_json(D("articles_clean.jsonl"), orient="records", lines=True, force_ascii=False)
    # versi ringan tanpa isi penuh (untuk dibuka di Excel/Sheets)
    df.drop(columns=["isi"]).to_csv(D("articles_meta.csv"), index=False, quoting=csv.QUOTE_ALL)

    # --- ringkasan
    df[df.tanggal != ""].groupby("tanggal").agg(
        jml_artikel=("id", "count"),
        jml_media=("domain", "nunique"),
        skor_rata=("skor_sentimen", "mean"),
    ).round(3).to_csv(D("ringkasan_harian.csv"))
    df.groupby(["media", "tipe_media"]).agg(
        jml_artikel=("id", "count"), skor_rata=("skor_sentimen", "mean")
    ).round(3).sort_values("jml_artikel", ascending=False).to_csv(D("ringkasan_media.csv"))
    tc = Counter(t for ts in df.topik for t in ts.split("; ") if t)
    pd.DataFrame(tc.most_common(), columns=["topik", "jml_artikel"]).to_csv(D("ringkasan_topik.csv"), index=False)
    ac = Counter(a for as_ in df.aktor for a in as_.split("; ") if a)
    pd.DataFrame(ac.most_common(), columns=["aktor", "jml_disebut"]).to_csv(D("ringkasan_aktor.csv"), index=False)
    df.groupby(["tanggal", "sentimen_baseline"]).size().unstack(fill_value=0).to_csv(D("ringkasan_sentimen_harian.csv"))

    print(f"[process] tulis {len(df)} baris -> {D('articles_clean.csv')}")
    print(df.tipe_media.value_counts().to_string())
    print("\nTop media:\n" + df.media.value_counts().head(15).to_string())
    print("\nSentimen baseline:\n" + df.sentimen_baseline.value_counts().to_string())


if __name__ == "__main__":
    main()
