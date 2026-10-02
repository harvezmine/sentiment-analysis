#!/usr/bin/env python3
"""Tahap 12: Social Network Analysis (SNA) — gaya Drone Emprit.

Dua graf yang sengaja DIPISAH:

  sosial : siapa berinteraksi dengan siapa di media sosial
           X         penulis -> akun yang di-mention / dibalas
           YouTube   komentator -> kanal;  pembalas -> komentator induk
           Instagram komentator -> pemilik post;  pembalas -> komentator induk;
                     pemilik post -> akun yang di-mention di caption
  berita : media -> aktor/lembaga yang disebut di artikel (ko-mention)

Versi sebelumnya mencampur keduanya dan 93% sisinya berasal dari berita,
sehingga peta yang tampak adalah "media menyebut lembaga", bukan percakapan
publik — itulah sebabnya visualnya tidak menyimpulkan apa-apa.

Setiap sisi di graf sosial membawa SENTIMEN dan EMOSI (Plutchik) dari unggahan
yang membentuknya, sehingga peta bisa diwarnai "SNA by sentiment" dan
"SNA by emotion". Tiap klaster diringkas: tokoh utama, komposisi sentimen &
emosi, narasi, kata khas, contoh unggahan. Kesimpulan kurasi (nama klaster +
butir narasi) dibaca dari data/sna_narasi.json bila tersedia.

Tata letak: ForceAtlas2 (algoritma yang sama dengan Gephi / Drone Emprit).

Output: data/sna.json
"""
import csv
import json
import math
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict

import networkx as nx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from konteks import T, DATA, SLUG  # noqa: E402
import label_ai  # noqa: E402
from label_teks import EMOSI8, klasifikasi as _klasifikasi  # noqa: E402
from tanggal_yt import acuan_file, dari_relatif, video_relevan  # noqa: E402
from label_teks import NARASI as NARASI_BAWAAN  # noqa: E402
# Laporan per periode: SNA_DARI / SNA_SAMPAI mempersempit jendela topik, SNA_KELUAR menunjuk
# folder hasil (bawaan: folder data topik, yaitu graf seluruh periode yang dipakai dashboard).
KELUAR = os.environ.get("SNA_KELUAR") or DATA
os.makedirs(KELUAR, exist_ok=True)
OUT = os.path.join(KELUAR, "sna.json")
OUT_TEKS = os.path.join(KELUAR, "sna_teks.json")   # isi unggahan per sisi, dimuat saat pencarian
OUT_AKUN = os.path.join(KELUAR, "sna_akun.json")   # profil akun per sentimen (untuk laporan)
KURASI = os.path.join(DATA, "sna_narasi.json")
TEKS_PER_SISI = 6          # unggahan yang disimpan per sisi untuk pencarian isi
TEKS_MAKS = 280            # karakter per unggahan

# Aktor yang disebut di unggahan (T.AKTOR), dipakai filter "aktor" di peta
AKTOR_RX = {nama: re.compile(pola, re.I) for nama, pola in T.AKTOR.items()}


def aktor_disebut(teks):
    return [nama for nama, rx in AKTOR_RX.items() if rx.search(teks or "")]


# Daftar tetap untuk filter di peta: sisi menyimpan indeks, bukan nama, agar file ringkas.
# Narasi media sosial (NARASI) dan berita (TOPIK_BERITA) digabung; di Virgo keduanya berbeda.
NARASI_DAFTAR = list(dict.fromkeys(list((T.NARASI or NARASI_BAWAAN).keys())
                                   + list((T.TOPIK_BERITA or {}).keys())))
AKTOR_DAFTAR = list(T.AKTOR.keys())
_NI = {n: i for i, n in enumerate(NARASI_DAFTAR)}
_AI = {n: i for i, n in enumerate(AKTOR_DAFTAR)}


def klasifikasi(teks):
    """Label dengan narasi topik aktif."""
    return _klasifikasi(teks, narasi=T.NARASI, aturan=getattr(T, "ATURAN", None))

MAKS_SIMPUL = 3000        # sama dengan batas tampilan Drone Emprit
MIN_KOMPONEN = 3          # komponen lebih kecil dari ini hanya menambah bising
N_KLASTER = 8             # klaster yang diringkas
JATAH_PLATFORM = 250      # simpul minimum per platform di graf yang ditampilkan
FA2_ITERASI = 180

KODE = {"X (Twitter)": "x", "YouTube": "yt", "Instagram": "ig", "Threads": "th"}

STOP = set("""
yang di ke dari dan atau untuk pada dengan ini itu adalah akan telah sudah dalam
tidak ada juga sebagai oleh karena saat saya kami kita mereka dia para lebih bisa
dapat masih hingga setelah sebelum antara serta agar bahwa apa siapa kapan mengapa
bagaimana tak pun lah nya kah per kepada terhadap tentang secara namun tetapi jika
kalau maka sehingga satu dua tiga orang hari kata ujar tutur sebut jelas terkait
https http com amp yg gak ga dg utk dr krn sdh nih tuh aja banget kok sih deh dong
lagi kan jadi mau udah gue lu kalo sama buat biar semua banyak sangat karna emang
the and for you with this that are was
semoga allah ini itu tuh aku kamu kau mas mbak pak bu bapak ibu bang ada yaa
""".split()) | set(T.STOP)


# ------------------------------------------------------------------ baca
def _jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


AWAL = max(T.JENDELA[0], os.environ.get("SNA_DARI") or T.JENDELA[0])
AKHIR = min(T.JENDELA[1], os.environ.get("SNA_SAMPAI") or T.JENDELA[1])
# nama dan catatan klaster kurasi ditulis untuk seluruh periode; graf periode lain memakai nama otomatis
PERIODE_PENUH = (AWAL, AKHIR) == tuple(T.JENDELA)


def _dalam(tgl):
    """Hanya interaksi di jendela topik, sama dengan dashboard (tanpa tanggal = dibuang)."""
    t = str(tgl or "")[:10]
    return bool(t) and AWAL <= t <= AKHIR


def _ia(asal, tujuan, jenis, platform, teks, lab, likes=0, url="", aktor=None):
    """Satu interaksi = satu calon sisi, lengkap dengan label unggahannya.
    ns = semua narasi yang cocok, ak = aktor yang disebut (untuk filter di peta).
    Label AI topik (bila aktif) menggantikan sentimen & emosi; konten yang ditandai tidak relevan
    menghasilkan None dan dibuang pemanggil."""
    if platform != "berita":
        lab = label_ai.terapkan(SLUG, teks, lab)
        if lab is None:
            return None
    ns = [x.strip() for x in str(lab.get("narasi") or "").split(";") if x.strip()]
    return {"a": asal, "b": tujuan, "j": jenis, "p": platform,
            "s": lab["sentimen"], "e": lab["emosi8"],
            "n": lab.get("narasi_utama") or "Lainnya", "ns": ns,
            "ak": aktor if aktor is not None else aktor_disebut(teks),
            "t": teks, "l": int(likes or 0), "u": url}


def interaksi_x():
    out = []
    for r in _jsonl(os.path.join(DATA, "x", "tweets_labeled.jsonl")):
        if r.get("relevan") == 0 or not _dalam(r.get("tanggal")):
            continue
        asal = (r.get("username") or "").strip()
        if not asal:
            continue
        lab = {"sentimen": r.get("sentimen", "netral"),
               "emosi8": r.get("emosi8") or klasifikasi(r.get("teks", ""))["emosi8"],
               "narasi_utama": r.get("narasi_utama"), "narasi": r.get("narasi")}
        tujuan = {}
        for m in str(r.get("mentions") or "").split(";"):
            m = m.strip()
            if m:
                tujuan[m.lower()] = (m, "mention")
        rt = (r.get("reply_to") or "").strip()
        if rt:
            tujuan[rt.lower()] = (rt, "balasan")    # balasan menimpa mention ganda
        for low, (nama, jenis) in tujuan.items():
            if low != asal.lower():
                out.append(_ia("x:" + asal, "x:" + nama, jenis, "x", r.get("teks", ""),
                               lab, r.get("likes"), r.get("url", "")))
    return out


_AT = re.compile(r"^[\s​\xa0]*(@[\w.\-]{2,40})")


def interaksi_youtube():
    fk = os.path.join(DATA, "yt", "komentar.jsonl")
    rows = _jsonl(fk)
    penulis = {r["komentar_id"]: (r.get("penulis") or "").strip() for r in rows}
    rel, acuan = video_relevan(os.path.join(DATA, "yt")), acuan_file(fk)
    out = []
    for r in rows:
        asal = (r.get("penulis") or "").strip()
        teks = r.get("teks") or ""
        if not asal or rel.get(str(r.get("video_id")), 1) == 0:
            continue
        if not _dalam(dari_relatif(r.get("terbit_relatif"), acuan)):
            continue
        lab = klasifikasi(teks)
        if r.get("level") == 1:
            # balasan: sasaran = @handle di awal teks bila ada (membalas
            # sesama pembalas), selain itu penulis komentar induk
            m = _AT.match(teks)
            tujuan = m.group(1) if m else penulis.get(r["komentar_id"].split(".")[0], "")
            jenis = "balasan"
        else:
            tujuan, jenis = (r.get("kanal") or "").strip(), "komentar"
        if tujuan and tujuan != asal:
            out.append(_ia("yt:" + asal, "yt:" + tujuan, jenis, "yt", teks, lab,
                           r.get("likes"), r.get("video_url", "")))
    return out


def interaksi_instagram():
    out = []
    for p in _jsonl(os.path.join(DATA, "ig", "posts.jsonl")):
        if not p.get("relevan") or not _dalam(p.get("tanggal")):
            continue
        lab = klasifikasi(p.get("caption", ""))
        pemilik = p.get("username", "")
        tujuan = {m for m in (p.get("mentions") or "").split(";") if m}
        tujuan |= {k for k in (p.get("kolaborator") or "").split(";") if k}
        for m in tujuan:
            if m != pemilik:
                out.append(_ia("ig:" + pemilik, "ig:" + m, "mention", "ig",
                               p.get("caption", ""), lab, p.get("likes"), p.get("url", "")))
    for r in _jsonl(os.path.join(DATA, "ig", "komentar.jsonl")):
        asal, teks = r.get("username", ""), r.get("teks", "")
        if not asal or not _dalam(r.get("tanggal")):
            continue
        lab = klasifikasi(teks)
        if r.get("level") == 1:
            m = _AT.match(teks)
            tujuan = m.group(1).lstrip("@") if m else r.get("balas_ke", "")
            jenis = "balasan"
        else:
            tujuan, jenis = r.get("pemilik_post", ""), "komentar"
        if tujuan and tujuan != asal:
            out.append(_ia("ig:" + asal, "ig:" + tujuan, jenis, "ig", teks, lab,
                           r.get("likes"), f"https://www.instagram.com/p/{r.get('kode')}/"))
    return out


def interaksi_threads():
    out = []
    induk = set()
    for nama in ("posts.jsonl", "balasan.jsonl"):
        for r in _jsonl(os.path.join(DATA, "threads", nama)):
            if nama == "posts.jsonl":
                if not r.get("relevan"):
                    continue
                induk.add(str(r.get("post_id")))
            elif r.get("induk_id") and str(r["induk_id"]) not in induk:
                continue                          # balasan mewarisi relevansi post induk
            if not _dalam(r.get("tanggal")):
                continue
            asal, teks = r.get("username", ""), r.get("teks", "")
            if not asal:
                continue
            lab = klasifikasi(teks)
            tujuan = {m: "mention" for m in (r.get("mentions") or "").split(";") if m}
            if r.get("balas_ke"):
                tujuan[r["balas_ke"]] = "balasan"
            for t, jenis in tujuan.items():
                if t != asal:
                    out.append(_ia("th:" + asal, "th:" + t, jenis, "th", teks, lab,
                                   r.get("likes"), r.get("url", "")))
    return out


def interaksi_berita():
    f = os.path.join(DATA, "articles_clean.csv")
    if not os.path.exists(f):
        return []
    csv.field_size_limit(10 ** 8)
    out = []
    netral = {"sentimen": "netral", "emosi8": "netral", "narasi_utama": None}
    with open(f, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            media = (row.get("media") or "").strip()
            if not media or not _dalam(row.get("tanggal")):
                continue
            lab = dict(netral, narasi_utama=row.get("topik_utama") or "Lainnya",
                       narasi=row.get("topik") or "")
            for a in str(row.get("aktor") or "").split(";"):
                a = a.strip()
                if a:
                    out.append(_ia("media:" + media, "aktor:" + a, "sebut", "berita",
                                   row.get("judul", ""), lab, 0, row.get("url", ""), aktor=[a]))
    return out


# ---------------------------------------------------------------- metrik
def pagerank_manual(G, alpha=0.85, iterasi=100, toleransi=1e-9):
    """PageRank berbobot dengan power iteration.

    Ditulis manual karena nx.pagerank pada networkx 3.x membutuhkan SciPy,
    dan SciPy adalah dependensi terkompilasi yang tidak sepadan hanya untuk
    satu metrik. Dangling node (tanpa sisi keluar) menyebar massanya merata.
    """
    n = G.number_of_nodes()
    if n == 0:
        return {}
    simpul = list(G.nodes())
    idx = {v: i for i, v in enumerate(simpul)}
    keluar = [0.0] * n
    tetangga = [[] for _ in range(n)]
    for a, b, d in G.edges(data=True):
        w = float(d.get("weight", 1.0))
        i, j = idx[a], idx[b]
        tetangga[i].append((j, w))
        keluar[i] += w
    r = [1.0 / n] * n
    for _ in range(iterasi):
        baru = [(1.0 - alpha) / n] * n
        dangling = 0.0
        for i in range(n):
            if keluar[i] == 0.0:
                dangling += r[i]
                continue
            bagi = alpha * r[i] / keluar[i]
            for j, w in tetangga[i]:
                baru[j] += bagi * w
        if dangling:
            tambah = alpha * dangling / n
            baru = [x + tambah for x in baru]
        selisih = sum(abs(baru[i] - r[i]) for i in range(n))
        r = baru
        if selisih < toleransi:
            break
    return {simpul[i]: r[i] for i in range(n)}


def _dominan(c, kecuali=None):
    for k, _ in c.most_common():
        if k != kecuali:
            return k
    return kecuali or "netral"


def _pct(c, k):
    t = sum(c.values())
    return round(100.0 * c.get(k, 0) / t, 1) if t else 0.0


def _kata_khas(ias, teks_semua_cnt, total_semua, n=8):
    """Kata yang frekuensinya di klaster jauh di atas rata-rata seluruh graf
    (rasio log-odds sederhana) — bukan sekadar kata paling sering.

    Dihitung per AKUN unik, bukan per unggahan: satu akun yang mengulang kata
    yang sama belasan kali ("baptizo", "magabut") tidak boleh jadi penanda
    klaster."""
    per_akun = defaultdict(set)
    for i in ias:
        for w in re.findall(r"[a-z][a-z']{3,}", i["t"].lower()):
            if w not in STOP:
                per_akun[w].add(i["a"])
    c = Counter({w: len(a) for w, a in per_akun.items()})
    tot = max(sum(c.values()), 1)
    skor = {}
    # ambang >=5 unggahan: kata yang muncul 3–4 kali di klaster kecil hampir
    # selalu salah ketik atau kata langka, bukan penanda narasi
    for w, k in c.items():
        if k < 5:
            continue
        p1 = (k + 1) / (tot + 1000)
        p0 = (teks_semua_cnt.get(w, 0) + 1) / (total_semua + 1000)
        rasio = p1 / p0
        if rasio >= 1.5:
            skor[w] = math.log(rasio) * k
    return [w for w, _ in sorted(skor.items(), key=lambda kv: -kv[1])[:n]]


# ------------------------------------------------------------ bangun graf
def bangun(interaksi, maks_simpul, iterasi=FA2_ITERASI):
    agg = {}
    for ia in interaksi:
        k = (ia["a"], ia["b"])
        e = agg.get(k)
        if e is None:
            e = agg[k] = {"w": 0, "s": Counter(), "e": Counter(), "j": Counter(),
                          "p": ia["p"], "ns": Counter(), "ak": Counter(), "t": {}}
        e["w"] += 1
        e["s"][ia["s"]] += 1
        e["e"][ia["e"]] += 1
        e["j"][ia["j"]] += 1
        e["ns"].update(ia.get("ns") or [])
        e["ak"].update(ia.get("ak") or [])
        t = re.sub(r"\s+", " ", ia.get("t") or "").strip()[:TEKS_MAKS]
        if t:                                     # teks unik, yang paling disukai didahulukan
            e["t"][t] = max(e["t"].get(t, 0), ia.get("l", 0))

    G = nx.DiGraph()
    for (a, b), e in agg.items():
        G.add_edge(a, b, weight=e["w"])
    total_ia, total_akun = len(interaksi), G.number_of_nodes()

    # --- pangkas: hub + jembatan dulu, lalu daun milik hub terbesar
    U = G.to_undirected()
    for u, v in U.edges():
        U[u][v]["weight"] = (G[u][v]["weight"] if G.has_edge(u, v) else 0) + \
                            (G[v][u]["weight"] if G.has_edge(v, u) else 0)
    deg = dict(U.degree(weight="weight"))
    nbmax = {n: max((deg[m] for m in U[n]), default=0) for n in U}
    urut = sorted(U, key=lambda n: (U.degree(n) < 2, -deg[n], -nbmax[n], n))
    # Jatah minimum per platform: komentator sekali-lewat diprioritaskan menurut
    # besar hub-nya, dan hub YouTube (ratusan komentator) menghabiskan jatah
    # sebelum giliran Instagram/Threads (puluhan). Tiap platform dijamin
    # JATAH_PLATFORM simpul teratasnya, sisanya menurut peringkat global.
    per_plat = defaultdict(list)
    for n in urut:
        per_plat[n.partition(":")[0]].append(n)
    simpan = set()
    for daftar in per_plat.values():
        simpan.update(daftar[:JATAH_PLATFORM])
    for n in urut:
        if len(simpan) >= maks_simpul:
            break
        simpan.add(n)
    U = U.subgraph(simpan).copy()
    U.remove_nodes_from([n for c in list(nx.connected_components(U))
                         if len(c) < MIN_KOMPONEN for n in c])
    G = G.subgraph(U.nodes).copy()
    # Urutan kanonis: Python mengacak urutan set per proses (hash randomization),
    # sehingga urutan simpul/sisi -- dan hasil Louvain -- berubah tiap run walau
    # datanya sama. Graf disusun ulang dalam urutan terurut agar hasil stabil.
    Uc = nx.Graph()
    Uc.add_nodes_from(sorted(U.nodes))
    Uc.add_edges_from(sorted(((min(a, b), max(a, b), d) for a, b, d in U.edges(data=True)),
                             key=lambda e: (e[0], e[1])))
    U = Uc
    Gc = nx.DiGraph()
    Gc.add_nodes_from(sorted(G.nodes))
    Gc.add_edges_from(sorted(G.edges(data=True), key=lambda e: (e[0], e[1])))
    G = Gc
    print(f"  graf: {total_akun} akun / {total_ia} interaksi -> "
          f"{U.number_of_nodes()} simpul, {U.number_of_edges()} sisi", flush=True)
    if not U.number_of_nodes():
        return None

    # --- metrik
    pr = pagerank_manual(G)
    try:
        btw = nx.betweenness_centrality(U, k=min(300, U.number_of_nodes()), seed=42)
    except Exception:
        btw = {n: 0.0 for n in U}
    try:
        import community as community_louvain
        part = community_louvain.best_partition(U, weight="weight", random_state=42)
    except Exception:
        part = {n: i for i, c in enumerate(nx.connected_components(U)) for n in c}
    # nomor klaster diurutkan menurut ukuran -> warna konsisten antar-run
    ukuran = Counter(part.values())
    ganti = {k: i for i, (k, _) in enumerate(ukuran.most_common())}
    part = {n: ganti[k] for n, k in part.items()}

    # --- tata letak
    # spring_layout tidak dipakai: di atas 500 simpul ia butuh SciPy.
    # Mode LinLog + scaling besar: graf ini berupa banyak "bintang" (kanal +
    # komentatornya); setelan bawaan (scaling 2) memampatkannya jadi satu
    # gumpalan, sedangkan LinLog memisahkan klaster seperti peta Gephi.
    t0 = time.time()
    awal = _posisi_awal(part)
    pos = nx.forceatlas2_layout(U, pos=awal, max_iter=iterasi, scaling_ratio=30,
                                gravity=0.5, linlog=True, weight="weight", seed=42)
    for n, (x, y) in pos.items():          # LinLog bisa membagi nol -> NaN
        if not (math.isfinite(x) and math.isfinite(y)):
            pos[n] = awal[n]
    print(f"  tata letak ForceAtlas2: {time.time() - t0:.0f} dtk", flush=True)
    return G, U, agg, pr, btw, part, pos, total_ia, total_akun


def _posisi_awal(part):
    """Pusat klaster disebar melingkar sebagai titik awal; ForceAtlas2 lalu
    merapikan dari sana — konvergen lebih cepat dan klaster tidak menumpuk."""
    rnd = random.Random(42)
    anggota = defaultdict(list)
    for n, k in part.items():
        anggota[k].append(n)
    urut = sorted(anggota.items(), key=lambda kv: -len(kv[1]))
    pos, m = {}, max(len(urut), 1)
    besar = max(len(urut[0][1]), 1) if urut else 1
    for i, (k, nodes) in enumerate(urut):
        sudut = 2 * math.pi * i * 0.618
        jari = 30 * math.sqrt(i / m + 0.02)
        cx, cy = jari * math.cos(sudut), jari * math.sin(sudut)
        sebar = 2 + 10 * math.sqrt(len(nodes) / besar)
        for v in nodes:
            pos[v] = (cx + rnd.uniform(-sebar, sebar), cy + rnd.uniform(-sebar, sebar))
    return pos


def ekspor(hasil, interaksi, kurasi, nama_graf):
    G, U, agg, pr, btw, part, pos, total_ia, total_akun = hasil
    simpul_id = list(U.nodes)
    idx = {n: i for i, n in enumerate(simpul_id)}

    # label per simpul dari semua interaksi yang menyentuhnya
    s_node, e_node = defaultdict(Counter), defaultdict(Counter)
    for ia in interaksi:
        for n in (ia["a"], ia["b"]):
            if n in idx:
                s_node[n][ia["s"]] += 1
                e_node[n][ia["e"]] += 1

    d_in = dict(G.in_degree(weight="weight"))
    d_out = dict(G.out_degree(weight="weight"))
    simpul = []
    for n in simpul_id:
        x, y = pos[n]
        plat, _, label = n.partition(":")
        sc, ec = s_node[n], e_node[n]
        simpul.append({
            "id": n, "l": label, "p": plat,
            "x": round(float(x), 3), "y": round(float(y), 3),
            "i": int(d_in.get(n, 0)), "o": int(d_out.get(n, 0)),
            "pr": round(pr.get(n, 0) * 1000, 4),
            "b": round(btw.get(n, 0), 5),
            "k": part[n],
            # netral mendominasi hampir semua hub; warna simpul memakai sentimen
            # beropini yang dominan asal porsinya cukup (>=30%) agar peta terbaca
            "s": _dominan(sc, "netral") if (sc.get("negatif", 0) + sc.get("positif", 0)) * 10
                 >= sum(sc.values()) * 3 else "netral",
            "e": _dominan(ec, "netral") if sum(v for k, v in ec.items() if k != "netral") * 3
                 >= sum(ec.values()) else "netral",
            "sn": [sc.get("negatif", 0), sc.get("netral", 0), sc.get("positif", 0)],
        })

    sisi, teks_sisi = [], []
    for a, b in G.edges():
        e = agg[(a, b)]
        d = {"a": idx[a], "b": idx[b], "w": e["w"], "p": e["p"],
             "s": _dominan(e["s"]),
             "e": _dominan(e["e"], "netral") if e["e"].get("netral", 0) < e["w"]
             else "netral",
             "j": _dominan(e["j"])}
        ns = sorted(_NI[n] for n in e["ns"] if n in _NI)
        ak = sorted(_AI[n] for n in e["ak"] if n in _AI)
        if ns:
            d["n"] = ns
        if ak:
            d["ak"] = ak
        sisi.append(d)
        teks_sisi.append([t for t, _ in sorted(e["t"].items(), key=lambda kv: -kv[1])[:TEKS_PER_SISI]])

    # --- ringkasan klaster
    ia_klaster = defaultdict(list)
    for ia in interaksi:
        if ia["a"] in part and ia["b"] in part:
            ia_klaster[part[ia["a"]]].append(ia)
    semua_cnt, total_kata = Counter(), 0
    for ia in interaksi:
        ws = set(re.findall(r"[a-z][a-z']{3,}", ia["t"].lower())) - STOP
        semua_cnt.update(ws)
        total_kata += len(ws)
    ukuran = Counter(part.values())
    klaster = []
    # 8 klaster terbesar + klaster terbesar dari platform yang belum terwakili
    # (maks 2): tanpa ini Threads/X tenggelam di bawah klaster kolom komentar
    # YouTube yang jauh lebih besar, padahal karakter percakapannya berbeda.
    plat_k = defaultdict(Counter)
    for n in simpul_id:
        plat_k[part[n]][n.partition(":")[0]] += 1
    dominan = {k: c.most_common(1)[0][0] for k, c in plat_k.items()}
    pilih = [k for k, _ in ukuran.most_common(N_KLASTER)]
    terwakili = {dominan[k] for k in pilih}
    for k, n in ukuran.most_common():
        if len(pilih) >= N_KLASTER + 2:
            break
        if n >= 30 and dominan[k] not in terwakili:
            pilih.append(k)
            terwakili.add(dominan[k])
    kurasi_terpakai = set()
    for k in pilih:
        n_simpul = ukuran[k]
        anggota = [n for n in simpul_id if part[n] == k]
        tokoh = sorted(anggota, key=lambda n: -(d_in.get(n, 0) * 2 + d_out.get(n, 0)))[:6]
        ias = ia_klaster.get(k, [])
        sc = Counter(i["s"] for i in ias)
        ec = Counter(i["e"] for i in ias)
        nc = Counter(i["n"] for i in ias if i["n"] and i["n"] != "Lainnya")
        pc = Counter(i["p"] for i in ias)
        ec_non = Counter({e: v for e, v in ec.items() if e != "netral"})
        contoh, lihat = [], set()
        for i in sorted(ias, key=lambda i: -i["l"]):
            kunci = i["t"][:60]
            if len(i["t"]) < 25 or kunci in lihat:
                continue
            lihat.add(kunci)
            contoh.append({"oleh": i["a"].partition(":")[2], "p": i["p"],
                           "t": i["t"][:260], "s": i["s"], "e": i["e"], "l": i["l"],
                           "u": i["u"]})
            if len(contoh) == 4:
                break
        ringkas = {
            "k": k, "simpul": n_simpul, "interaksi": len(ias),
            "persen": round(100.0 * n_simpul / max(len(simpul_id), 1), 1),
            "tokoh": [t.partition(":")[2] for t in tokoh],
            "tokoh_id": tokoh,
            "platform": {p: v for p, v in pc.most_common()},
            "sentimen": {s: _pct(sc, s) for s in ("negatif", "netral", "positif")},
            "emosi": {e: _pct(ec, e) for e in EMOSI8 + ["netral"]},
            "emosi_utama": [e for e, _ in ec_non.most_common(3)],
            "narasi": [n for n, _ in nc.most_common(3)],
            "kata": _kata_khas(ias, semua_cnt, total_kata),
            "contoh": contoh,
        }
        ringkas["nama_auto"], ringkas["butir_auto"] = _narasi_otomatis(ringkas)
        # dicocokkan ke 3 tokoh teratas (hub bisa bergeser saat data bertambah);
        # satu entri kurasi hanya dipakai satu klaster
        kunci_kur = next((t for t in tokoh[:3] if t in kurasi and t not in kurasi_terpakai), None)
        kur = kurasi.get(kunci_kur) if kunci_kur else None
        if kunci_kur:
            kurasi_terpakai.add(kunci_kur)
        if kur:
            ringkas["nama"], ringkas["butir"] = kur.get("nama"), kur.get("butir", [])
            ringkas["kurasi"] = kur.get("kurasi", "")
        klaster.append(ringkas)

    sc_all = Counter(i["s"] for i in interaksi if i["a"] in idx and i["b"] in idx)
    ec_all = Counter(i["e"] for i in interaksi if i["a"] in idx and i["b"] in idx)
    statistik = {
        "interaksi_total": total_ia, "akun_total": total_akun,
        "simpul": len(simpul), "sisi": len(sisi),
        "kepadatan": round(nx.density(U), 5),
        "derajat_rata": round(2.0 * U.number_of_edges() / max(U.number_of_nodes(), 1), 2),
        "komunitas": len(ukuran),
        "sentimen": {s: _pct(sc_all, s) for s in ("positif", "netral", "negatif")},
        "emosi": {e: _pct(ec_all, e) for e in EMOSI8 + ["netral"]},
    }
    wawasan = _wawasan(simpul, klaster, statistik, part, U) if nama_graf == "sosial" else []
    return {"simpul": simpul, "sisi": sisi, "_teks": teks_sisi, "klaster": klaster,
            "statistik": statistik, "wawasan": wawasan}


# ------------------------------------------------------- narasi otomatis
NAMA_EMOSI = {"marah": "marah", "jijik": "muak/sinis", "takut": "takut", "sedih": "duka",
              "terkejut": "terkejut", "percaya": "percaya/apresiasi", "senang": "lega/syukur",
              "antisipasi": "harap/menanti", "netral": "netral"}
# Istilah bawaan khas musibah (Virgo); topik lain bisa menggantinya lewat T.ISTILAH
ISTILAH = {"nada_positif": "suportif/empatik", "kantong_positif": "empati/dukungan"}
ISTILAH.update({k: v for k, v in getattr(T, "ISTILAH", {}).items() if k != "emosi"})
NAMA_EMOSI.update(getattr(T, "ISTILAH", {}).get("emosi", {}))


def _nada(sen):
    neg, pos = sen.get("negatif", 0), sen.get("positif", 0)
    if neg >= 30 and neg > pos * 1.2:
        return "kritis"
    if pos >= 30 and pos > neg * 1.5:
        return ISTILAH["nada_positif"]
    if neg + pos < 30:
        return "informatif"
    return "campuran"


def _k(x, d=1):
    """Angka desimal gaya Indonesia (koma)."""
    return f"{x:.{d}f}".replace(".", ",")


def _narasi_otomatis(c):
    """Nama & butir klaster dari angka. Sengaja deskriptif, bukan interpretatif —
    interpretasi manusia ditaruh di data/sna_narasi.json."""
    hub = c["tokoh"][0] if c["tokoh"] else "?"
    nama = f"Percakapan di sekitar {hub.lstrip('@')}"
    plat = {"x": "X", "yt": "YouTube", "ig": "Instagram", "th": "Threads", "berita": "Berita"}
    platform = ", ".join(plat.get(p, p) for p in c["platform"]) or "-"
    sen = c["sentimen"]
    butir = [
        f"Node sentral: {', '.join(c['tokoh'][:3])}. {c['simpul']} akun ({_k(c['persen'])}% graf), "
        f"{c['interaksi']} interaksi dari {platform}.",
        f"Sentimen interaksi: negatif {_k(sen['negatif'])}%, positif {_k(sen['positif'])}%, netral {_k(sen['netral'])}%.",
    ]
    if c["emosi_utama"]:
        butir.append("Emosi utama: " + ", ".join(
            f"{NAMA_EMOSI.get(e, e)} {_k(c['emosi'][e])}%" for e in c["emosi_utama"]) + ".")
    if c["narasi"]:
        butir.append("Isu: " + ", ".join(c["narasi"]) + ".")
    if c["kata"]:
        butir.append("Kata khas: " + ", ".join(c["kata"][:7]) + ".")
    return nama, butir


def _wawasan(simpul, klaster, st, part, U):
    """Ringkasan tingkat graf yang bisa dibaca tanpa melihat graf."""
    out = []
    total_in = sum(s["i"] for s in simpul) or 1
    top = sorted(simpul, key=lambda s: -s["i"])[:5]
    share = 100.0 * sum(s["i"] for s in top) / total_in
    out.append({
        "judul": "In-degree terpusat pada lima akun" if share >= 40 else "In-degree tersebar",
        "isi": f"Lima akun dengan in-degree tertinggi ({', '.join(s['l'] for s in top)}) menerima {_k(share)}% "
               f"dari semua interaksi masuk.",
    })
    cukup = [c for c in klaster if c["interaksi"] >= 30]
    if cukup:
        neg = max(cukup, key=lambda c: c["sentimen"]["negatif"])
        out.append({
            "judul": f"Klaster paling negatif: {neg.get('nama') or neg['nama_auto']}",
            "isi": f"{_k(neg['sentimen']['negatif'])}% interaksi di klaster ini negatif, dibanding "
                   f"{_k(st['sentimen']['negatif'])}% di seluruh graf. Node sentral: {', '.join(neg['tokoh'][:3])}"
                   + (f". Isu utama: {', '.join(neg['narasi'][:2])}." if neg["narasi"] else "."),
            "k": neg["k"],
        })
        pos = max(cukup, key=lambda c: c["sentimen"]["positif"])
        if pos["k"] != neg["k"]:
            out.append({
                "judul": f"Klaster paling positif: {pos.get('nama') or pos['nama_auto']}",
                "isi": f"{_k(pos['sentimen']['positif'])}% interaksi positif. Emosi utama: "
                       f"{', '.join(NAMA_EMOSI.get(e, e) for e in pos['emosi_utama'][:2]) or '-'}. "
                       f"Node sentral: {', '.join(pos['tokoh'][:3])}.",
                "k": pos["k"],
            })
        marah = max(cukup, key=lambda c: c["emosi"].get("marah", 0) + c["emosi"].get("jijik", 0))
        nilai = marah["emosi"].get("marah", 0) + marah["emosi"].get("jijik", 0)
        if nilai > 0:
            out.append({
                "judul": "Porsi marah dan muak tertinggi",
                "isi": f"{_k(nilai)}% interaksi di {marah.get('nama') or marah['nama_auto']} bernada marah atau "
                       f"muak, tertinggi di antara klaster dengan minimal 30 interaksi.",
                "k": marah["k"],
            })
    emo = sorted(((e, v) for e, v in st["emosi"].items() if e != "netral"), key=lambda kv: -kv[1])
    if emo:
        out.append({
            "judul": "Emosi di seluruh graf",
            "isi": (lambda t: t[:1].upper() + t[1:])(", ".join(f"{NAMA_EMOSI.get(e, e)} {_k(v)}%" for e, v in emo[:4]))
                   + f". Sisanya ({_k(st['emosi'].get('netral', 0))}%) tanpa emosi yang jelas.",
        })
    jem = sorted(simpul, key=lambda s: -s["b"])[:3]
    ket = []
    for s in jem:
        kl = {part[m] for m in U[s["id"]]} if s["id"] in U else set()
        ket.append(f"{s['l']} (terhubung ke {len(kl)} klaster)")
    if jem and jem[0]["b"] > 0:
        out.append({"judul": "Betweenness tertinggi",
                    "isi": "Akun yang paling sering menjadi penghubung antarklaster: " + ", ".join(ket) + "."})
    return out


def ekspor_akun(interaksi, graf_sosial):
    """Profil akun per sentimen dari SELURUH interaksi (bukan hanya node yang tampil di peta):
    jumlah interaksi yang dikirim dan diterima per sentimen, akun yang paling sering disasar,
    dan akun yang paling sering berinteraksi dengannya. Dipakai bagian penyebar sentimen di laporan."""
    klaster = {n["id"]: n["k"] for n in (graf_sosial or {}).get("simpul", [])}
    akun = defaultdict(lambda: {"out": Counter(), "in": Counter(), "suka": Counter(),
                                "sasaran": defaultdict(Counter), "dari": defaultdict(Counter)})
    for ia in interaksi:
        s_ = ia["s"]
        a, b = akun[ia["a"]], akun[ia["b"]]
        a["out"][s_] += 1
        a["suka"][s_] += ia.get("l", 0)
        a["sasaran"][s_][ia["b"]] += 1
        b["in"][s_] += 1
        b["dari"][s_][ia["a"]] += 1
    out = {}
    for nid, d in akun.items():
        if not (d["out"]["negatif"] or d["out"]["positif"] or d["in"]["negatif"] or d["in"]["positif"]):
            continue
        out[nid] = {
            "k": klaster.get(nid),
            "out": dict(d["out"]), "in": dict(d["in"]), "suka": dict(d["suka"]),
            "sasaran": {s_: c.most_common(8) for s_, c in d["sasaran"].items() if s_ != "netral"},
            "dari": {s_: c.most_common(8) for s_, c in d["dari"].items() if s_ != "netral"},
        }
    json.dump(out, open(OUT_AKUN, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"[sna] profil {len(out)} akun -> {OUT_AKUN} ({os.path.getsize(OUT_AKUN) / 1e6:.1f} MB)")


def main():
    kurasi = {}
    if os.path.exists(KURASI) and PERIODE_PENUH:
        try:
            kurasi = json.load(open(KURASI, encoding="utf-8"))
        except Exception as e:
            print(f"[sna] sna_narasi.json tidak terbaca: {e}")

    print("[sna] membaca interaksi…", flush=True)
    ix, iy, ig, it = interaksi_x(), interaksi_youtube(), interaksi_instagram(), interaksi_threads()
    sosial = [x for x in ix + iy + ig + it if x]
    print(f"  X {len(ix)} · YouTube {len(iy)} · Instagram {len(ig)} · Threads {len(it)}", flush=True)
    berita = interaksi_berita()
    print(f"  Berita {len(berita)}", flush=True)

    hasil = {"dibuat": time.strftime("%Y-%m-%d %H:%M"), "rentang": [AWAL, AKHIR],
             "istilah": {**ISTILAH, "emosi": NAMA_EMOSI},
             "narasi_daftar": NARASI_DAFTAR, "aktor_daftar": AKTOR_DAFTAR}
    print("[sna] graf SOSIAL", flush=True)
    h = bangun(sosial, MAKS_SIMPUL)
    hasil["sosial"] = ekspor(h, sosial, kurasi, "sosial") if h else None
    ekspor_akun(sosial, hasil["sosial"])
    print("[sna] graf BERITA (media -> aktor)", flush=True)
    h = bangun(berita, 700, iterasi=200)
    hasil["berita"] = ekspor(h, berita, {}, "berita") if h else None

    # isi unggahan per sisi dipisah: hanya diunduh peramban saat pengguna mencari isi
    teks = {nama: (hasil[nama] or {}).pop("_teks", []) for nama in ("sosial", "berita")}
    json.dump(teks, open(OUT_TEKS, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(hasil, open(OUT, "w", encoding="utf-8"), ensure_ascii=False,
              separators=(",", ":"))
    print(f"\n[sna] ditulis ke {OUT} ({os.path.getsize(OUT) / 1e6:.1f} MB), "
          f"teks {os.path.getsize(OUT_TEKS) / 1e6:.1f} MB")
    s = hasil["sosial"]
    if s:
        print(f"  statistik: {s['statistik']}")
        print("\n=== KLASTER SOSIAL ===")
        for c in s["klaster"]:
            print(f"  k{c['k']} {c['simpul']:>4} simpul {c['interaksi']:>5} ia | "
                  f"neg {c['sentimen']['negatif']:>4}% pos {c['sentimen']['positif']:>4}% | "
                  f"{','.join(c['emosi_utama'])} | {', '.join(c['tokoh'][:4])}")
            print(f"      kata: {', '.join(c['kata'])}")
        print("\n=== WAWASAN ===")
        for w in s["wawasan"]:
            print(f"  • {w['judul']}: {w['isi']}")


if __name__ == "__main__":
    main()
