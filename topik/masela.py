"""Topik: demo & aksi unjuk rasa terkait INPEX Masela (Blok Masela, Kepulauan Tanimbar).

Konteks (riset 30 Sep 2026): proyek LNG Abadi di Blok Masela yang dioperasikan
INPEX Masela memicu rangkaian aksi sepanjang 2026:
  - Feb 2026   Aliansi Tanimbar demo di SKK Migas Jakarta (hak adat, dugaan
               kongkalikong pejabat Pemda dan INPEX)
  - 31 Mar     nelayan Lermatang demo di shelter INPEX, kompensasi disepakati
  - 4 Agu      ±300 warga Tanimbar demo di Kedubes Jepang (ganti rugi lahan 28,9 ha)
  - 3 Sep      Mahasiswa Tanimbar Menggugat demo di kantor INPEX Senayan: tuntut
               status PSN dicabut, tanah adat dikembalikan, stop "ekosida" Laut
               Arafura, audit AMDAL dan KLHS
Selain itu ada aksi APKRT dan AMT (pembebasan lahan, tanah adat jadi tanah
negara) serta kelompok yang menyatakan dukungan pada proyek.
"""
import re
from datetime import date

SLUG = "masela"
NAMA = "INPEX Masela"
JUDUL = "Demo & aksi unjuk rasa INPEX Masela"
ATAS = "Laporan percakapan publik · Januari–September 2026"
LEDE = ("Proyek LNG Abadi di Blok Masela, Kepulauan Tanimbar, yang dioperasikan INPEX memicu "
        "rangkaian aksi sepanjang 2026: tuntutan hak tanah adat dan ganti rugi lahan, kompensasi "
        "nelayan, tenaga kerja lokal, hingga desakan mencabut status Proyek Strategis Nasional. "
        "Halaman ini memetakan cara media dan warganet membicarakannya.")
STATUS = "berjalan"
JENDELA = ("2026-01-01", date.today().isoformat())
PRESET = [
    ("Seluruh 2026", "2026-01-01", JENDELA[1]),
    ("Aksi SKK Migas · Feb", "2026-02-01", "2026-02-28"),
    ("Nelayan Lermatang · Mar–Apr", "2026-03-25", "2026-04-15"),
    ("Kedubes Jepang · Agu", "2026-08-01", "2026-08-15"),
    ("Aksi Senayan · Sep", "2026-09-01", JENDELA[1]),
    ("3 bulan terakhir", "2026-07-01", JENDELA[1]),
]

# ------------------------------------------------------------------ berita
KUERI_BERITA = [
    '"Blok Masela"', '"Inpex Masela"', '"LNG Abadi"', '"Abadi LNG"',
    'Inpex Masela demo', 'Blok Masela unjuk rasa', 'Blok Masela aksi mahasiswa',
    'Blok Masela tanah adat', 'Blok Masela hak ulayat', 'Blok Masela ganti rugi lahan',
    'Blok Masela pembebasan lahan', 'Blok Masela nelayan kompensasi', 'Inpex nelayan Lermatang',
    'Blok Masela tenaga kerja lokal', 'Blok Masela PSN', 'Blok Masela cabut PSN',
    'Blok Masela AMDAL', 'Blok Masela lingkungan Laut Arafura', 'Blok Masela Tanimbar',
    'Inpex Tanimbar', 'Inpex SKK Migas demo', 'Blok Masela Kedubes Jepang',
    'Mahasiswa Tanimbar Menggugat', 'Aliansi Tanimbar Inpex', 'Blok Masela participating interest Maluku',
    'Blok Masela Gubernur Maluku', 'Blok Masela Bahlil', 'Blok Masela Pertamina Petronas',
    'Blok Masela groundbreaking', 'Blok Masela DPR',
    # kueri yang menyasar tiap aksi: liputannya kebanyakan di media lokal/kecil
    'Mahasiswa Tanimbar Menggugat', 'demo kantor Inpex Senayan', 'aksi mahasiswa Inpex Masela Jakarta',
    'APKRT Blok Masela', 'AMT demo Blok Masela', 'Aliansi Masyarakat Tanimbar Inpex',
    'Luckycentre Foundation Tanimbar', 'warga Tanimbar Kedubes Jepang', 'nelayan Lermatang demo Inpex',
    'harga tanah Pulau Nustual', 'tanah adat Tanimbar Inpex', 'ekosida Laut Arafura',
    'tolak PSN Blok Masela', 'Front Mahasiswa Tanimbar Blok Masela', 'demo Saumlaki Inpex',
]
KUERI_BERITA_INTI = ['"Blok Masela"', '"Inpex Masela"', 'Masela Tanimbar']
KUERI_SITUS = ['"Masela"', '"Inpex"']
SITUS_TAMBAHAN = [
    # media Maluku: sering memberitakan aksi lebih dulu daripada media nasional
    "ambonterkini.id", "klikmaluku.com", "dinamikamaluku.com", "titastory.id",
    "serambimaluku.com", "siwalimanews.com", "terasmaluku.com", "kabartimurnews.com",
    "malukupost.com", "ameks.fajar.co.id", "headlinetimur.com", "beritabeta.com",
    "rakyatmaluku.fajar.co.id", "tribunambon.com", "ambon.antaranews.com", "kabar17.id",
    # media energi & lembaga
    "dunia-energi.com", "ruangenergi.com", "esdm.go.id", "skkmigas.go.id",
]
KUERI_NATIVE = ["Blok Masela", "Inpex Masela", "Masela Tanimbar", "demo Inpex", "tanah adat Tanimbar"]
JUDUL_KUAT = r"masela|marsela|inpex|abadi lng|lng abadi"
JUDUL_LONGGAR = (r"tanimbar.{0,60}(lng|migas|gas|kilang|psn|lahan|adat|demo|unjuk rasa|nelayan)|"
                 r"(lng|migas|kilang).{0,40}tanimbar|saumlaki.{0,40}(lng|gas|kilang|demo)")

# ----------------------------------------------------------------- YouTube
KUERI_YT = [
    'Blok Masela', 'Inpex Masela', 'demo Blok Masela', 'demo Inpex Masela',
    'Blok Masela tanah adat', 'Tanimbar Blok Masela', 'aksi mahasiswa Tanimbar Inpex',
    'nelayan Lermatang Inpex', 'LNG Abadi Masela', 'Blok Masela PSN',
    'Blok Masela Kedubes Jepang', 'Blok Masela ganti rugi lahan', 'Blok Masela Bahlil',
    'Blok Masela 2026', 'Masela Saumlaki', 'Inpex Tanimbar',
    'Mahasiswa Tanimbar Menggugat', 'demo Inpex Senayan', 'demo Kedubes Jepang Tanimbar',
    'Lermatang Nustual', 'tanah adat Tanimbar', 'tolak PSN Masela',
]

# ---------------------------------------------- X / IG / Threads (fase berikut)
KUERI_X = [
    '"Blok Masela"', '"Inpex Masela"', '#BlokMasela', '#Masela', '#Inpex',
    'Masela demo', 'Inpex demo', 'Masela tanah adat', 'Tanimbar Inpex',
    'Masela PSN', '"LNG Abadi"', 'Masela nelayan',
]
KUERI_X_HARIAN = ['"Blok Masela"', 'Inpex Masela']
TAGAR_IG = ["blokmasela", "inpexmasela", "masela", "abadilng", "savetanimbar"]
TAGAR_IG_LEBAR = ["tanimbar", "saumlaki", "kepulauantanimbar", "inpex"]
KUERI_IG = ["Blok Masela", "Inpex Masela", "demo Blok Masela", "Tanimbar Masela",
            "Masela tanah adat", "LNG Abadi"]
KUERI_THREADS = ["Blok Masela", "Inpex Masela", "Masela", "demo Inpex", "Tanimbar Masela",
                 "Masela tanah adat"]

# --------------------------------------------------------------- relevansi
_KUAT = re.compile(r"abadi ?lng|lng ?abadi|lapangan ?abadi|"
                   r"(blok|inpex|lng|gas|proyek|ladang|lapangan|kilang) ?mar?sela|masela ?(lng|gas|block|project)", re.I)
# "Masela"/"Marsela" saja juga nama orang, merek, kata Swahili ("masela" = teman), Pulau Masela
# di MBD, dan kapal KMP Marsela; di media sosial itu banyak. Tanpa istilah pendamping, bukan topik ini.
_MASELA = re.compile(r"mar?sela", re.I)                                          # "Marsela": salah ketik umum
_PENDAMPING = re.compile(r"\b(blok|lng|migas|gas|kilang|psn|proyek|inpex|abadi|tanimbar|saumlaki|maluku|"
                         r"skk|esdm|investasi|prabowo|bahlil|jokowi|pertamina|petronas|ptro|groundbreaking|"
                         r"konstruksi|energi|lapangan|shell|danantara|smelter|hulu|ccs|carbon capture|cadangan|"
                         r"lifting|epc|kontraktor|konsorsium|emiten|pipa|jepang|presiden|pemerintah|rakyat|negara|triliun|"
                         r"miliar|dolar|ekonomi|menteri|dpr)", re.I)
_INPEX = re.compile(r"\binpex\b", re.I)
# INPEX banyak dibahas sebagai saham Jepang & proyek Australia: wajib ada konteks Indonesia,
# baik istilahnya maupun sekadar teks berbahasa Indonesia (CSR INPEX di desa sering tanpa kata migas)
_KONTEKS_RI = re.compile(r"\b(indonesia|maluku|prabowo|bahlil|jokowi|skk ?migas|esdm|pertamina|kementerian|"
                         r"pemerintah|migas|kilang|psn|dpr|pemkab|pemprov|bupati|gubernur|abadi|lermatan|"
                         r"yang|dan|di|untuk|dengan|dari|ini|itu|tidak|kami|kita|desa|bagi|akan|sudah|juga)\b|"
                         r"tanimbar|saumlaki", re.I)
_TANIMBAR = re.compile(r"tanimbar|saumlaki|lermatang|yamdena|selaru|nustual|arafura", re.I)
_MIGAS = re.compile(r"\b(lng|migas|gas|kilang|psn|proyek strategis|skk migas|esdm|blok)\b", re.I)
# Nustual (lokasi kilang) & Lermatang (desa area proyek): isu tanah/aksi di sana
# hampir selalu soal Blok Masela walau tidak menyebut istilah migas
_LOKASI_PROYEK = re.compile(r"lermatang|nustual", re.I)
_ISU_LOKAL = re.compile(r"tanah|lahan|ganti rugi|kompensasi|harga|demo|aksi|unjuk rasa|turun ke jalan|"
                        r"tuntut|tolak|nelayan|adat", re.I)
# INPEX juga mengoperasikan proyek lain (Ichthys, Australia): tanpa Masela/Tanimbar, bukan topik ini
_INPEX_LAIN = re.compile(r"ichthys|darwin|australia|browse basin|abu dhabi|kazakhstan", re.I)


def relevan(teks):
    teks = teks or ""
    if _KUAT.search(teks):
        return 1
    if _MASELA.search(teks) and _PENDAMPING.search(teks):
        return 1
    if _INPEX.search(teks):
        if _INPEX_LAIN.search(teks) and not _TANIMBAR.search(teks):
            return 0
        return 1 if _KONTEKS_RI.search(teks) else 0
    if _TANIMBAR.search(teks) and _MIGAS.search(teks):
        return 1
    if _LOKASI_PROYEK.search(teks) and _ISU_LOKAL.search(teks):
        return 1
    return 0


# ---------------------------------------------------------------- analisis
NARASI = {
    # dipertajam setelah korpus berita pertama: kata umum ("ekonomi", "investasi",
    # "kementerian", "aksi") membuat narasi cocok dengan hampir semua artikel.
    # Putaran kedua (setelah media sosial): kata latar yang ada di hampir semua berita
    # proyek ("Laut Arafura", "proyek strategis nasional", "Jepang", "mendukung") dibuang;
    # narasi harus menangkap pembahasan isunya, bukan deskripsi proyek.
    "Hak Tanah Adat & Ganti Rugi Lahan": r"\b(tanah adat|hak ulayat|hak adat|ganti rugi|pembebasan lahan|"
                                         r"harga tanah|petuanan|masyarakat adat|tanah negara|sengketa lahan)\b",
    "Kompensasi Nelayan & Ruang Laut": r"\b(nelayan|wilayah tangkap|area tangkap|daerah tangkapan|rumput laut|"
                                       r"ruang laut|kompensasi (bagi |untuk |kepada )?(nelayan|warga|masyarakat)|"
                                       r"budidaya (rumput laut|ikan|mutiara))\b",
    "Tenaga Kerja & Pengusaha Lokal": r"\b(tenaga kerja lokal|rekrutmen|putra daerah|anak daerah|pengusaha lokal|"
                                      r"kontraktor lokal|pekerja lokal|tkdn|konten lokal|pelatihan kerja)\b",
    "Lingkungan & AMDAL": r"\b(amdal|klhs|dampak lingkungan|ekosida|kerusakan lingkungan|pencemaran|mangrove|"
                          r"terumbu|limbah|reklamasi)\b",
    "Status PSN & Kebijakan Pusat": r"\b(cabut status|pencabutan status|status psn|dicabut dari psn|"
                                    r"(keluarkan|dikeluarkan) dari psn|evaluasi psn|pemerintah pusat|"
                                    r"revisi pod|plan of development|perpres|kebijakan pusat)\b",
    "Participating Interest & Dana Daerah": r"\b(participating interest|pi 10|bumd|dana bagi hasil|"
                                            r"pendapatan asli daerah|bagi hasil migas)\b",
    "Aksi Massa & Pengamanan": r"\b(demo|demonstrasi|unjuk rasa|berunjuk rasa|orasi|blokade|demonstran|"
                               r"massa aksi|menggelar aksi|aksi (damai|protes|demo|mahasiswa|warga|massa)|"
                               r"turun ke jalan|ditangkap|represif|kriminalisasi|mediasi)\b",
    "Groundbreaking & Konstruksi": r"\b(groundbreaking|ground breaking|peletakan batu|konstruksi|epc|feed|"
                                   r"pembangunan kilang|onshore lng|fasilitas lng)\b",
    "Investasi, Pendanaan & Mitra": r"\b(nilai investasi|pendanaan|danantara|final investment|fid|konsorsium|"
                                    r"hak partisipasi|divestasi|pertamina hulu|petronas)\b",
    "Dukungan & Harapan Kesejahteraan": r"\b(berkah|kesejahteraan|sejahtera|kemakmuran|makmur|harapan baru|"
                                        r"manfaat bagi masyarakat|lapangan kerja|multiplier effect|efek berganda|"
                                        r"mendukung (penuh )?(proyek|pembangunan|blok masela|pemerintah))\b",
    # tuduhan kolusi pejabat-perusahaan (dituntut pendemo) dipisah dari kekhawatiran korupsi
    # umum di kolom komentar ("semoga tidak dikorupsi"), agar lensa fokus aksi tidak tercemar
    "Dugaan Kongkalikong & Transparansi": r"\b(kongkalikong|kolusi|persekongkolan|main mata|transparansi|"
                                          r"tidak transparan|calo tanah|mafia tanah|makelar)\b",
    "Kekhawatiran Korupsi": r"\b(korupsi|dikorupsi|koruptor|korup|suap|kkn|mafia|oknum|tikus|bancakan)\b",
    "Peran Jepang": r"\b(pemerintah jepang|kedubes jepang|kedutaan besar jepang|dubes jepang|jbic|nexi|"
                    r"pm jepang|perdana menteri jepang|(kunjungan|lawatan) (kerja )?ke jepang|investor jepang|"
                    r"(dikuasai|milik|dimiliki) jepang|tokyo)\b",
}
TOPIK_BERITA = NARASI

# Lensa "fokus aksi": konten yang menyentuh demo atau tuntutan pendemo. Dashboard
# memakainya sebagai filter dan panel sorotan (porsi suara aksi vs narasi proyek).
FOKUS = {
    "nama": "Fokus aksi",
    "ket": "konten yang menyentuh demo atau isu yang dituntut pendemo (termasuk liputan pro-proyek tentang isu yang sama)",
    "narasi": ["Aksi Massa & Pengamanan", "Hak Tanah Adat & Ganti Rugi Lahan",
               "Kompensasi Nelayan & Ruang Laut", "Lingkungan & AMDAL",
               "Tenaga Kerja & Pengusaha Lokal", "Dugaan Kongkalikong & Transparansi"],
}

AKTOR = {
    "INPEX Masela": r"\binpex\b",
    "SKK Migas": r"\bskk ?migas\b",
    "Kementerian ESDM": r"\besdm\b|\bbahlil\b|menteri energi",
    "Pertamina": r"\bpertamina\b",
    "Petronas": r"\bpetronas\b",
    "Pemkab Kep. Tanimbar": r"\bbupati\b|pemkab|pemerintah kabupaten kepulauan tanimbar|pemda tanimbar",
    "Pemprov Maluku": r"gubernur maluku|pemprov maluku|pemerintah provinsi maluku",
    "DPRD": r"\bdprd\b",
    "DPR RI": r"\bdpr ri\b|\bkomisi xii\b|\bdpr\b",
    "Polri/Polda Maluku": r"\bpolri\b|\bpolda\b|\bpolres\b|\bkapolda\b|\bkapolres\b|\bpolsek\b",
    "Masyarakat Adat Tanimbar": r"masyarakat adat|tetua adat|tokoh adat|marga|petuanan",
    "Nelayan": r"\bnelayan\b",
    "Mahasiswa": r"\bmahasiswa\b|\bbem\b",
    "Kedubes Jepang": r"kedubes jepang|kedutaan besar jepang|pemerintah jepang",
    "Presiden": r"\bpresiden\b|\bprabowo\b",
    "Aktivis Lingkungan": r"\bwalhi\b|\bjatam\b|greenpeace|aktivis lingkungan",
}

STOP = {"blok", "masela", "marsela", "inpex", "abadi", "lng"}

# Aturan pengklasifikasi (scripts/label_teks.py): kata kerja kritik/dukungan sama dengan
# Virgo, hanya pihaknya yang berbeda. Dukungan yang dinegasikan ("tidak mendukung proyek")
# otomatis tidak dihitung. "abaikan": kata yang di Virgo menandai kritik (operator cari
# untung/cuan) tetapi di topik investasi ini netral ("untung presidennya...", "cuan saham").
ATURAN = {
    "pihak": r"inpex|skk ?migas|esdm|kementerian|menteri|bahlil|pertamina|petronas|bupati|gubernur|"
             r"pemda|pemkab|pemprov|dprd|aparat|kedubes|jepang|investor|kontraktor",
    "didukung": r"proyek|pembangunan|blok masela|masela|lng abadi|investasi|pemerintah|presiden|prabowo|"
                r"inpex|bupati|gubernur",
    "abaikan": r"untung|cuan|bisnis|duit",
}

# Istilah wawasan SNA: positif di topik ini berarti dukungan pada proyek/pihak, bukan empati musibah
ISTILAH = {"nada_positif": "suportif", "kantong_positif": "dukungan/apresiasi",
           "emosi": {"senang": "senang/optimis", "sedih": "sedih/kecewa"}}

# --------------------------------------------------------------- dashboard
KET_PLATFORM = {
    "Berita": "Artikel media nasional, media energi, dan media lokal Maluku, dipanen lewat Google News dan mesin pencari internal media. Sentimen berita masih baseline lexicon.",
    "X (Twitter)": "Tweet dari kata kunci dan tagar Masela beserta balasannya (utas relevan di 2026). Hasil kueri #Inpex yang berupa konten saham Jepang dibuang oleh filter relevansi.",
    "YouTube": "Video pemberitaan dan komentar serta balasannya, dipanen tanpa login lewat InnerTube. Tanggal komentar diperkirakan dari waktu relatif.",
    "Instagram": "Caption post dari tagar dan kata kunci Masela (didominasi akun resmi dan media) serta komentar pada 23 post dengan komentar terbanyak; sesi komentar berikutnya menyusul.",
    "Threads": "Post dan balasan dari pencarian kata kunci. Percakapan Masela di Threads tipis.",
}
CATATAN_LINIMASA = "Jumlah konten per pekan. Periode panjang (sejak Januari) diringkas per pekan agar terbaca."

# --------------------------------------------------------------- laporan
# Kesimpulan analis untuk laporan PDF (scripts/laporan.py); ditulis setelah membaca isi
# percakapan dan klaster. Angka bisa bergeser bila data dipanen ulang.
# judul sampul laporan PDF (JUDUL dipakai dashboard)
JUDUL_LAPORAN = "Proyek LNG Abadi INPEX di Blok Masela"
KESIMPULAN_TANGGAL = "1 Oktober 2026"
KESIMPULAN = [
    {"judul": "Volume tertinggi mengikuti groundbreaking",
     "isi": "Dua puncak terbesar (pekan 13 dan 27 Juli) mengikuti peresmian groundbreaking kilang oleh Presiden pada "
            "16 Juli. Groundbreaking dan konstruksi adalah isu terbesar, jauh di atas isu yang dituntut dalam aksi warga."},
    {"judul": "Kekhawatiran korupsi adalah isu negatif terbesar",
     "isi": "Ada 1.408 konten negatif (16,4% konten media sosial), tiga perempatnya komentar YouTube. Isu yang paling "
            "sering muncul adalah kekhawatiran proyek menjadi ladang korupsi, lalu skema investasi dan porsi saham asing. "
            "Penyebar terbanyak adalah MichaelRodney-l6h (11 konten) dan Rivan_Uchiha (10). Interaksi negatif paling "
            "banyak tertuju ke kanal METRO TV (95) dan cuanomik (63)."},
    {"judul": "Sebagian konten positif datang dari akun yang selalu bernada positif",
     "isi": "Ada 2.202 konten positif (25,6%). Penyebar terbanyak adalah kabkeptanimbar (24 konten, 92% positif), yang "
            "mengunggah kegiatan pemerintah daerah menjelang groundbreaking. Sriellypuryani dan kodimsaumlaki3208 "
            "masing-masing menulis 11 komentar YouTube yang semuanya positif; seluruh komentar kodimsaumlaki3208 ada di "
            "kanal Mpaktaraman. Akun X PendamPattimura menerima 85 interaksi positif."},
    {"judul": "Jaringan akun Instagram mengunggah caption identik",
     "isi": "Pada 30 Juni, 30 akun Instagram, sebagian besar bernama bulletin…qvl atau acehbarat…, mengunggah dua caption "
            "identik tentang percepatan Blok Masela dalam waktu sekitar 20 menit (90 unggahan). Nama akunnya memakai "
            "nama daerah di luar Maluku, seperti Muaro Jambi, Ngaglik, dan Kota Bogor."},
    {"judul": "Akun X baru membalas Pendam Pattimura",
     "isi": "Ada 52 akun X yang dibuat sejak Juli 2025 dan ikut membahas Masela. Enam di antaranya dibuat pada hari yang "
            "sama, 3 Juni 2026, dengan nol atau satu pengikut (Sandhitnjng20, ukkaisupy, ZulfanKodok, Marnur55, "
            "MalfinkauMalfin, ADRIAN4fp). Semua unggahan mereka berupa balasan pendek ke @PendamPattimura seperti \"TNI "
            "jaya\". Izalt25 (dibuat 9 Juni 2026) mengirim 34 balasan serupa."},
    {"judul": "Tuntutan aksi lebih banyak diberitakan daripada dibicarakan",
     "isi": "Lensa fokus aksi mencakup sekitar 40% berita tetapi hanya 1–4% konten media sosial. Liputan aksi massa hanya "
            "puluhan artikel, sebagian besar dari media lokal Maluku."},
    {"judul": "Suara lokal Maluku terdengar di Instagram",
     "isi": "Komentar di akun lokal Maluku membahas kekhawatiran laut tercemar, keraguan tenaga kerja lokal bisa terserap "
            "tanpa pelatihan migas, rasa \"dianaktirikan\" sebagai Indonesia Timur, dan besarnya pengamanan peresmian. "
            "Nadanya berbeda dengan klaster YouTube nasional."},
    {"judul": "Proyek dibahas lewat sudut kedaulatan dan geopolitik",
     "isi": "Shell yang hengkang, persaingan dengan Singapura dan Malaysia, serta peran Jepang sering dibahas. MoU "
            "investasi dengan Jepang disambut skeptis karena dinilai tidak mengikat dan dibandingkan dengan anggaran MBG."},
]
REKOMENDASI = [
    "Untuk memahami tuntutan warga Tanimbar, pantau media lokal Maluku dan akun lokal di Instagram. Percakapan nasional "
    "hampir tidak menyentuh isu itu.",
    "Isu yang perlu dijawab terbuka: ganti rugi lahan dan tanah adat, kompensasi nelayan, kesiapan tenaga kerja lokal "
    "(pelatihan dan sertifikasi), dampak lingkungan laut, dan pengawasan anggaran proyek.",
    "Saat membaca angka dukungan, keluarkan unggahan jaringan akun bulletin di Instagram dan balasan akun X baru ke "
    "@PendamPattimura (lihat bagian indikator amplifikasi).",
    "Simpan daftar akun dari bagian sentimen negatif, sentimen positif, dan indikator amplifikasi, lalu periksa apakah "
    "akun yang sama muncul lagi di topik lain.",
    "Lengkapi pengumpulan komentar Instagram agar suara lokal Maluku terwakili lebih utuh.",
]
