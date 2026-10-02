"""Tugas AI Analisa Sentimen: pelabelan konten, nama & catatan klaster SNA, draf kesimpulan laporan,
dan draf konfigurasi topik baru. Semua memanggil scripts/ai_klien.py dan mengembalikan data yang
sudah diperiksa (nilai label di luar daftar diganti, id yang hilang diminta ulang, angka di
kesimpulan dicocokkan dengan data).

Hasil AI selalu draf yang ditinjau di halaman Kelola sebelum dipakai, kecuali label sentimen yang
dipakai setelah topik diubah ke "label AI" (setelah divalidasi dengan sampel berlabel manual).
"""
import json
import re

import ai_klien
from label_ai import EMOSI8, SENTIMEN, STANCE

# Aturan gaya untuk semua teks yang akan dibaca manusia (nama klaster, kesimpulan)
GAYA = """Aturan bahasa:
- Bahasa Indonesia yang wajar dan mudah dibaca, seperti tulisan analis manusia. Kalimat pendek. Angka dulu.
- Jangan memakai kiasan atau kata berlebihan: "kantong", "jembatan", "pekat", "cermin", "lanskap", "dinamika",
  "signifikan", "krusial", "menyoroti", "tidak hanya ... tetapi juga", tanda pisah panjang (—).
- Istilah SNA boleh dipakai bila tepat: node, edge, klaster, in-degree, out-degree, betweenness, ego-network.
- Desimal memakai koma (16,4%), ribuan memakai titik (1.408). Daftar memakai koma sebelum "dan".
- Jangan menyebut akun sebagai "buzzer", "pendengung", "akun bayaran", atau "bot". Gambarkan perilakunya
  dengan bukti (teks identik, waktu unggah berdekatan, akun baru, nada seragam).
- Jangan menyebut tujuan pemantauan akun. Jangan menambah fakta atau angka yang tidak ada di data."""


def _konteks_topik(T):
    pihak = []
    aturan = getattr(T, "ATURAN", None) or {}
    for k in ("pihak", "didukung"):
        if aturan.get(k):
            pihak += [x for x in re.split(r"\|", re.sub(r"[\\()?:]|\\b", "", aturan[k])) if 2 < len(x) < 40][:12]
    if not pihak:
        pihak = list(getattr(T, "AKTOR", {}).keys())[:12]
    lede = re.sub(r"\s*Halaman ini [^.]*\.", "", getattr(T, "LEDE", "")).strip()
    return lede, ", ".join(dict.fromkeys(pihak))


# --------------------------------------------------------------- pelabelan konten
RUBRIK = """Definisi label:
sentimen = sikap atau penilaian PENULIS, bukan isi peristiwanya.
- negatif: kritik, kecaman, kemarahan, sindiran atau sinis, tuduhan, keluhan, kekecewaan, ketidakpercayaan,
  penolakan, tuntutan yang menyalahkan pihak tertentu.
- positif: dukungan, pujian, apresiasi, terima kasih, kebanggaan, optimisme, doa atau harapan baik
  ("semoga cepat ditemukan", "semoga lancar", "aamiin").
- netral: berita atau informasi faktual, pertanyaan tanpa sikap, promosi atau ajakan menonton, ucapan duka
  murni tanpa penilaian ("innalillahi", "turut berduka"), teks yang maksudnya tidak jelas.
Catatan: kata peristiwa ("tenggelam", "korban", "demo", "investasi", "groundbreaking") tidak membuat konten
negatif atau positif. Sarkasme dinilai dari maksudnya ("hebat ya, kapal tua diizinkan berlayar" = negatif).
Berita atau kutipan yang hanya melaporkan kritik pihak lain tanpa sikap penulis = netral.
emosi (Plutchik): senang, percaya, takut, terkejut, sedih, jijik (muak, jijik, sinis), marah,
antisipasi (harap, menanti), atau netral bila tidak ada emosi yang jelas.
stance terhadap pihak atau proyek terkait: kritik, dukungan, atau netral.
relevan: true bila konten membahas topik ini, false bila jelas membahas hal lain (salah tangkap kata kunci)."""


# Versi 2 (dipilih lewat scripts/ai_evaluasi.py terhadap 240 konten berlabel manual): selaras dengan rubrik
# dashboard (takut dan sinis = negatif, doa = positif, duka murni = netral), aturan kalimat campuran, definisi
# relevansi yang tegas, dan contoh. Contoh ditulis sendiri, bukan diambil dari sampel uji.
RUBRIK_V2 = """Definisi label (ikuti persis):
sentimen = sikap atau penilaian PENULIS terhadap peristiwa, pihak, atau proyek dalam topik ini.
- negatif: kritik, kecaman, makian, kemarahan, sindiran atau sinis (termasuk tawa mengejek), tuduhan korupsi atau
  kelalaian, keluhan, kekecewaan, ketidakpercayaan atau skeptis ("yakin?", "paling cuma seremoni"), tuntutan yang
  menyalahkan atau mendesak pihak tertentu ("nakhoda harus dihukum", "kenapa diizinkan berlayar"), dan rasa takut
  atau tidak aman ("serem naik kapal", "ngeri").
- positif: dukungan, pujian, apresiasi, terima kasih, kebanggaan, optimisme; doa dan harapan baik untuk korban,
  petugas, atau proyek ("semoga cepat ditemukan", "semoga husnul khotimah", "aamiin"); promosi atau rilis yang
  menyanjung pihak atau proyek ("sigap", "kesempatan emas", "langkah penting").
- netral: berita atau informasi faktual tanpa pujian atau celaan dari penulis; pertanyaan yang tidak menyiratkan
  sikap; permintaan informasi (lowongan, kabar keluarga); ucapan duka atau rasa sedih dan empati tanpa doa dan tanpa
  penilaian ("innalillahi", "turut berduka", "gak kebayang", "😭"); obrolan, iklan jasa, atau teks yang maksudnya tidak jelas.
Kalimat campuran: kritik atau tuntutan ke pihak tertentu mengalahkan doa (negatif); doa atau terima kasih mengalahkan
duka (positif). Kata peristiwa ("tenggelam", "korban", "demo", "investasi", "groundbreaking") tidak menentukan sentimen.
Berita atau rilis yang mengutip pernyataan, komitmen, atau optimisme pejabat ("Presiden menegaskan…", "Gubernur
berkomitmen…", "diharapkan mendorong…") tetap netral; positif hanya bila penulis sendiri memuji atau mengajak
mendukung. Pertanyaan bernada ragu atau mengejek ("mangkrak lagi nggak nih? 😏", "itu termasuk swasembada?") negatif.
emosi (Plutchik): senang, percaya, takut, terkejut, sedih, jijik (muak, jijik, sinis), marah, antisipasi (harap,
menanti), atau netral bila tidak ada emosi yang jelas.
stance terhadap pihak atau proyek terkait: kritik, dukungan, atau netral.
relevan: true bila konten membicarakan topik ini atau peristiwa, pihak, dan isu yang terkait langsung. Konten ini
diambil dari utas, video, dan unggahan tentang topik ini, jadi balasan pendek tanpa topik lain ("setuju 👍", "mantap",
"aamiin", "bangga", "TNI jaya") dan komentar tentang pihak yang terlibat (presiden, menteri, pemda, aparat, perusahaan)
tetap relevan. false hanya bila isinya jelas membahas hal lain: program atau kasus lain (mis. makan bergizi gratis,
ijazah, kasus pidana lain), politik umum yang tidak menyinggung topik, promosi jasa, obrolan pribadi, sapaan perkenalan,
atau permintaan bantuan yang tidak berkaitan."""

CONTOH_LABEL = [
    ("Kapalnya udah tua masih aja dikasih izin, Syahbandar ngapain aja", "negatif", "marah", "kritik", True),
    ("Semoga semua korban segera ditemukan, kuat ya tim SAR 🙏", "positif", "percaya", "dukungan", True),
    ("Innalillahi wa inna ilaihi rojiun 😭", "netral", "sedih", "netral", True),
    ("Ngeri banget, jadi takut naik kapal laut", "negatif", "takut", "netral", True),
    ("Tim gabungan kembali mengevakuasi tiga jenazah pada Sabtu pagi.", "netral", "netral", "netral", True),
    ("Yakin dananya nggak dikorupsi? 😂", "negatif", "jijik", "kritik", True),
    ("Kesempatan emas! Yuk daftar program teknisi untuk putra-putri daerah", "positif", "antisipasi", "dukungan", True),
    ("Bang ada info lowongan di proyek ini?", "netral", "netral", "netral", True),
    ("Tolong pak, anak saya demam, ada yang bisa bantu?", "netral", "sedih", "netral", False),
    ("STOP program makan gratis, alihkan anggarannya ke guru!", "negatif", "marah", "kritik", False),
    ("Menteri menegaskan proyek ini menjadi tonggak kemandirian energi dan membuka ribuan lapangan kerja.",
     "netral", "netral", "netral", True),
    ("Mantap 👍👍", "positif", "senang", "dukungan", True),
    ("Mangkrak lagi nggak nih? 😏", "negatif", "jijik", "kritik", True),
]


def _sistem_label(T, versi="v2"):
    lede, pihak = _konteks_topik(T)
    awal = (f"Kamu pelabel konten media sosial berbahasa Indonesia untuk analisis percakapan publik tentang "
            f"{T.NAMA}. Konteks: {lede}" + (f" Pihak terkait: {pihak}." if pihak else ""))
    bentuk = ('Jawab hanya dalam JSON: {"hasil": [{"id": 1, "s": "negatif|netral|positif", "e": "<emosi>", '
              '"st": "kritik|dukungan|netral", "r": true}]} dengan satu entri untuk setiap id.')
    if versi == "v1":
        return f"{awal}\n\n{RUBRIK}\n\n{bentuk}"
    contoh = "\n".join(f'- "{t}" → s={s}, e={e}, st={st}, r={"true" if r else "false"}' for t, s, e, st, r in CONTOH_LABEL)
    return f"{awal}\n\n{RUBRIK_V2}\n\nContoh:\n{contoh}\n\n{bentuk}"


def label_konten(item, T, *, topik=None, ukuran=25, progres=None, versi="v2", berpikir=False, model=None):
    """item = [{"id", "teks", "platform"}]. Mengembalikan ({id: {"s","e","st","r"}}, galat).
    versi/berpikir/model untuk uji varian (scripts/ai_evaluasi.py); bawaan = varian terbaik hasil uji."""
    sistem = _sistem_label(T, versi)
    paket = [item[i:i + ukuran] for i in range(0, len(item), ukuran)]

    def kirim(pk):
        hasil = {}
        sisa = list(pk)
        for _ in range(2):                                    # minta ulang id yang hilang sekali
            baris = "\n".join(f"[{i + 1}] ({x.get('platform', '')}) {' '.join(str(x['teks']).split())[:600]}"
                              for i, x in enumerate(sisa))
            d = ai_klien.obrolan([{"role": "system", "content": sistem},
                                  {"role": "user", "content": f"Beri label {len(sisa)} konten berikut.\n\n{baris}"}],
                                 tugas="label", topik=topik, berpikir=berpikir, model=model)
            for e in d.get("hasil", []) if isinstance(d, dict) else []:
                try:
                    x = sisa[int(e.get("id")) - 1]
                except (TypeError, ValueError, IndexError):
                    continue
                hasil[x["id"]] = {"s": e.get("s") if e.get("s") in SENTIMEN else "netral",
                                  "e": e.get("e") if e.get("e") in EMOSI8 else "netral",
                                  "st": e.get("st") if e.get("st") in STANCE else "netral",
                                  "r": 0 if e.get("r") is False else 1}
            sisa = [x for x in sisa if x["id"] not in hasil]
            if not sisa:
                break
        return hasil

    def maju(i, n):
        if progres:
            progres(min(i * ukuran, len(item)), len(item))

    hasil_paket, galat = ai_klien.paralel(kirim, paket, progres=maju)
    out = {}
    for h in hasil_paket:
        out.update(h or {})
    return out, galat


# --------------------------------------------------------------- klaster SNA
CONTOH_KLASTER = {
    "nama": "Explainer Geopolitik: Shell Hengkang & Kedaulatan Gas",
    "butir": [
        "Berkumpul di video penjelas cuanomik (\"28 tahun, 6 presiden, Rp390 triliun\") dan Info Global soal Shell mundur.",
        "Nada kebanggaan nasional: keberanian menghadapi Shell dipuji, sebagian menuntut investor asing diusir.",
        "Debat substansi muncul di sini: kilang darat dinilai lebih baik untuk kerja warga setempat.",
        "Dukungan diberi dengan syarat: \"asal jangan seperti dulu, dijual murah ke Singapura\".",
    ]}


def nama_klaster(data, T, *, topik=None):
    """data = {"no", "simpul", "interaksi", "platform", "sentimen", "emosi", "isu", "kata", "tokoh",
    "contoh": [{"oleh", "ke", "teks", "suka", "s"}]}. Mengembalikan {"nama", "butir"}."""
    lede, _ = _konteks_topik(T)
    sistem = (f"Kamu analis social network analysis (SNA) yang menulis catatan klaster untuk laporan percakapan "
              f"publik tentang {T.NAMA}. Konteks: {lede}\n\n{GAYA}\n\n"
              "Tugas: beri nama klaster (paling banyak 70 karakter) yang menggambarkan ISI percakapannya, lalu 3–5 "
              "butir catatan (masing-masing 1–2 kalimat, paling banyak 220 karakter) tentang apa yang dibicarakan, "
              "nadanya, dan akun yang menonjol. Kutipan pendek dari contoh boleh dipakai dalam tanda petik. "
              "Jangan mengulang jumlah akun, jumlah interaksi, atau persentase sentimen dan emosi (sudah tampil di "
              "kartu klaster); tulis isi percakapannya. Hanya berdasarkan data dan contoh yang diberikan.\n\n"
              f"Contoh gaya:\n{json.dumps(CONTOH_KLASTER, ensure_ascii=False)}\n\n"
              'Jawab hanya JSON: {"nama": "...", "butir": ["...", "..."]}')
    contoh = "\n".join(f"- {c['oleh']} → {c['ke']} ({c.get('s', '')}, {c.get('suka', 0)} suka): "
                       f"{' '.join(str(c['teks']).split())[:280]}" for c in data.get("contoh", [])[:30])
    pengguna = (f"Klaster K{data['no']}: {data['simpul']} akun, {data['interaksi']} interaksi, platform {data['platform']}.\n"
                f"Sentimen interaksi: {data['sentimen']}. Emosi utama: {data.get('emosi', '-')}.\n"
                f"Isu: {', '.join(data.get('isu') or []) or '-'}. Kata khas: {', '.join(data.get('kata') or []) or '-'}.\n"
                f"Akun sentral (in-degree tertinggi): {', '.join(data.get('tokoh') or [])}.\n\n"
                f"Contoh interaksi (asal → tujuan):\n{contoh}")
    d = ai_klien.obrolan([{"role": "system", "content": sistem}, {"role": "user", "content": pengguna}],
                         tugas="klaster", topik=topik, berpikir="low")
    nama = re.sub(r"\s+", " ", str(d.get("nama", ""))).strip()[:90]
    butir = [re.sub(r"\s+", " ", str(b)).strip() for b in (d.get("butir") or []) if str(b).strip()][:5]
    if not nama or not butir:
        raise ai_klien.AIError("jawaban klaster tidak lengkap")
    return {"nama": nama, "butir": butir}


# --------------------------------------------------------------- kesimpulan laporan
def _angka(teks):
    """Angka dalam teks, dinormalkan: '1.408' -> 1408, '16,4%' -> 16.4."""
    out = set()
    for m in re.findall(r"\d[\d.,]*", teks):
        m = m.rstrip(".,")
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", m):
            m = m.replace(".", "")
        m = m.replace(",", ".")
        try:
            out.add(round(float(m), 1))
        except ValueError:
            pass
    return out


def periksa_angka(hasil, fakta):
    """Angka di draf yang tidak ditemukan di data (abaikan 0–12: urutan, jumlah kecil, bulan)."""
    sumber = _angka(json.dumps(fakta, ensure_ascii=False))
    # angka di data juga muncul sebagai pembulatan (16,4% -> 16%)
    sumber |= {round(x) for x in sumber} | {round(x, 0) for x in sumber}
    teks = " ".join([k.get("judul", "") + " " + k.get("isi", "") for k in hasil.get("kesimpulan", [])]
                    + hasil.get("rekomendasi", []))
    return sorted({x for x in _angka(teks) if x > 12 and x not in sumber and round(x) not in sumber})


def kesimpulan(fakta, T, *, topik=None):
    """fakta = ringkasan data periode (lihat fakta_ringkas). Mengembalikan
    {"kesimpulan": [{"judul", "isi"}], "rekomendasi": [str], "angka_tak_dikenal": [..]}."""
    lede, _ = _konteks_topik(T)
    sistem = (f"Kamu analis senior yang menulis bagian Kesimpulan dan Rekomendasi untuk laporan percakapan publik "
              f"tentang {T.NAMA} yang akan diserahkan ke klien. Konteks: {lede}\n\n{GAYA}\n\n"
              "Tulis 5–7 kesimpulan. Tiap kesimpulan punya judul (paling banyak 70 karakter, berupa temuan, bukan "
              "nama topik) dan isi 2–4 kalimat. Pilih paling banyak 3–4 angka terpenting per poin dan jelaskan "
              "artinya; jangan menderetkan semua angka per platform seperti membaca tabel. Sebut nama akun bila "
              "relevan. Urutkan dari yang paling penting. Sertakan temuan tentang akun penyebar konten negatif dan positif serta pola amplifikasi bila "
              "datanya ada, digambarkan sebagai pola perilaku dengan bukti. Lalu tulis 3–5 rekomendasi praktis "
              "(satu atau dua kalimat masing-masing) yang langsung mengikuti temuan.\n\n"
              'Jawab hanya JSON: {"kesimpulan": [{"judul": "...", "isi": "..."}], "rekomendasi": ["..."]}')
    d = ai_klien.obrolan([{"role": "system", "content": sistem},
                          {"role": "user", "content": "Data periode laporan:\n" + json.dumps(fakta, ensure_ascii=False)}],
                         tugas="kesimpulan", topik=topik, berpikir="high", maks_token=12000)
    ks = [{"judul": str(k.get("judul", "")).strip(), "isi": str(k.get("isi", "")).strip()}
          for k in d.get("kesimpulan", []) if k.get("judul") and k.get("isi")][:8]
    rk = [str(r).strip() for r in d.get("rekomendasi", []) if str(r).strip()][:6]
    if len(ks) < 3:
        raise ai_klien.AIError("draf kesimpulan terlalu pendek")
    hasil = {"kesimpulan": ks, "rekomendasi": rk}
    hasil["angka_tak_dikenal"] = periksa_angka(hasil, fakta)
    return hasil


def fakta_ringkas(F):
    """Ringkasan F (dari laporan.fakta) yang cukup untuk menulis kesimpulan, tanpa objek modul."""
    def akun(P):
        return [{"akun": a["nama"], "platform": a["platform"], "konten_bernada_ini": a["n"],
                 "persen_unggahan_akun_yang_bernada_ini": round(a["porsi"]),
                 "menanggapi": [s["nama"] for s in a["sasaran"]], "ditanggapi_oleh": [s["nama"] for s in a["dari"]],
                 "contoh": a["contoh"][:160]} for a in (P or {}).get("akun", [])[:8]]
    ko = F.get("koordinasi") or {}
    sna = F.get("sna") or {}
    return {
        "topik": F["T"].NAMA, "periode": F["periode"], "total_konten": F["total"], "akun_dan_media": F["penulis"],
        "engagement": F["engagement"], "tayangan": F["jangkauan"],
        "platform": [{"nama": p["nama"], "konten": p["n"], "porsi_%": round(p["pct"], 1)} for p in F["platform"]],
        "puncak": [{"waktu": p["label"], "per": F["per"], "konten": p["n"], "isu": p["narasi"], "judul_berita": p["judul"][:2]}
                   for p in F["puncak"]],
        "sentimen_media_sosial_%": {k: round(v, 1) for k, v in (F.get("sentimen") or {}).items()},
        "konten_media_sosial": F["n_sosial"],
        "sentimen_per_platform": [{"platform": s["nama"], "konten": s["n"], "negatif_%": round(s["neg"], 1),
                                   "positif_%": round(s["pos"], 1)} for s in F["sentimen_platform"]],
        "emosi_%": [{"emosi": e["nama"], "porsi": round(e["pct"], 1)} for e in F["emosi"]],
        "isu": [{"isu": x["nama"], "konten": x["n"], "porsi_%": round(x["pct"], 1)} for x in F["narasi"][:8]],
        "lensa_fokus": ({"nama": F["fokus"]["nama"], "konten": F["fokus"]["n"], "porsi_%": round(F["fokus"]["pct"], 1),
                         "per_platform_%": {p["nama"]: round(p["pct"], 1) for p in F["fokus"]["platform"]}}
                        if F.get("fokus") else None),
        "aktor_disebut": [{"aktor": a["nama"], "konten": a["n"]} for a in F["aktor"][:8]],
        "media_teratas": [{"media": m["nama"], "artikel": m["n"]} for m in F["media"][:6]],
        "akun_engagement_tertinggi": [{"akun": a["nama"], "platform": a["platform"], "engagement": a["eng"]} for a in F["akun"][:6]],
        "konten_negatif": {"jumlah": (F.get("neg") or {}).get("n"), "akun_penyebar": akun(F.get("neg")),
                           "contoh_teratas": [k["teks"][:200] for k in (F.get("neg") or {}).get("konten", [])[:4]]},
        "konten_positif": {"jumlah": (F.get("pos") or {}).get("n"), "akun_penyebar": akun(F.get("pos")),
                           "contoh_teratas": [k["teks"][:200] for k in (F.get("pos") or {}).get("konten", [])[:4]]},
        "amplifikasi": {
            "teks_identik": [{"teks": k["teks"][:160], "akun": k["akun"], "unggahan": k["unggahan"], "tanggal": k["dari"],
                              "rentang_jam": round(k["jam"], 1) if k["jam"] is not None else None,
                              "contoh_akun": k["contoh_akun"][:6]} for k in ko.get("kembar", [])[:6]],
            "mention_massal": ko.get("massal_n"), "akun_satu_nada": ko.get("satu_nada_total"),
            "contoh_akun_satu_nada": [{"akun": a["nama"], "konten": a["n"], "nada": a["nada"]} for a in ko.get("satu_nada", [])[:6]],
            "akun_x_baru": ko.get("akun_baru_total"),
            "contoh_akun_x_baru": [{"akun": a["nama"], "dibuat": a["dibuat"], "pengikut": a["followers"], "konten": a["n"]}
                                   for a in ko.get("akun_baru", [])[:6]]},
        "klaster_sna": [{"no": k["no"], "nama": k["nama"], "akun": k["simpul"], "interaksi": k["interaksi"],
                         "negatif_%": k["sentimen"]["negatif"], "positif_%": k["sentimen"]["positif"],
                         "catatan": k["butir"][:3]} for k in sna.get("klaster", [])[:8]],
        "ringkasan_graf": [w["isi"] for w in sna.get("wawasan", [])[:4]],
    }


# --------------------------------------------------------------- draf topik baru
SKEMA_TOPIK = """{
 "judul": "judul dashboard, 4-8 kata",
 "judul_laporan": "judul sampul laporan",
 "lede": "2-3 kalimat konteks peristiwa untuk pembaca awam",
 "kueri_berita": ["20-40 kueri Google News: 4-8 kueri inti berupa nama utama saja, lalu kueri isu 2-4 kata"],
 "kueri_yt": ["10-20 kueri YouTube, juga diawali nama utama"],
 "kueri_x": ["8-15 kueri X, boleh tagar"],
 "tagar_ig": ["5-10 tagar Instagram tanpa #, huruf kecil"],
 "kueri_threads": ["5-8 kueri Threads"],
 "situs_lokal": ["domain media lokal wilayah peristiwa yang benar-benar ada, kosongkan bila ragu"],
 "wajib": ["istilah yang hampir pasti hanya dipakai untuk topik ini; satu saja cukup untuk relevan"],
 "pasangan": [{"jika": ["istilah ambigu"], "dan": ["konteks yang harus ikut muncul"]}],
 "kecuali": ["frasa yang menandai topik lain dengan kata yang sama"],
 "narasi": {"Nama Isu": ["8-15 kata kunci 1-2 kata huruf kecil yang muncul persis di teks, termasuk bentuk turunan (tolak, menolak, penolakan); bukan kalimat"]},
 "aktor": {"Nama Aktor": ["variasi penyebutan, huruf kecil"]},
 "fokus": {"nama": "Fokus ...", "ket": "konten yang menyentuh ...", "narasi": ["nama isu dari narasi"]},
 "aturan": {"pihak": ["pihak yang sering dikritik"], "didukung": ["pihak yang sering dipuji"],
            "abaikan": ["kata yang tampak menilai tetapi netral di topik ini"],
            "samarkan": ["kata nama topik yang kebetulan juga kata sifat, mis. tangguh"]},
 "stop": ["kata nama topik yang muncul di mana-mana"],
 "preset": [{"label": "nama momen", "dari": "YYYY-MM-DD", "sampai": "YYYY-MM-DD"}]
}"""


def draf_topik(brief, contoh_judul=None):
    """brief = {"nama", "deskripsi", "wilayah", "pihak", "dari", "sampai", "catatan"}. contoh_judul = judul berita dan
    video nyata hasil riset (scripts/ai_topik.py) supaya nama, tempat, dan istilah sesuai yang dipakai media.
    Mengembalikan konfigurasi topik (lihat SKEMA_TOPIK) untuk ditinjau di wizard topik baru."""
    sistem = ("Kamu menyiapkan konfigurasi pemantauan percakapan publik Indonesia (berita daring, X, YouTube, "
              "Instagram, Threads) untuk satu topik. Konfigurasi dipakai untuk mencari konten dan menyaring "
              "relevansi dengan kata kunci, jadi pilih istilah yang benar-benar dipakai media dan warganet "
              "Indonesia, termasuk singkatan, ejaan alternatif, dan tagar. Hindari istilah terlalu umum yang akan "
              "menjaring topik lain; istilah ambigu masukkan ke 'pasangan' dengan konteksnya, dan tuliskan "
              "frasa topik lain yang sering tertukar di 'kecuali'. Untuk nama wilayah, buat pasangan dengan konteks "
              "umum peristiwa (warga, tolak, demo, aparat, polisi, ditangkap, alat berat, izin, dan istilah sektornya) "
              "supaya berita warga yang tidak menyebut nama perusahaan tetap terjaring. Isu (narasi) adalah sudut "
              "pembicaraan yang kemungkinan muncul: tuntutan warga, dampak, kebijakan, dukungan, kritik, aparat, dan "
              "sebagainya. Kata kunci isu dan aktor harus pendek (1–2 kata) dan benar-benar dipakai di teks, termasuk "
              "bentuk turunannya (tolak, menolak, penolakan); hindari frasa panjang yang jarang muncul persis dan "
              "singkatan dua huruf yang ambigu. Lensa fokus berisi 3–6 isu keresahan atau tuntutan warga saja, bukan "
              "semua isu. Jangan mengarang nama orang, media, atau peristiwa yang tidak kamu yakini.\n\n"
              "Kueri pencarian: Google News dan YouTube mensyaratkan setiap kata kueri muncul, jadi kueri yang "
              "menggabungkan frasa bertanda petik dengan kata lain (mis. \"PT X\" proyek Y) sangat sempit. Awali "
              "kueri_berita dan kueri_yt dengan nama utama topik saja beserta variasinya (nama proyek, perusahaan, "
              "kapal, atau lokasi khas; mis. \"Tangguh LNG\", \"LNG Tangguh\", \"Ubadari\"), lalu kueri isu 2–4 kata "
              "tanpa tanda petik kecuali untuk nama baku berupa frasa. Nama utama yang tidak ambigu juga masuk 'wajib'.\n\n"
              f"Jawab hanya JSON dengan bentuk:\n{SKEMA_TOPIK}")
    pengguna = "Topik baru:\n" + json.dumps(brief, ensure_ascii=False)
    if contoh_judul:
        pengguna += ("\n\nJudul berita dan video nyata dari pencarian awal (sebagian mungkin tidak relevan). Pakai nama "
                     "orang, lembaga, tempat, singkatan, dan istilah yang benar-benar muncul di sini; perhatikan juga "
                     "judul tidak relevan yang memakai kata sama untuk mengisi 'kecuali':\n" + "\n".join(contoh_judul))
    d = ai_klien.obrolan([{"role": "system", "content": sistem}, {"role": "user", "content": pengguna}],
                         tugas="topik", berpikir="high", maks_token=32000)
    if not isinstance(d, dict) or not d.get("kueri_berita") or not d.get("narasi"):
        raise ai_klien.AIError("draf topik tidak lengkap")
    return d
