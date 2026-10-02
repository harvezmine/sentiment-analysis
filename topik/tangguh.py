"""Topik: keresahan & tuntutan masyarakat terkait proyek bp Tangguh (Ubadari), Papua Barat.

Konteks (riset 30 Sep 2026): proyek Tangguh UCC (Ubadari, CCUS Vorwata, Compression) yang
dioperasikan bp (BP Berau) di Teluk Bintuni dan Fakfak memicu rangkaian ketegangan 2026:
  - Feb–Mar 2026  masyarakat Petuanan Arguni (Raja Hanafi Paus Paus) memasang sasi adat
                  pada kapal seismik bp di Teluk Arguni karena merasa tidak diberitahu;
                  muncul kapal TNI AL; Bupati Fakfak Samaun Dahlan meminta warga Kokas dan
                  Arguni menahan diri; sasi dicabut 10 Maret, seismik dilanjutkan
  - Mei 2026      LMA Suku Besar Sebyar (Teluk Bintuni) menyampaikan 8 tuntutan: kejelasan
                  PI 10%, alokasi kargo LNG untuk daerah penghasil, evaluasi CSR, pelibatan
                  masyarakat adat dalam perpanjangan kontrak hingga 2055; Menteri ESDM
                  meminta bp mengalokasikan PI 10% ke pemerintah daerah Papua Barat
  - Jun 2026      Kepala Distrik Arguni menuntut transparansi pemasangan anjungan (jacket)
                  UB-A dan UB-B, zona aman nelayan, tenaga kerja lokal, saluran pengaduan
Isu yang dipantau: radius aman & ruang laut nelayan, kompensasi & hak petuanan, PI 10% & DBH.
"""
import re
from datetime import date

SLUG = "tangguh"
NAMA = "bp Tangguh Ubadari"
JUDUL = "Keresahan nelayan & masyarakat adat di proyek bp Tangguh"
ATAS = "Laporan percakapan publik · Januari–September 2026"
LEDE = ("Proyek Tangguh UCC (lapangan Ubadari) yang dioperasikan bp di Teluk Bintuni dan Fakfak, "
        "Papua Barat, memicu keresahan sepanjang 2026: sasi adat masyarakat Petuanan Arguni atas kapal "
        "seismik (Februari–Maret), tuntutan PI 10% dan dana bagi hasil dari Teluk Bintuni (Mei), serta "
        "tuntutan zona aman nelayan saat pemasangan anjungan UB-A dan UB-B (Juni). Halaman ini memetakan "
        "cara media dan warganet membicarakannya.")
STATUS = "berjalan"
JENDELA = ("2026-01-01", date.today().isoformat())
PRESET = [
    ("Seluruh 2026", "2026-01-01", JENDELA[1]),
    ("Sasi kapal seismik · Feb–Mar", "2026-02-01", "2026-03-20"),
    ("Tuntutan PI & LMA Sebyar · Mei", "2026-05-01", "2026-06-05"),
    ("Anjungan UB-A/UB-B · Jun", "2026-06-01", "2026-06-30"),
    ("3 bulan terakhir", "2026-07-01", JENDELA[1]),
]

# ------------------------------------------------------------------ berita
KUERI_BERITA = [
    '"BP Tangguh"', '"Tangguh LNG"', '"LNG Tangguh"', '"Ubadari"', '"Tangguh UCC"',
    'bp Indonesia Tangguh', '"BP Berau"', 'Vorwata CCUS', 'bp Indonesia Papua Barat',
    # insiden seismik & sasi adat (Feb–Mar)
    'kapal seismik Arguni', 'sasi kapal seismik', 'sasi adat seismik Fakfak', 'Raja Arguni seismik',
    'Hanafi Paus Paus', 'Petuanan Arguni', 'seismik Arguni Fakfak', 'seismik bp Fakfak nelayan',
    'Kokas Arguni bp', 'Teluk Arguni migas', 'blok Gaea Fakfak', 'Samaun Dahlan seismik',
    # nelayan & zona aman (Jun)
    'nelayan Fakfak bp Tangguh', 'nelayan Teluk Bintuni bp', 'anjungan UB-A UB-B',
    'zona aman nelayan bp Tangguh', 'Distrik Arguni bp Tangguh', 'Kepala Distrik Arguni',
    # kompensasi, hak adat, PI & DBH (Mei)
    'LMA Sebyar', 'LMA Sebyar bp Tangguh', 'Suku Besar Sebyar LNG', 'bp Tangguh masyarakat adat',
    'bp Tangguh kompensasi', 'participating interest Teluk Bintuni', 'PI 10 persen Tangguh',
    'dana bagi hasil Teluk Bintuni', 'DBH migas Teluk Bintuni', 'kargo LNG Teluk Bintuni',
    'perpanjangan kontrak Tangguh 2055', 'Bupati Teluk Bintuni bp', 'Bupati Fakfak bp Tangguh',
    'bp Tangguh Bahlil', 'bp Tangguh SKK Migas Papua Barat',
    # tenaga kerja, CSR, lingkungan, aksi
    'bp Tangguh tenaga kerja lokal', 'bp Tangguh CSR', 'bp Tangguh lingkungan',
    'demo bp Tangguh', 'palang bp Tangguh', 'bp Tangguh Teluk Bintuni 2026',
]
KUERI_BERITA_INTI = ['"BP Tangguh"', '"Tangguh LNG"', 'Ubadari Arguni']
KUERI_SITUS = ['"Tangguh"', '"Arguni"']
SITUS_TAMBAHAN = [
    # media Papua: insiden di Arguni dan Bintuni sering hanya diberitakan di sini
    "jubi.id", "klikpapua.com", "koreri.com", "mataradarindonesia.com", "infofakfak.com",
    "papuabaratnews.co", "suarapapua.com", "cenderawasihpos.jawapos.com", "seputarpapua.com",
    "kabarpapua.co", "linkpapua.com", "papuabarat.antaranews.com", "papuabarat.tribunnews.com",
    "fajarpapua.com", "teropongnews.com", "papuakini.co", "tabloidjubi.com", "wartaplus.com",
    # media energi & lembaga
    "dunia-energi.com", "ruangenergi.com", "petromindo.com", "esdm.go.id", "skkmigas.go.id",
]
KUERI_NATIVE = ["BP Tangguh", "Tangguh LNG", "Ubadari", "Arguni", "Teluk Bintuni migas"]
JUDUL_KUAT = (r"tangguh ?lng|lng tangguh|bp tangguh|ubadari|vorwata|tangguh uc+|uc+ tangguh|uc+ (offshore|onshore)|"
              r"uba jacket|bp berau|arguni|sebyar|bomberai|(gas|proyek|kilang|terminal|fasilitas) tangguh|"
              r"tangguh papua|di tangguh\b")
JUDUL_LONGGAR = (r"(teluk bintuni|bintuni|fakfak|kokas|babo).{0,60}(lng|migas|gas|seismik|\bbp\b|kilang|psn|"
                 r"participating|bagi hasil|nelayan|adat|terminal|pipa|jacket|anjungan)|(\bbp\b|british petroleum)"
                 r".{0,40}(papua|bintuni|fakfak|tangguh|migas|lng|kontrak|blok|psc|eksplorasi)")

# ----------------------------------------------------------------- YouTube
KUERI_YT = [
    'BP Tangguh', 'Tangguh LNG', 'LNG Tangguh Bintuni', 'Ubadari', 'Tangguh UCC',
    'kapal seismik Arguni', 'sasi kapal seismik Fakfak', 'Raja Arguni', 'nelayan Arguni',
    'Teluk Bintuni LNG', 'Teluk Bintuni BP', 'Fakfak BP Tangguh', 'LMA Sebyar',
    'demo BP Tangguh', 'participating interest Teluk Bintuni', 'Bahlil Teluk Bintuni',
    'bp Indonesia Papua', 'Vorwata CCUS', 'Kokas Fakfak migas', 'Tangguh LNG 2026',
    'dana bagi hasil Teluk Bintuni', 'Petuanan Arguni',
]

# ---------------------------------------------- X / IG / Threads (fase berikut)
KUERI_X = [
    '"BP Tangguh"', '"Tangguh LNG"', '"LNG Tangguh"', 'Ubadari', 'Arguni',
    'Teluk Bintuni BP', 'Teluk Bintuni LNG', 'Fakfak BP', 'Tangguh Bintuni', '#TelukBintuni', 'Sebyar',
]
KUERI_X_HARIAN = ['"BP Tangguh"', 'Tangguh Bintuni']
TAGAR_IG = ["bptangguh", "tangguhlng", "lngtangguh", "telukbintuni", "arguni", "ubadari"]
TAGAR_IG_LEBAR = ["fakfak", "bintuni", "bpindonesia", "papuabarat"]
KUERI_IG = ["BP Tangguh", "Tangguh LNG", "Teluk Bintuni LNG", "Arguni", "Ubadari"]
KUERI_THREADS = ["BP Tangguh", "Tangguh LNG", "Teluk Bintuni", "Arguni", "Ubadari", "Fakfak BP"]

# --------------------------------------------------------------- relevansi
# "Tangguh" juga kata biasa ("Desa Tangguh Bencana", "tim tangguh") dan "BP" juga singkatan lain
# (BP Batam, BP2MI, BP Tapera): keduanya hanya dihitung bersama konteks proyek.
_KUAT = re.compile(r"tangguh ?lng|lng ?tangguh|bp ?tangguh|kilang tangguh|tangguh uc+|uc+ tangguh|proyek tangguh|"
                   r"gas tangguh|uba jacket|uc+ (offshore|onshore)|"
                   r"(lapangan|proyek|blok|gas|ladang|anjungan|jacket) ubadari|ubadari (field|gas|ccus|project|"
                   r"development|uc+)|vorwata|bp ?berau|blok berau|blok wiriagar|blok muturi|"
                   r"lma (suku besar )?sebyar", re.I)
# "Ubadari" juga nama kampung dan air terjun di Fakfak: tanpa konteks proyek, bukan topik ini
_UBADARI = re.compile(r"ubadari", re.I)
_BP = re.compile(r"\bbp\b|british petroleum|bp indonesia", re.I)
# "Bp" juga singkatan "Bapak": "Bp/Ibu Pdt", "Bp. Kepala Distrik", "Ibu/Bp"
_BAPAK = re.compile(r"\bbp\s*[/.]\s*(ibu|bu\b)|\bibu\s*/\s*bp\b|\bbp\.\s*[A-Z]|\bbp\s+(pdt|pendeta|kepala|bupati|camat|lurah|"
                    r"presiden|gubernur|haji|h\.)", re.I)
_TANGGUH = re.compile(r"\btangguh\b", re.I)
_WILAYAH = re.compile(r"teluk bintuni|bintuni|fakfak|arguni|kokas|babo|tanah merah|saengga|onar|taver|"
                      r"papua barat|bomberai|domberai", re.I)
_MIGAS = re.compile(r"\b(lng|migas|gas|kilang|seismik|seismic|anjungan|platform|psn|skk ?migas|esdm|"
                    r"participating interest|pi 10|dana bagi hasil|dbh|minyak|hulu|offshore|jacket|pipa)\b", re.I)
# Arguni & Sebyar juga nama wilayah/suku dengan banyak konten budaya, wisata, dan olahraga
# ("Piala Raja Arguni", "Sebyar Cup", sasi pala di Kaimana): hanya dihitung bersama isu proyek
_ARGUNI = re.compile(r"arguni|sebyar", re.I)
# tanpa "gas" polos: di media sosial "gas" juga berarti "ayo" ("gas ke Karas")
_ISU_ARGUNI = re.compile(r"seismik|seismic|seimik|bp tangguh|bp indonesia|british petroleum|migas|\blng\b|"
                         r"gas (bumi|alam)|tangguh|"
                         r"perusahaan|industri|kompensasi|tenaga kerja|rekrut|participating|\bpi\b|dbh|"
                         r"bagi hasil|kapal (seismik|survei|pendeteksi)|sasi (kapal|laut)|anjungan|jacket", re.I)
_BP_LAIN = re.compile(r"bp ?batam|bp2mi|bp tapera|bp jamsostek|bpjs|bp haji|bp2|bp ?kkn|tekanan darah|"
                      r"blood pressure|bp ?ppd|bp ?mpr|badan pengkajian", re.I)
# bp juga punya SPBU di Indonesia: berita harga BBM eceran bukan topik ini
_RITEL = re.compile(r"spbu|harga bbm|\bbbm\b|bp ultimate|ultimate diesel|bp 9[25]|pertamax|\bvivo\b|bp-akr|bp akr", re.I)
# istilah hulu yang cukup kuat untuk mengaitkan "bp" dengan proyek walau tanpa nama wilayah
_HULU = re.compile(r"\b(lng|seismik|seismic|kilang|hulu|offshore|anjungan|eksplorasi|blok|psc|kontrak bagi hasil|"
                   r"participating interest|skk ?migas|gas bumi|ladang gas|lapangan gas|ccus)\b", re.I)


def relevan(teks):
    teks = teks or ""
    if _KUAT.search(teks):
        return 1
    if _ARGUNI.search(teks) and _ISU_ARGUNI.search(teks):
        return 1
    if _UBADARI.search(teks) and (_HULU.search(teks) or _MIGAS.search(teks)) and not re.search(
            r"air terjun|wisata", teks, re.I):
        return 1
    bp = _BP.search(teks) and not _BP_LAIN.search(teks)
    if bp and _BAPAK.search(teks) and len(_BP.findall(teks)) == len(_BAPAK.findall(teks)):
        bp = False                        # semua "bp" di teks ini berarti "Bapak"
    if bp and _RITEL.search(teks) and not _HULU.search(teks):
        bp = False                        # daftar harga BBM per wilayah juga menyebut "Papua Barat"
    if bp and (_WILAYAH.search(teks) or (_HULU.search(teks) and not _RITEL.search(teks))):
        return 1
    # "tangguh" tanpa bp hanya dihitung bila ada wilayah proyek DAN istilah migas
    if _TANGGUH.search(teks) and _WILAYAH.search(teks) and _MIGAS.search(teks):
        return 1
    # "sasi" di Fakfak juga sasi pala (larangan panen pala): hanya dihitung bila menyasar kapal
    if _WILAYAH.search(teks) and re.search(r"\b(lng|seismik|participating interest|dana bagi hasil migas|"
                                            r"kilang lng|skk ?migas)\b|sasi.{0,30}kapal|kapal.{0,30}"
                                            r"(seismik|pendeteksi gas)", teks, re.I):
        return 1
    return 0


_SEBUT = re.compile(r"tangguh|bintuni|arguni|sebyar|ubadari|vorwata|\bbp\b|fakfak", re.I)


def relevan_x(teks, kueri=""):
    """Tweet: aturan relevan() ditambah satu syarat. Utas panjang soal Papua atau politik
    yang menyebut Tangguh sekali lewat (mis. daftar kekayaan alam Papua) bukan topik ini."""
    teks = teks or ""
    if not relevan(teks):
        return 0
    if len(teks) > 1200 and len(_SEBUT.findall(teks)) < 2:
        return 0
    return 1


# ---------------------------------------------------------------- analisis
NARASI = {
    "Sasi Adat & Penghentian Seismik": r"\b(sasi|kera-kera|larangan adat|kapal seismik|survei seismik|seismik|"
                                       r"seismic|penghentian seismik|hentikan seismik|sanksi adat)\b",
    "Keselamatan Nelayan & Zona Aman": r"\b(nelayan|zona aman|radius aman|zona terlarang|daerah terlarang|"
                                       r"wilayah tangkap|area tangkap|alur pelayaran|keselamatan pelayaran|"
                                       r"rumpon|perahu|longboat|jaring)\b",
    "Kompensasi & Hak Petuanan": r"\b(kompensasi|ganti rugi|tali asih|hak adat|hak ulayat|petuanan|tanah adat|"
                                 r"pemilik hak ulayat|dana adat|hak masyarakat adat)\b",
    "PI 10% & Dana Bagi Hasil": r"\b(participating interest|pi 10|pi sepuluh|dana bagi hasil|dbh|"
                                r"bagi hasil migas|bumd|keadilan fiskal|kargo lng|alokasi lng|daerah penghasil)\b",
    "Transparansi & Sosialisasi": r"\b(transparansi|tidak transparan|keterbukaan|sosialisasi|tidak diberitahu|"
                                  r"tidak dilibatkan|pelibatan|konsultasi publik|fpic|saluran pengaduan)\b",
    "Tenaga Kerja & Pengusaha Lokal": r"\b(tenaga kerja lokal|pekerja lokal|putra daerah|anak adat|orang asli papua|"
                                      r"\boap\b|pengusaha lokal|kontraktor lokal|rekrutmen|koperasi)\b",
    "Lingkungan & Ekosistem Pesisir": r"\b(amdal|dampak lingkungan|limbah|pencemaran|mangrove|ekosistem|"
                                      r"terumbu|abrasi|kerusakan lingkungan|kelestarian laut)\b",
    "Aksi Protes & Pemalangan": r"\b(demo|demonstrasi|unjuk rasa|pemalangan|palang|blokade|orasi|protes|"
                                r"menggelar aksi|aksi (damai|protes|demo|massa|warga))\b",
    "Pengamanan & Aparat": r"\b(tni al|kapal perang|lanal|brimob|aparat keamanan|pengamanan|militer|"
                           r"intimidasi|kodim|dandim)\b",
    "Mediasi & Penyelesaian": r"\b(mediasi|musyawarah|dialog|kesepakatan|cabut sasi|pencabutan sasi|sasi dicabut|"
                              r"sasi dibuka|menahan diri|rekonsiliasi|jalan tengah|duduk bersama)\b",
    "Proyek Ubadari & Konstruksi": r"\b(anjungan|jacket|ub-a|ub-b|uba|ubb|pemasangan platform|pipa bawah laut|"
                                   r"konstruksi|epc|saipem|meindo|offshore)\b",
    # "SKK Migas"/"Kementerian ESDM" disebut sebagai latar di hampir semua berita proyek: bukan narasi
    "Kontrak & Kebijakan Pusat": r"\b(perpanjangan kontrak|2055|plan of development|revisi kontrak|"
                                 r"kontrak bagi hasil|kebijakan pusat|pemerintah pusat|keputusan menteri)\b",
    "Dukungan & Harapan Kesejahteraan": r"\b(kesejahteraan|sejahtera|lapangan kerja|harapan baru|manfaat bagi masyarakat|"
                                        r"mendukung (penuh )?(proyek|pembangunan|kegiatan|investasi|bp))\b",
}
TOPIK_BERITA = NARASI

# Lensa sorotan: konten yang menyentuh keresahan atau tuntutan warga (termasuk tanggapan
# perusahaan/pemerintah atas isu yang sama). Dashboard memakainya sebagai filter + panel porsi.
FOKUS = {
    "nama": "Fokus keresahan",
    "ket": "konten yang menyentuh keresahan atau tuntutan warga: sasi & seismik, zona aman nelayan, kompensasi & hak petuanan, PI & DBH, transparansi, aksi protes",
    "narasi": ["Sasi Adat & Penghentian Seismik", "Keselamatan Nelayan & Zona Aman",
               "Kompensasi & Hak Petuanan", "PI 10% & Dana Bagi Hasil",
               "Transparansi & Sosialisasi", "Aksi Protes & Pemalangan"],
}

AKTOR = {
    "bp (BP Tangguh/Berau)": r"\bbp\b|british petroleum|bp tangguh|bp berau|bp indonesia",
    "SKK Migas": r"\bskk ?migas\b",
    "Kementerian ESDM": r"\besdm\b|\bbahlil\b|menteri energi",
    "Pemkab Fakfak": r"bupati fakfak|samaun dahlan|pemkab fakfak|pemerintah kabupaten fakfak|pemda fakfak",
    "Pemkab Teluk Bintuni": r"bupati teluk bintuni|bupati bintuni|pemkab teluk bintuni|pemkab bintuni|"
                            r"pemerintah kabupaten teluk bintuni|pemda teluk bintuni",
    "Pemprov Papua Barat": r"gubernur papua barat|pemprov papua barat|pemerintah provinsi papua barat",
    "Raja Petuanan Arguni": r"raja arguni|raja petuanan|petuanan arguni|hanafi paus",
    "LMA Sebyar": r"\bsebyar\b|lembaga masyarakat adat|\blma\b",
    "Masyarakat Adat": r"masyarakat adat|tokoh adat|pemilik hak ulayat|tetua adat|marga",
    "Nelayan": r"\bnelayan\b",
    "Kepala Distrik Arguni": r"kepala distrik|distrik arguni|fatamasya",
    "TNI/TNI AL": r"\btni\b|\blanal\b|kapal perang|\bkodim\b|\bdandim\b",
    "Polri": r"\bpolri\b|\bpolda\b|\bpolres\b|\bkapolres\b|\bkapolda\b",
    "DPRD": r"\bdprd\b|\bdprk\b",
    "DPR RI": r"\bdpr ri\b|\bkomisi xii\b",
    "Kontraktor (Saipem/Meindo)": r"\bsaipem\b|\bmeindo\b|deepocean|kontraktor",
}

STOP = {"bp", "tangguh", "lng", "ubadari", "teluk", "bintuni"}

# Aturan pengklasifikasi: kata kerja kritik/dukungan sama dengan topik lain, pihaknya disesuaikan
ATURAN = {
    "pihak": r"\bbp\b|british petroleum|skk ?migas|esdm|kementerian|menteri|bahlil|bupati|gubernur|"
             r"pemda|pemkab|pemprov|dprd|aparat|\btni\b|kontraktor|kepala distrik",
    "didukung": r"proyek|pembangunan|kegiatan|seismik|\bbp\b|tangguh|investasi|pemerintah|presiden|bupati|"
                r"raja|kepala distrik",
    "abaikan": r"untung|cuan|bisnis|duit",
    # "Tangguh" di topik ini adalah nama proyek, bukan pujian ("tangguh" ada di leksikon percaya):
    # tanpa ini "kebakaran hutan dekati LNG Tangguh" terbaca positif
    "samarkan": r"\btangguh\b",
}

ISTILAH = {"nada_positif": "suportif", "kantong_positif": "dukungan/apresiasi",
           "emosi": {"senang": "senang/optimis", "sedih": "sedih/kecewa"}}

# --------------------------------------------------------------- dashboard
KET_PLATFORM = {
    "Berita": "Artikel media nasional, media energi, dan media lokal Papua (Jubi, Klik Papua, Koreri, Info Fakfak, dll.), dipanen lewat Google News dan mesin pencari internal media. Sentimen berita masih baseline lexicon.",
    "X (Twitter)": "Tweet dari kata kunci proyek dan wilayah beserta balasannya. Percakapan X soal isu 2026 sangat tipis; utas panjang soal Papua yang menyebut Tangguh sekali lewat tidak dihitung.",
    "YouTube": "Video pemberitaan dan komentar serta balasannya, dipanen tanpa login lewat InnerTube. Tanggal komentar diperkirakan dari waktu relatif.",
    "Instagram": "Caption post dari tagar dan kata kunci proyek; didominasi unggahan pribadi pekerja, program pelatihan P2TIM, dan akun pemerintah daerah. Komentar belum dipanen (jumlahnya kecil).",
    "Threads": "Post dan balasan dari pencarian kata kunci; isinya terutama cerita pekerja proyek. \"Ubadari\" yang merujuk kampung atau air terjun di Fakfak dan \"Bp\" yang berarti Bapak tidak dihitung.",
}
CATATAN_LINIMASA = "Jumlah konten per pekan. Periode panjang (sejak Januari) diringkas per pekan agar terbaca."

# --------------------------------------------------------------- laporan
# Kesimpulan analis untuk laporan PDF (scripts/laporan.py); ditulis setelah membaca isi
# percakapan dan klaster. Angka bisa bergeser bila data dipanen ulang.
# judul sampul laporan PDF (JUDUL dipakai dashboard)
JUDUL_LAPORAN = "Proyek bp Tangguh Ubadari di Teluk Bintuni dan Fakfak"
KESIMPULAN_TANGGAL = "1 Oktober 2026"
KESIMPULAN = [
    {"judul": "Tiga gelombang pemberitaan",
     "isi": "Februari: kapal seismik disebut mengusir nelayan dan sasi adat Arguni dipasang. Mei: pelantikan dan tuntutan "
            "LMA Sebyar, pemberangkatan jacket UBA. September, yang paling ramai: desakan audit PI 10%, kesepakatan LMA "
            "Sebyar, roadmap PAD migas yang belum ditandatangani bp, usulan DBH 45%, dan kebakaran hutan dekat kilang."},
    {"judul": "Isu seismik mereda, isu fiskal dan hak adat bertambah",
     "isi": "Ketegangan di Arguni turun setelah sasi dicabut pada 10 Maret dan tuntutan kompensasi disampaikan. "
            "Pemberitaan soal PI 10%, dana bagi hasil, dan pelibatan LMA Sebyar justru bertambah menjelang akhir September."},
    {"judul": "Keresahan warga terdengar lewat media lokal Papua",
     "isi": "Lensa fokus keresahan mencakup sekitar 39% berita tetapi hanya 0–8% konten media sosial. Suara warga Arguni, "
            "Kokas, dan Sebyar muncul terutama di Garda Papua, Jubi, Mata Radar Indonesia, Info Fakfak, dan RRI."},
    {"judul": "Konten positif datang dari pekerja proyek dan kampanye PSN",
     "isi": "Ada 98 konten positif, hampir separuhnya dari Instagram: unggahan pekerja dengan tagar #LNGTangguh, info "
            "lowongan, dan akun resmi bp_plc. Di X, itsyoungmikco menerima 7 interaksi positif. Tiga akun "
            "(Lamine175638484, MKogoya55201, carolinede49544) membalas unggahannya dengan kalimat yang sama dalam 28 jam."},
    {"judul": "Konten negatif sedikit dan tersebar",
     "isi": "Hanya ada 19 konten negatif. Isinya terutama lingkungan pesisir dan konflik ruang laut. Hanya satu akun "
            "(eddesign_) yang mengunggah lebih dari satu konten negatif."},
    {"judul": "Aktor kunci dalam pemberitaan",
     "isi": "Graf pemberitaan menempatkan bp, Kementerian ESDM, dan SKK Migas di pusat. Aktor warga yang paling sering "
            "disebut adalah masyarakat adat, LMA Sebyar, nelayan, dan Raja Petuanan Arguni."},
    {"judul": "Volume percakapan kecil",
     "isi": "Hanya sekitar 450 konten sepanjang 2026 yang membahas topik ini. Diskusi warga terdampak kemungkinan besar "
            "berlangsung di Facebook dan grup WhatsApp, yang tidak tercakup dalam laporan ini."},
]
REKOMENDASI = [
    "Pantau media lokal Papua secara rutin (Garda Papua, Jubi, Mata Radar Indonesia, Info Fakfak, RRI Fakfak dan "
    "Manokwari). Keresahan warga muncul di sana lebih dulu.",
    "Isu yang perlu dijawab terbuka: kejelasan PI 10% dan dana bagi hasil, termasuk pelibatan LMA Sebyar; kompensasi dan "
    "pelibatan langsung pemilik petuanan; zona aman dan sosialisasi kegiatan laut bagi nelayan.",
    "Pertimbangkan pemantauan halaman dan grup Facebook lokal (dengan izin) untuk menangkap suara warga terdampak.",
    "Sentimen positif di media sosial berasal dari pekerja proyek dan kampanye PSN, sehingga tidak bisa dipakai sebagai "
    "ukuran dukungan warga terdampak.",
    ]
