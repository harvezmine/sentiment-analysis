"""Pengklasifikasi teks bersama untuk semua platform (X, YouTube, Instagram).

Dipindahkan dari 09_x_sentimen.py agar X, YouTube, dan Instagram dilabeli
dengan aturan yang SAMA — tanpa itu perbandingan antar-platform tidak sah.

Catatan metodologis — dibaca dulu sebelum memakai angkanya:
Percakapan musibah penuh kata negatif yang sifatnya FAKTUAL ("tewas",
"hilang", "tenggelam"). Lexicon polos akan melabeli hampir semuanya negatif;
itu artefak, bukan temuan. Maka klasifikasi di sini memisahkan:

  sentimen  : nada evaluatif penulis  -> negatif / netral / positif
  emosi     : kategori lokal lama (duka, marah, takut, sinis, apresiasi, datar)
  emosi8    : 8 emosi dasar Plutchik — dipakai SNA by emotion, setara
              kategori laporan Drone Emprit
  stance    : sikap terhadap otoritas -> kritik / dukungan / netral
  narasi    : bingkai isu yang dipakai
"""
import re
import unicodedata


def _rx(pola, flags=re.I):
    """Rakit regex dari pola multi-baris TANPA re.X.

    Versi awal memakai re.X, yang diam-diam membuang SEMUA spasi di pola:
    frasa "terima kasih", "luar biasa", "usut tuntas", "tim sar" berubah
    jadi "terimakasih", "luarbiasa", ... dan tidak pernah cocok. Di sini
    tiap baris cukup di-strip lalu digabung, spasi di dalam frasa tetap utuh.
    """
    return re.compile("".join(b.strip() for b in pola.strip().splitlines()), flags)

# ------------------------------------------------------------ normalisasi
SLANG = {
    "gk": "tidak", "ga": "tidak", "gak": "tidak", "nggak": "tidak", "ngga": "tidak",
    "tdk": "tidak", "gada": "tidak ada", "bgt": "banget", "bngt": "banget",
    "yg": "yang", "dgn": "dengan", "krn": "karena", "krna": "karena", "utk": "untuk",
    "sdh": "sudah", "udh": "sudah", "udah": "sudah", "blm": "belum", "blom": "belum",
    "aja": "saja", "aj": "saja", "bs": "bisa", "gmn": "bagaimana", "knp": "kenapa",
    "emg": "memang", "emang": "memang", "bkn": "bukan", "jd": "jadi", "dr": "dari",
    "dlm": "dalam", "pd": "pada", "tp": "tapi", "tpi": "tapi", "sm": "sama",
    "org": "orang", "orng": "orang", "pemrintah": "pemerintah", "pemrinth": "pemerintah",
    "nih": "ini", "tuh": "itu", "bgs": "bagus", "jlk": "jelek", "prihatin": "prihatin",
    "kpn": "kapan", "hrs": "harus", "sy": "saya", "gw": "saya", "gue": "saya",
    "lu": "kamu", "lo": "kamu", "kl": "kalau", "klo": "kalau", "klu": "kalau",
    "bnyk": "banyak", "bnyak": "banyak", "smoga": "semoga", "smga": "semoga",
    "mdh": "mudah", "trs": "terus", "lg": "lagi", "dah": "sudah", "ky": "seperti",
    "kyk": "seperti", "kek": "seperti", "gitu": "begitu", "gini": "begini",
}

# Kata musibah yang FAKTUAL — sengaja TIDAK dimasukkan ke NEG_EVAL, itulah yang
# membuatnya netral. Set ini hanya dokumentasi/daftar periksa, tidak dipakai
# dalam perhitungan skor.
NETRAL_FAKTUAL = {
    "tenggelam", "tewas", "meninggal", "jenazah", "jasad", "korban", "hilang",
    "kecelakaan", "musibah", "terbalik", "karam", "evakuasi", "sar", "basarnas",
    "penyelam", "identifikasi", "dvi", "kapal", "penumpang", "selamat", "ditemukan",
    "pencarian", "bangkai", "mayat", "meninggalnya", "duka", "insiden", "tragedi",
}

EMOJI_POS = "😊😁😀🙏❤️💪👍🥰😇✨🤲🕊️"
EMOJI_NEG = "😡🤬😠👎🤮💀😤🙄😒"
EMOJI_SEDIH = "😭😢😞😔💔🥺😥"

# ------------------------------------------------------------ penanda
NEG_EVAL = _rx(r"""\b(
 lalai|kelalaian|abai|mengabaikan|teledor|ceroboh|serampangan|nekat|
 kecewa|mengecewakan|kecam|mengecam|kritik|mengkritik|protes|demo|
 desak|mendesak|tuntut|menuntut|tuntutan|marah|geram|murka|berang|
 sorot|menyoroti|disorot|(?<!cuaca )buruk|amburadul|semrawut|kacau|bobrok|
 carut.?marut|gagal|kegagalan|lambat|lamban|lelet|telat|terlambat|
 tidak becus|tak becus|becus|janggal|mencurigakan|curiga|patut diduga|
 melanggar|pelanggaran|langgar|manipulasi|dimanipulasi|rekayasa|
 korupsi|pungli|kongkalikong|suap|tutup.?tutupi|ditutupi|
 tidak transparan|tak transparan|minim|kurang|overload|kelebihan muatan|
 tidak laik|tak laik|kadaluarsa|uzur|rongsok|besi tua|karatan|
 dipertanyakan|pertanggungjawaban|tanggung jawab|siapa yang bertanggung|
 copot|pecat|mundur|turun|usut|usut tuntas|adili|penjara|hukum berat|
 miris|memprihatinkan|ironi|ironis|malu|memalukan|keterlaluan|
 pembiaran|dibiarkan|percuma|sia.?sia|omong kosong|janji palsu|
 mafia|oknum|bisnis|cuan|untung|duit|bancakan|
 tolak|menolak|penolakan|cabut|rampas|perampasan(?! aset)|ekosida|kriminalisasi|represif|
 intimidasi|diskriminasi|ingkar janji|dibohongi|diabaikan|pengkhianatan|merugikan|
 dirugikan|kongkalikong|kolusi|serakah|eksploitasi
)\b""")

POS_EVAL = _rx(r"""\b(
 apresiasi|mengapresiasi|terima kasih|makasih|trims|bangga|salut|hormat|
 sigap|cepat tanggap|responsif|gerak cepat|tanggap|optimal|maksimal|
 berhasil|sukses|luar biasa|hebat|keren|mantap|top|profesional|
 harapan|berharap|bersyukur|syukur|alhamdulillah|lega|
 solidaritas|gotong royong|bahu.?membahu|peduli|kepedulian|empati|
 dukung|mendukung|dukungan|bantu|membantu|bantuan|donasi|relawan|
 heroik|pahlawan|berjasa|jasa|tulus|ikhlas|
 semoga|doa|mendoakan|husnul|khotimah|khusnul|tenang di sisi|
 transparan|akuntabel|adil|tepat|sejahtera|kesejahteraan|berkah|membawa manfaat|
 bermanfaat|kemajuan|harapan baru
)\b""")

DUKA = re.compile(r"\b(turut berduka|berduka|belasungkawa|innalillahi|inna lillahi|"
                  r"al.?fatihah|alfatihah|rip|istirahat dalam damai|sedih|pilu|"
                  r"menangis|nangis|air mata|hancur|kehilangan|husnul|khusnul|"
                  r"tenang di sana|semoga tenang|lapang kuburnya)\b", re.I)
MARAH = re.compile(r"\b(marah|geram|murka|berang|emosi|kesal|kzl|muak|jijik|"
                   r"keterlaluan|kelewatan|gila|edan|anjir|anjay|bangsat|"
                   r"tidak terima|gak terima|ga terima)\b", re.I)
TAKUT = re.compile(r"\b(takut|ngeri|seram|trauma(?! healing)|waswas|khawatir|cemas|"
                   r"deg.?degan|merinding|horor|serem)\b", re.I)
SINIS = re.compile(r"\b((?<!luar )biasa|lagi.?lagi|seperti biasa|ujung.?ujungnya|paling juga|"
                   r"halah|alah|basi|drama|pencitraan|settingan|wacana|"
                   r"janji manis|kambing hitam(nya)?|cuma|hanya jadi)\b", re.I)

STANCE_KRITIK = _rx(r"""(
 (pemerintah|kemenhub|menhub|dishub|ksop|syahbandar|basarnas|polisi|polri|
  negara|pejabat|dpr|presiden|operator|perusahaan|pemilik kapal|pemilik|
  pengusaha|nakhoda|nahkoda|kapten|awak kapal|abk|pengawas|pengawasan|
  klasifikasi|bki|asdp|agen|owner)
 [^.!?\n]{0,80}
 (lalai|abai|gagal|lambat|buruk|salah(?!\s(satu|seorang))|tanggung jawab|dituntut|didesak|
  dikritik|dikecam|disorot|harus|wajib|jangan|usut|copot|pecat|mundur|
  seharusnya|harusnya|mestinya|kenapa|mengapa|diperiksa|periksa|tangkap|
  dihukum|diadili|kabur|kocak|parah|payah|ngawur)
)|(
 (lalai|abai|gagal|lambat|buruk|usut|copot|pecat|mundur|tuntut|desak|kritik|kecam|
  kenapa|mengapa|periksa|tangkap|hukum)
 [^.!?\n]{0,80}
 (pemerintah|kemenhub|menhub|dishub|ksop|syahbandar|basarnas|polisi|polri|
  negara|pejabat|dpr|presiden|operator|perusahaan|pemilik kapal|pemilik|
  pengusaha|nakhoda|nahkoda|kapten|awak kapal|abk|pengawas|pengawasan|
  klasifikasi|bki|asdp|agen|owner)
)""")

# Kritik yang tidak menyebut sasaran secara eksplisit: pertanyaan retoris,
# "seharusnya ...", tuduhan meninggalkan penumpang.
KRITIK_TERSIRAT = _rx(r"""(
 (menyelamatkan|selamatkan) diri sendiri|kabur duluan|lari duluan|
 (meninggalkan|tinggalkan|tinggalin) penumpang|
 \b(kenapa|mengapa|kok)\b[^.!?\n]{0,60}\b(tidak|belum|dibiarkan|diizinkan|
  lolos|berlayar|diam|boleh|bisa)\b|
 \b(seharusnya|harusnya|mestinya|sepatutnya)\b|
 \b(wajib|harus)\s+(di\s?)?(periksa|proses|tangkap|hukum|adili|pidana|usut|
  cabut|tindak)|
 \b(di)?tangk[ae]p\b|
 \b(\w+ ?nya|nurani|empati|hati) (di ?mana|ke ?mana)\b|tone deaf|
 \b(di)?penjara(kan)?\b|\bdi ?hukum (mati|berat|seumur)
)""")

# Doa untuk korban / petugas tanpa kata "semoga"
DOA = re.compile(r"\b(ya (allah|alloh|rabb|robb|tuhan)|lindungi(lah)?|selamatkan(lah)?(?! diri)|"
                 r"mudahkan(lah)?|dimudahkan|dikuatkan|diberi kekuatan|diberikan kekuatan|"
                 r"aamiin|amiin|amin)\b", re.I)

STANCE_DUKUNG = _rx(r"""(
 (basarnas|tni|tim sar|penyelam|relawan|petugas|polisi|kemenhub|pemerintah)
 [^.!?\n]{0,60}
 (hebat|luar biasa|salut|apresiasi|terima kasih|sigap|profesional|berjasa|
  bangga|dukung|semangat|kerja keras)
)|(
 (salut|apresiasi|terima kasih|bangga|dukung|semangat)
 [^.!?\n]{0,60}
 (basarnas|tni|tim sar|penyelam|relawan|petugas|polisi|kemenhub)
)""")

# Pihak di atas khas Virgo. Topik lain menambah pihaknya sendiri lewat
# topik/<slug>.py ATURAN = {"pihak": regex sasaran kritik, "didukung": regex
# sasaran dukungan, "abaikan": regex kata evaluatif yang di topik itu netral};
# kata kerjanya sama dengan pola Virgo agar metode setara.
_SALAH = (r"lalai|abai|gagal|lambat|buruk|salah(?!\s(satu|seorang))|tanggung jawab|dituntut|didesak|dikritik|dikecam|disorot|"
          r"harus|wajib|jangan|usut|copot|pecat|mundur|seharusnya|harusnya|mestinya|kenapa|mengapa|"
          r"diperiksa|periksa|tangkap|dihukum|diadili|kabur|kocak|parah|payah|ngawur")
_TUDUH = r"lalai|abai|gagal|lambat|buruk|usut|copot|pecat|mundur|tuntut|desak|kritik|kecam|kenapa|mengapa|periksa|tangkap|hukum"
_PUJI = r"hebat|luar biasa|salut|apresiasi|terima kasih|sigap|profesional|berjasa|bangga|dukung|semangat|kerja keras"
_PUJI_DEPAN = r"salut|apresiasi|terima kasih|bangga|dukung|semangat"
# "tidak mendukung proyek", "menolak dan tidak setuju": dukungan yang dinegasikan bukan dukungan
_NEGASI_DUKUNG = re.compile(r"\b(tidak|tak|bukan|jangan|belum|enggan|ogah|menolak|tolak)\b")
_STANCE_CACHE = {}


def _stance_rx(aturan):
    """[(regex, cek_negasi)] untuk kritik dan dukungan: pola Virgo + pihak topik bila ada."""
    if not aturan:
        return [(STANCE_KRITIK, False)], [(STANCE_DUKUNG, False)]
    kunci = id(aturan)
    if kunci not in _STANCE_CACHE:
        p, d = aturan.get("pihak"), aturan.get("didukung")
        kr, du = [(STANCE_KRITIK, False)], [(STANCE_DUKUNG, False)]
        if p:
            kr.append((re.compile(rf"({p})[^.!?\n]{{0,80}}({_SALAH})|({_TUDUH})[^.!?\n]{{0,80}}({p})", re.I), False))
        if d:
            du.append((re.compile(rf"({d})[^.!?\n]{{0,60}}({_PUJI})|({_PUJI_DEPAN})[^.!?\n]{{0,60}}({d})", re.I), True))
        _STANCE_CACHE[kunci] = (kr, du)
    return _STANCE_CACHE[kunci]


def _cari_stance(daftar, low):
    """Cocokan pertama (objek match) dari daftar pola stance, atau None."""
    for rx, cek_negasi in daftar:
        for m in rx.finditer(low):
            if cek_negasi and _NEGASI_DUKUNG.search(low[max(0, m.start() - 15):m.end()]):
                continue
            return m
    return None

NARASI = {
    "Duka & Belasungkawa": DUKA,
    "Kritik Regulasi & Kelaiklautan": re.compile(
        r"\b(kapal tua|usia kapal|39 tahun|laik laut|kelaiklautan|sertifikat|"
        r"uji petik|ramp check|izin|standar keselamatan|regulasi|aturan|"
        r"moratorium|audit|bekas jepang|eks jepang|rongsok|besi tua)\b", re.I),
    "Kritik Penanganan SAR": re.compile(
        r"\b(sar|pencarian|evakuasi|basarnas)[^.!?\n]{0,60}"
        r"(lambat|lamban|telat|terlambat|minim|kurang|lelet|tidak maksimal|"
        r"tak maksimal|dihentikan|distop)\b", re.I),
    "Apresiasi Tim SAR": STANCE_DUKUNG,
    "Manifes & Penumpang Gelap": re.compile(
        r"\b(manifes|tidak terdaftar|tak terdaftar|penumpang gelap|data penumpang|"
        r"selisih|overload|kelebihan (muatan|penumpang)|jumlah penumpang)\b", re.I),
    "Tuntutan Hukum & Tersangka": re.compile(
        r"\b(tersangka|pidana|penjara|adili|diadili|usut tuntas|proses hukum|"
        r"bareskrim|mabes|hukum berat|jerat|pasal|kejaksaan)\b", re.I),
    "Santunan & Nasib Keluarga": re.compile(
        r"\b(santunan|jasa raharja|asuransi|ganti rugi|kompensasi|ahli waris|"
        r"nasib keluarga|anak yatim|tulang punggung)\b", re.I),
    "Cuaca & Penyebab Teknis": re.compile(
        r"\b(cuaca buruk|gelombang tinggi|ombak|angin kencang|bmkg|miring|oleng|"
        r"kemiringan|bocor|air masuk|stabilitas|muatan bergeser|kelebihan beban)\b", re.I),
    "Hoaks & Klarifikasi": re.compile(
        r"\b(hoaks|hoax|cek fakta|disinformasi|misinformasi|video lama|"
        r"tidak benar|klarifikasi|jangan sebar|bukan video)\b", re.I),
    "Kelas Sosial & Ketimpangan": re.compile(
        r"\b(rakyat kecil|rakyat jelata|wong cilik|grassroot|kelas bawah|"
        r"orang miskin|yang mampu|naik pesawat|kalau pejabat|kalau orang kaya|"
        r"nyawa rakyat|nyawa murah)\b", re.I),
}


def normalize(t):
    t = unicodedata.normalize("NFKC", str(t or ""))
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"@\w+", " ", t)
    t = re.sub(r"\bRT\b", " ", t)
    return t


def slangify(t):
    # kata ulang ("lagi-lagi", "ujung-ujungnya") dipertahankan utuh; tanpa ini
    # tokenizer memecahnya jadi "lagi - lagi" dan penanda sinis tidak pernah cocok
    return " ".join(SLANG.get(w, w) for w in re.findall(r"[a-zA-Z']+(?:-[a-zA-Z']+)*|\S", t.lower()))


_NARASI_CACHE = {}


def _narasi_rx(narasi):
    """Kompilasi dict narasi topik (nama -> regex str) sekali saja."""
    if narasi is None:
        return NARASI
    kunci = id(narasi)
    if kunci not in _NARASI_CACHE:
        _NARASI_CACHE[kunci] = {n: (r if hasattr(r, "search") else re.compile(r, re.I))
                                for n, r in narasi.items()}
    return _NARASI_CACHE[kunci]


# "tidak mendukung", "belum sejahtera", "bukan berkah": kata positif yang dinegasikan
# (maksimal satu kata sisipan, "tidak pernah mendukung") dihitung sebagai penanda negatif
_NEGASI_DEPAN = re.compile(r"\b(tidak|tak|bukan|jangan|belum)\s+(\w+\s+)?$")
# kata doa/syukur membuka anak kalimat baru ("... gk terjadi, semoga ..."), tidak bisa dinegasikan
_TAK_DINEGASI = re.compile(r"^(semoga|moga|aamiin|amiin|amin|alhamdulillah|syukur|terima kasih|makasih)", re.I)


def _eval_positif(low):
    """(kata positif utuh, kata positif yang dinegasikan) dari POS_EVAL."""
    utuh, dinegasi = [], []
    for m in POS_EVAL.finditer(low):
        n = _NEGASI_DEPAN.search(low[max(0, m.start() - 25):m.start()])
        if n and not _TAK_DINEGASI.match(m.group(0)):
            dinegasi.append(f"{n.group(1)} {m.group(0)}")
        else:
            utuh.append(m.group(0))
    return utuh, dinegasi


_ABAIKAN_CACHE = {}


def _eval_negatif(low, aturan=None):
    """Kata evaluatif negatif, tanpa kata yang di topik ini netral (ATURAN["abaikan"])."""
    kata = NEG_EVAL.findall(low)
    pola = (aturan or {}).get("abaikan")
    if not pola:
        return kata
    rx = _ABAIKAN_CACHE.setdefault(pola, re.compile(rf"({pola})", re.I))
    return [k for k in kata if not rx.fullmatch(k)]


_SAMAR_CACHE = {}


def _samarkan(teks, aturan):
    """Nama diri yang kebetulan juga kata evaluatif (proyek "Tangguh") diganti token netral
    sebelum dicocokkan dengan leksikon, lewat ATURAN["samarkan"] topik."""
    pola = (aturan or {}).get("samarkan")
    if not pola or not teks:
        return teks
    rx = _SAMAR_CACHE.setdefault(pola, re.compile(pola, re.I))
    return rx.sub("NAMADIRI", teks)


def klasifikasi(teks, narasi=None, aturan=None):
    """narasi: dict narasi topik (topik/<slug>.py NARASI); None = narasi bawaan (Virgo).
    aturan: dict aturan topik (topik/<slug>.py ATURAN); None = aturan bawaan (Virgo)."""
    raw = normalize(_samarkan(teks, aturan))
    low = slangify(raw)
    low = re.sub(r"\bbantu (up|naikin|naikkan)\b", "naikkan", low)

    pos_utuh, pos_negasi = _eval_positif(low)
    neg = len(_eval_negatif(low, aturan)) + len(pos_negasi)
    pos = len(pos_utuh)
    # penanda emoji
    pos += sum(low.count(e) for e in EMOJI_POS) * 1
    neg += sum(raw.count(e) for e in EMOJI_NEG) * 1
    sedih = sum(raw.count(e) for e in EMOJI_SEDIH)

    duka = bool(DUKA.search(low)) or sedih > 0
    marah = bool(MARAH.search(low))
    takut = bool(TAKUT.search(low))
    sinis = bool(SINIS.search(low))
    st_kritik, st_dukung = _stance_rx(aturan)
    kritik = bool(_cari_stance(st_kritik, low)) or bool(KRITIK_TERSIRAT.search(low))
    dukung = bool(_cari_stance(st_dukung, low))
    doa = bool(DOA.search(low))
    if doa:
        pos += 1

    if kritik or marah:
        neg += 2
    if sinis:
        neg += 1
    if dukung:
        pos += 2

    # Duka murni tanpa penanda evaluatif = netral secara sentimen,
    # emosinya yang bernilai (sedih), bukan penilaian terhadap pihak mana pun.
    if duka and neg == 0 and pos <= 1:
        sentimen = "netral"
    elif neg > pos:
        sentimen = "negatif"
    elif pos > neg:
        sentimen = "positif"
    else:
        sentimen = "netral"

    if marah or (kritik and neg >= 3):
        emosi = "marah"
    elif duka:
        emosi = "duka"
    elif takut:
        emosi = "takut"
    elif sinis:
        emosi = "sinis"
    elif dukung or pos > neg:
        emosi = "apresiasi"
    else:
        emosi = "datar"

    if kritik and not dukung:
        stance = "kritik"
    elif dukung and not kritik:
        stance = "dukungan"
    else:
        stance = "netral"

    narasi = [n for n, rx in _narasi_rx(narasi).items() if rx.search(low)]

    emosi8 = emosi_plutchik(raw, low, duka=duka, kritik=kritik, dukung=dukung, doa=doa)
    # Leksikon Plutchik lebih luas daripada penanda evaluatif lama; teks yang
    # jelas marah/muak/takut tapi lolos sebagai netral diselaraskan di sini
    # agar peta sentimen dan peta emosi tidak saling bertentangan.
    if sentimen == "netral":
        if emosi8 in ("marah", "jijik", "takut"):
            sentimen = "negatif"
        elif emosi8 in ("percaya", "senang"):
            sentimen = "positif"
    return {
        "sentimen": sentimen, "emosi": emosi, "emosi8": emosi8, "stance": stance,
        "narasi": "; ".join(narasi), "narasi_utama": narasi[0] if narasi else "Lainnya",
        "skor_neg": neg, "skor_pos": pos,
    }


# ------------------------------------------------------- emosi Plutchik
# Delapan emosi dasar Plutchik, sama dengan kategori laporan Drone Emprit
# (Joy, Trust, Fear, Surprise, Sadness, Disgust, Anger, Anticipation).
# Leksikon disesuaikan dengan konteks musibah kapal: "semoga cepat ditemukan"
# adalah antisipasi, "kapal tua / overload" adalah muak (disgust) terhadap
# kelalaian, "salut tim SAR" adalah kepercayaan.
EMOSI8 = ["marah", "jijik", "takut", "sedih", "terkejut", "percaya", "senang", "antisipasi"]
EMOSI8_EN = {"marah": "Anger", "jijik": "Disgust", "takut": "Fear", "sedih": "Sadness",
             "terkejut": "Surprise", "percaya": "Trust", "senang": "Joy",
             "antisipasi": "Anticipation", "netral": "Neutral"}

_E8 = {
    "marah": (re.compile(r"\b(marah|geram|murka|berang|kesal|kzl|emosi|tidak terima|"
                         r"usut tuntas|tangkap|hukum berat|hukum mati|penjara|adili|pecat|"
                         r"copot|lalai|kelalaian|teledor|ceroboh|serakah|rakus|brengsek|"
                         r"bangsat|anjing|goblok|bodoh|tolol|kurang ajar|biadab|keterlaluan|"
                         r"kelewatan|harus tanggung jawab|siapa yang bertanggung)\b", re.I),
              "😡🤬😠😤👿"),
    "jijik": (re.compile(r"\b(bobrok|busuk|memalukan|muak|jijik|nyawa murah|pencitraan|mafia|"
                         r"cuan|pungli|korup|korupsi|suap|omong kosong|sandiwara|halah|alah|"
                         r"basi|kapal tua|besi tua|rongsok|karatan|overload|kelebihan muatan|"
                         r"seperti biasa|lagi.?lagi|konoha|wakanda|negeri ini|ujung.?ujungnya|"
                         r"paling juga|kambing hitam|janji manis|amburadul|semrawut|carut.?marut)\b",
                         re.I),
              "🤮🙄😒🤦🤢"),
    "takut": (re.compile(r"\b(takut|ngeri|seram|serem|trauma(?! healing)|waswas|was.?was|khawatir|cemas|"
                         r"panik|merinding|horor|kapok|ogah naik|tidak berani|gak berani|"
                         r"deg.?degan)\b", re.I),
              "😨😰😱"),
    "sedih": (re.compile(r"\b(turut berduka|berduka|duka|belasungkawa|innalillahi|inna lillahi|"
                         r"innalilahi|al.?fatihah|rip|sedih|pilu|menangis|nangis|air mata|"
                         r"kasihan|kasian|husnul|khusnul|khotimah|khatimah|tabah|ketabahan|"
                         r"kehilangan|ditinggal|yatim|tenang di sisi|lapang kubur|ya allah|"
                         r"ya rabb|hancur hati|patah hati)\b", re.I),
              "😭😢😞😔💔🥺😥🥀"),
    "terkejut": (re.compile(r"\b(kok bisa|koq bisa|kaget|terkejut|astaga|astagfirullah|"
                            r"astaghfirullah|ya ampun|yaampun|tidak menyangka|tak menyangka|"
                            r"nyangka|masa sih|mengejutkan|tiba.?tiba|wow|hah|loh|lho)\b", re.I),
                 "😱😮😲🤯😳"),
    "percaya": (re.compile(r"\b(terima kasih|terimakasih|makasih|salut|hormat|hebat|luar biasa|"
                           r"bangga|pahlawan|heroik|berjasa|profesional|sigap|tangguh|"
                           r"kerja keras|semangat|percaya|amanah|mantap|keren|respect|"
                           r"apresiasi|mengapresiasi)\b", re.I),
                "💪👏🫡🙌"),
    "senang": (re.compile(r"\b(alhamdulillah|syukur|bersyukur|lega|bahagia|senang|gembira|"
                          r"ditemukan selamat|ditemukan hidup|masih hidup|berhasil diselamatkan|"
                          r"keajaiban|mukjizat)\b", re.I),
               "😊😁😀🥰😍🥳❤️"),
    "antisipasi": (re.compile(r"\b(semoga (cepat|segera|lekas|bisa|ditemukan|tidak terulang|"
                              r"jadi pelajaran|jadi evaluasi)|segera|menunggu|nunggu|kapan|"
                              r"berharap|harapan|mohon|tolong|evaluasi|ke depan|kedepan|"
                              r"jangan sampai|jangan terulang|tidak terulang|pelajaran|waspada|"
                              r"antisipasi|perbaiki|pembenahan|kawal|pantau|kabar terbaru|"
                              r"masih dicari|doakan|mari berdoa)\b", re.I),
                   "🤲🙏"),
}


_NEGASI = re.compile(r"\b(tidak|tak|bukan|tanpa|jangan) (\w+)")
_NEGASI_UTUH = {"terima", "berani", "menyangka", "nyangka", "becus", "laik", "transparan"}


def emosi_plutchik(raw, low, duka=False, kritik=False, dukung=False, doa=False):
    """Pilih satu emosi dominan. Skor = jumlah penanda leksikal + emoji,
    ditambah sinyal stance dari pengklasifikasi utama. Seri dipecahkan oleh
    urutan EMOSI8 (emosi yang lebih spesifik/kuat menang)."""
    # negasi: "tidak takut", "jangan sedih" bukan takut/sedih. Frasa yang
    # justru bermakna emosi ("tidak terima", "tidak berani", "tidak menyangka")
    # dibiarkan utuh.
    low = _NEGASI.sub(lambda m: m.group(0) if m.group(2) in _NEGASI_UTUH
                      else f"{m.group(1)}_{m.group(2)}", low)
    skor = {}
    for e, (rx, emoji) in _E8.items():
        s = len(rx.findall(low)) + sum(raw.count(ch) for ch in emoji)
        skor[e] = s
    if kritik:
        skor["marah"] += 1
    if dukung:
        skor["percaya"] += 2
    if duka:
        skor["sedih"] += 1
    if doa:
        skor["antisipasi"] += 1     # doa = harapan atas hasil yang belum terjadi
    terbaik = max(EMOSI8, key=lambda e: (skor[e], -EMOSI8.index(e)))
    return terbaik if skor[terbaik] > 0 else "netral"


# ------------------------------------------------------ penjelasan label
def penanda(teks, narasi=None, aturan=None):
    """Kata/pola yang membuat sebuah teks dilabeli seperti itu — untuk
    ditampilkan di dashboard sebagai bukti, dengan bobot yang sama persis
    dengan klasifikasi()."""
    raw = normalize(_samarkan(teks, aturan))
    low = slangify(raw)
    low = re.sub(r"\bbantu (up|naikin|naikkan)\b", "naikkan", low)
    pos, neg = [], []
    pos_utuh, pos_negasi = _eval_positif(low)
    pos += pos_utuh
    neg += pos_negasi
    pos += [e for e in EMOJI_POS if e in low]
    neg += _eval_negatif(low, aturan)
    neg += [e for e in EMOJI_NEG if e in raw]
    m = DOA.search(low)
    if m:
        pos.append(f"doa: {m.group(0)}")
    st_kritik, st_dukung = _stance_rx(aturan)
    m = _cari_stance(st_dukung, low)
    if m:
        pos.append(f"dukungan ×2: {m.group(0)[:40]}")
    m = _cari_stance(st_kritik, low) or KRITIK_TERSIRAT.search(low)
    if m:
        neg.append(f"kritik ×2: {m.group(0)[:40]}")
    elif MARAH.search(low):
        neg.append(f"marah ×2: {MARAH.search(low).group(0)}")
    m = SINIS.search(low)
    if m:
        neg.append(f"sinis: {m.group(0)}")
    duka = DUKA.search(low)
    # label yang diputus lewat penyelarasan emosi (lihat klasifikasi) tidak
    # punya penanda sentimen sendiri — tampilkan emosinya sebagai alasan
    k = klasifikasi(teks, narasi=narasi, aturan=aturan)
    if k["sentimen"] == "negatif" and not neg:
        neg.append(f"via emosi {k['emosi8']}")
    if k["sentimen"] == "positif" and not pos:
        pos.append(f"via emosi {k['emosi8']}")
    return {"pos": list(dict.fromkeys(pos))[:6], "neg": list(dict.fromkeys(neg))[:6],
            "duka": duka.group(0) if duka else ""}
