"""Topik: tenggelamnya KM Virgo Transport 8 (Laut Jawa, 13 September 2026).

Semua konstanta di sini dipindahkan apa adanya dari skrip pipeline versi awal
(sebelum proyek menjadi multi-topik), supaya hasil Virgo tidak berubah.
"""
import re

SLUG = "virgo"
NAMA = "KM Virgo Transport 8"
JUDUL = "Tenggelamnya KM Virgo Transport 8"
ATAS = "Laporan percakapan publik · 12–30 September 2026"
LEDE = ("Feri rute Surabaya–Banjarmasin yang membawa 243 orang terbalik di Laut Jawa dini hari "
        "13 September 2026. Halaman ini merangkum cara media dan warganet membicarakannya: kapan "
        "ramai, bernada apa, siapa terhubung dengan siapa, dan narasi apa yang mendominasi.")
STATUS = "selesai"
JENDELA = ("2026-09-12", "2026-09-30")
PRESET = [
    ("Seluruh periode", "2026-09-12", "2026-09-30"),
    ("Pekan 1 · 12–18", "2026-09-12", "2026-09-18"),
    ("Pekan 2 · 19–25", "2026-09-19", "2026-09-25"),
    ("Pekan 3 · 26–30", "2026-09-26", "2026-09-30"),
    ("72 jam pertama", "2026-09-13", "2026-09-15"),
]

# ------------------------------------------------------------------ berita
KUERI_BERITA = [
    '"Virgo Transport 8"', '"KM Virgo"', '"KMP Virgo"', 'kapal Virgo tenggelam',
    'Virgo Transport 8 korban', 'Virgo Transport 8 Basarnas', 'Virgo Transport 8 SAR',
    'Virgo Transport 8 penyelam', 'Virgo Transport 8 DVI', 'Virgo Transport 8 tersangka',
    'Virgo Transport 8 KNKT', 'Virgo Transport 8 Kemenhub', 'Virgo Transport 8 manifes',
    'Virgo Transport 8 santunan', 'Virgo Transport 8 Jasa Raharja',
    'Virgo Transport 8 evakuasi jenazah', 'Virgo Transport 8 bangkai kapal',
    'Virgo Transport 8 Prabowo', 'Virgo Transport 8 DPR', 'Virgo Transport 8 polisi',
    'kapal tenggelam Laut Jawa Surabaya Banjarmasin', 'kapal tenggelam rute Surabaya Banjarmasin korban',
    'feri tenggelam Laut Jawa September 2026', 'kapal feri tenggelam Masalembu',
    'tenggelamnya kapal Laut Jawa penumpang hilang',
]
KUERI_BERITA_INTI = ['"Virgo Transport 8"', '"KM Virgo"', '"KMP Virgo"',
                     'kapal tenggelam Laut Jawa', 'kapal tenggelam Banjarmasin']
KUERI_SITUS = ['"Virgo"', '"Virgo Transport 8"']
SITUS_TAMBAHAN = [
    "solopos.com", "surya.co.id", "radarsurabaya.jawapos.com", "bangkapos.com",
    "banjarmasinpost.co.id", "kalselpos.com", "prokal.co", "antarajatim.com",
    "harianjogja.com", "krjogja.com", "suarasurabaya.net", "ayobandung.com",
    "kaltimpost.jawapos.com", "dephub.go.id",
]
KUERI_NATIVE = ["Virgo Transport 8", "KM Virgo", "KMP Virgo", "kapal tenggelam Laut Jawa"]
JUDUL_KUAT = r"virgo"
JUDUL_LONGGAR = (r"(kapal|feri|ferry|kmp|km)\b.{0,40}(tenggelam|terbalik|karam|kecelakaan)|"
                 r"tenggelamnya\s+(kapal|km|kmp)|korban\s+kapal|manifes|"
                 r"(operasi\s+sar|basarnas).{0,40}(kapal|laut jawa)")

# ----------------------------------------------------------------- YouTube
KUERI_YT = [
    '"Virgo Transport 8"', '"KM Virgo Transport 8"', '"KMP Virgo Transport 8"',
    'KM Virgo tenggelam', 'KMP Virgo terbalik', 'kapal Virgo Laut Jawa',
    'kapal tenggelam Surabaya Banjarmasin', 'kapal tenggelam Laut Jawa 2026',
    'Basarnas KM Virgo', 'evakuasi korban KM Virgo', 'penyelam KM Virgo',
    'jenazah korban KM Virgo', 'identifikasi korban KM Virgo',
    'manifes KM Virgo', 'KNKT kapal Virgo', 'Kemenhub kapal tenggelam Virgo',
    'keluarga korban KM Virgo', 'saksi selamat KM Virgo',
    'kronologi tenggelamnya KM Virgo', 'kapal tua KM Virgo',
]

# ------------------------------------------------------ X / IG / Threads
KUERI_X = [
    '"Virgo Transport 8"', '"KM Virgo"', '"KMP Virgo"', '"Virgo Transport"',
    '#KMVirgo', '#KMVirgoTransport8', '#VirgoTransport8', '#KapalVirgo',
    '#KapalTerbalik', '#KapalTenggelam', '#LautJawa',
    'kapal tenggelam Laut Jawa', 'kapal terbalik Surabaya Banjarmasin',
    'Basarnas Virgo', 'korban KM Virgo', 'evakuasi KM Virgo',
    'KNKT Virgo', 'Kemenhub kapal tenggelam', 'jenazah KM Virgo',
    'penyelam KM Virgo', 'manifes KM Virgo', 'DVI KM Virgo',
    'kapal Virgo Banjarmasin', 'tenggelamnya KM Virgo',
]
KUERI_X_HARIAN = ['"Virgo Transport 8"', '"KM Virgo"', 'kapal tenggelam']
TAGAR_IG = [
    "kmvirgo", "virgotransport8", "kmvirgotransport8", "kapalvirgo",
    "kmpvirgotransport8", "kmpvirgo", "virgotransport", "kapalvirgotransport8",
    "prayforkmvirgo", "prayforvirgo", "kmvirgotenggelam",
]
TAGAR_IG_LEBAR = ["kapaltenggelam", "kecelakaankapal", "kapalterbalik", "operasisar",
                  "basarnas", "lautjawa", "timsar"]
KUERI_IG = [
    "KM Virgo Transport 8", "kapal Virgo tenggelam", "Virgo Transport 8",
    "korban kapal Virgo", "penyelam kapal Virgo", "Basarnas kapal Virgo",
    "keluarga korban KM Virgo", "manifes kapal Virgo", "tersangka kapal Virgo",
    "bangkai kapal Virgo", "santunan korban Virgo", "kapal tenggelam Laut Jawa",
    "kapal Surabaya Banjarmasin tenggelam", "KNKT kapal Virgo",
    "nakhoda kapal Virgo", "doa korban kapal Virgo",
]
KUERI_THREADS = [
    "KM Virgo", "kmvirgo", "Virgo Transport 8", "kapal Virgo",
    "kapal Virgo tenggelam", "korban kapal Virgo", "penyelam Virgo",
    "nakhoda kapal Virgo", "basarnas Virgo", "keluarga korban Virgo",
    "kapal tenggelam laut jawa", "tragedi kapal Virgo",
]

# --------------------------------------------------------------- relevansi
_VIRGO = re.compile(r"virgo", re.I)
_ZODIAK = re.compile(r"zodiak|zodiac|horoscope|horoskop|ramalan|astrolog", re.I)
_KAPAL = re.compile(r"\b(kapal|kmp|km|feri|ferry)\b.{0,50}\b(tenggelam|terbalik|karam|kecelakaan|hilang)\b"
                    r"|\b(tenggelam|terbalik|karam|kecelakaan laut)\b.{0,50}\b(kapal|kmp|feri|ferry)\b", re.I)
_TEMPAT = re.compile(r"laut jawa|banjarmasin|surabaya|masalembu|bawean|kalimantan selatan|"
                     r"java sea|tanjung perak|trisakti", re.I)
_SAR = re.compile(r"operasi sar|tim sar|basarnas|penyelam|bangkai kapal|salvage|"
                  r"evakuasi jenazah|dvi|korban kapal|ferry disaster", re.I)
_KORBAN = re.compile(r"korban|jenazah|penumpang|hilang|selamat|meninggal|jasad", re.I)
# bukan kapal penumpang / bukan peristiwa ini sama sekali
_KECUALI = re.compile(r"kapal pesiar|yacht|kapal perang|kapal selam|titanic|pangandaran|"
                      r"harga seafood|panen tengiri|kapal pinisi|tongkang|tugboat|kapal tanker|"
                      r"kapal ikan|perahu nelayan", re.I)
# insiden kapal lain pada periode yang sama (termasuk kapal wartawan Anak Krakatau)
INSIDEN_LAIN = re.compile(r"selat bali|labuan bajo|pulau pari|danau toba|sungai musi|bakauheni|"
                          r"merak|ketapang.{0,12}gilimanuk|kapal wisata|kmp tunu|nusa penida|"
                          r"raja ampat|wakatobi|kepulauan seribu|situ gintung|krakatau|wartawan|"
                          r"jurnalis|danau victoria|uganda|mesir|cianjur|pinisi|kapal induk", re.I)


def relevan(teks):
    """Menyebut Virgo (bukan zodiak) = relevan. Selebihnya kapal tenggelam /
    operasi SAR dianggap relevan KECUALI teridentifikasi sebagai insiden lain."""
    teks = teks or ""
    if _VIRGO.search(teks) and not _ZODIAK.search(teks):
        return 1
    if _KECUALI.search(teks) or INSIDEN_LAIN.search(teks):
        return 0
    if _KAPAL.search(teks) or _SAR.search(teks):
        return 1
    if _KORBAN.search(teks) and _TEMPAT.search(teks):
        return 1
    return 0


_RUTE = re.compile(r"surabaya|banjarmasin|laut jawa", re.I)
_MUSIBAH = re.compile(r"korban|jenazah|jasad|penumpang|basarnas|tim sar|penyelam|evakuasi|"
                      r"merantau|tenggelam|hilang|selamat", re.I)


# hasil kueri "virgo" yang tidak menyebut Virgo di teksnya (X ikut mencocokkan tweet yang dikutip):
# dipercaya hanya bila membawa konteks kapal, SAR, atau duka, atau hanya berisi tautan/emoji
_KONTEKS_LAUT = re.compile(r"kapal|ferry|feri|\bkmp?\b|laut|pelabuhan|penyelam|selam|diving|diver|recovery|"
                           r"identifikasi|\bdvi\b|operasi|\bsar\b|\bship\b|vessel|capsiz|sank|sink|evakuasi|"
                           r"nakhoda|nahkoda|syahbandar|laik|transportasi air|masalembu|manifes|kurushima|"
                           r"pelampung|\bdlu\b|regulator|duka|doa|semoga|innalillahi|inna lillahi", re.I)
_URL_X = re.compile(r"https?://\S+|@[\w.]+")


def relevan_x(teks, kueri=""):
    """Kueri umum X menjaring ~20% insiden lain. Tweet dari kueri spesifik Virgo diterima bila
    menyebut Virgo, membawa konteks kapal/SAR/duka, atau hanya berisi tautan/emoji; dari kueri
    rute relevan bila membahas korban/SAR; selebihnya wajib lolos relevan()."""
    teks = teks or ""
    if _VIRGO.search(teks) and not _ZODIAK.search(teks):
        return 1
    if INSIDEN_LAIN.search(teks) or _ZODIAK.search(teks):
        return 0
    if "virgo" in (kueri or "").lower():
        sisa = _URL_X.sub(" ", teks)
        return int(bool(_KONTEKS_LAUT.search(teks) or _MUSIBAH.search(teks)
                        or len(re.sub(r"\W+", "", sisa)) < 12))
    if _RUTE.search(kueri or "") and _MUSIBAH.search(teks):
        return 1
    return relevan(teks)


# ---------------------------------------------------------------- analisis
NARASI = None   # pakai narasi bawaan label_teks (dirancang untuk Virgo)

TOPIK_BERITA = {
    "SAR & Evakuasi": r"\b(sar|basarnas|pencarian|evakuasi|penyelam|penyelaman|kapal sar|"
                      r"helikopter|kri |tim gabungan|operasi pencarian|perpanjang.{0,15}pencarian)\b",
    "Korban & Identifikasi": r"\b(korban|jenazah|jasad|dvi|identifikasi|teridentifikasi|"
                             r"post ?mortem|ante ?mortem|rs bhayangkara|keluarga korban|"
                             r"meninggal|tewas|hilang|selamat|kantong jenazah)\b",
    "Penyebab & Cuaca": r"\b(penyebab|cuaca buruk|gelombang tinggi|ombak|angin kencang|"
                        r"bmkg|miring|oleng|kemiringan|bocor|air masuk|stabilitas|"
                        r"muatan bergeser|kronologi)\b",
    "Hukum & Tersangka": r"\b(tersangka|penyidikan|penyelidikan|polisi|polri|bareskrim|"
                         r"mabes|gelar perkara|pidana|pasal|ditahan|saksi|proses hukum|"
                         r"kejaksaan|jaksa|berkas perkara|p21)\b",
    "Regulasi & Keselamatan Pelayaran": r"\b(knkt|kemenhub|ksop|syahbandar|laik laut|"
                         r"kelaiklautan|sertifikat|uji petik|ramp check|audit|izin|"
                         r"standar keselamatan|life ?jacket|sekoci|regulasi|aturan pelayaran|"
                         r"kapal tua|usia kapal|moratorium)\b",
    "Manifes & Overload": r"\b(manifes|data penumpang|tidak terdaftar|tak terdaftar|"
                          r"penumpang gelap|overload|kelebihan (muatan|penumpang)|"
                          r"jumlah penumpang|kendaraan|truk|selisih data)\b",
    "Santunan & Asuransi": r"\b(santunan|jasa raharja|asuransi|kompensasi|ganti rugi|"
                           r"bantuan (sosial|tunai)|dana|klaim)\b",
    "Politik & Pemerintah": r"\b(dpr|komisi v|presiden|prabowo|menteri|menhub|wakil menteri|"
                            r"gubernur|bupati|wali kota|pemerintah|rapat kerja|sidak|"
                            r"instruksi|perintah presiden)\b",
    "Hoaks & Disinformasi": r"\b(hoaks|hoax|cek fakta|disinformasi|misinformasi|"
                            r"video (palsu|lama)|tidak benar|keliru|klaim)\b",
    "Dampak Ekonomi & Logistik": r"\b(logistik|distribusi|harga|pelabuhan|bongkar muat|"
                                 r"rute|penyeberangan|asdp|tarif|arus barang|sopir|ekspedisi)\b",
}

AKTOR = {
    "Basarnas": r"\bbasarnas|badan sar nasional|kantor sar\b",
    "Kemenhub": r"\bkemenhub|kementerian perhubungan|menteri perhubungan|menhub\b",
    "KNKT": r"\bknkt|komite nasional keselamatan transportasi\b",
    "Polri/Polda": r"\bpolri|polda|polres|bareskrim|mabes polri|kapolda|kapolres\b",
    "TNI AL": r"\btni al|koarmada|lantamal|kri \b",
    "KSOP/Syahbandar": r"\bksop|syahbandar|kantor kesyahbandaran\b",
    "Jasa Raharja": r"\bjasa raharja\b",
    "DPR": r"\bdpr\b|\bkomisi v\b",
    "Presiden/Prabowo": r"\bpresiden\b|\bprabowo\b",
    "Pemda Jatim": r"\bjawa timur|jatim|gubernur khofifah|pemprov jatim\b",
    "Pemda Kalsel": r"\bkalimantan selatan|kalsel|banjarmasin|pemprov kalsel\b",
    "Operator/Pemilik Kapal": r"\boperator kapal|pemilik kapal|perusahaan pelayaran|"
                              r"pt\.? [a-z]+ (transport|pelayaran|shipping)|nakhoda|abk\b",
    "BMKG": r"\bbmkg\b",
    "Keluarga Korban": r"\bkeluarga korban|ahli waris|kerabat korban|posko keluarga\b",
}

STOP = {"kapal", "virgo", "transport", "km", "kmp", "korban"}

# --------------------------------------------------------------- dashboard
KET_PLATFORM = {
    "Berita": "Artikel dari lebih dari 600 media daring, dipanen lewat Google News dan mesin pencari internal media. Sentimen berita masih baseline lexicon; yang andal di sini adalah volume, media, aktor, dan narasi.",
    "X (Twitter)": "Cuitan hasil pencarian kata kunci, tagar, dan jendela harian, ditambah balasan pada utas yang relevan. Tweet tentang insiden kapal lain sudah dikeluarkan lewat filter relevansi.",
    "YouTube": "Video pemberitaan dan komentar serta balasannya. Tanggal komentar diperkirakan dari waktu relatif, jadi pola harian YouTube kurang presisi.",
    "Instagram": "Post dari tagar dan pencarian kata kunci, ditambah komentar teratas dan balasannya pada post dengan komentar terbanyak. Panen dibatasi 120 permintaan per sesi demi keamanan akun.",
    "Threads": "Post dari pencarian kata kunci (tab Teratas dan Terbaru) dan balasan teratas pada post yang paling banyak dibalas.",
}
CATATAN_LINIMASA = ("Jumlah konten yang terbit per hari. Lonjakan YouTube pada 15 Sep sebagian "
                    "adalah artefak tanggal relatif komentar.")

# --------------------------------------------------------------- laporan
# Kesimpulan analis untuk laporan PDF (scripts/laporan.py); ditulis setelah membaca isi
# percakapan dan klaster. Angka bisa bergeser bila data dipanen ulang.
# judul sampul laporan PDF (JUDUL dipakai dashboard)
JUDUL_LAPORAN = "Tenggelamnya KM Virgo Transport 8"
KESIMPULAN_TANGGAL = "1 Oktober 2026"
KESIMPULAN = [
    {"judul": "Volume mengikuti kabar pencarian korban",
     "isi": "Puncak tertinggi terjadi pada 15 September (6.058 konten), dua hari setelah kapal tenggelam. Volume naik "
            "lagi pada 29 September ketika 18 jenazah ditemukan."},
    {"judul": "Konten negatif paling banyak menyasar regulator dan operator",
     "isi": "Ada 4.080 konten negatif (16,6% konten media sosial). Isinya terutama izin berlayar dari Syahbandar, kapal "
            "buatan 1987 yang dinilai tidak laik, dugaan muatan berlebih, nakhoda yang diduga meninggalkan penumpang, dan "
            "desakan agar Menteri Perhubungan mundur. Di graf SNA negatif, in-degree tertinggi dimiliki kanal YouTube "
            "METRO TV (297 interaksi negatif), tvOneNews (218), dan KOMPASTV (192)."},
    {"judul": "Konten positif berpusat pada tim SAR",
     "isi": "Ada 6.939 konten positif (28,3%), sebagian besar doa dan apresiasi untuk penyelam, nelayan, dan Basarnas. "
            "Penyebar terbanyak adalah pw_gun (46 konten), RadioElshinta (45), dan antaranews (39). DivHumas_Polri "
            "menerima 238 interaksi positif, atau 64% dari semua interaksi yang masuk ke akun itu."},
    {"judul": "Akun humas kepolisian mengunggah teks seragam",
     "isi": "Pada 15 September pukul 11.06–14.28 WIB, 28 akun X mengunggah kalimat \"Polri #SiagaHadapiBencana dan Terus "
            "Berkomitmen ...\"; 17 di antaranya dengan teks yang persis sama. Sebagian besar adalah akun humas polda, "
            "polres, dan polsek. Empat akun pribadi (nuraniarsita7, AndinLES, nkri_n, AslheyKinson) mengunggahnya dalam "
            "lima menit, pukul 13.14–13.19 WIB. Di Instagram, akun non-resmi seperti hirukpikuk2025, brun.owls, "
            "gondraicekut, dan dodoremember mengunggah ulang rilis Polda Kalsel dan Polresta Banjarmasin dengan teks yang sama."},
    {"judul": "Balasan pujian seragam dan akun X baru",
     "isi": "Lima akun (Alyazahra86, SaqilaMaharani8, Renda3sg7, kanzaaurel04, Haikal11Ha5) membalas dengan kalimat "
            "pujian yang sama untuk personel Polri dalam 3,5 jam pada 14 September. Ada 104 akun X yang dibuat dalam "
            "enam bulan sebelum kecelakaan atau sesudahnya dan ikut membahas topik ini. Yang paling aktif adalah "
            "apelhiijauu (dibuat 11 Agustus 2026, 3.042 pengikut, 72 unggahan)."},
    {"judul": "Kecelakaan dikaitkan dengan ketidakpuasan politik",
     "isi": "Daftar \"bentuk tone deaf pemerintah\" yang menyandingkan korban Virgo dengan isu lain termasuk unggahan X "
            "dengan engagement tertinggi. Sindiran \"Konoha\" dan tudingan korupsi sebagai penyebab armada tua muncul di "
            "banyak klaster."},
    {"judul": "Kanal televisi menjadi node penghubung",
     "isi": "KOMPASTV, tvOneNews, dan METRO TV masing-masing terhubung ke 14 klaster. Di luar pola seragam di atas, "
            "percakapan tersebar di banyak klaster kecil tanpa satu akun yang dominan."},
    {"judul": "Pemberitaan berfokus pada korban dan operasi SAR",
     "isi": "Isu berita terbanyak adalah korban dan identifikasi serta SAR dan evakuasi. Aktor yang paling sering "
            "diberitakan adalah Pemda Kalsel, Basarnas, Polri, dan TNI AL."},
]
REKOMENDASI = [
    "Sampaikan pembaruan resmi pencarian dan identifikasi korban secara berkala lewat siaran langsung televisi di "
    "YouTube. Volume percakapan naik setiap ada kabar korban.",
    "Jawab pertanyaan yang paling sering muncul di konten negatif: dasar izin berlayar, kelaiklautan kapal, manifes dan "
    "muatan, serta proses hukum nakhoda dan operator.",
    "Saat mengukur dukungan publik terhadap penanganan, pisahkan unggahan seragam akun humas dan akun penyalur rilis "
    "(lihat bagian indikator amplifikasi) dari percakapan warga.",
    "Simpan daftar akun dari bagian sentimen negatif, sentimen positif, dan indikator amplifikasi, lalu periksa apakah "
    "akun yang sama muncul lagi di topik lain.",
    ]
