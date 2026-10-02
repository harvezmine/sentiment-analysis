# Analisa Sentimen

Pemetaan percakapan publik di berita daring dan media sosial (X, YouTube, Instagram, Threads): volume,
sentimen, emosi Plutchik, jaringan percakapan (SNA), dan narasi. Satu kerangka dipakai untuk banyak
topik dengan metode yang sama.

| Topik | Slug | Status |
|---|---|---|
| Tenggelamnya KM Virgo Transport 8 | `virgo` | selesai |
| Demo & aksi unjuk rasa INPEX Masela | `masela` | berjalan |
| Keresahan nelayan & masyarakat adat di proyek bp Tangguh | `tangguh` | berjalan |

## Struktur

```
topik/            satu file per topik: kata kunci, jendela waktu, filter relevansi, narasi, aktor, teks dashboard
  __init__.py     registri topik (DAFTAR) + kontrak isi file topik
  virgo.py, masela.py, tangguh.py
scripts/          pipeline panen & olah data; semua membaca topik aktif lewat scripts/konteks.py
lexicon/          lexicon InSet (Koto & Rahmaningtyas, 2017) untuk skor dasar sentimen berita (04_process)
data/<slug>/      data tiap topik terpisah (berita, x/, yt/, ig/, threads/, sna.json, sna_narasi.json)
data/_bersama/    cache lintas topik (mis. queryId GraphQL X)
webapp/           dashboard Flask: satu dashboard, topik dipilih di bilah atas (/<slug>/)
laporan/          PDF hasil scripts/laporan.py
```

Yang masuk git hanya kode, templat, lexicon, dan `data/<slug>/sna_narasi.json` (catatan klaster yang ditulis
manual). Data hasil panen, log (`raw/`), dan PDF tidak masuk git karena besar dan berisi nama akun serta unggahan
pengguna media sosial; pindahkan folder `data/` secara terpisah bila perlu (mis. `rsync`). Simpan repositori
sebagai **private**.

## Instalasi

```
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium     # hanya bila Google Chrome tidak terpasang (untuk laporan PDF)
```

Kredensial panen disimpan di luar repo, satu berkas JSON per platform di `~/.config/virgo-sentiment/`
(izin `chmod 600`), diisi dari cookie peramban akun yang dipakai memanen:

| Berkas | Isi | Ganti lokasi lewat |
|---|---|---|
| `x_auth.json` | `{"auth_token": "...", "ct0": "..."}` | `X_AUTH_PATH` |
| `ig_auth.json` | `{"sessionid", "csrftoken", "ds_user_id", "mid", "ig_did"}` | `IG_AUTH_PATH` |
| `threads_auth.json` | `{"sessionid", "csrftoken", "ds_user_id", "mid", "ig_did"}` | `THREADS_AUTH_PATH` |

## Menjalankan pipeline untuk satu topik

Pilih topik dengan `TOPIK=<slug>` atau `--topik <slug>`. Pakai Python 3.13
(`/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`); `python3` bawaan macOS tidak punya
dependensinya.

| Tahap | Perintah | Butuh login |
|---|---|---|
| Berita | `01_harvest_urls` → `02_decode_urls` → `05_harvest_native` → `03_scrape_articles` → `06_retry_failed` → `04_process` | tidak |
| YouTube | `10_yt_harvest` → `yt_relevan` → `11_yt_comments` | tidak |
| X | `07_x_harvest` → `09_x_sentimen` → `08_x_replies` → `09_x_sentimen` | ya |
| Instagram | `13_ig_harvest` → `14_ig_komentar` | ya |
| Threads | `15_threads_harvest` | ya |
| Jaringan | `12_sna` (setelah platform mana pun selesai) | tidak |

Contoh: `TOPIK=masela python3 scripts/10_yt_harvest.py`

Skrip pendukung (tidak dijalankan langsung kecuali disebut):

| Berkas | Fungsi |
|---|---|
| `konteks.py` | memilih topik aktif (`TOPIK`/`--topik`) dan folder datanya |
| `gnews_decode.py` | mengurai tautan Google News ke URL asli (dipakai `02_decode_urls`) |
| `x_client.py`, `x_parse.py` | klien dan pengurai GraphQL X |
| `x_qid.py` | menambang queryId GraphQL X terbaru; jalankan bila panen X gagal setelah X merilis versi baru |
| `ig_client.py`, `threads_client.py` | klien Instagram dan Threads (lambat, berhenti total saat diminta verifikasi) |
| `yt_client.py`, `yt_relevan.py`, `tanggal_yt.py` | klien YouTube tanpa login, penyaring video relevan, pengubah waktu relatif komentar |
| `label_teks.py` | pelabelan sentimen, emosi, isu, dan stance (dipakai pipeline dan dashboard) |
| `laporan.py` | generator laporan PDF |
| `ai_klien.py`, `ai_tugas.py`, `ai_jalan.py` | klien AI, tugas AI (label, klaster, kesimpulan, draf topik), dan pelaksananya |
| `ai_topik.py` | penyusun topik baru: riset judul berita/YouTube, draf, uji aturan terhadap penilaian AI, perbaikan |
| `ai_evaluasi.py`, `ai_uji_topik.py` | uji mutu: label AI vs sampel berlabel manual, dan draf topik AI vs konfigurasi buatan tangan |
| `label_ai.py` | label AI dan tanda tidak relevan per topik, diterapkan bersama di dashboard, graf SNA, dan laporan |
| `antrean.py` | antrean pekerjaan halaman Kelola |
| `x_akun_tipe.py` | klasifikasi tipe akun X versi awal; tidak dipakai pipeline saat ini |

Cookie sesi disimpan di luar repo, `~/.config/virgo-sentiment/` (`x_auth.json`, `ig_auth.json`,
`threads_auth.json`). Panen Instagram dan Threads sengaja lambat (jeda 12–25 detik, istirahat tiap 20
permintaan, batas per sesi) dan berhenti total pada tanda verifikasi atau rate-limit.

## Dashboard

```
python3 webapp/app.py      # lalu buka http://127.0.0.1:8080
```

## Halaman Kelola dan AI

Tombol ikon penggeser di bilah atas membuka `/<slug>/kelola`, tempat semua pekerjaan rutin dijalankan tanpa
terminal. Pekerjaan berat masuk antrean (`scripts/antrean.py`) sebagai proses terpisah: tetap berjalan walau
dashboard dimuat ulang, satu per satu per lajur, dengan log yang bisa dibuka dari halaman.

| Tab | Isi |
|---|---|
| Panen | Jalankan pipa per sumber (berita, YouTube, X, Instagram unggahan/komentar, Threads, graf SNA, queryId X). Panen selalu berurutan, jadi Instagram dan Threads tidak pernah bersamaan; ada jeda wajib antar-sesi (Instagram 4 jam, Threads 2 jam) dan tombol mati bila berkas login belum ada. |
| Validasi sentimen | Sampel acak bertingkat, beri label sendiri (pintasan 1/2/3/4), lalu bandingkan dengan label aturan dan label AI: akurasi, kappa, matriks, dan daftar konten yang berbeda. Dari sini sumber label topik dipilih (aturan atau AI), konten ditandai tidak relevan, dan semua konten bisa dilabeli AI dengan batas biaya. |
| Klaster | Nama dan catatan klaster SNA: draf AI dari contoh unggahan, ditinjau dan disimpan ke `sna_narasi.json`, lalu graf dibangun ulang. |
| Kesimpulan | Per periode: draf AI dari data periode itu (angka yang tidak ada di data ditandai), diedit, lalu disetujui. Versi disetujui dipakai laporan PDF sebagai catatan analis. |
| AI | Status key (disamarkan), saldo, model, batas biaya per tugas, dan pemakaian 30 hari. |

**Topik baru** (pemilih topik › Topik baru): tulis gambaran topik, minta draf dari AI atau isi manual, periksa, lalu
simpan. Draf AI (4–8 menit, sekitar $0,10–0,20; separuhnya di luar jam sibuk DeepSeek) dibuat dalam empat tahap oleh `scripts/ai_topik.py`:

1. riset: mencari judul Google News dan YouTube pada periode topik. Dua kueri luas (nama utama topik) dicari per
   jendela waktu bila periodenya panjang, ditambah kueri per isu;
2. draf: menyusun kata kunci, aturan relevansi, isu, dan aktor dengan judul hasil riset sebagai contoh nyata;
3. uji: AI menilai relevansi setiap judul riset, lalu aturan draf dicocokkan dengan penilaian itu. Ukurannya:
   ketepatan, kelengkapan, cakupan isu, jangkauan kueri, dan isu yang terlalu umum;
4. perbaiki: aturan, kata kunci isu, dan kueri diperbaiki dari contoh yang meleset (hingga dua kali), lalu versi
   dengan skor terbaik dipakai. Kata isu yang sebenarnya nama topik, nama aktor, wilayah, atau angka dibuang otomatis.

Hasil uji dan contoh judul yang meleset tampil di atas formulir, dan judul riset otomatis terisi di kotak uji contoh
teks. Istilah beberapa kata juga cocok dengan tagar tanpa spasi ("blok masela" menangkap #BlokMasela). Konfigurasi
disimpan sebagai data di `topik/<slug>.json` (lihat `topik/_umum.py`) dan langsung bisa dipanen dari
tab Panen; topik buatan tangan (`.py`) tidak diubah dari web.

AI memakai API kompatibel OpenAI, bawaan DeepSeek (`deepseek-flash` untuk klasifikasi tanpa mode berpikir,
`model_nalar` untuk klaster, kesimpulan, dan draf topik). Key di `~/.config/virgo-sentiment/ai.json` (izin 600) atau
`AI_API_KEY`; cek koneksi dengan `python3 scripts/ai_klien.py --cek`. Jawaban di-cache di `data/_bersama/ai_cache.sqlite`
(permintaan sama tidak dibayar ulang) dan pemakaian dicatat di `data/_bersama/ai_pemakaian.jsonl`. Hasil AI per topik
ada di `data/<slug>/_ai/` (`label.jsonl`, `validasi.json`, `klaster.json`, `kesimpulan/`, `setelan.json`). Label AI baru
dipakai dashboard, graf SNA, dan laporan setelah topik diubah ke "AI" di tab Validasi. Tugas AI juga bisa dijalankan
dari terminal, misalnya `TOPIK=masela python3 scripts/ai_jalan.py label --batas-usd 1`.

Teks unggahan dan nama akun dikirim ke penyedia AI (DeepSeek memproses di server Tiongkok). Kredensial panen dan berkas
data tidak pernah dikirim.

**Uji mutu.** `python3 scripts/ai_evaluasi.py --varian v3` membandingkan label aturan dan label AI dengan sampel berlabel
manual di `data/_bersama/evaluasi/sampel_<slug>.json`. `python3 scripts/ai_uji_topik.py --topik virgo` menyusun topik
yang sudah ada dari gambarannya saja, lalu membandingkan aturan hasil AI dengan konfigurasi buatan tangan pada data yang
sudah dipanen. Hasil keduanya disimpan di folder yang sama (`hasil_klasifikasi.json`, `hasil_topik.json`).

### Memasang daring

Dashboard bisa dipasang di server mana pun yang menjalankan Python (VPS, Render, Railway, Fly.io):

```
DASHBOARD_USER=... DASHBOARD_PASS=... gunicorn --chdir webapp -w 2 -t 300 -b 0.0.0.0:8080 app:app
```

- **Wajib pakai login.** `DASHBOARD_USER` dan `DASHBOARD_PASS` membuat semua halaman, API, dan unduhan laporan
  meminta login. Tanpa keduanya dashboard terbuka untuk siapa saja.
- **Data** tidak ada di git: salin folder `data/` ke server. Dashboard membaca langsung dari sana.
- **Laporan PDF** di server butuh Chromium (`playwright install --with-deps chromium`); `LAPORAN_CHROME=""`
  memaksa Chromium bawaan Playwright. Timeout gunicorn 300 detik karena laporan per rentang membangun graf SNA dulu.
- **Panen tetap dari laptop.** X, Instagram, dan Threads mudah memblokir sesi dari IP server/data center, dan
  sesi Instagram yang dipakai adalah akun utama. Alurnya: panen dan olah di laptop, lalu sinkronkan `data/` ke server.

## Laporan PDF

Satu perintah membuat laporan satu topik untuk seluruh periode atau rentang tanggal tertentu: sampul, daftar
isi bernomor, header dan footer, grafik dan graf SNA dari dashboard (tema cetak terang), paragraf penjelasan dari
data, lalu kesimpulan. Urutan bagian: ringkasan eksekutif, latar belakang dan metodologi, tren volume, sentimen
dan emosi, isu dan aktor, SNA (dengan istilah dan isi klaster), akun dan media berpengaruh, sentimen negatif dan
positif (graf SNA khusus satu sentimen, akun penyebar beserta akun yang mereka tanggapi dan yang menanggapi
mereka, ego-network, konten teratas), indikator amplifikasi terkoordinasi, serta kesimpulan.

```
python3 scripts/laporan.py --topik masela                                         # seluruh periode
python3 scripts/laporan.py --topik masela --dari 2026-07-01 --sampai 2026-07-31  # satu rentang
python3 scripts/laporan.py --topik virgo --keluar ~/Desktop/virgo.pdf
python3 scripts/laporan.py --topik tangguh --url http://127.0.0.1:8080/           # pakai dashboard yang sudah jalan
python3 scripts/laporan.py --topik masela --dari 2026-07-01 --sampai 2026-07-31 --ai  # nama klaster & kesimpulan oleh AI
```

Sumber kesimpulan laporan, berurutan: versi yang disetujui di Kelola › Kesimpulan untuk periode itu, catatan analis di
file topik (hanya seluruh periode), draf AI (bila `--ai` atau setelan topik mengizinkan), lalu ringkasan dari data.
Laporan per rentang dengan AI juga memberi nama klaster graf periode itu.

Hasil: `laporan/<slug>-laporan-<dari>_<sampai>-YYYYMMDD-HHMM.pdf`. Dari kode:
`from laporan import buat_laporan; buat_laporan("masela", dari="2026-07-01", sampai="2026-07-31")`.
Di dashboard, tombol **Laporan PDF** membuka panel pemilih periode (terisi periode filter yang aktif, plus preset
topik). Seluruh periode ±20 detik; rentang lain sedikit lebih lama karena graf SNA rentang itu dibangun dulu
(`12_sna.py` dengan `SNA_DARI`/`SNA_SAMPAI`/`SNA_KELUAR` ke `data/<slug>/_rentang/<dari>_<sampai>/`, dipakai ulang
selama data belum berubah). PDF yang masih mutakhir untuk periode yang sama langsung dikirim ulang (Shift+klik
atau `?baru=1` memaksa cetak ulang; di CLI `--cache` memakai yang tersimpan).

Kesimpulan dan rekomendasi analis ditulis di `topik/<slug>.py` (`KESIMPULAN`, `REKOMENDASI`, `KESIMPULAN_TANGGAL`,
judul sampul `JUDUL_LAPORAN`) dan hanya dipakai untuk laporan seluruh periode. Laporan rentang lain memakai
kesimpulan yang disusun dari data rentang itu, dan nama klaster otomatis (catatan kurasi `sna_narasi.json` ditulis
untuk seluruh periode). Label hasil pelabelan disimpan di `data/<slug>/_cache_label.pkl` dan otomatis diabaikan bila
aturan label berubah. Desain ada di `webapp/templates/laporan/` dan `webapp/static/laporan.css`; dashboard bertema
cetak bisa dibuka dengan `/<slug>/?cetak=1&dari=…&sampai=…`. Butuh Google Chrome dan `pip install pypdf`.

## Menambah topik baru

Cara termudah: halaman Kelola › Topik baru (lihat di atas). Cara manual untuk topik dengan aturan relevansi khusus:

1. Salin `topik/masela.py` menjadi `topik/<slug>.py`, isi kata kunci, jendela, filter relevansi, narasi, aktor.
2. Tambahkan `<slug>` ke `DAFTAR` di `topik/__init__.py`.
3. Tambahkan `webapp/templates/topik/<slug>_metode.html` (konteks peristiwa & catatan metode).
4. Jalankan pipeline dengan `TOPIK=<slug>`. Topik langsung muncul di pemilih topik.
5. Setelah membaca isi data, tulis `KESIMPULAN` dan `REKOMENDASI` di file topik untuk laporan PDF.

Nama dan butir kesimpulan klaster SNA dikurasi manual di `data/<slug>/sna_narasi.json` setelah membaca
isi tiap klaster, lalu `12_sna.py` dijalankan ulang.
