/* Halaman Kelola: panen, validasi sentimen, klaster, kesimpulan, dan pengaturan AI.
   Semua pekerjaan berat dijalankan antrean di server; halaman ini hanya memulai dan memantau. */
const KL = window.KELOLA;
const $ = id => document.getElementById(id);
const esc = t => String(t == null ? '' : t).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const STATUS = { antre: 'Antre', jalan: 'Berjalan', selesai: 'Selesai', gagal: 'Gagal', batal: 'Dibatalkan' };
const SEN = { negatif: 'Negatif', netral: 'Netral', positif: 'Positif' };
const pr = (v, d = 0) => v == null ? '–' : (100 * v).toLocaleString('id-ID', { maximumFractionDigits: d }) + '%';
const usd = v => v == null ? '–' : (v > 0 && v < 0.0005) ? '<$0,001' : '$' + Number(v).toLocaleString('id-ID', { minimumFractionDigits: v < 1 ? 3 : 2, maximumFractionDigits: v < 1 ? 4 : 2 });

async function minta(url, data) {
  const r = await fetch(url, data === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.galat || `HTTP ${r.status}`);
  return d;
}
const API = jalur => `/api/${KL.slug}/kelola/${jalur}`;

function jam(t) { return new Date(t * 1000).toLocaleString('id-ID', { hour: '2-digit', minute: '2-digit' }).replace(':', '.'); }
function waktu(t) {
  if (!t) return '–';
  const d = new Date(t * 1000), kini = new Date();
  const hariSama = d.toDateString() === kini.toDateString();
  return (hariSama ? '' : d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' }) + ' ') + jam(t);
}
function relatif(t) {
  const s = Date.now() / 1000 - t;
  if (s < 90) return 'baru saja';
  if (s < 3600) return `${Math.round(s / 60)} menit lalu`;
  if (s < 86400) return `${Math.round(s / 3600)} jam lalu`;
  return `${Math.round(s / 86400)} hari lalu`;
}
function durasi(a, z) {
  if (!a) return '';
  const s = Math.max(0, (z || Date.now() / 1000) - a);
  return s < 60 ? `${Math.round(s)} dtk` : s < 3600 ? `${Math.round(s / 60)} mnt` : `${(s / 3600).toFixed(1).replace('.', ',')} jam`;
}
function status(el, teks, jenis) { if (!el) return; el.textContent = teks || ''; el.className = 'kel-status' + (jenis ? ' ' + jenis : ''); }

/* ---------------------------------------------------------------- tab */
const TAB = { panen: muatPanen, validasi: muatValidasi, klaster: muatKlaster, kesimpulan: muatKesimpulan, ai: muatAI };
let tabAktif = 'panen';
function bukaTab(nama) {
  if (!TAB[nama]) nama = 'panen';
  tabAktif = nama;
  document.querySelectorAll('.kel-tab button').forEach(b => {
    const on = b.dataset.tab === nama;
    b.classList.toggle('aktif', on); b.setAttribute('aria-selected', String(on));
  });
  document.querySelectorAll('.kel-bagian').forEach(s => { s.hidden = s.id !== `tab-${nama}`; });
  history.replaceState(null, '', `#${nama}`);
  TAB[nama]();
}
document.querySelectorAll('.kel-tab button').forEach(b => b.onclick = () => bukaTab(b.dataset.tab));

/* ---------------------------------------------------------------- antrean & log */
let jejak = {};                      // id -> status terakhir, untuk tahu kapan pekerjaan selesai
function barisPekerjaan(p) {
  const aktif = p.status === 'antre' || p.status === 'jalan';
  const langkah = p.status === 'jalan' && p.langkah_n > 1 ? `langkah ${p.langkah_ke + 1}/${p.langkah_n} · ${esc(p.langkah[p.langkah_ke])}` : '';
  const prog = p.progres && p.progres[1] ? `<div class="kel-bar"><i style="width:${Math.min(100, 100 * p.progres[0] / p.progres[1])}%"></i></div>
      <small>${p.progres[0].toLocaleString('id-ID')} / ${p.progres[1].toLocaleString('id-ID')}</small>` : '';
  return `<tr data-id="${esc(p.id)}" class="${aktif ? 'aktif' : ''}">
    <td><span class="kel-chip ${p.status}">${STATUS[p.status] || p.status}</span></td>
    <td><b>${esc(p.judul)}</b><br><small class="kel-redup">${langkah || esc(p.pesan || '')}</small>${prog}</td>
    <td class="num">${p.biaya != null ? usd(p.biaya) : ''}</td>
    <td class="num">${waktu(p.mulai || p.dibuat)}<br><small class="kel-redup">${durasi(p.mulai, p.selesai)}</small></td>
    <td class="num">${aktif ? `<button type="button" class="tombol hantu kecil" data-batal="${esc(p.id)}">Batalkan</button>` : ''}</td></tr>`;
}
function tampilAntrean(el, daftar) {
  if (!el) return;
  if (!daftar.length) { el.innerHTML = '<p class="memuat">Belum ada pekerjaan.</p>'; return; }
  el.innerHTML = `<table class="kel-tabel"><thead><tr><th>Status</th><th>Pekerjaan</th><th class="num">Biaya AI</th>
    <th class="num">Waktu</th><th></th></tr></thead><tbody>${daftar.map(barisPekerjaan).join('')}</tbody></table>`;
  el.querySelectorAll('tr[data-id]').forEach(tr => tr.onclick = e => {
    if (e.target.closest('button')) return;
    const p = daftar.find(x => x.id === tr.dataset.id);
    bukaLog(p);
  });
  el.querySelectorAll('[data-batal]').forEach(b => b.onclick = async () => {
    if (!confirm('Batalkan pekerjaan ini? Data yang sudah terkumpul tetap disimpan.')) return;
    await minta(`/api/kelola/pekerjaan/${b.dataset.batal}/batal`, {});
    segarkan();
  });
}

let log = { id: null, dari: 0, waktu: null };
function bukaLog(p) {
  log = { id: p.id, dari: 0, waktu: null, aktif: p.status === 'antre' || p.status === 'jalan' };
  $('kel-log').hidden = false;
  $('kel-log-judul').textContent = `${p.judul} · ${STATUS[p.status]}`;
  $('kel-log-isi').textContent = '';
  $('kel-log-batal').hidden = !log.aktif;
  $('kel-log-batal').onclick = async () => { await minta(`/api/kelola/pekerjaan/${p.id}/batal`, {}); segarkan(); };
  ambilLog();
}
async function ambilLog() {
  if (!log.id) return;
  clearTimeout(log.waktu);
  try {
    const d = await minta(`/api/kelola/pekerjaan/${log.id}/log?dari=${log.dari}`);
    const pre = $('kel-log-isi');
    const bawah = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 30;
    if (log.dari === 0) pre.textContent = d.teks; else pre.textContent += d.teks;
    log.dari = d.ukuran;
    if (bawah) pre.scrollTop = pre.scrollHeight;
  } catch (e) { /* log belum ada */ }
  if (log.aktif) log.waktu = setTimeout(ambilLog, 2000);
}
$('kel-log-tutup').onclick = () => { $('kel-log').hidden = true; clearTimeout(log.waktu); log.id = null; };

async function segarkan() {
  let d;
  try { d = await minta(`/api/kelola/pekerjaan?topik=${KL.slug}`); } catch (e) { return; }
  let berubah = false;
  for (const p of d.pekerjaan) {
    if (jejak[p.id] && jejak[p.id] !== p.status && !['antre', 'jalan'].includes(p.status)) berubah = true;
    jejak[p.id] = p.status;
    if (log.id === p.id) {
      $('kel-log-judul').textContent = `${p.judul} · ${STATUS[p.status]}`;
      const aktif = p.status === 'antre' || p.status === 'jalan';
      $('kel-log-batal').hidden = !aktif;
      if (log.aktif && !aktif) { log.aktif = false; ambilLog(); }
    }
  }
  if (tabAktif === 'panen') tampilAntrean($('kel-antrean'), d.pekerjaan);
  if (berubah) TAB[tabAktif]();
  else if (tabAktif === 'panen' && d.pekerjaan.some(p => p.status === 'jalan')) muatPanen(true);
}
setInterval(segarkan, 3000);

/* ---------------------------------------------------------------- panen */
const SOSIAL = ['x', 'instagram', 'instagram_komentar', 'threads', 'youtube'];
async function muatPanen(diam) {
  let d;
  try { d = await minta(API('panen')); } catch (e) { $('kel-pipa').innerHTML = `<p class="memuat">${esc(e.message)}</p>`; return; }
  const cek = {};
  document.querySelectorAll('[data-sna]').forEach(c => { cek[c.dataset.sna] = c.checked; });
  $('kel-pipa').innerHTML = d.pipa.map(p => {
    const login = p.login == null ? '' : p.login ? '<span class="kel-chip ok">Login tersedia</span>'
      : '<span class="kel-chip gagal">Berkas login belum ada</span>';
    const jeda = p.jeda_sampai ? `<span class="kel-chip waspada">Boleh lagi pukul ${jam(p.jeda_sampai)}</span>`
      : p.jeda_jam ? `<span class="kel-chip">Jeda ${p.jeda_jam} jam antar-sesi</span>` : '';
    const mati = p.aktif || p.login === false || p.jeda_sampai;
    const sna = SOSIAL.includes(p.kunci) ? `<label class="kel-centang kecil"><input type="checkbox" data-sna="${p.kunci}"
      ${cek[p.kunci] === false ? '' : 'checked'}> bangun ulang graf SNA sesudahnya</label>` : '';
    return `<div class="kel-kartu">
      <div class="kel-kartu-atas"><h3>${esc(p.judul)}</h3>${p.aktif ? `<span class="kel-chip ${p.aktif}">${STATUS[p.aktif]}</span>` : ''}</div>
      <p class="kel-kecil">${esc(p.ket)}</p>
      <p class="kel-angka">${p.konten != null ? `<b>${angka(p.konten)}</b> konten` : ''}<span>${p.terakhir ? 'diperbarui ' + relatif(p.terakhir) : 'belum pernah dijalankan'}</span></p>
      <div class="kel-chips">${login}${jeda}</div>${sna}
      <div class="kel-kartu-bawah"><button type="button" class="tombol hantu kecil" data-pipa="${p.kunci}" ${mati ? 'disabled' : ''}>${p.aktif ? 'Di antrean' : 'Jalankan'}</button>
      <details class="kel-langkah"><summary>${p.langkah.length} langkah</summary><ol>${p.langkah.map(s => `<li>${esc(s)}</li>`).join('')}</ol></details></div>
    </div>`;
  }).join('');
  $('kel-pipa').querySelectorAll('[data-pipa]').forEach(b => b.onclick = async () => {
    const k = b.dataset.pipa;
    if (k.startsWith('instagram') && !confirm('Panen Instagram memakai sesi akun utama dan berjalan pelan (jeda 12–25 detik, berhenti total bila diminta verifikasi). Lanjutkan?')) return;
    b.disabled = true;
    try {
      const sna = document.querySelector(`[data-sna="${k}"]`);
      await minta(API('panen'), { pipa: k, sna: sna ? sna.checked : false });
      segarkan(); muatPanen(true);
    } catch (e) { alert(e.message); b.disabled = false; }
  });
  if (!diam || tabAktif === 'panen') tampilAntrean($('kel-antrean'), d.pekerjaan);
}

/* ---------------------------------------------------------------- validasi */
let V = { item: [], idx: 0, metrik: null, setelan: null };
async function muatValidasi() {
  const [v, l] = await Promise.all([minta(API('validasi')), minta(API('label-ai')).catch(() => null)]);
  V.item = v.item || []; V.metrik = v.metrik; V.setelan = v.setelan;
  if (V.idx >= V.item.length) V.idx = 0;
  const belum = V.item.findIndex(x => !x.manusia);
  if (!V.item[V.idx] || V.item[V.idx].manusia) V.idx = belum >= 0 ? belum : V.idx;
  status($('val-status'), v.aktif && v.aktif.length ? 'Sampel sedang dibuat…' : (v.dibuat ? `Sampel dibuat ${v.dibuat}` : ''), v.aktif && v.aktif.length ? 'jalan' : '');
  tampilRingkasVal(); tampilKartu(); tampilMatriks(); tampilBeda(); tampilSumber(l);
}
function tampilRingkasVal() {
  const m = V.metrik || {};
  const kotak = (judul, nilai, ket) => `<div><small>${judul}</small><b>${nilai}</b><em>${ket || ''}</em></div>`;
  $('val-ringkas').innerHTML = !V.item.length ? '' : [
    kotak('Sudah dinilai', `${m.dinilai || 0} / ${m.total || 0}`, 'konten sampel'),
    kotak('Label aturan cocok', pr(m.aturan && m.aturan.akurasi), m.aturan ? `kappa ${(m.aturan.kappa ?? 0).toFixed(2).replace('.', ',')}` : 'menunggu penilaian kamu'),
    kotak('Label AI cocok', pr(m.ai && m.ai.akurasi), m.ai ? `kappa ${(m.ai.kappa ?? 0).toFixed(2).replace('.', ',')}`
      : V.item.some(x => x.ai) ? 'menunggu penilaian kamu' : 'belum ada label AI'),
    kotak('Tidak relevan', m.tidak_relevan || 0, 'ditandai kamu'),
  ].join('');
}
function tampilKartu() {
  const el = $('val-kartu');
  const x = V.item[V.idx];
  if (!x) { el.innerHTML = '<p class="memuat">Belum ada sampel. Klik "Buat sampel baru".</p>'; return; }
  const sudah = x.manusia && x.manusia.s;
  const lihat = sudah || !$('val-sembunyi').checked;
  const mesin = lihat ? `<p class="kel-mesin">Aturan: <b class="${'l-' + (x.aturan.s || '').slice(0, 3)}">${SEN[x.aturan.s] || '–'}</b>
      · AI: <b>${x.ai ? SEN[x.ai.s] : 'belum ada'}</b>${x.ai && x.ai.r === 0 ? ' <span class="kel-chip waspada">AI: tidak relevan</span>' : ''}</p>` : '';
  const b = (s, k) => `<button type="button" class="tombol ${sudah === s ? 'utama' : 'hantu'} kecil" data-s="${s}">${k} ${SEN[s]}</button>`;
  const tr = x.manusia && x.manusia.relevan === false;
  el.innerHTML = `<div class="kel-val">
    <p class="kel-redup">${V.idx + 1} dari ${V.item.length} · ${esc(x.platform)} · ${esc(x.penulis || '')} · ${esc(tglPendek(x.tanggal || ''))}</p>
    <blockquote>${esc(x.teks)}</blockquote>
    <div class="kel-val-tombol">${b('negatif', 1)}${b('netral', 2)}${b('positif', 3)}
      <button type="button" class="tombol ${tr ? 'utama' : 'hantu'} kecil" data-tr="1">4 Tidak relevan</button></div>
    ${mesin}
    <div class="kel-val-nav"><button type="button" class="tombol hantu kecil" data-nav="-1">← Sebelumnya</button>
      <button type="button" class="tombol hantu kecil" data-nav="lompat">Konten berikutnya yang belum dinilai</button>
      <button type="button" class="tombol hantu kecil" data-nav="1">Berikutnya →</button></div></div>`;
  el.querySelectorAll('[data-s]').forEach(t => t.onclick = () => nilai(t.dataset.s));
  el.querySelector('[data-tr]').onclick = () => nilai(x.manusia && x.manusia.s ? x.manusia.s : 'netral', !tr);
  el.querySelectorAll('[data-nav]').forEach(t => t.onclick = () => pindah(t.dataset.nav));
}
async function nilai(s, tidakRelevan) {
  const x = V.item[V.idx];
  if (!x) return;
  const relevanLama = !(x.manusia && x.manusia.relevan === false);
  const relevan = tidakRelevan === undefined ? relevanLama : !tidakRelevan;
  try {
    const d = await minta(API('validasi/label'), { h: x.h, s, relevan, relevan_sebelumnya: relevanLama });
    x.manusia = { s, relevan };
    V.metrik = d.metrik;
    tampilRingkasVal(); tampilMatriks(); tampilBeda();
    if (tidakRelevan === undefined) { tampilKartu(); setTimeout(() => pindah('lompat'), 350); } else tampilKartu();
  } catch (e) { alert(e.message); }
}
function pindah(arah) {
  if (!V.item.length) return;
  if (arah === 'lompat') {
    const i = V.item.findIndex((x, j) => j > V.idx && !x.manusia);
    const k = i >= 0 ? i : V.item.findIndex(x => !x.manusia);
    if (k >= 0) V.idx = k;
  } else V.idx = (V.idx + Number(arah) + V.item.length) % V.item.length;
  tampilKartu();
}
document.addEventListener('keydown', e => {
  if (tabAktif !== 'validasi' || /input|textarea|select/i.test(e.target.tagName)) return;
  const peta = { 1: 'negatif', 2: 'netral', 3: 'positif' };
  if (peta[e.key]) nilai(peta[e.key]);
  else if (e.key === '4') { const x = V.item[V.idx]; if (x) nilai(x.manusia && x.manusia.s ? x.manusia.s : 'netral', !(x.manusia && x.manusia.relevan === false)); }
  else if (e.key === 'ArrowRight') pindah(1);
  else if (e.key === 'ArrowLeft') pindah(-1);
});
$('val-sembunyi').onchange = tampilKartu;
$('val-buat').onclick = async () => {
  const n = $('val-n').value;
  if (V.item.length && !confirm(`Ganti sampel dengan ${n} konten acak baru? Label kamu untuk konten yang sama tetap dipakai.`)) return;
  try { await minta(API('validasi/buat'), { n: Number(n) }); status($('val-status'), 'Sampel sedang dibuat…', 'jalan'); segarkan(); }
  catch (e) { alert(e.message); }
};
function matriks(judul, m) {
  if (!m) return '';
  const K = ['negatif', 'netral', 'positif'];
  return `<div class="kel-matriks"><p><b>${judul}</b> · cocok ${pr(m.akurasi)} dari ${m.n} konten</p>
    <table><thead><tr><th></th>${K.map(k => `<th>${SEN[k]}</th>`).join('')}<th>Recall</th></tr></thead><tbody>
    ${K.map(a => `<tr><th>${SEN[a]}</th>${K.map(b => `<td class="${a === b ? 'diag' : ''}">${m.matriks[a][b]}</td>`).join('')}
      <td>${pr(m.per_kelas[a].recall)}</td></tr>`).join('')}</tbody></table></div>`;
}
function tampilMatriks() {
  const m = V.metrik || {};
  $('val-matriks').innerHTML = (m.dinilai ? matriks('Aturan kata kunci', m.aturan) + matriks('AI', m.ai) : '')
    || '<p class="memuat">Beri label beberapa konten dulu.</p>';
}
function tampilBeda() {
  const xs = V.item.filter(x => x.manusia && (x.aturan.s !== x.manusia.s || (x.ai && x.ai.s !== x.manusia.s)));
  $('val-beda').innerHTML = !xs.length ? '<p class="memuat">Belum ada.</p>' : `<table class="kel-tabel"><thead><tr><th>Konten</th>
    <th>Kamu</th><th>Aturan</th><th>AI</th></tr></thead><tbody>${xs.slice(0, 80).map(x => `<tr>
    <td>${esc(x.teks.slice(0, 220))}${x.teks.length > 220 ? '…' : ''}<br><small class="kel-redup">${esc(x.platform)}</small></td>
    <td><b>${SEN[x.manusia.s]}</b>${x.manusia.relevan === false ? '<br><small>tidak relevan</small>' : ''}</td>
    <td class="${x.aturan.s === x.manusia.s ? 'cocok' : 'beda'}">${SEN[x.aturan.s]}</td>
    <td class="${x.ai && x.ai.s === x.manusia.s ? 'cocok' : 'beda'}">${x.ai ? SEN[x.ai.s] : '–'}</td></tr>`).join('')}</tbody></table>`;
}
function tampilSumber(l) {
  const s = V.setelan || {};
  document.querySelectorAll('#lab-sumber button').forEach(b => b.classList.toggle('aktif', b.dataset.v === s.label));
  $('lab-buang').checked = !!s.buang_tidak_relevan;
  $('lab-laporan').checked = s.laporan_ai !== false;
  const m = V.metrik || {};
  let saran = 'Nilai minimal 50 konten untuk membandingkan kedua sumber label dengan cukup yakin.';
  if (m.aturan && m.ai && m.ai.n >= 50) {
    const sel = m.ai.akurasi - m.aturan.akurasi;
    saran = sel > 0.05 ? `Label AI ${pr(sel)} lebih cocok dengan penilaian kamu. Disarankan memakai label AI.`
      : sel < -0.05 ? `Label aturan ${pr(-sel)} lebih cocok dengan penilaian kamu. Tetap pakai label aturan.`
      : 'Kedua sumber label hampir sama cocoknya dengan penilaian kamu.';
  }
  $('lab-ket').textContent = `Sekarang memakai ${s.label === 'ai' ? 'label AI' : 'label aturan kata kunci'}. ${saran}`;
  const el = $('lab-ai');
  if (!l) { el.innerHTML = ''; return; }
  const aktif = l.aktif && l.aktif.length;
  el.innerHTML = `<p>${angka(l.sudah)} dari ${angka(l.konten)} konten media sosial sudah berlabel AI.
    ${l.belum ? `${angka(l.belum)} teks unik belum; perkiraan biaya ${usd(l.perkiraan.luar_sibuk)}–${usd(l.perkiraan.sibuk)}
    ${l.jam_sibuk ? '(sekarang jam sibuk, tarif penuh)' : '(sekarang di luar jam sibuk, tarif separuh)'}.` : ''}
    ${s.label === 'ai' && l.belum ? ' Konten yang belum berlabel AI tetap memakai label aturan.' : ''}</p>
    ${l.belum ? `<div class="kel-aksi"><label class="kel-pilih">Batas biaya (USD)<input type="number" id="lab-batas" min="0.05" step="0.05"
      value="${Math.max(0.1, Math.ceil(l.perkiraan.sibuk * 1.5 * 20) / 20).toFixed(2)}"></label>
      <button type="button" class="tombol hantu kecil" id="lab-jalan" ${aktif ? 'disabled' : ''}>${aktif ? 'Sedang melabeli…' : 'Label sisanya dengan AI'}</button></div>` : ''}`;
  const jalan = $('lab-jalan');
  if (jalan) jalan.onclick = async () => {
    try { await minta(API('label-ai'), { batas_usd: Number($('lab-batas').value) }); segarkan(); muatValidasi(); }
    catch (e) { alert(e.message); }
  };
}
document.querySelectorAll('#lab-sumber button').forEach(b => b.onclick = async () => {
  if (V.setelan && b.dataset.v === V.setelan.label) return;
  const teks = b.dataset.v === 'ai'
    ? 'Pakai label AI untuk dashboard, graf SNA, dan laporan topik ini? Graf SNA akan dibangun ulang.'
    : 'Kembali ke label aturan kata kunci? Graf SNA akan dibangun ulang.';
  if (!confirm(teks)) return;
  V.setelan = await minta(API('setelan'), { label: b.dataset.v, bangun_sna: true });
  muatValidasi(); segarkan();
});
$('lab-buang').onchange = async e => {
  V.setelan = await minta(API('setelan'), { buang_tidak_relevan: e.target.checked, bangun_sna: true }); segarkan();
};
$('lab-laporan').onchange = async e => { V.setelan = await minta(API('setelan'), { laporan_ai: e.target.checked }); };

/* ---------------------------------------------------------------- klaster */
const WK = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767', '#5a5954', '#5a5954'];
async function muatKlaster() {
  let d;
  try { d = await minta(API('klaster')); } catch (e) { $('kl-daftar').innerHTML = `<p class="memuat">${esc(e.message)}</p>`; return; }
  const aktif = d.aktif && d.aktif.length;
  status($('kl-status'), aktif ? 'Pekerjaan klaster sedang berjalan…' : '', aktif ? 'jalan' : '');
  $('kl-terapkan').hidden = !d.perlu_terapkan;
  $('kl-draf-semua').disabled = !!aktif;
  if (!d.klaster.length) { $('kl-daftar').innerHTML = `<p class="memuat">${esc(d.pesan || 'Belum ada klaster.')}</p>`; return; }
  $('kl-daftar').innerHTML = d.klaster.map(k => {
    const t = k.tersimpan, df = k.draf;
    const awal = t || df || { nama: k.kurasi ? k.nama_sekarang : '', butir: [] };
    return `<div class="panel kel-kl" data-kunci="${esc(k.kunci || '')}">
      <div class="kel-kl-kepala"><span class="kel-kl-no" style="background:${WK[k.no - 1] || '#5a5954'}">K${k.no}</span>
        <div><h3>${esc(k.nama_sekarang)}</h3><p class="kel-redup">${angka(k.simpul)} akun · ${angka(k.interaksi)} interaksi · ${esc(k.platform)} · ${esc(k.sentimen)}</p></div>
        <span class="kel-chip ${t ? 'ok' : ''}">${t ? 'Tersimpan ' + esc(t.kurasi || '') : 'Belum dikurasi'}</span></div>
      <p class="kel-kecil"><b>Akun sentral:</b> ${esc(k.tokoh.join(', '))}${k.isu.length ? ` · <b>Isu:</b> ${esc(k.isu.join(', '))}` : ''}${k.kata.length ? ` · <b>Kata khas:</b> ${esc(k.kata.slice(0, 7).join(', '))}` : ''}</p>
      <details class="kel-contoh"><summary>Contoh unggahan (${k.contoh.length})</summary><ul>${k.contoh.map(c =>
        `<li><b>${esc(c.oleh || '')}</b>${c.ke ? ` → ${esc(c.ke)}` : ''}: ${esc(String(c.teks).slice(0, 260))}</li>`).join('')}</ul></details>
      ${df ? `<div class="kel-draf"><p class="kel-redup">Draf AI · ${esc(df.dibuat || '')}</p><b>${esc(df.nama)}</b>
        <ul>${df.butir.map(b => `<li>${esc(b)}</li>`).join('')}</ul>
        <button type="button" class="tombol hantu kecil" data-pakai>Pakai draf ini</button></div>` : ''}
      <div class="kel-form kel-kl-form">
        <label>Nama klaster <input type="text" maxlength="120" data-nama value="${esc(awal.nama)}"></label>
        <label>Catatan <small>satu butir per baris</small><textarea rows="4" data-butir>${esc((awal.butir || []).join('\n'))}</textarea></label>
        <div class="kel-aksi"><button type="button" class="tombol utama kecil" data-simpan ${k.kunci ? '' : 'disabled'}>Simpan</button>
          <button type="button" class="tombol hantu kecil" data-draf>Draf AI klaster ini</button>
          ${t ? '<button type="button" class="tombol hantu kecil" data-hapus>Hapus kurasi</button>' : ''}</div>
      </div></div>`;
  }).join('');
  $('kl-daftar').querySelectorAll('.kel-kl').forEach((el, i) => {
    const k = d.klaster[i];
    const pakai = el.querySelector('[data-pakai]');
    if (pakai) pakai.onclick = () => { el.querySelector('[data-nama]').value = k.draf.nama; el.querySelector('[data-butir]').value = k.draf.butir.join('\n'); };
    el.querySelector('[data-simpan]').onclick = async () => {
      const nama = el.querySelector('[data-nama]').value.trim();
      const butir = el.querySelector('[data-butir]').value.split('\n').map(s => s.trim()).filter(Boolean);
      const dariDraf = k.draf && nama === k.draf.nama;
      try { await minta(API('klaster/simpan'), { kunci: k.kunci, nama, butir, sumber: dariDraf ? 'ai-ditinjau' : 'manual' }); muatKlaster(); }
      catch (e) { alert(e.message); }
    };
    el.querySelector('[data-draf]').onclick = async () => {
      try { await minta(API('klaster/draf'), { k: k.no }); segarkan(); muatKlaster(); } catch (e) { alert(e.message); }
    };
    const hapus = el.querySelector('[data-hapus]');
    if (hapus) hapus.onclick = async () => {
      if (!confirm('Hapus nama dan catatan tersimpan untuk klaster ini?')) return;
      await minta(API('klaster/simpan'), { kunci: k.kunci, hapus: true }); muatKlaster();
    };
  });
}
$('kl-draf-semua').onclick = async () => {
  try { await minta(API('klaster/draf'), {}); segarkan(); muatKlaster(); } catch (e) { alert(e.message); }
};
$('kl-terapkan').onclick = async () => {
  try { await minta(API('klaster/terapkan'), {}); status($('kl-status'), 'Graf SNA sedang dibangun ulang…', 'jalan'); segarkan(); }
  catch (e) { alert(e.message); }
};

/* ---------------------------------------------------------------- kesimpulan */
let KS = null;
function presetKesimpulan() {
  const preset = [['Seluruh periode', KL.penuh[0], KL.penuh[1]], ...(INFO.preset || []).filter(p => p[1] !== KL.penuh[0] || p[2] !== KL.penuh[1])];
  $('ks-preset').innerHTML = preset.map(p => `<button type="button" class="ss-chip" data-a="${p[1]}" data-z="${p[2]}">${esc(p[0])}</button>`).join('');
  $('ks-preset').querySelectorAll('button').forEach(b => b.onclick = () => { $('ks-dari').value = b.dataset.a; $('ks-sampai').value = b.dataset.z; muatKesimpulan(); });
}
function isiEditor(ks, rk) {
  $('ks-daftar').innerHTML = '';
  (ks.length ? ks : [{ judul: '', isi: '' }]).forEach(tambahPoin);
  $('ks-rekom').value = (rk || []).join('\n');
}
function tambahPoin(k) {
  const div = document.createElement('div');
  div.className = 'kel-poin';
  div.innerHTML = `<input type="text" maxlength="120" placeholder="Judul temuan" value="${esc(k.judul || '')}">
    <textarea rows="3" placeholder="Isi: 2–4 kalimat dengan angka dari data">${esc(k.isi || '')}</textarea>
    <button type="button" class="tombol hantu kecil" title="Hapus poin">Hapus</button>`;
  div.querySelector('button').onclick = () => div.remove();
  $('ks-daftar').appendChild(div);
}
async function muatKesimpulan() {
  if (!$('ks-preset').children.length) presetKesimpulan();
  const q = `dari=${$('ks-dari').value}&sampai=${$('ks-sampai').value}`;
  try { KS = await minta(API(`kesimpulan?${q}`)); } catch (e) { status($('ks-status'), e.message, 'galat'); return; }
  $('ks-preset').querySelectorAll('button').forEach(b => b.classList.toggle('aktif', b.dataset.a === KS.dari && b.dataset.z === KS.sampai));
  const sumber = KS.disetujui ? `Laporan ${KS.periode} memakai versi yang disetujui ${KS.disetujui.tanggal}.`
    : KS.file_topik ? `Laporan ${KS.periode} memakai catatan analis di file topik${KS.file_topik.tanggal ? ` (per ${KS.file_topik.tanggal})` : ''}.`
    : `Belum ada versi yang disetujui untuk ${KS.periode}; laporan memakai ${KS.penuh ? 'ringkasan dari data' : 'draf AI bila diaktifkan, atau ringkasan dari data'}.`;
  $('ks-sumber').textContent = sumber;
  $('ks-isi-draf').hidden = !KS.draf;
  $('ks-isi-topik').hidden = !KS.file_topik;
  $('ks-hapus').hidden = !KS.disetujui;
  const aktif = KS.aktif && KS.aktif.length;
  $('ks-draf').disabled = !!aktif;
  status($('ks-status'), aktif ? 'Draf sedang ditulis (±1 menit)…' : KS.draf ? `Draf AI terakhir ${KS.draf.dibuat}` : '', aktif ? 'jalan' : '');
  const angkaAsing = KS.draf && KS.draf.angka_tak_dikenal || [];
  $('ks-angka').hidden = !angkaAsing.length || !!KS.disetujui;
  $('ks-angka').textContent = `Periksa angka berikut di draf AI; tidak ditemukan di data periode ini: ${angkaAsing.map(x => String(x).replace('.', ',')).join(', ')}.`;
  const sumberEditor = KS.disetujui || KS.file_topik || KS.draf || { kesimpulan: [], rekomendasi: [] };
  isiEditor(sumberEditor.kesimpulan || [], sumberEditor.rekomendasi || []);
}
$('ks-muat').onclick = muatKesimpulan;
$('ks-tambah').onclick = () => tambahPoin({});
$('ks-isi-draf').onclick = () => KS && KS.draf && isiEditor(KS.draf.kesimpulan, KS.draf.rekomendasi);
$('ks-isi-topik').onclick = () => KS && KS.file_topik && isiEditor(KS.file_topik.kesimpulan, KS.file_topik.rekomendasi);
$('ks-draf').onclick = async () => {
  try { await minta(API('kesimpulan/draf'), { dari: $('ks-dari').value, sampai: $('ks-sampai').value }); segarkan(); muatKesimpulan(); }
  catch (e) { alert(e.message); }
};
$('ks-setujui').onclick = async () => {
  const ks = [...document.querySelectorAll('.kel-poin')].map(d => ({ judul: d.querySelector('input').value.trim(), isi: d.querySelector('textarea').value.trim() }))
    .filter(k => k.judul && k.isi);
  const rk = $('ks-rekom').value.split('\n').map(s => s.trim()).filter(Boolean);
  if (!ks.length) { alert('Isi minimal satu poin kesimpulan.'); return; }
  try {
    await minta(API('kesimpulan/simpan'), { dari: KS.dari, sampai: KS.sampai, kesimpulan: ks, rekomendasi: rk });
    status($('ks-status'), 'Disetujui. Laporan periode ini akan memakai versi ini.', 'ok'); muatKesimpulan();
  } catch (e) { alert(e.message); }
};
$('ks-hapus').onclick = async () => {
  if (!confirm('Hapus persetujuan? Laporan kembali memakai catatan analis, draf AI, atau ringkasan dari data.')) return;
  await minta(API('kesimpulan/simpan'), { dari: KS.dari, sampai: KS.sampai, hapus: true }); muatKesimpulan();
};

/* ---------------------------------------------------------------- AI */
async function muatAI() {
  let d;
  try { d = await minta('/api/kelola/ai'); } catch (e) { $('ai-status').innerHTML = `<p class="memuat">${esc(e.message)}</p>`; return; }
  $('ai-lokasi').textContent = d.lokasi_konfig;
  const saldo = d.saldo && d.saldo.total != null ? `${d.saldo.total.toLocaleString('id-ID', { minimumFractionDigits: 2 })} ${d.saldo.mata_uang}` : (d.saldo && d.saldo.galat) || '–';
  $('ai-status').innerHTML = `<dl class="kel-dl"><dt>Status</dt><dd>${d.tersedia ? '<span class="kel-chip ok">Siap</span>' : '<span class="kel-chip gagal">Key belum diatur</span>'}</dd>
    <dt>Penyedia</dt><dd>${esc(d.penyedia)} · <code>${esc(d.base_url)}</code></dd><dt>Key</dt><dd><code>${esc(d.key)}</code></dd>
    <dt>Saldo</dt><dd>${esc(saldo)}</dd><dt>Tarif sekarang</dt><dd>${d.jam_sibuk ? 'Jam sibuk (tarif penuh)' : 'Di luar jam sibuk (tarif separuh)'}
    <small class="kel-redup"> · jam sibuk Senin–Jumat 08.00–11.00 dan 13.00–17.00 WIB</small></dd></dl>`;
  $('ai-model').value = d.model; $('ai-model-nalar').value = d.model_nalar;
  $('ai-paralel').value = d.paralel; $('ai-batas').value = d.batas_usd_per_tugas;
  const p = d.pemakaian;
  const NAMA = { label: 'Label sentimen', klaster: 'Nama klaster', kesimpulan: 'Kesimpulan', topik: 'Draf topik', uji: 'Uji koneksi' };
  $('ai-pakai').innerHTML = `<div class="kel-ringkas kecil"><div><small>Biaya</small><b>${usd(p.total.usd)}</b></div>
    <div><small>Panggilan</small><b>${angka(p.total.panggilan)}</b></div><div><small>Token</small><b>${angka(p.total.token)}</b></div></div>
    ${p.per_tugas.length ? `<table class="kel-tabel"><thead><tr><th>Tugas</th><th class="num">Panggilan</th><th class="num">Token</th><th class="num">Biaya</th></tr></thead>
    <tbody>${p.per_tugas.map(t => `<tr><td>${esc(NAMA[t.tugas] || t.tugas)}</td><td class="num">${angka(t.panggilan)}</td><td class="num">${angka(t.token)}</td><td class="num">${usd(t.usd)}</td></tr>`).join('')}</tbody></table>` : ''}
    ${p.per_hari.length ? `<table class="kel-tabel"><thead><tr><th>Tanggal</th><th class="num">Panggilan</th><th class="num">Biaya</th></tr></thead>
    <tbody>${p.per_hari.slice(-10).reverse().map(t => `<tr><td>${esc(tglPendek(t.tanggal))}</td><td class="num">${angka(t.panggilan)}</td><td class="num">${usd(t.usd)}</td></tr>`).join('')}</tbody></table>` : '<p class="memuat">Belum ada pemakaian.</p>'}`;
}
$('ai-form').onsubmit = async e => {
  e.preventDefault();
  try {
    await minta('/api/kelola/ai', { api_key: $('ai-key').value.trim(), model: $('ai-model').value, model_nalar: $('ai-model-nalar').value,
      paralel: Number($('ai-paralel').value), batas_usd_per_tugas: Number($('ai-batas').value) });
    $('ai-key').value = ''; muatAI();
  } catch (err) { alert(err.message); }
};

/* ---------------------------------------------------------------- mulai */
bukaTab((location.hash || '#panen').slice(1));
window.addEventListener('hashchange', () => { const t = location.hash.slice(1); if (t !== tabAktif) bukaTab(t); });
segarkan();
