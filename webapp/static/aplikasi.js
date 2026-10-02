/* Utilitas bersama dashboard: palet, grafik, filter, dan kontrol custom.

   Semua warna data berasal dari palet yang divalidasi untuk buta warna di
   permukaan gelap (#1c1c1a). Warna mengikuti ENTITAS, bukan peringkat:
   YouTube selalu hijau-toska, narasi yang sama selalu warna yang sama,
   walau filter mengubah urutannya. */

/* ------------------------------------------------------------- palet */
// tema cetak (laporan PDF): bidang terang, tinta gelap; diaktifkan lewat ?cetak=1
const CETAK = !!window.CETAK;
const WARNA_SENT = { negatif: '#e66767', netral: CETAK ? '#bdbab1' : '#5a5954', positif: '#3987e5',
                     'belum dilabeli': CETAK ? '#dedbd3' : '#3a3a36' };
const SLOT = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'];
const WARNA_PLATFORM = { 'Berita': SLOT[0], 'X (Twitter)': SLOT[1], 'YouTube': SLOT[2],
                         'Instagram': SLOT[3], 'Threads': SLOT[4] };
// emosi Plutchik dipetakan ke 8 slot dengan urutan yang sama (lolos uji CVD berdampingan)
const SNA_EMO = { sedih: SLOT[0], antisipasi: SLOT[1], percaya: SLOT[2], senang: SLOT[3],
                  terkejut: SLOT[4], takut: SLOT[5], jijik: SLOT[6], marah: SLOT[7], netral: CETAK ? '#bdbab1' : '#5a5954' };
const SNA_EMO_NAMA = { senang: 'Senang', percaya: 'Percaya', takut: 'Takut', terkejut: 'Terkejut',
                       sedih: 'Sedih', jijik: 'Muak', marah: 'Marah', antisipasi: 'Antisipasi',
                       netral: 'Netral' };
const SNA_EMO_EN = { senang: 'Joy', percaya: 'Trust', takut: 'Fear', terkejut: 'Surprise',
                     sedih: 'Sadness', jijik: 'Disgust', marah: 'Anger',
                     antisipasi: 'Anticipation', netral: 'Neutral' };
const IKON_PLATFORM = { 'X (Twitter)': '𝕏', 'YouTube': '▶', 'Instagram': '◎', 'Threads': '@', 'Berita': '▤' };
const WARNA_SATU = SLOT[0];             // grafik satu seri: satu warna
const HURUF = "'Plus Jakarta Sans', sans-serif";
const INK = CETAK ? { 1: '#1d1d1b', 2: '#45443f', 3: '#6c6b65', 4: '#9a978f' }
                  : { 1: '#ebe9e3', 2: '#c5c3ba', 3: '#908e86', 4: '#6c6b65' };
const GARIS = CETAK ? '#e9e6df' : '#2a2a27', PERMUKAAN = CETAK ? '#ffffff' : '#1b1b19';
const GARIS_SUMBU = CETAK ? '#cfcbc1' : '#393935';

/* narasi: warna ditetapkan saat pertama terlihat, disimpan per sesi */
const WARNA_NARASI = (() => { try { return JSON.parse(sessionStorage.getItem('warnaNarasi') || '{}'); } catch (e) { return {}; } })();
function warnaNarasi(nama) {
  if (!WARNA_NARASI[nama]) {
    const n = Object.keys(WARNA_NARASI).length;
    WARNA_NARASI[nama] = n < SLOT.length ? SLOT[n] : INK[4];
    try { sessionStorage.setItem('warnaNarasi', JSON.stringify(WARNA_NARASI)); } catch (e) { /* abaikan */ }
  }
  return WARNA_NARASI[nama];
}

/* ------------------------------------------------------ default Chart.js */
Chart.defaults.color = INK[3];
Chart.defaults.locale = 'id-ID';          // 5.000, bukan 5,000
Chart.defaults.borderColor = GARIS;
Chart.defaults.font.family = HURUF;
Chart.defaults.font.size = 12;
Chart.defaults.maintainAspectRatio = false;
Chart.defaults.animation.duration = 350;
Object.assign(Chart.defaults.plugins.legend.labels, {
  usePointStyle: true, pointStyle: 'circle', boxWidth: 7, boxHeight: 7, padding: 16, color: INK[2],
});
Chart.defaults.plugins.legend.align = 'start';
Object.assign(Chart.defaults.plugins.tooltip, {
  backgroundColor: CETAK ? '#ffffff' : '#2a2a27', borderColor: GARIS_SUMBU, borderWidth: 1, cornerRadius: 9,
  padding: { x: 12, y: 10 }, titleColor: INK[1], bodyColor: INK[2], titleFont: { weight: '700', size: 12.5 },
  bodyFont: { size: 12.5 }, boxPadding: 5, usePointStyle: true, caretSize: 5,
});
Chart.defaults.elements.bar.borderRadius = 4;
Chart.defaults.elements.line.borderWidth = 2;
Chart.defaults.elements.point.radius = 0;
Chart.defaults.elements.point.hoverRadius = 4;

// sumbu tenang: grid hairline hanya di sumbu nilai, tanpa garis tepi
function sumbu(nilai = 'y', opsi = {}) {
  const kat = nilai === 'y' ? 'x' : 'y';
  return {
    [nilai]: { beginAtZero: true, grid: { color: GARIS, drawTicks: false }, border: { display: false },
               ticks: { padding: 8, color: INK[3], ...(opsi.ticks || {}) }, stacked: !!opsi.tumpuk,
               ...(opsi.maks ? { max: opsi.maks } : {}) },
    [kat]: { grid: { display: false }, border: { color: GARIS_SUMBU },
             // sumbu kategori horizontal (bar menyamping) tidak boleh melewatkan label
             ticks: { padding: 6, color: INK[3], autoSkipPadding: 14, maxRotation: 0,
                      autoSkip: nilai === 'y', ...(opsi.ticksKat || {}) },
             stacked: !!opsi.tumpuk },
  };
}

/* ------------------------------------------------------------- data */
const grafik = {};

function kueri(tambahan = {}) {
  const p = new URLSearchParams();
  const g = id => (document.getElementById(id) || {}).value || '';
  if (g('f-platform')) p.set('platform', g('f-platform'));
  if (g('f-tipe')) p.set('tipe', g('f-tipe'));
  if (g('f-dari')) p.set('dari', g('f-dari'));
  if (g('f-sampai')) p.set('sampai', g('f-sampai'));
  if (INFO.per) p.set('per', INFO.per);
  const fk = document.getElementById('f-fokus');
  if (fk && fk.checked) p.set('fokus', '1');
  for (const k in tambahan) if (tambahan[k] !== '' && tambahan[k] != null) p.set(k, tambahan[k]);
  return p.toString();
}

// topik aktif (diisi base.html): {slug, awal, akhir, preset}
const INFO = window.TOPIK_INFO || { slug: '', awal: '', akhir: '', preset: [] };

// '/api/sentimen' -> '/api/<topik>/sentimen': template cukup menulis jalur tanpa topik
function api(jalur) {
  return INFO.slug && jalur.startsWith('/api/') ? `/api/${INFO.slug}/${jalur.slice(5)}` : jalur;
}

async function ambil(jalur, tambahan) {
  const r = await fetch(api(jalur) + '?' + kueri(tambahan));
  if (!r.ok) throw new Error(jalur + ' → HTTP ' + r.status);
  return r.json();
}

function gambar(id, konfigurasi) {
  const el = document.getElementById(id);
  if (!el) return;
  if (grafik[id]) grafik[id].destroy();
  grafik[id] = new Chart(el.getContext('2d'), konfigurasi);
}

function angka(n) { return (n || 0).toLocaleString('id-ID'); }
function ringkasAngka(n) {
  n = n || 0;
  if (n >= 1e9) return (n / 1e9).toFixed(1).replace('.0', '').replace('.', ',') + ' M';
  if (n >= 1e6) return (n / 1e6).toFixed(1).replace('.0', '').replace('.', ',') + ' jt';
  if (n >= 1e3) return (n / 1e3).toFixed(1).replace('.0', '').replace('.', ',') + ' rb';
  return String(n);
}
function persen(v, total) { return total ? (100 * v / total) : 0; }
function aman(t) { return String(t == null ? '' : t).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }
const kapital = t => t ? t[0].toUpperCase() + t.slice(1) : t;
function kelasSentimen(s) { return { negatif: 'l-neg', netral: 'l-net', positif: 'l-pos' }[s] || 'l-none'; }
function tglPendek(t) {
  const b = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
  const [, m, d] = String(t).split('-');
  return d ? `${+d} ${b[+m - 1]}` : t;
}

/* ------------------------------------------------------ grafik umum */
const URUT_PLATFORM = Object.keys(WARNA_PLATFORM);
const urutPlatform = seri => [...seri].sort((a, b) => URUT_PLATFORM.indexOf(a.nama) - URUT_PLATFORM.indexOf(b.nama));

function grafikLinimasa(data, id = 'g-linimasa') {
  data = { ...data, seri: urutPlatform(data.seri) };
  gambar(id, {
    type: 'line',
    data: { labels: data.label.map(tglPendek), datasets: data.seri.map(s => ({
      label: s.nama, data: s.data, borderColor: WARNA_PLATFORM[s.nama] || INK[3],
      backgroundColor: WARNA_PLATFORM[s.nama] || INK[3], tension: .3, pointHoverBorderWidth: 2,
      pointHoverBorderColor: PERMUKAAN })) },
    options: { interaction: { mode: 'index', intersect: false }, scales: sumbu('y'),
               plugins: { legend: { display: data.seri.length > 1 } } },
  });
}

function grafikKumulatif(data, id = 'g-kumulatif') {
  data = { ...data, seri: urutPlatform(data.seri) };
  gambar(id, {
    type: 'line',
    data: { labels: data.label.map(tglPendek), datasets: data.seri.map(s => ({
      label: s.nama, data: s.data, borderColor: WARNA_PLATFORM[s.nama] || INK[3],
      backgroundColor: (WARNA_PLATFORM[s.nama] || INK[3]) + '40', fill: true, tension: .3, borderWidth: 1.5 })) },
    options: { interaction: { mode: 'index', intersect: false },
               scales: sumbu('y', { tumpuk: true, ticks: { callback: v => ringkasAngka(v) } }),
               plugins: { legend: { display: false } } },
  });
}

// pengganti donat: tiga angka + satu batang 100% (lebih mudah dibandingkan)
function isiSentimenRingkas(d, id = 'sen-ringkas') {
  const el = document.getElementById(id);
  if (!el) return;
  const nilai = {};
  d.label.forEach((k, i) => { nilai[k] = d.data[i]; });
  const kunci = ['negatif', 'netral', 'positif'];
  const total = kunci.reduce((s, k) => s + (nilai[k] || 0), 0);
  if (!total) { el.innerHTML = '<p class="memuat">Belum ada konten berlabel.</p>'; return; }
  el.innerHTML = `
    <dl class="sen-angka">${kunci.map(k => `<div>
      <dt><i style="background:${WARNA_SENT[k]}"></i>${k[0].toUpperCase() + k.slice(1)}</dt>
      <dd>${persen(nilai[k] || 0, total).toFixed(1).replace('.', ',')}%<small>${angka(nilai[k] || 0)} konten</small></dd>
    </div>`).join('')}</dl>
    <div class="sen-bar" role="img" aria-label="Komposisi sentimen">${kunci.map(k =>
      `<i style="width:${persen(nilai[k] || 0, total)}%;background:${WARNA_SENT[k]}"></i>`).join('')}</div>
    ${nilai['belum dilabeli'] ? `<p class="sen-catat">${angka(nilai['belum dilabeli'])} konten belum dilabeli tidak dihitung.</p>` : ''}`;
}

function grafikSentimenHarian(h, id = 'g-sentimen-harian') {
  const urut = ['negatif', 'netral', 'positif'];
  const seri = urut.map(k => (h.seri || []).find(s => s.nama === k)).filter(Boolean);
  h = { label: h.label || [], seri: h.seri || [] };
  gambar(id, {
    type: 'bar',
    data: { labels: h.label.map(tglPendek), datasets: seri.map(s => ({
      label: kapital(s.nama), data: s.data, backgroundColor: WARNA_SENT[s.nama],
      borderColor: PERMUKAAN, borderWidth: { top: 2 }, borderRadius: 0, maxBarThickness: 26 })) },
    options: { interaction: { mode: 'index', intersect: false }, scales: sumbu('y', { tumpuk: true }) },
  });
}

// batang 100% bertumpuk: membandingkan komposisi antar-kategori yang berbeda ukuran
function grafikTumpuk100(id, label, seri, opsi = {}) {
  const total = label.map((_, i) => seri.reduce((s, x) => s + (x.data[i] || 0), 0));
  gambar(id, {
    type: 'bar',
    data: { labels: label, datasets: seri.map(x => ({
      label: kapital(x.nama), data: x.data.map((v, i) => +persen(v, total[i]).toFixed(1)), mentah: x.data,
      backgroundColor: x.warna, borderColor: PERMUKAAN, borderWidth: { right: 2 }, borderRadius: 0,
      maxBarThickness: 22 })) },
    options: {
      indexAxis: 'y',
      plugins: { tooltip: { callbacks: { label: c =>
        ` ${c.dataset.label}: ${c.raw}% (${angka(c.dataset.mentah[c.dataIndex])})` } } },
      scales: sumbu('x', { tumpuk: true, maks: 100, ticks: { callback: v => v + '%' } }),
      onClick: opsi.onClick,
    },
  });
}

function grafikBatangH(id, label, data, warna, opsi = {}) {
  gambar(id, {
    type: 'bar',
    data: { labels: label, datasets: [{ data, backgroundColor: warna || WARNA_SATU,
      borderSkipped: 'start', maxBarThickness: 18, categoryPercentage: .78 }] },
    options: {
      indexAxis: 'y', plugins: { legend: { display: false },
        tooltip: { callbacks: { label: c => ' ' + (opsi.format ? opsi.format(c.raw) : angka(c.raw)) } } },
      scales: sumbu('x', { ticks: { callback: v => ringkasAngka(v) },
                           ticksKat: { color: INK[2], callback(v) { const t = this.getLabelForValue(v);
                             return t.length > 30 ? t.slice(0, 29) + '…' : t; } } }),
    },
  });
}

function grafikBatang(id, label, data, warna) {
  gambar(id, {
    type: 'bar',
    data: { labels: label, datasets: [{ data, backgroundColor: warna || WARNA_SATU,
      borderSkipped: 'start', maxBarThickness: 30 }] },
    options: { plugins: { legend: { display: false } },
               scales: sumbu('y', { ticks: { callback: v => ringkasAngka(v) } }) },
  });
}

function grafikNarasiHarian(nh, id = 'g-narasi-harian') {
  nh.seri.forEach(x => warnaNarasi(x.nama));
  gambar(id, {
    type: 'line',
    data: { labels: nh.label.map(tglPendek), datasets: nh.seri.map(x => ({
      // isian hampir pekat: area bertumpuk transparan saling mencampur warna jadi keruh
      label: x.nama, data: x.data, borderColor: PERMUKAAN,
      backgroundColor: warnaNarasi(x.nama) + 'd9', borderWidth: 1, tension: .35, fill: true })) },
    options: { interaction: { mode: 'index', intersect: false },
               plugins: { legend: { position: 'bottom' } },
               scales: sumbu('y', { tumpuk: true }) },
  });
}

function grafikEmosi(em, id = 'g-emosi') {
  const el = document.getElementById(id);
  if (!el) return;
  if (!em.label.length) {
    el.parentElement.innerHTML = '<p class="memuat">Konten ini tidak dilabeli emosi (berita memakai baseline sentimen saja).</p>';
    return;
  }
  gambar(id, {
    type: 'bar',
    data: { labels: em.label.map(k => SNA_EMO_NAMA[k]),
            datasets: [{ data: em.persen, backgroundColor: em.label.map(k => SNA_EMO[k]),
                         borderSkipped: 'start', maxBarThickness: 16 }] },
    options: { indexAxis: 'y', plugins: { legend: { display: false },
                 tooltip: { callbacks: { title: c => `${SNA_EMO_NAMA[em.label[c[0].dataIndex]]} · ${SNA_EMO_EN[em.label[c[0].dataIndex]]}`,
                                         label: c => ` ${String(c.raw).replace('.', ',')}% · ${angka(em.data[c.dataIndex])} konten` } } },
               scales: sumbu('x', { ticks: { callback: v => v + '%' }, ticksKat: { color: INK[2] } }) },
  });
}

function isiAwan(id, item) {
  const el = document.getElementById(id);
  if (!el) return;
  if (!item.length) { el.innerHTML = '<p class="memuat">Belum ada data.</p>'; return; }
  const maks = item[0].n;
  el.innerHTML = item.map(k => {
    const skala = (0.86 + (k.n / maks) * 0.7).toFixed(2);
    return `<span style="font-size:${skala}em">${aman(k.t)}<b>${angka(k.n)}</b></span>`;
  }).join('');
}

/* peta panas tanggal × jam — satu hue, gelap ke terang */
function gambarHeatmap(id, d) {
  const el = document.getElementById(id);
  if (!el) return;
  if (!d.tanggal || !d.tanggal.length) { el.innerHTML = '<p class="memuat">Belum ada data.</p>'; return; }
  const nilai = {};
  d.sel.forEach(s => { nilai[s.y + '_' + s.x] = s.v; });
  const maks = d.maks || 1;
  const warna = v => v ? `rgba(57,135,229,${(0.16 + Math.sqrt(v / maks) * 0.84).toFixed(3)})` : '';
  let html = '<div class="hm"><div class="hm-baris hm-kepala"><span class="hm-label"></span>';
  for (let j = 0; j < 24; j++) html += `<span class="hm-jam">${j % 3 === 0 ? String(j).padStart(2, '0') : ''}</span>`;
  html += '</div>';
  d.tanggal.forEach((tgl, iy) => {
    html += `<div class="hm-baris"><span class="hm-label">${tglPendek(tgl)}</span>`;
    for (let j = 0; j < 24; j++) {
      const v = nilai[iy + '_' + j] || 0;
      html += `<span class="hm-sel" style="${v ? 'background:' + warna(v) : ''}"
                title="${tglPendek(tgl)}, ${String(j).padStart(2, '0')}.00 WIB: ${angka(v)} konten"></span>`;
    }
    html += '</div>';
  });
  html += `</div><div class="hm-skala"><span>sepi</span>${[0.05, 0.2, 0.45, 0.7, 1].map(f =>
    `<i style="background:${warna(f * maks)}"></i>`).join('')}<span>ramai (maks ${angka(maks)})</span></div>`;
  el.innerHTML = html;
}

function isiContohSentimen(d, id = 'contoh-sentimen') {
  const el = document.getElementById(id);
  if (!el) return;
  const kartu = x => `<div class="cs-kartu">
      <div class="cs-atas"><b>${IKON_PLATFORM[x.platform] || ''} ${aman(x.penulis)}</b>
        <span>${tglPendek(x.tanggal)}${x.engagement ? ' · ♥ ' + angka(x.engagement) : ''}</span></div>
      <p>${aman(x.teks)}</p>
      <div class="cs-penanda">
        ${x.penanda.pos.map(t => `<span class="p">+ ${aman(t)}</span>`).join('')}
        ${x.penanda.neg.map(t => `<span class="n">− ${aman(t)}</span>`).join('')}
        ${x.penanda.duka ? `<span class="d">duka: ${aman(x.penanda.duka)}</span>` : ''}
        ${!x.penanda.pos.length && !x.penanda.neg.length && !x.penanda.duka
          ? '<span class="o">tanpa penanda evaluatif</span>' : ''}
        ${x.emosi ? `<span class="chip"><i style="background:${SNA_EMO[x.emosi] || INK[4]}"></i>${SNA_EMO_NAMA[x.emosi] || x.emosi}</span>` : ''}
        ${x.url ? `<a href="${aman(x.url)}" target="_blank" rel="noopener">buka<svg class="ik"><use href="#ik-keluar"/></svg></a>` : ''}
      </div></div>`;
  const kolom = { negatif: 'Negatif', netral: 'Netral', positif: 'Positif' };
  el.innerHTML = Object.entries(kolom).map(([k, nama]) => {
    const c = d[k] || {};
    return `<div class="cs-kolom">
      <h3><i style="background:${WARNA_SENT[k]}"></i>${nama}<small>${angka(c.jumlah || 0)} konten</small></h3>
      <h4>Posting</h4>${(c.posting || []).map(kartu).join('') || '<p class="memuat">Tidak ada.</p>'}
      <h4>Komentar dan balasan</h4>${(c.komentar || []).map(kartu).join('') || '<p class="memuat">Tidak ada.</p>'}
    </div>`;
  }).join('');
}

// topik yang belum dipanen: pemberitahuan di bawah kepala halaman, sekali saja
function tandaiKosong(r) {
  if (r.total || document.getElementById('topik-kosong')) return;
  const kepala = document.querySelector('.kepala');
  if (!kepala) return;
  const el = document.createElement('div');
  el.id = 'topik-kosong';
  el.className = 'catatan';
  el.style.marginTop = '22px';
  el.innerHTML = `<b>Belum ada data untuk ${INFO.awal && document.getElementById('f-dari').value !== INFO.awal ? 'filter ini' : 'topik ini'}.</b>
    Mulai dari berita dan YouTube (tanpa login):<br>
    <code>TOPIK=${INFO.slug} python3 scripts/01_harvest_urls.py</code> lalu 02, 03, 04 untuk berita;
    <code>TOPIK=${INFO.slug} python3 scripts/10_yt_harvest.py</code> lalu 11 untuk YouTube.`;
  kepala.after(el);
}

// panel lensa sorotan: porsi konten fokus dibanding seluruh percakapan
function isiFokus(d) {
  const el = document.getElementById('panel-fokus');
  if (!el) return;
  if (!d.ada) { el.remove(); return; }
  const t = d.total;
  const pl = Object.entries(d.per_platform).sort((a, b) =>
    Object.keys(WARNA_PLATFORM).indexOf(a[0]) - Object.keys(WARNA_PLATFORM).indexOf(b[0]));
  const maksN = Math.max(1, ...d.per_narasi.map(x => x.n));
  document.getElementById('fokus-ringkas').innerHTML = `
    <div class="fokus-angka"><b>${String(t.persen).replace('.', ',')}%</b>
      <span>${angka(t.fokus)} dari ${angka(t.konten)} konten menyentuh demo atau isu yang dituntut pendemo</span></div>
    <div class="kk-label">Per platform</div>
    ${pl.map(([p, v]) => `<div class="kk-emo-baris"><span>${p === 'X (Twitter)' ? 'X' : p}</span>
      <div class="kk-emo-trek"><i style="width:${Math.min(100, v.persen)}%;background:${WARNA_PLATFORM[p]}"></i></div>
      <b>${String(v.persen).replace('.', ',')}%</b></div>`).join('')}
    <div class="kk-label">Narasi dalam fokus</div>
    ${d.per_narasi.map(x => `<div class="kk-emo-baris fokus-narasi"><span title="${aman(x.nama)}">${aman(x.nama)}</span>
      <div class="kk-emo-trek"><i style="width:${100 * x.n / maksN}%;background:${WARNA_SATU}"></i></div>
      <b>${angka(x.n)}</b></div>`).join('')}`;
  // garis gabungan sengaja tidak digambar: porsi berita (~50%) dan komentar
  // (~5%) jauh berbeda, jadi garis gabungan hanya mengikuti komposisi platform
  const seri = d.seri.filter(x => x.nama !== 'Semua platform' && x.total.reduce((a, b) => a + b, 0) >= 20);
  gambar('g-fokus', {
    type: 'line',
    data: { labels: d.label.map(tglPendek), datasets: seri.map(x => ({
      label: x.nama, data: x.persen, spanGaps: true, tension: .3,
      borderColor: x.nama === 'Semua platform' ? INK[1] : WARNA_PLATFORM[x.nama],
      backgroundColor: x.nama === 'Semua platform' ? INK[1] : WARNA_PLATFORM[x.nama],
      borderWidth: x.nama === 'Semua platform' ? 2.5 : 1.5,
      borderDash: x.nama === 'Semua platform' ? [] : [] })) },
    options: { interaction: { mode: 'index', intersect: false },
      elements: { line: { tension: .25 } },
      plugins: { tooltip: { callbacks: { label: c => {
        const x = seri[c.datasetIndex], i = c.dataIndex;
        return ` ${x.nama}: ${c.raw == null ? '-' : String(c.raw).replace('.', ',') + '%'} (${angka(x.fokus[i])} dari ${angka(x.total[i])})`;
      } } } },
      scales: sumbu('y', { ticks: { callback: v => v + '%' } }) },
  });
}

/* ------------------------------------------------------------ filter */
function paksaPlatform(nilai) {          // halaman per-platform mengunci filter platform
  const sel = document.getElementById('f-platform');
  if (sel) { sel.value = nilai; sel.disabled = true; }
}

function pasangFilter(muatUlang) {
  const b = document.getElementById('f-terap');
  const r = document.getElementById('f-reset');
  if (b) b.onclick = () => { ringkasSaring(); muatUlang(); };
  if (r) r.onclick = () => {
    const sel = document.getElementById('f-platform');
    if (sel && !sel.disabled) sel.value = 'semua';
    document.getElementById('f-tipe').value = 'semua';
    document.getElementById('f-dari').value = INFO.awal;
    document.getElementById('f-sampai').value = INFO.akhir;
    const fk = document.getElementById('f-fokus');
    if (fk) fk.checked = false;
    segarkanKontrol(); ringkasSaring(); muatUlang();
  };
}

function ringkasSaring() {
  const el = document.getElementById('saring-ringkas');
  if (!el) return;
  const p = document.getElementById('f-platform'), t = document.getElementById('f-tipe');
  const d1 = document.getElementById('f-dari').value, d2 = document.getElementById('f-sampai').value;
  const aktif = [];
  if (p.value !== 'semua' && !p.disabled) aktif.push(p.value);
  if (t.value !== 'semua') aktif.push(t.value);
  if (d1 !== INFO.awal || d2 !== INFO.akhir) aktif.push(`${tglPendek(d1)}–${tglPendek(d2)}`);
  const fk = document.getElementById('f-fokus');
  if (fk && fk.checked) aktif.push(fk.parentElement.textContent.trim());
  el.textContent = aktif.length ? `Filter aktif: ${aktif.join(' · ')}` : '';
}

function isiOpsiTipe(opsi) {
  const sel = document.getElementById('f-tipe');
  if (!sel) return;
  const lama = sel.value;
  sel.innerHTML = '<option value="semua">Semua tipe</option>' +
    opsi.map(o => `<option value="${aman(o)}">${aman(o)}</option>`).join('');
  if (opsi.includes(lama)) sel.value = lama;
  segarkanKontrol();
}

/* ------------------------------------------------ kontrol custom */
function tutupSemua(kecuali) {
  document.querySelectorAll('.pilih.buka, .periode.buka').forEach(el => { if (el !== kecuali) el.classList.remove('buka'); });
}
document.addEventListener('click', e => { if (!e.target.closest('.pilih, .periode')) tutupSemua(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') tutupSemua(); });

// dropdown custom yang tetap memakai <select> asli sebagai sumber nilai
function pasangPilih(sel) {
  if (sel._pilih) { sel._pilih(); return; }
  const w = document.createElement('div');
  w.className = 'pilih';
  sel.parentNode.insertBefore(w, sel);
  const b = document.createElement('button');
  b.type = 'button'; b.className = 'pilih-tombol'; b.setAttribute('aria-haspopup', 'listbox');
  const ul = document.createElement('ul');
  ul.className = 'pilih-daftar'; ul.setAttribute('role', 'listbox');
  w.append(sel, b, ul);
  let sorot = 0;
  const segarkan = () => {
    const o = sel.options[sel.selectedIndex];
    b.innerHTML = `<span>${aman(o ? o.text : '')}</span><svg class="ik"><use href="#ik-chevron"/></svg>`;
    b.disabled = sel.disabled;
    ul.innerHTML = [...sel.options].map((o, i) => `<li role="option" data-i="${i}" aria-selected="${i === sel.selectedIndex}">
      <svg class="ik"><use href="#ik-centang"/></svg>${aman(o.text)}</li>`).join('');
  };
  const tandai = i => {
    sorot = Math.max(0, Math.min(sel.options.length - 1, i));
    ul.querySelectorAll('li').forEach((li, j) => li.classList.toggle('sorot', j === sorot));
    const li = ul.children[sorot]; if (li) li.scrollIntoView({ block: 'nearest' });
  };
  const pilih = i => {
    if (sel.selectedIndex !== i) { sel.selectedIndex = i; sel.dispatchEvent(new Event('change')); }
    segarkan(); w.classList.remove('buka'); b.focus(); ringkasSaring();
  };
  b.onclick = () => { const buka = !w.classList.contains('buka'); tutupSemua(w); w.classList.toggle('buka', buka); if (buka) tandai(sel.selectedIndex); };
  b.onkeydown = e => {
    const buka = w.classList.contains('buka');
    if (['ArrowDown', 'ArrowUp'].includes(e.key)) {
      e.preventDefault();
      if (!buka) { tutupSemua(w); w.classList.add('buka'); tandai(sel.selectedIndex); return; }
      tandai(sorot + (e.key === 'ArrowDown' ? 1 : -1));
    } else if ((e.key === 'Enter' || e.key === ' ') && buka) { e.preventDefault(); pilih(sorot); }
  };
  ul.onclick = e => { const li = e.target.closest('li'); if (li) pilih(+li.dataset.i); };
  sel._pilih = segarkan;
  segarkan();
}

// pemilih periode: garis waktu jendela topik, tinggi batang = volume.
// Periode pendek dibagi per hari; periode panjang (> 45 hari) per pekan.
function isoTambah(t, n) { const d = new Date(t + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); }
function isoSelisih(a, z) { return Math.round((new Date(z + 'T00:00:00Z') - new Date(a + 'T00:00:00Z')) / 864e5); }
function isoSenin(t) { const d = new Date(t + 'T00:00:00Z'); return isoTambah(t, -((d.getUTCDay() + 6) % 7)); }
const BULAN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];

function ruasPeriode() {
  const n = isoSelisih(INFO.awal, INFO.akhir);
  const ruas = [];
  if (n <= 45) {
    for (let i = 0; i <= n; i++) { const t = isoTambah(INFO.awal, i); ruas.push({ a: t, z: t, kunci: t, label: String(+t.slice(8)) }); }
    return { pekanan: false, ruas };
  }
  let s = isoSenin(INFO.awal), bulanLalu = '';
  while (s <= INFO.akhir) {
    const z = isoTambah(s, 6), a = s < INFO.awal ? INFO.awal : s;
    const bln = a.slice(0, 7);
    ruas.push({ a, z: z > INFO.akhir ? INFO.akhir : z, kunci: s, label: bln !== bulanLalu ? BULAN[+a.slice(5, 7) - 1] : '' });
    bulanLalu = bln;
    s = isoTambah(s, 7);
  }
  return { pekanan: true, ruas };
}

async function pasangPeriode() {
  const el = document.getElementById('periode');
  if (!el || el._siap || !INFO.awal) return;
  el._siap = true;
  const dari = document.getElementById('f-dari'), sampai = document.getElementById('f-sampai');
  const { pekanan, ruas } = ruasPeriode();
  let volume = {};
  try {
    // linimasa tanpa filter: label harian, atau awal pekan untuk topik panjang
    const d = await (await fetch(api('/api/linimasa'))).json();
    d.label.forEach((t, i) => { volume[t] = d.seri.reduce((s, x) => s + (x.data[i] || 0), 0); });
  } catch (e) { /* histogram opsional */ }
  const vol = r => volume[r.kunci] || 0;
  const maks = Math.max(1, ...ruas.map(vol));
  const tahun = INFO.akhir.slice(0, 4);
  let klikAwal = null;
  el.innerHTML = `<button type="button" class="pilih-tombol" style="min-width:230px"><span></span>
      <svg class="ik"><use href="#ik-kalender"/></svg></button>
    <div class="periode-panel" role="dialog" aria-label="Pilih periode">
      <div class="periode-preset">${INFO.preset.map(([n, a, z]) => `<button type="button" data-a="${a}" data-z="${z}">${n}</button>`).join('')}</div>
      <div class="periode-hari" style="grid-template-columns:repeat(${ruas.length},1fr)">${ruas.map((r, i) =>
        `<button type="button" data-i="${i}" title="${r.a === r.z ? tglPendek(r.a) : tglPendek(r.a) + '–' + tglPendek(r.z)}: ${angka(vol(r))} konten">
        <i style="height:${6 + 52 * Math.sqrt(vol(r) / maks)}px"></i><span>${r.label}</span></button>`).join('')}</div>
      <div class="periode-ket"><span>Klik ${pekanan ? 'pekan' : 'tanggal'} awal lalu ${pekanan ? 'pekan' : 'tanggal'} akhir</span><span id="periode-pilihan"></span></div>
    </div>`;
  const tombol = el.querySelector('.pilih-tombol');
  const segarkan = () => {
    const a = dari.value, z = sampai.value;
    tombol.querySelector('span').textContent = a === INFO.awal && z === INFO.akhir
      ? `Seluruh periode · ${tglPendek(INFO.awal)}–${tglPendek(INFO.akhir)}` : `${tglPendek(a)} – ${tglPendek(z)} ${tahun}`;
    el.querySelectorAll('.periode-hari button').forEach(b => {
      const r = ruas[+b.dataset.i];
      b.classList.toggle('dalam', r.z >= a && r.a <= z);
      b.classList.toggle('ujung', (a >= r.a && a <= r.z) || (z >= r.a && z <= r.z));
    });
    el.querySelectorAll('.periode-preset button').forEach(b => b.classList.toggle('aktif', b.dataset.a === a && b.dataset.z === z));
    const n = ruas.filter(r => r.z >= a && r.a <= z).reduce((s, r) => s + vol(r), 0);
    el.querySelector('#periode-pilihan').innerHTML = klikAwal ? `pilih ${pekanan ? 'pekan' : 'tanggal'} akhir…`
      : `<b>${isoSelisih(a, z) + 1} hari</b> · ${angka(n)} konten`;
  };
  tombol.onclick = () => { const buka = !el.classList.contains('buka'); tutupSemua(el); el.classList.toggle('buka', buka); };
  el.querySelector('.periode-preset').onclick = e => {
    const b = e.target.closest('button'); if (!b) return;
    dari.value = b.dataset.a; sampai.value = b.dataset.z; klikAwal = null; segarkan(); ringkasSaring();
  };
  el.querySelector('.periode-hari').onclick = e => {
    const b = e.target.closest('button'); if (!b) return;
    const r = ruas[+b.dataset.i];
    if (!klikAwal) { klikAwal = r; dari.value = r.a; sampai.value = r.z; }
    else { dari.value = r.a < klikAwal.a ? r.a : klikAwal.a; sampai.value = r.z > klikAwal.z ? r.z : klikAwal.z; klikAwal = null; }
    segarkan(); ringkasSaring();
  };
  el._segarkan = segarkan;
  segarkan();
}

// segmented control yang menulis ke <input type=hidden> dan memicu 'input'
function pasangSegmen() {
  document.querySelectorAll('.segmen[data-untuk]').forEach(s => {
    if (s._siap) return;
    s._siap = true;
    const inp = document.getElementById(s.dataset.untuk);
    const segarkan = () => s.querySelectorAll('button').forEach(b => b.classList.toggle('aktif', b.dataset.v === inp.value));
    s.onclick = e => {
      const b = e.target.closest('button'); if (!b) return;
      inp.value = b.dataset.v; segarkan(); inp.dispatchEvent(new Event('input'));
    };
    segarkan();
  });
}

function segarkanKontrol() {
  document.querySelectorAll('select').forEach(s => s._pilih && s._pilih());
  const p = document.getElementById('periode');
  if (p && p._segarkan) p._segarkan();
}

// status data di bilah atas
async function isiStatus() {
  const el = document.getElementById('status-data');
  if (!el) return;
  try {
    const d = await (await fetch(api('/api/status'))).json();
    el.querySelector('span').textContent = d.total ? `${d.diperbarui} · ${angka(d.total)} konten` : 'Belum ada data';
    el.title = d.total ? `Data topik ini terakhir diperbarui ${d.diperbarui}; ${angka(d.total)} konten` : el.title;
  } catch (e) { el.querySelector('span').textContent = 'Status data tidak tersedia'; }
}

// sub-navigasi bagian: tandai bagian yang sedang dibaca
function pasangSubnav() {
  const tautan = [...document.querySelectorAll('.subnav a[href^="#"]')];
  if (!tautan.length) return;
  const target = tautan.map(a => document.querySelector(a.getAttribute('href'))).filter(Boolean);
  const amati = new IntersectionObserver(ents => {
    ents.forEach(en => {
      if (!en.isIntersecting) return;
      tautan.forEach(a => a.classList.toggle('aktif', a.getAttribute('href') === '#' + en.target.id));
    });
  }, { rootMargin: '-130px 0px -65% 0px' });
  target.forEach(t => amati.observe(t));
}

// pemilih topik di bilah atas: satu dashboard, banyak topik. Jumlah konten tiap
// topik dimuat saat panel pertama kali dibuka, bukan saat halaman dimuat.
function pasangPemilihTopik() {
  const w = document.getElementById('tp');
  if (!w) return;
  const b = document.getElementById('tp-tombol');
  let dimuat = false;
  const isi = async () => {
    if (dimuat) return; dimuat = true;
    await Promise.all([...w.querySelectorAll('.tp-jumlah')].map(async el => {
      const slug = el.dataset.slug;
      try {
        const d = await (await fetch(`/api/${slug}/status`)).json();
        el.textContent = d.total ? `${angka(d.total)} konten · ${d.diperbarui}` : 'Belum ada data';
        const bar = w.querySelector(`.tp-komposisi[data-slug="${slug}"]`);
        const plat = Object.entries(d.platform || {}).filter(([, n]) => n > 0);
        bar.innerHTML = plat.map(([p, n]) =>
          `<i style="flex:${n};background:${WARNA_PLATFORM[p] || INK[4]}" title="${aman(p)} ${angka(n)}"></i>`).join('');
      } catch (e) { el.textContent = ''; }
    }));
  };
  const buka = on => {
    w.classList.toggle('buka', on); b.setAttribute('aria-expanded', String(on));
    if (on) { tutupSemua(w); isi(); }
  };
  b.onclick = () => buka(!w.classList.contains('buka'));
  document.addEventListener('click', e => { if (!e.target.closest('#tp')) buka(false); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') buka(false); });
  // ganti topik: buka halaman yang sama (subhalaman + bagian) pada topik lain
  w.querySelectorAll('.tp-item').forEach(a => a.onclick = e => {
    e.preventDefault();
    const baru = a.dataset.slug;
    location.href = baru === INFO.slug ? location.href
      : location.pathname.replace(`/${INFO.slug}/`, `/${baru}/`) + location.hash;
  });
}

// tombol "Laporan PDF": pembuatan memakan ±1 menit, jadi tampilkan status lalu unduh berkasnya
/* tombol Laporan PDF: panel kecil untuk memilih periode, lalu unduh */
function pasangUnduhLaporan() {
  const b = document.getElementById('unduh-laporan');
  const pop = document.getElementById('laporan-pop');
  if (!b || !pop || !INFO.slug) return;
  const d1 = document.getElementById('lp-dari'), d2 = document.getElementById('lp-sampai');
  const info = document.getElementById('lp-info'), unduh = document.getElementById('lp-unduh');
  const teks = unduh.querySelector('span');
  [d1, d2].forEach(x => { x.min = INFO.awal; x.max = INFO.akhir; });
  if (INFO.ai) { document.getElementById('lp-ai-baris').hidden = false; document.getElementById('lp-ai').checked = INFO.laporan_ai !== false; }
  const preset = [['Seluruh periode', INFO.awal, INFO.akhir], ...(INFO.preset || []).filter(p => p[1] !== INFO.awal || p[2] !== INFO.akhir)];
  const fd = document.getElementById('f-dari'), fs = document.getElementById('f-sampai');
  if (fd && (fd.value !== INFO.awal || fs.value !== INFO.akhir)) preset.splice(1, 0, ['Sesuai filter', fd.value, fs.value]);
  document.getElementById('lp-preset').innerHTML = preset.map(p =>
    `<button type="button" class="ss-chip" data-a="${p[1]}" data-z="${p[2]}">${p[0]}</button>`).join('');
  const segarkan = () => {
    const penuh = d1.value === INFO.awal && d2.value === INFO.akhir;
    const sah = d1.value && d2.value && d1.value <= d2.value;
    unduh.disabled = !sah;
    info.textContent = !sah ? 'Tanggal akhir harus sama dengan atau sesudah tanggal awal.'
      : penuh ? 'Seluruh periode topik, lengkap dengan kesimpulan analis. Sekitar 20 detik.'
      : `${tglPendek(d1.value)} – ${tglPendek(d2.value)}. Graf SNA periode ini dibangun dulu, jadi bisa butuh 1–2 menit.`;
    pop.querySelectorAll('.lp-preset button').forEach(x =>
      x.classList.toggle('aktif', x.dataset.a === d1.value && x.dataset.z === d2.value));
  };
  pop.querySelectorAll('.lp-preset button').forEach(x => x.onclick = () => { d1.value = x.dataset.a; d2.value = x.dataset.z; segarkan(); });
  d1.onchange = d2.onchange = segarkan;
  const tutup = () => { pop.hidden = true; b.setAttribute('aria-expanded', 'false'); };
  b.onclick = () => {
    if (!pop.hidden) return tutup();
    // isi awal: periode filter yang sedang aktif
    d1.value = (fd && fd.value) || INFO.awal; d2.value = (fs && fs.value) || INFO.akhir;
    segarkan(); pop.hidden = false; b.setAttribute('aria-expanded', 'true'); d1.focus();
  };
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !pop.hidden) { tutup(); b.focus(); } });
  document.addEventListener('click', e => { if (!pop.hidden && !pop.contains(e.target) && !b.contains(e.target)) tutup(); });
  unduh.onclick = async (e) => {
    if (unduh.disabled) return;
    const q = new URLSearchParams({ dari: d1.value, sampai: d2.value });
    if (INFO.ai) q.set('ai', document.getElementById('lp-ai').checked ? '1' : '0');
    if (e.shiftKey) q.set('baru', '1');                 // Shift+klik: cetak ulang walau data belum berubah
    unduh.disabled = true; b.classList.add('memuat-laporan');
    const mulai = Date.now();
    const jam = setInterval(() => { teks.textContent = `Menyiapkan… ${Math.round((Date.now() - mulai) / 1000)} dtk`; }, 1000);
    try {
      const r = await fetch(`/${INFO.slug}/laporan.pdf?${q}`);
      if (!r.ok) throw new Error(r.status);
      const blob = await r.blob();
      const nama = (r.headers.get('Content-Disposition') || '').match(/filename="?([^";]+)/);
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = nama ? nama[1] : `${INFO.slug}-laporan.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 30000);
      teks.textContent = 'Laporan siap';
    } catch (err) {
      teks.textContent = 'Gagal membuat laporan';
    } finally {
      clearInterval(jam);
      unduh.disabled = false; b.classList.remove('memuat-laporan');
      setTimeout(() => { teks.textContent = 'Buat PDF'; }, 4000);
    }
  };
}

function pasangKontrol() {
  pasangUnduhLaporan();
  document.querySelectorAll('select').forEach(pasangPilih);
  document.querySelectorAll('.titik[data-platform]').forEach(t => { t.style.background = WARNA_PLATFORM[t.dataset.platform] || INK[4]; });
  pasangPeriode(); pasangSegmen(); pasangSubnav(); isiStatus(); ringkasSaring();
  pasangPemilihTopik();
  // grafik yang terlanjur digambar sebelum font termuat digambar ulang dengan font yang benar
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(() => {
      Object.values(grafik).forEach(g => g.update('none'));
      if (typeof snaGambar === 'function') snaGambar();
    });
  }
}
