/* SNA gaya Drone Emprit: graf interaksi diwarnai sentimen, emosi, atau klaster.
   Data: /api/sna (hasil scripts/12_sna.py — tata letak ForceAtlas2 sudah dihitung).
   Graf percakapan sosial dan graf pemberitaan (media ↔ aktor) digabung dalam satu
   kanvas, sehingga tiap sumber bisa dinyalakan/dimatikan seperti platform lain. */

// palet bersama dari aplikasi.js; kanvas graf selalu gelap, jadi abu netral tetap versi gelap
const SNA_SENT = { ...WARNA_SENT, netral: '#5a5954' };
const SNA_EMO_G = { ...SNA_EMO, netral: '#5a5954' };
// palet emosi (SNA_EMO, SNA_EMO_NAMA, SNA_EMO_EN) ada di aplikasi.js
const SNA_KOM = SLOT;                // 8 slot kategorikal tervalidasi, urutan tetap
const SNA_PLAT = { x: '𝕏', yt: '▶', ig: '◎', th: '@', media: '■', aktor: '◆' };
const SNA_PLAT_NAMA = { x: 'X', yt: 'YouTube', ig: 'Instagram', th: 'Threads', media: 'Media', aktor: 'Aktor' };
const SNA_SUMBER = [
  { k: 'x', nama: 'X', warna: WARNA_PLATFORM['X (Twitter)'] },
  { k: 'yt', nama: 'YouTube', warna: WARNA_PLATFORM['YouTube'] },
  { k: 'ig', nama: 'Instagram', warna: WARNA_PLATFORM['Instagram'] },
  { k: 'th', nama: 'Threads', warna: WARNA_PLATFORM['Threads'] },
  { k: 'berita', nama: 'Peta berita', warna: WARNA_PLATFORM['Berita'] },
];
// peta pemberitaan (media → aktor) sifatnya lain dari percakapan: mati secara bawaan
const SNA_SOSIAL = ['x', 'yt', 'ig', 'th'];
const SNA_FILTER = { 'X (Twitter)': 'x', 'YouTube': 'yt', 'Instagram': 'ig', 'Threads': 'th', 'Berita': 'berita' };
const SNA_JENIS = { komentar: 'Komentar', balasan: 'Balasan', mention: 'Mention', sebut: 'Disebut media' };
const SNA_SENTS = ['negatif', 'netral', 'positif'];
// simpul berita dibedakan lewat bentuk (■ media, ◆ aktor) dan warna netral:
// warna data sudah dipakai sentimen/emosi/klaster
const SNA_BERITA_WARNA = { media: '#8a877f', aktor: '#d8d4c8' };

const grupP = p => (p === 'media' || p === 'aktor') ? 'berita' : p;
const snaFilterAwal = () => ({
  plat: new Set(SNA_SOSIAL), sent: new Set(SNA_SENTS),
  jenis: new Set(Object.keys(SNA_JENIS)), emo: '', narasi: -1, aktor: -1, klaster: -1,
  min: 1, q: '', qMode: 'akun', tampil: 'sorot',
});

const S = { data: null, gab: null, teks: null, teksLow: null, mode: 'sentimen',
            view: { x: 0, y: 0, z: 1 }, pilih: null, sorotK: null, hover: null, g: null,
            f: snaFilterAwal(), platGlobal: 'semua' };

const pk = v => String(v).replace('.', ',');   // 15.2 -> 15,2
const snaAdaKlaster = k => typeof k === 'number';
const snaLabelK = n => snaAdaKlaster(n.k) ? `K${n.k + 1}` : 'Berita';

function snaWarnaKlaster(k) { return snaAdaKlaster(k) && k < SNA_KOM.length ? SNA_KOM[k] : '#4a4a45'; }

function snaWarnaSimpul(n) {
  if (n.grp === 'berita') return SNA_BERITA_WARNA[n.p] || '#8a877f';
  if (S.mode === 'sentimen') return SNA_SENT[n.s] || '#7d8590';
  if (S.mode === 'emosi') return SNA_EMO_G[n.e] || '#5a5954';
  return snaWarnaKlaster(n.k);
}

function snaWarnaSisi(e) {
  if (e.src === 'b') return '#6c6b65';
  if (S.mode === 'sentimen') return SNA_SENT[e.s] || '#7d8590';
  if (S.mode === 'emosi') return SNA_EMO_G[e.e] || '#5a5954';
  return snaWarnaKlaster(S.g.simpul[e.a].k);
}

function snaNetral(e) {
  if (e.src === 'b') return true;
  if (S.mode === 'sentimen') return e.s === 'netral';
  if (S.mode === 'emosi') return e.e === 'netral';
  return false;
}

/* ---------- gabungkan graf sosial + berita (sekali setelah data dimuat) ---------- */
function snaBatasP(nodes) {
  const xs = nodes.map(n => n.x).sort((a, b) => a - b), ys = nodes.map(n => n.y).sort((a, b) => a - b);
  // persentil 1–99: satu komponen kecil yang terlempar jauh tidak boleh
  // membuat seluruh graf mengecil jadi satu titik di tengah
  const q = (a, f) => a.length ? a[Math.floor(f * (a.length - 1))] : 0;
  const lo = nodes.length > 40 ? 0.01 : 0, hi = nodes.length > 40 ? 0.99 : 1;
  const x0 = q(xs, lo), x1 = q(xs, hi), y0 = q(ys, lo), y1 = q(ys, hi);
  return { x0, x1, y0, y1, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2,
           lx: Math.max(x1 - x0, 1e-6), ly: Math.max(y1 - y0, 1e-6) };
}

function snaGabung() {
  const d = S.data, so = d.sosial, be = d.berita;
  const simpul = [], sisi = [];
  if (so) {
    so.simpul.forEach(n => simpul.push({ ...n, src: 's', grp: grupP(n.p) }));
    so.sisi.forEach((e, i) => sisi.push({ ...e, src: 's', ti: i }));
  }
  const off = simpul.length;
  if (be) {
    // graf pemberitaan diletakkan di kanan graf percakapan, tingginya ±60%
    let skala = 1, dx = 0, dy = 0;
    if (so && so.simpul.length) {
      const bs = snaBatasP(so.simpul), bb = snaBatasP(be.simpul);
      skala = bs.ly * 0.62 / bb.ly;
      dx = bs.x1 + bs.lx * 0.14 - bb.x0 * skala;
      dy = bs.cy - bb.cy * skala;
    }
    be.simpul.forEach(n => simpul.push({ ...n, x: n.x * skala + dx, y: n.y * skala + dy,
                                         src: 'b', grp: 'berita', kb: n.k, k: 'b' }));
    be.sisi.forEach((e, i) => sisi.push({ ...e, a: e.a + off, b: e.b + off, src: 'b', ti: i }));
  }
  simpul.forEach((n, i) => { n.idx = i; n.low = n.l.toLowerCase(); });
  sisi.forEach((e, i) => { e.idx = i; });
  S.gab = { simpul, sisi, off };
}

/* ---------- mesin filter ---------- */
function snaKriteriaAktif() {
  const f = S.f;
  const q = f.q.trim().toLowerCase();
  return { q, akun: f.qMode === 'akun' && q.length >= 2,
           isi: f.qMode === 'isi' && q.length >= 3 && !!S.teksLow,
           ada: f.narasi >= 0 || f.aktor >= 0 || (f.qMode === 'akun' ? q.length >= 2 : q.length >= 3) };
}

function snaSiapkan() {
  const A = S.gab;
  if (!A || !A.simpul.length) { S.g = null; return; }
  const f = S.f;
  const nOK = A.simpul.map(n => f.plat.has(n.grp) && (f.klaster < 0 || n.k === f.klaster));
  // berita tidak dilabeli sentimen/emosi: filter itu hanya berlaku untuk sisi sosial
  let sisi = A.sisi.filter(e => nOK[e.a] && nOK[e.b] && f.jenis.has(e.j)
    && (e.src === 'b' || (f.sent.has(e.s) && (!f.emo || e.e === f.emo))));

  // kriteria pencarian: narasi, aktor, teks, nama akun (digabung DAN)
  const K = snaKriteriaAktif();
  let cocokE = null, cocokN = null, akunCocok = null;
  if (K.ada) {
    if (K.akun) akunCocok = new Set(A.simpul.filter(n => nOK[n.idx] && n.low.includes(K.q)).map(n => n.idx));
    const lolos = e => (f.narasi < 0 || (e.n && e.n.includes(f.narasi)))
      && (f.aktor < 0 || (e.ak && e.ak.includes(f.aktor)))
      && (!K.isi || S.teksLow[e.idx].includes(K.q))
      && (!akunCocok || akunCocok.has(e.a) || akunCocok.has(e.b));
    // pencarian isi yang teksnya belum termuat: tunggu, jangan kosongkan graf
    const tunggu = f.qMode === 'isi' && K.q.length >= 3 && !S.teksLow;
    if (!tunggu || f.narasi >= 0 || f.aktor >= 0) {
      cocokE = new Set(sisi.filter(lolos).map(e => e.idx));
      cocokN = new Set();
      sisi.forEach(e => { if (cocokE.has(e.idx)) { cocokN.add(e.a); cocokN.add(e.b); } });
      if (akunCocok) akunCocok.forEach(i => cocokN.add(i));
      if (f.tampil === 'saring') sisi = sisi.filter(e => cocokE.has(e.idx));
    }
  }

  // minimal interaksi per akun, lalu derajat akhir
  let derajat = new Array(A.simpul.length).fill(0);
  sisi.forEach(e => { derajat[e.a] += e.w; derajat[e.b] += e.w; });
  if (f.min > 1) {
    sisi = sisi.filter(e => derajat[e.a] >= f.min && derajat[e.b] >= f.min);
    derajat = new Array(A.simpul.length).fill(0);
    sisi.forEach(e => { derajat[e.a] += e.w; derajat[e.b] += e.w; });
  }
  const simpul = A.simpul.map((n, i) => ({ ...n, tampak: nOK[i] && derajat[i] > 0, deg: derajat[i] }));
  const vis = simpul.filter(n => n.tampak);
  const maksDeg = Math.max(1, ...vis.map(n => n.deg));
  simpul.forEach(n => { n.r = 1.6 + Math.sqrt(n.deg / maksDeg) * 19; });

  // titik label klaster: rata-rata posisi anggota terbesar klaster itu
  const pusat = {}, perK = {};
  vis.forEach(n => { if (snaAdaKlaster(n.k)) (perK[n.k] = perK[n.k] || []).push(n); });
  for (const k in perK) {
    const top = perK[k].sort((a, b) => b.deg - a.deg).slice(0, 30);
    const w = top.reduce((s, n) => s + n.deg, 0) || 1;
    pusat[k] = { x: top.reduce((s, n) => s + n.x * n.deg, 0) / w,
                 y: top.reduce((s, n) => s + n.y * n.deg, 0) / w, n: perK[k].length };
  }
  const so = S.data.sosial || {};
  const bVis = vis.filter(n => n.grp === 'berita');
  S.g = { simpul, sisi, vis, klaster: so.klaster || [], wawasan: so.wawasan || [],
          statistik: so.statistik || {}, batas: snaBatasP(vis.length ? vis : A.simpul),
          pusat, maksDeg, cocokE, cocokN, K,
          adaBerita: bVis.length > 0, adaSosial: vis.length > bVis.length,
          hanyaBerita: bVis.length > 0 && bVis.length === vis.length,
          batasBerita: bVis.length && vis.length > bVis.length ? snaBatasP(bVis) : null };
  if (S.pilih != null && !simpul[S.pilih].tampak) S.pilih = null;
}

function snaSkala(lebar, tinggi) {
  const b = S.g.batas, pad = 40, t = snaTepi();
  const w = Math.max(200, lebar - t.kiri - t.kanan), h = Math.max(200, tinggi - t.atas - t.bawah);
  const ox = t.kiri + w / 2, oy = t.atas + h / 2;
  const dasar = Math.min((w - pad * 2) / b.lx, (h - pad * 2) / b.ly);
  const skala = dasar * S.view.z;
  return { px: x => ox + (x - b.cx) * skala + S.view.x,
           py: y => oy + (y - b.cy) * skala + S.view.y, dasar, ox, oy };
}

/* pas-kan tampilan ke sekumpulan simpul (hasil pencarian, simpul terpilih + tetangga) */
function snaPasKe(idxs) {
  const c = document.getElementById('graf');
  const G = S.g;
  const nodes = [...idxs].map(i => G.simpul[i]).filter(n => n && n.tampak);
  if (!c || !nodes.length) return;
  const t = snaBatasP(nodes), b = G.batas;
  const z = Math.max(0.3, Math.min(14, 0.8 * Math.min(b.lx / Math.max(t.lx, b.lx / 14),
                                                      b.ly / Math.max(t.ly, b.ly / 14))));
  const { dasar } = snaSkala(c.clientWidth, c.clientHeight);
  S.view = { z, x: -(t.cx - b.cx) * dasar * z, y: -(t.cy - b.cy) * dasar * z };
  snaGambar();
}

function snaTetangga(i) {
  const s = new Set([i]);
  S.g.sisi.forEach(e => { if (e.a === i) s.add(e.b); if (e.b === i) s.add(e.a); });
  return s;
}

/* ---------- gambar ---------- */
function snaPenuh() {
  const l = document.getElementById('sna-layar');
  return !!(l && l.classList.contains('penuh'));
}

function snaUkuranKanvas(c) {
  if (snaPenuh()) return { lebar: window.innerWidth, tinggi: window.innerHeight };
  const lebar = c.parentElement.clientWidth;
  return { lebar, tinggi: Math.max(520, Math.min(720, lebar * 0.72)) };
}

/* ruang yang tertutup widget melayang (layar penuh): graf dipusatkan di sisa ruang */
function snaTepi() {
  if (!snaPenuh()) return { kiri: 0, kanan: 0, atas: 0, bawah: 0 };
  const l = document.getElementById('sna-layar');
  const lebar = el => (el && el.offsetParent !== null) ? el.getBoundingClientRect().width + 24 : 0;
  return { kiri: l.classList.contains('tanpa-saring') ? 0 : lebar(document.getElementById('sna-saring')),
           kanan: l.classList.contains('tanpa-info') ? 0 : lebar(document.getElementById('sna-insight')),
           atas: 64, bawah: 56 };
}

function snaBentuk(g, n, x, y) {
  g.beginPath();
  if (n.p === 'media') {
    const s = n.r * 0.9; g.rect(x - s, y - s, s * 2, s * 2);
  } else if (n.p === 'aktor') {
    const s = n.r * 1.15; g.moveTo(x, y - s); g.lineTo(x + s, y); g.lineTo(x, y + s); g.lineTo(x - s, y); g.closePath();
  } else g.arc(x, y, n.r, 0, 6.2832);
}

function snaGambar() {
  const c = document.getElementById('graf');
  if (!c) return;
  const dpr = window.devicePixelRatio || 1;
  const { lebar, tinggi } = snaUkuranKanvas(c);
  c.style.width = lebar + 'px'; c.style.height = tinggi + 'px';
  c.width = lebar * dpr; c.height = tinggi * dpr;
  const g = c.getContext('2d');
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, lebar, tinggi);
  if (!S.g || !S.g.vis.length) {
    g.fillStyle = INK_G[3]; g.font = '13px ' + HURUF; g.textAlign = 'center';
    g.fillText(S.gab && S.gab.simpul.length ? 'Tidak ada akun yang tampak dengan filter ini.'
      : 'Belum ada data jaringan. Jalankan scripts/12_sna.py', lebar / 2, tinggi / 2);
    return;
  }
  const { px, py } = snaSkala(lebar, tinggi);
  const G = S.g;
  const fokus = S.pilih != null ? snaTetangga(S.pilih) : null;
  const redup = n => (fokus && !fokus.has(n.idx)) || (S.sorotK != null && n.k !== S.sorotK)
    || (G.cocokN && !G.cocokN.has(n.idx));

  // sisi: netral dulu (tipis, pudar), lalu yang bermuatan di atasnya
  const lapis = [[], []];
  G.sisi.forEach(e => lapis[snaNetral(e) ? 0 : 1].push(e));
  lapis.forEach((daftar, li) => {
    for (const e of daftar) {
      const a = G.simpul[e.a], b = G.simpul[e.b];
      const bukanCocok = G.cocokE && !G.cocokE.has(e.idx);
      const mati = (redup(a) && redup(b)) || (fokus && !(e.a === S.pilih || e.b === S.pilih)) || bukanCocok;
      const x1 = px(a.x), y1 = py(a.y), x2 = px(b.x), y2 = py(b.y);
      const cx = (x1 + x2) / 2 - (y2 - y1) * 0.14, cy = (y1 + y2) / 2 + (x2 - x1) * 0.14;
      // garis di dalam klaster lebih tegas daripada garis antar-klaster,
      // supaya struktur kelompok terbaca dan graf tidak jadi gumpalan benang
      const dalam = a.k === b.k;
      g.globalAlpha = mati ? 0.03 : (li === 0 ? (dalam ? 0.14 : 0.05) : (dalam ? 0.55 : 0.2));
      if (G.cocokE && !mati) g.globalAlpha = Math.max(g.globalAlpha, li === 0 ? 0.35 : 0.75);
      g.strokeStyle = snaWarnaSisi(e);
      g.lineWidth = Math.min(3, 0.5 + Math.log2(1 + e.w) * 0.5) * ((fokus || G.cocokE) && !mati ? 1.8 : 1);
      g.beginPath(); g.moveTo(x1, y1); g.quadraticCurveTo(cx, cy, x2, y2); g.stroke();
    }
  });

  // simpul (kecil dulu supaya hub tidak tertimbun)
  const urut = [...G.vis].sort((a, b) => a.r - b.r);
  for (const n of urut) {
    const x = px(n.x), y = py(n.y);
    const cocok = G.cocokN && G.cocokN.has(n.idx);
    const r0 = n.r;
    if (cocok) n.r = Math.max(n.r, 4.5);          // hasil pencarian kecil tetap terlihat
    g.globalAlpha = redup(n) ? 0.12 : 0.95;
    snaBentuk(g, n, x, y);
    g.fillStyle = snaWarnaSimpul(n); g.fill();
    if (n.r > 7) { g.lineWidth = 1.2; g.strokeStyle = 'rgba(13,17,23,.9)'; g.stroke(); }
    if (n.idx === S.pilih) { g.lineWidth = 2.5; g.strokeStyle = '#fff'; g.stroke(); }
    else if (cocok) { g.lineWidth = 1.6; g.strokeStyle = '#f0c77a'; g.stroke(); }
    n.r = r0;
  }
  g.globalAlpha = 1;

  // judul wilayah berita, supaya dua peta yang berbeda sifat tidak tertukar
  if (G.batasBerita) {
    const bb = G.batasBerita;
    g.font = '600 12px ' + HURUF; g.textAlign = 'left'; g.fillStyle = INK_G[3];
    g.fillText('Pemberitaan: media ■ → aktor ◆', px(bb.x0), py(bb.y0) - 14);
  }

  // label akun teratas
  const nLabel = +document.getElementById('sna-label').value;
  let kandidat = [...G.vis];
  if (G.cocokN) kandidat = kandidat.filter(n => G.cocokN.has(n.idx));
  let berlabel = kandidat.sort((a, b) => b.deg - a.deg).slice(0, G.cocokN ? Math.max(nLabel, 25) : nLabel);
  if (fokus) berlabel = [...fokus].map(i => G.simpul[i]).filter(n => n.tampak).sort((a, b) => b.deg - a.deg).slice(0, 25);
  if (S.pilih != null) berlabel = [G.simpul[S.pilih], ...berlabel.filter(n => n.idx !== S.pilih)];
  g.textAlign = 'center'; g.lineJoin = 'round';
  const kotak = [];                       // label yang bertabrakan dilewati
  const tag = snaTataTag(g, px, py, fokus);
  tag.forEach(t => kotak.push(t));
  const tabrak = (r) => kotak.some(k => r.x < k.x + k.w && r.x + r.w > k.x && r.y < k.y + k.h && r.y + r.h > k.y);
  for (const n of berlabel) {
    if (redup(n) && !(fokus && fokus.has(n.idx))) continue;
    const t = (SNA_PLAT[n.p] || '') + ' ' + (n.l.length > 24 ? n.l.slice(0, 23) + '…' : n.l);
    g.font = `${n.r > 12 ? 600 : 500} ${n.r > 12 ? 12.5 : 11}px ${HURUF}`;
    const w = g.measureText(t).width, x = px(n.x), y = py(n.y) - n.r - 5;
    const r = { x: x - w / 2 - 2, y: y - 12, w: w + 4, h: 15 };
    if (tabrak(r) && n.idx !== S.pilih) continue;
    kotak.push(r);
    g.strokeStyle = 'rgba(22,22,20,.92)'; g.lineWidth = 3.5;
    g.strokeText(t, x, y);
    g.fillStyle = n.idx === S.pilih ? '#fffaf0' : INK_G[1]; g.fillText(t, x, y);
  }
  S.kotakLabel = kotak;

  // nama klaster langsung di atas graf, seperti anotasi laporan Drone Emprit
  tag.forEach(t => {
    g.font = '700 12.5px ' + HURUF;
    g.globalAlpha = 0.92; g.fillStyle = 'rgba(22,22,20,.92)';
    snaPil(g, t.x, t.y, t.w, t.h, 12); g.fill();
    g.globalAlpha = 1; g.lineWidth = 1.5; g.strokeStyle = t.garis; g.stroke();
    g.fillStyle = t.warna; g.fillText(t.teks, t.x + t.w / 2, t.y + 16.5);
  });
}

function snaTataTag(g, px, py, fokus) {
  // posisi tag dihitung sebelum label akun, supaya label akun yang menabrak
  // tag dilewati — bukan tag yang menimpa nama akun
  const tag = [];
  if (!document.getElementById('sna-tagklaster').checked || fokus || S.g.cocokN) return tag;
  const G = S.g;
  G.klaster.slice(0, 10).forEach(c => {
    const p = G.pusat[c.k];
    if (!p || p.n < 8 || (S.sorotK != null && S.sorotK !== c.k)) return;
    const teks = `K${c.k + 1} · ${snaNamaPendek(c)}`;
    g.font = '700 12.5px ' + HURUF;
    const w = g.measureText(teks).width + 18;
    const x = px(p.x) - w / 2;
    let y = py(p.y) + 18;
    for (let i = 0; i < 6; i++) {           // geser turun bila menabrak tag lain
      if (!tag.some(k => x < k.x + k.w && x + w > k.x && y < k.y + k.h && y + 24 > k.y)) break;
      y += 27;
    }
    // di mode sentimen/emosi tag dibuat netral: tag hijau/merah mudah
    // disangka warna sentimen
    const netral = S.mode !== 'klaster';
    tag.push({ x, y, w, h: 24, teks, warna: netral ? INK_G[1] : snaWarnaKlaster(c.k),
               garis: netral ? '#5a5954' : snaWarnaKlaster(c.k) });
  });
  return tag;
}

function snaPil(g, x, y, w, h, r) {
  g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r);
  g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r);
  g.closePath();
}

function snaNamaPendek(c) {
  const n = c.nama || c.tokoh[0] || '?';
  return n.length > 34 ? n.slice(0, 33) + '…' : n;
}

/* ---------- cara membaca & temuan utama (berubah per tab) ---------- */
// kanvas graf selalu gelap (juga di tema cetak), jadi tinta label graf tetap terang
const INK_G = { 1: '#ebe9e3', 2: '#c5c3ba', 3: '#908e86', 4: '#6c6b65' };
// periode filter, bila bukan seluruh jendela: server memakai graf periode itu bila sudah dibuat
function snaRentang() {
  const d1 = (document.getElementById('f-dari') || {}).value, d2 = (document.getElementById('f-sampai') || {}).value;
  return d1 && d2 && (d1 !== INFO.awal || d2 !== INFO.akhir) ? `?dari=${d1}&sampai=${d2}` : '';
}

const SNA_BACA = {
  sentimen: 'Node = akun. Edge = interaksi (komentar, balasan, mention). <b>Warna edge = sentimen unggahan</b> yang membentuk interaksi itu. Warna node = sentimen yang paling sering muncul di unggahan akun itu (di luar netral). Ukuran node = jumlah interaksi yang diterima (in-degree).',
  emosi: '<b>Warna edge = emosi Plutchik</b> dari unggahan: biru sedih, oranye antisipasi, merah marah, ungu muak, hijau muda percaya. Abu-abu berarti tanpa emosi yang jelas.',
  klaster: '<b>Warna node = klaster Louvain</b>, yaitu kelompok akun yang lebih sering berinteraksi satu sama lain daripada dengan akun di luar kelompok. Isi tiap klaster dijelaskan di kartu di bawah.',
  berita: 'Graf <b>media ■ → aktor ◆</b>: edge menghubungkan media dengan lembaga atau tokoh yang disebut di artikelnya. Graf ini tidak memakai label sentimen, jadi warnanya <b>abu-abu</b>.',
};
/* persen dengan koma desimal */
const pr = v => (+v || 0).toLocaleString('id-ID', { maximumFractionDigits: 1 }) + '%';

function snaTemuan() {
  const el = document.getElementById('sna-temuan');
  const G = S.g;
  if (!el) return;
  if (!G) { el.innerHTML = ''; return; }
  const besar = G.klaster.filter(c => c.interaksi >= 30);
  const nama = c => `K${c.k + 1} ${snaNamaPendek(c)}`;
  let t = '';
  if (G.hanyaBerita) {
    const hub = [...G.vis].filter(n => n.p === 'aktor').sort((a, b) => b.deg - a.deg).slice(0, 3);
    t = `Aktor paling banyak diberitakan: <b>${hub.map(n => aman(n.l)).join(', ')}</b>.`;
  } else if (S.mode === 'sentimen' && besar.length) {
    const neg = besar.reduce((a, b) => b.sentimen.negatif > a.sentimen.negatif ? b : a);
    const pos = besar.reduce((a, b) => b.sentimen.positif > a.sentimen.positif ? b : a);
    const st = G.statistik.sentimen || {};
    t = `Seluruh graf: <b style="color:${SNA_SENT.positif}">positif ${pr(st.positif)}</b>,
      <b style="color:${SNA_SENT.negatif}">negatif ${pr(st.negatif)}</b>. Klaster paling negatif:
      <b>${nama(neg)}</b> (${pr(neg.sentimen.negatif)} negatif). Klaster paling positif:
      <b>${nama(pos)}</b> (${pr(pos.sentimen.positif)} positif).`;
  } else if (S.mode === 'emosi' && besar.length) {
    const st = G.statistik.emosi || {};
    const top = Object.entries(st).filter(([k]) => k !== 'netral').sort((a, b) => b[1] - a[1]).slice(0, 3);
    const marah = besar.reduce((a, b) => (b.emosi.marah + b.emosi.jijik) > (a.emosi.marah + a.emosi.jijik) ? b : a);
    t = `Emosi terbesar: ${top.map(([k, v]) => `<b style="color:${SNA_EMO[k]}">${SNA_EMO_NAMA[k]} ${pr(v)}</b>`).join(', ')}.
      Porsi marah dan muak tertinggi di <b>${nama(marah)}</b>
      (${pr(marah.emosi.marah + marah.emosi.jijik)}).`;
  } else if (S.mode === 'klaster' && besar.length) {
    t = `${G.klaster.length} klaster terbesar mencakup
      <b>${pr(G.klaster.reduce((s, c) => s + c.persen, 0))}</b> akun.
      Klaster terbesar: <b>${nama(G.klaster[0])}</b> (${pr(G.klaster[0].persen)} akun).`;
  }
  const baca = G.hanyaBerita ? SNA_BACA.berita
    : SNA_BACA[S.mode] + (G.adaBerita ? ' ' + SNA_BACA.berita.replace('Graf', 'Di sisi kanan: graf') : '');
  el.innerHTML = `<div class="sna-baca">${baca}</div>
    ${t ? `<div class="sna-temuan-isi"><span>Temuan</span>${t}</div>` : ''}`;
}

/* ---------- legenda ---------- */
function snaLegenda() {
  const el = document.getElementById('sna-legenda');
  const G = S.g;
  let isi = '';
  if (!G || !G.hanyaBerita) {
    if (S.mode === 'sentimen') {
      isi = SNA_SENTS.map(k => `<span><i style="background:${SNA_SENT[k]}"></i>${kapital(k)}</span>`).join('');
    } else if (S.mode === 'emosi') {
      isi = Object.keys(SNA_EMO).map(k =>
        `<span><i style="background:${SNA_EMO[k]}"></i>${SNA_EMO_NAMA[k]}</span>`).join('');
    } else if (G) {
      isi = G.klaster.slice(0, 10).map(c =>
        `<span><i style="background:${snaWarnaKlaster(c.k)}"></i>K${c.k + 1}</span>`).join('');
    }
  }
  if (G && G.adaBerita) isi += `<span><i class="kotak" style="background:${SNA_BERITA_WARNA.media}"></i>Media</span>
    <span><i class="wajik" style="background:${SNA_BERITA_WARNA.aktor}"></i>Aktor diberitakan</span>
    <span class="leg-ket">abu-abu = berita, tanpa label sentimen</span>`;
  el.innerHTML = isi + '<em>ukuran = jumlah interaksi</em>';
}

/* ---------- panel Node Insight ---------- */
function snaInsight() {
  const el = document.getElementById('sna-insight');
  const G = S.g;
  if (!G) { el.innerHTML = '<p class="memuat">Belum ada data.</p>'; return; }
  // profil dihitung dari graf yang tampak agar ikut filter
  const n = G.vis.length, m = G.sisi.length;
  const interaksi = G.sisi.reduce((s, e) => s + e.w, 0);
  const sosial = G.sisi.filter(e => e.src === 's');
  const iSos = sosial.reduce((s, e) => s + e.w, 0);
  const cS = {}, cE = {};
  sosial.forEach(e => { cS[e.s] = (cS[e.s] || 0) + e.w; cE[e.e] = (cE[e.e] || 0) + e.w; });
  const pct = (c, k) => iSos ? (100 * (c[k] || 0) / iSos) : 0;
  const bar = (nama, w, v) => `<div class="ni-bar"><div class="ni-bar-atas"><span>${nama}</span>
      <b>${v.toFixed(0)}%</b></div><div class="ni-trek"><i style="width:${v}%;background:${w}"></i></div></div>`;
  let komposisi = '';
  if (!iSos) {
    komposisi = '<h3>Klaster</h3><p class="memuat">Graf pemberitaan tidak punya label sentimen dan emosi.</p>';
  } else if (S.mode === 'emosi') {
    komposisi = '<h3>Emosi</h3>' + Object.keys(SNA_EMO)
      .sort((a, b) => pct(cE, b) - pct(cE, a))
      .map(k => bar(`${SNA_EMO_NAMA[k]} <small>${SNA_EMO_EN[k]}</small>`, SNA_EMO[k], pct(cE, k))).join('');
  } else {
    komposisi = '<h3>Sentimen</h3>' + ['positif', 'netral', 'negatif']
      .map(k => bar(k[0].toUpperCase() + k.slice(1), SNA_SENT[k], pct(cS, k))).join('');
  }
  const kepadatan = n > 1 ? (2 * m / (n * (n - 1)) * 100) : 0;
  const tot = S.gab.simpul.length;
  el.innerHTML = `
    <div class="sw-kepala"><h2>Detail node</h2>
      <button type="button" class="sw-tutup hanya-penuh" data-tutup="info" aria-label="Sembunyikan info">×</button></div>
    <div id="sna-detail"></div>
    <h3>Profil graf <small class="ni-ket">${n < tot ? 'sesuai filter' : 'seluruh graf'}</small></h3>
    <div class="ni-profil">
      <div><small>Interaksi</small><b>${angka(interaksi)}</b></div>
      <div><small>Node (akun)</small><b>${angka(n)}</b></div>
      <div><small>Edge</small><b>${angka(m)}</b></div>
      <div><small>Kepadatan</small><b>${pr(kepadatan)}</b></div>
      <div><small>Rata-rata degree</small><b>${n ? (2 * m / n).toLocaleString('id-ID', { maximumFractionDigits: 1 }) : 0}</b></div>
      <div><small>Porsi dari semua node</small><b>${tot ? Math.round(100 * n / tot) : 0}%</b></div>
    </div>
    ${komposisi}
    <h3>${G.cocokN ? 'Akun yang cocok' : 'Degree tertinggi'} (50)</h3>
    <div class="ni-top" id="sna-top"></div>`;
  snaIsiTop();
  snaDetail();
}

function snaIsiTop() {
  const G = S.g;
  const el = document.getElementById('sna-top');
  if (!el) return;
  const top = [...G.vis].filter(n => !G.cocokN || G.cocokN.has(n.idx))
    .sort((a, b) => b.deg - a.deg).slice(0, 50);
  const maks = top.length ? top[0].deg : 1;
  el.innerHTML = top.map(n => `
    <div class="ni-simpul ${n.idx === S.pilih ? 'aktif' : ''}" data-i="${n.idx}">
      <span><i style="background:${snaWarnaSimpul(n)}"></i>${SNA_PLAT[n.p] || ''} ${aman(n.l)}</span>
      <b>${angka(n.deg)}</b>
      <div class="ni-trek"><i style="width:${100 * n.deg / maks}%"></i></div>
    </div>`).join('') || '<p class="memuat">Tidak ada.</p>';
  el.querySelectorAll('.ni-simpul').forEach(d => d.onclick = () => snaPilih(+d.dataset.i, true));
}

function snaDetail() {
  const el = document.getElementById('sna-detail');
  if (!el) return;
  if (S.pilih == null) { el.innerHTML = ''; return; }
  const G = S.g, n = G.simpul[S.pilih];
  const c = G.klaster.find(k => k.k === n.k);
  const tet = G.sisi.filter(e => e.a === n.idx || e.b === n.idx).sort((a, b) => b.w - a.w).slice(0, 8);
  const [neg, net, pos] = n.sn || [0, 0, 0];
  const tot = neg + net + pos || 1;
  const posisi = n.grp === 'berita' ? `Berita · ${n.p === 'media' ? 'media' : 'aktor yang diberitakan'}`
    : (c ? `K${c.k + 1} ${aman(snaNamaPendek(c))}` : 'klaster kecil');
  el.innerHTML = `<div class="ni-detail">
    <button class="ni-tutup" id="sna-tutup" aria-label="Tutup">×</button>
    <b>${SNA_PLAT[n.p] || ''} ${aman(n.l)}</b>
    <small>${SNA_PLAT_NAMA[n.p] || n.p} · ${posisi}</small>
    ${n.grp === 'berita' ? '' : `<div class="ni-sn"><i style="width:${100 * neg / tot}%;background:${SNA_SENT.negatif}"></i><i
      style="width:${100 * net / tot}%;background:${SNA_SENT.netral}"></i><i
      style="width:${100 * pos / tot}%;background:${SNA_SENT.positif}"></i></div>`}
    <table>
      <tr><td>In-degree / out-degree</td><td class="num">${angka(n.i)} / ${angka(n.o)}</td></tr>
      <tr><td>PageRank ×1000</td><td class="num">${n.pr}</td></tr>
      <tr><td>Betweenness</td><td class="num">${n.b}</td></tr>
      ${n.grp === 'berita' ? '' : `<tr><td>Emosi dominan</td><td class="num" style="color:${SNA_EMO[n.e]}">${SNA_EMO_NAMA[n.e] || '-'}</td></tr>`}
    </table>
    <div class="ni-aksi"><button class="tombol hantu kecil" id="sna-dekati" type="button"><svg class="ik"><use href="#ik-pas"/></svg>Dekati</button>
      <button class="tombol hantu kecil" id="sna-jadikan-cari" type="button"><svg class="ik"><use href="#ik-saring"/></svg>Saring ke akun ini</button></div>
    <small style="margin-top:8px">Interaksi terkuat</small>
    ${tet.map(e => {
      const lawan = G.simpul[e.a === n.idx ? e.b : e.a];
      return `<div class="ni-tet" data-i="${lawan.idx}"><span>${e.a === n.idx ? '→' : '←'} ${aman(lawan.l)}</span>
        <i style="background:${snaWarnaSisi(e)}"></i><b>${e.w}</b></div>`;
    }).join('')}
    <small style="margin-top:10px">Unggahan di interaksi ini</small>
    <div class="ni-unggahan" id="sna-unggahan">${S.teksLow ? snaUnggahanSimpul(n) : '<button class="tombol hantu kecil" id="sna-muat-teks" type="button">Tampilkan unggahan</button>'}</div>
  </div>`;
  document.getElementById('sna-tutup').onclick = () => snaPilih(null);
  document.getElementById('sna-dekati').onclick = () => snaPasKe(snaTetangga(n.idx));
  document.getElementById('sna-jadikan-cari').onclick = () => {
    S.f.qMode = 'akun'; S.f.q = n.l; S.f.tampil = 'saring';
    snaSinkronKontrol(); snaTerapkan(true);
  };
  const mt = document.getElementById('sna-muat-teks');
  if (mt) mt.onclick = async () => { mt.textContent = 'Memuat…'; await snaMuatTeks(); snaDetail(); };
  el.querySelectorAll('.ni-tet').forEach(d => d.onclick = () => snaPilih(+d.dataset.i, true));
}

function snaTeksSisi(e) {
  if (!S.teks) return [];
  return (S.teks[e.src === 's' ? 'sosial' : 'berita'] || [])[e.ti] || [];
}

function snaSorotTeks(t, q) {
  const a = aman(t);
  if (!q) return a;
  const i = t.toLowerCase().indexOf(q);
  if (i < 0) return a;
  return aman(t.slice(0, i)) + '<mark>' + aman(t.slice(i, i + q.length)) + '</mark>' + aman(t.slice(i + q.length));
}

function snaUnggahanSimpul(n) {
  const G = S.g, q = G.K && G.K.isi ? G.K.q : '';
  const daftar = [];
  G.sisi.filter(e => (e.a === n.idx || e.b === n.idx) && (!G.cocokE || G.cocokE.has(e.idx)))
    .sort((a, b) => b.w - a.w).forEach(e => snaTeksSisi(e).forEach(t => {
      if (!q || t.toLowerCase().includes(q)) daftar.push({ e, t });
    }));
  if (!daftar.length) return '<p class="memuat">Tidak ada teks.</p>';
  return daftar.slice(0, 6).map(({ e, t }) => {
    const a = G.simpul[e.a], b = G.simpul[e.b];
    return `<blockquote><p>${snaSorotTeks(t.length > 220 ? t.slice(0, 219) + '…' : t, q)}</p>
      <span>${aman(a.l)} → ${aman(b.l)}${e.src === 's' ? ` · <em style="color:${SNA_SENT[e.s]}">${e.s}</em>` : ''}</span></blockquote>`;
  }).join('');
}

function snaPilih(i, dekati) {
  S.pilih = i; S.sorotK = null;
  if (i != null && snaPenuh()) snaWidget('info', true);
  snaDetail();
  if (dekati && i != null) snaPasKe(snaTetangga(i)); else snaGambar();
  document.querySelectorAll('#sna-top .ni-simpul').forEach(d =>
    d.classList.toggle('aktif', +d.dataset.i === i));
  document.querySelectorAll('.kk').forEach(d => d.classList.remove('aktif'));
}

/* ---------- panel filter ---------- */
async function snaMuatTeks() {
  if (S.teksLow) return;
  if (!S._teksJanji) {
    S._teksJanji = fetch(api('/api/sna-teks') + snaRentang()).then(r => r.json()).then(t => {
      S.teks = t;
      S.teksLow = S.gab.sisi.map(e => snaTeksSisi(e).join(' \n ').toLowerCase());
    }).catch(() => { S._teksJanji = null; });
  }
  await S._teksJanji;
}

function snaChip(k, label, warna, aktif, jumlah, bentuk) {
  return `<button type="button" class="ss-chip ${aktif ? 'aktif' : ''}" data-k="${k}" aria-pressed="${aktif}">
    <i class="${bentuk || ''}" style="background:${warna}"></i>${label}${jumlah != null ? `<small>${angka(jumlah)}</small>` : ''}</button>`;
}

function snaBangunKontrol() {
  const A = S.gab, d = S.data;
  if (!A) return;
  // sumber: hanya yang punya simpul
  const nPlat = {};
  A.simpul.forEach(n => { nPlat[n.grp] = (nPlat[n.grp] || 0) + 1; });
  const plat = document.getElementById('ss-plat');
  plat.innerHTML = SNA_SUMBER.filter(s => nPlat[s.k] && s.k !== 'berita').map(s =>
    snaChip(s.k, s.nama, s.warna, S.f.plat.has(s.k), nPlat[s.k])).join('')
    + `<button type="button" class="ss-chip ss-semua" data-k="*">Semua media sosial</button>`;
  const brs = document.getElementById('ss-berita-baris'), cb = document.getElementById('ss-berita');
  if (brs) brs.hidden = !nPlat.berita;
  if (cb) {
    cb.checked = S.f.plat.has('berita');
    cb.onchange = () => { cb.checked ? S.f.plat.add('berita') : S.f.plat.delete('berita'); snaTerapkan(true); };
  }
  plat.onclick = e => {
    const b = e.target.closest('.ss-chip'); if (!b) return;
    if (b.dataset.k === '*') { SNA_SOSIAL.forEach(k => S.f.plat.add(k)); }
    else if (e.altKey || e.metaKey) S.f.plat = new Set([b.dataset.k]);       // alt/cmd-klik = hanya ini
    else S.f.plat.has(b.dataset.k) ? S.f.plat.delete(b.dataset.k) : S.f.plat.add(b.dataset.k);
    snaSinkronKontrol(); snaTerapkan(true);
  };
  plat.ondblclick = e => {                                                   // klik ganda = hanya ini
    const b = e.target.closest('.ss-chip'); if (!b || b.dataset.k === '*') return;
    S.f.plat = new Set([b.dataset.k]); snaSinkronKontrol(); snaTerapkan(true);
  };
  plat.title = 'Klik untuk menyalakan/mematikan · klik ganda = hanya sumber ini';

  const nSent = {}, nJenis = {};
  A.sisi.forEach(e => { if (e.src === 's') nSent[e.s] = (nSent[e.s] || 0) + e.w; nJenis[e.j] = (nJenis[e.j] || 0) + e.w; });
  const sent = document.getElementById('ss-sent');
  sent.innerHTML = SNA_SENTS.map(k => snaChip(k, kapital(k), SNA_SENT[k], S.f.sent.has(k), nSent[k] || 0)).join('');
  sent.onclick = e => {
    const b = e.target.closest('.ss-chip'); if (!b) return;
    S.f.sent.has(b.dataset.k) ? S.f.sent.delete(b.dataset.k) : S.f.sent.add(b.dataset.k);
    snaSinkronKontrol(); snaTerapkan(true);
  };
  const jenis = document.getElementById('ss-jenis');
  jenis.innerHTML = Object.keys(SNA_JENIS).filter(k => nJenis[k]).map(k =>
    snaChip(k, SNA_JENIS[k], '#908e86', S.f.jenis.has(k), nJenis[k])).join('');
  jenis.onclick = e => {
    const b = e.target.closest('.ss-chip'); if (!b) return;
    S.f.jenis.has(b.dataset.k) ? S.f.jenis.delete(b.dataset.k) : S.f.jenis.add(b.dataset.k);
    snaSinkronKontrol(); snaTerapkan(true);
  };

  // dropdown: hanya pilihan yang benar-benar muncul di graf, dengan jumlah interaksinya
  const hitung = (kunci) => { const c = {}; A.sisi.forEach(e => (e[kunci] || []).forEach(i => { c[i] = (c[i] || 0) + e.w; })); return c; };
  const isiSelect = (id, semua, opsi, nilai) => {
    const sel = document.getElementById(id);
    sel.innerHTML = `<option value="-1">${semua}</option>` + opsi.map(o =>
      `<option value="${o.v}">${aman(o.t)}${o.n != null ? ` (${angka(o.n)})` : ''}</option>`).join('');
    sel.value = String(nilai);
    if (typeof pasangPilih === 'function') pasangPilih(sel);
    return sel;
  };
  const cN = hitung('n'), cA = hitung('ak');
  isiSelect('ss-narasi', 'Semua topik', (d.narasi_daftar || []).map((t, i) => ({ v: i, t, n: cN[i] }))
    .filter(o => o.n).sort((a, b) => b.n - a.n), S.f.narasi)
    .onchange = e => { S.f.narasi = +e.target.value; snaTerapkan(true); };
  isiSelect('ss-aktor', 'Semua aktor', (d.aktor_daftar || []).map((t, i) => ({ v: i, t, n: cA[i] }))
    .filter(o => o.n).sort((a, b) => b.n - a.n), S.f.aktor)
    .onchange = e => { S.f.aktor = +e.target.value; snaTerapkan(true); };
  const cE = {};
  A.sisi.forEach(e => { if (e.src === 's') cE[e.e] = (cE[e.e] || 0) + e.w; });
  const selE = isiSelect('ss-emo', 'Semua emosi', Object.keys(SNA_EMO).filter(k => cE[k])
    .map(k => ({ v: k, t: SNA_EMO_NAMA[k], n: cE[k] })), S.f.emo || -1);
  selE.onchange = e => { S.f.emo = e.target.value === '-1' ? '' : e.target.value; snaTerapkan(true); };
  const kl = (d.sosial && d.sosial.klaster) || [];
  isiSelect('ss-klaster', 'Semua klaster', kl.slice(0, 10).map(c => ({ v: c.k, t: `K${c.k + 1} · ${snaNamaPendek(c)}`, n: c.simpul })),
    S.f.klaster).onchange = e => { S.f.klaster = +e.target.value; S.sorotK = null; snaTerapkan(true); };
}

function snaSinkronKontrol() {
  const f = S.f;
  document.querySelectorAll('#ss-plat .ss-chip[data-k]').forEach(b => {
    if (b.dataset.k === '*') return;
    const on = f.plat.has(b.dataset.k); b.classList.toggle('aktif', on); b.setAttribute('aria-pressed', on);
  });
  const cb = document.getElementById('ss-berita'); if (cb) cb.checked = f.plat.has('berita');
  document.querySelectorAll('#ss-sent .ss-chip').forEach(b => { const on = f.sent.has(b.dataset.k); b.classList.toggle('aktif', on); b.setAttribute('aria-pressed', on); });
  document.querySelectorAll('#ss-jenis .ss-chip').forEach(b => { const on = f.jenis.has(b.dataset.k); b.classList.toggle('aktif', on); b.setAttribute('aria-pressed', on); });
  [['ss-narasi', f.narasi], ['ss-aktor', f.aktor], ['ss-emo', f.emo || -1], ['ss-klaster', f.klaster]].forEach(([id, v]) => {
    const s = document.getElementById(id); if (s) { s.value = String(v); s._pilih && s._pilih(); }
  });
  const min = document.getElementById('ss-min'); if (min) min.value = String(f.min);
  document.querySelectorAll('.segmen[data-untuk="ss-min"] button').forEach(b => b.classList.toggle('aktif', b.dataset.v === String(f.min)));
  document.querySelectorAll('#ss-mode button').forEach(b => b.classList.toggle('aktif', b.dataset.v === f.qMode));
  document.querySelectorAll('#ss-tampil button').forEach(b => b.classList.toggle('aktif', b.dataset.v === f.tampil));
  const q = document.getElementById('ss-q');
  if (q && q.value !== f.q) q.value = f.q;
  if (q) q.placeholder = f.qMode === 'akun' ? 'Cari nama akun, kanal, media, atau aktor…'
    : 'Cari kata di isi unggahan, mis. "ganti rugi", "korupsi", "nelayan"…';
}

function snaJumlahFilterLanjut() {
  const f = S.f;
  return (f.sent.size < 3) + (f.jenis.size < Object.keys(SNA_JENIS).length) + !!f.emo
    + (f.narasi >= 0) + (f.aktor >= 0) + (f.klaster >= 0) + (f.min > 1);
}

function snaRingkas() {
  const el = document.getElementById('ss-ringkas');
  const G = S.g, f = S.f;
  if (!el) return;
  const jml = snaJumlahFilterLanjut();
  const lencana = document.getElementById('sna-jml-filter');
  if (lencana) lencana.textContent = jml ? String(jml) : '';
  if (!G) { el.innerHTML = ''; return; }
  const d = S.data;
  const tanda = [];
  const lencana2 = document.getElementById('sna-jml-filter2');
  if (lencana2) lencana2.textContent = jml ? String(jml) : '';
  const matiPlat = SNA_SUMBER.filter(s => s.k !== 'berita' && !f.plat.has(s.k)
    && S.gab.simpul.some(n => n.grp === s.k)).map(s => s.nama);
  if (matiPlat.length) tanda.push(`tanpa ${matiPlat.join(', ')}`);
  if (f.plat.has('berita')) tanda.push('+ peta berita');
  if (f.sent.size < 3) tanda.push(`sentimen: ${[...f.sent].join(', ') || 'tidak ada'}`);
  if (f.jenis.size < Object.keys(SNA_JENIS).length) tanda.push(`jenis: ${[...f.jenis].map(k => SNA_JENIS[k].toLowerCase()).join(', ') || 'tidak ada'}`);
  if (f.emo) tanda.push(`emosi: ${SNA_EMO_NAMA[f.emo].toLowerCase()}`);
  if (f.narasi >= 0) tanda.push(`topik: ${d.narasi_daftar[f.narasi]}`);
  if (f.aktor >= 0) tanda.push(`aktor: ${d.aktor_daftar[f.aktor]}`);
  if (f.klaster >= 0) tanda.push(`klaster K${f.klaster + 1}`);
  if (f.min > 1) tanda.push(`min. ${f.min} interaksi`);
  if (G.K.q && (G.K.akun || G.K.isi)) tanda.push(`${f.qMode === 'akun' ? 'akun' : 'isi'} "${G.K.q}"`);
  const tunggu = f.qMode === 'isi' && G.K.q.length >= 3 && !S.teksLow;
  const cocok = G.cocokE ? `<b class="ss-cocok">${angka(G.cocokE.size)} interaksi · ${angka(G.cocokN.size)} akun cocok</b>
      <button type="button" class="ss-tautan" id="ss-pas-hasil">pas ke hasil</button>` : '';
  el.innerHTML = `<span>Menampilkan <b>${angka(G.vis.length)}</b> akun · <b>${angka(G.sisi.length)}</b> garis</span>
    ${cocok}${tunggu ? '<span class="memuat">memuat isi unggahan…</span>' : ''}
    ${tanda.length ? `<span class="ss-tanda">${tanda.map(aman).join(' · ')}</span>
      <button type="button" class="ss-tautan" id="ss-hapus-cepat">hapus filter</button>` : ''}`;
  const pas = document.getElementById('ss-pas-hasil');
  if (pas) pas.onclick = () => snaPasKe(G.cocokN);
  const hapus = document.getElementById('ss-hapus-cepat');
  if (hapus) hapus.onclick = snaHapusFilter;
}

function snaHapusFilter() {
  const mode = S.f.qMode;
  S.f = snaFilterAwal(); S.f.qMode = mode; S.sorotK = null;
  snaSinkronKontrol(); snaTerapkan(true);
}

/* saran akun saat mengetik (mode Akun) */
function snaSaran() {
  const ul = document.getElementById('ss-saran');
  const q = S.f.q.trim().toLowerCase();
  if (!ul) return;
  if (S.f.qMode !== 'akun' || q.length < 1 || !S.gab) { ul.innerHTML = ''; ul.classList.remove('buka'); return; }
  const deg = n => n.i + n.o;
  const hasil = S.gab.simpul.filter(n => S.f.plat.has(n.grp) && n.low.includes(q))
    .sort((a, b) => (b.low.startsWith(q) - a.low.startsWith(q)) || deg(b) - deg(a)).slice(0, 8);
  ul.innerHTML = hasil.map((n, i) => `<li role="option" data-i="${n.idx}" class="${i === 0 ? 'sorot' : ''}">
      <span><i style="background:${snaWarnaSimpul(n)}"></i>${SNA_PLAT[n.p] || ''} ${snaSorotTeks(n.l, q)}</span>
      <small>${SNA_PLAT_NAMA[n.p] || ''} · ${angka(deg(n))}</small></li>`).join('')
    || '<li class="kosong">Tidak ada akun dengan nama itu.</li>';
  ul.classList.add('buka');
}

function snaPasangFilter() {
  const q = document.getElementById('ss-q');
  const ul = document.getElementById('ss-saran');
  let t = null;
  q.oninput = () => {
    S.f.q = q.value;
    snaSaran();
    clearTimeout(t);
    t = setTimeout(async () => {
      if (S.f.qMode === 'isi' && S.f.q.trim().length >= 3 && !S.teksLow) { snaTerapkan(false); await snaMuatTeks(); }
      snaTerapkan(false);
    }, S.f.qMode === 'isi' ? 350 : 220);
  };
  q.onkeydown = e => {
    const li = [...ul.querySelectorAll('li[data-i]')];
    const k = li.findIndex(x => x.classList.contains('sorot'));
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault(); if (!li.length) return;
      const j = (k + (e.key === 'ArrowDown' ? 1 : -1) + li.length) % li.length;
      li.forEach((x, i) => x.classList.toggle('sorot', i === j));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (S.f.qMode === 'akun' && k >= 0 && ul.classList.contains('buka')) { snaPilihSaran(+li[k].dataset.i); return; }
      ul.classList.remove('buka');
      if (S.g && S.g.cocokN && S.g.cocokN.size) snaPasKe(S.g.cocokN);
    } else if (e.key === 'Escape') {
      if (ul.classList.contains('buka')) ul.classList.remove('buka');
      else { q.value = ''; S.f.q = ''; snaTerapkan(false); }
    }
  };
  q.onfocus = snaSaran;
  ul.onmousedown = e => {
    const li = e.target.closest('li[data-i]'); if (!li) return;
    e.preventDefault(); snaPilihSaran(+li.dataset.i);
  };
  document.addEventListener('click', e => { if (!e.target.closest('#ss-cari')) ul.classList.remove('buka'); });

  document.getElementById('ss-mode').onclick = async e => {
    const b = e.target.closest('button'); if (!b) return;
    S.f.qMode = b.dataset.v; snaSinkronKontrol(); snaSaran();
    if (S.f.qMode === 'isi') { snaTerapkan(false); await snaMuatTeks(); }
    snaTerapkan(false); q.focus();
  };
  document.getElementById('ss-tampil').onclick = e => {
    const b = e.target.closest('button'); if (!b) return;
    S.f.tampil = b.dataset.v; snaSinkronKontrol(); snaTerapkan(true);
  };
  document.getElementById('ss-min').oninput = e => { S.f.min = +e.target.value; snaTerapkan(true); };
  document.getElementById('ss-reset').onclick = snaHapusFilter;
  const buka = document.getElementById('sna-saring-buka');
  buka.onclick = () => {
    const el = document.getElementById('sna-lanjut');
    el.hidden = !el.hidden; buka.setAttribute('aria-expanded', String(!el.hidden));
    buka.classList.toggle('aktif', !el.hidden);
    if (document.getElementById('sna-layar').classList.contains('penuh')) snaGambar();
  };
}

function snaPilihSaran(i) {
  const ul = document.getElementById('ss-saran');
  ul.classList.remove('buka');
  const n = S.gab.simpul[i];
  S.f.q = n.l; snaSinkronKontrol(); snaTerapkan(false);
  snaPilih(i, true);
}

/* terapkan filter: hitung ulang graf, lalu segarkan semua panel yang bergantung padanya */
function snaTerapkan(resetView) {
  S.hasilN = 30;
  if (resetView) S.view = { x: 0, y: 0, z: 1 };
  snaSiapkan();
  // akun terpilih yang tidak lagi cocok dengan pencarian dilepas, agar label tidak menyesatkan
  if (S.g && S.g.cocokN && S.pilih != null && !S.g.cocokN.has(S.pilih)) S.pilih = null;
  snaLegenda(); snaTemuan(); snaInsight(); snaRingkas(); snaHasil(); snaPeran(); snaGambar();
}

/* daftar unggahan yang cocok dengan narasi/aktor/pencarian, di bawah peta */
async function snaHasil() {
  const el = document.getElementById('sna-hasil');
  const G = S.g;
  if (!el) return;
  if (!G || !G.cocokE || !G.cocokE.size) { el.hidden = true; el.innerHTML = ''; return; }
  el.hidden = false;
  if (!S.teksLow) {
    el.innerHTML = '<p class="memuat">Memuat isi unggahan…</p>';
    await snaMuatTeks();
    if (S.g !== G) return;             // filter sudah berubah saat menunggu
  }
  const q = G.K.isi ? G.K.q : '';
  const baris = [];
  G.sisi.filter(e => G.cocokE.has(e.idx)).sort((a, b) => b.w - a.w).forEach(e => {
    snaTeksSisi(e).forEach(t => { if (!q || t.toLowerCase().includes(q)) baris.push({ e, t }); });
  });
  const tampil = baris.slice(0, S.hasilN || 30);
  el.innerHTML = `<div class="sh-kepala"><h3>Unggahan yang cocok</h3>
      <span>${angka(baris.length)} unggahan dari ${angka(G.cocokE.size)} interaksi${baris.length > tampil.length ? ` · ${tampil.length} teratas` : ''}</span></div>
    <div class="sh-daftar">${tampil.map(({ e, t }) => {
      const a = G.simpul[e.a], b = G.simpul[e.b];
      return `<article class="sh-item" data-i="${a.idx}">
        <p>${snaSorotTeks(t, q)}</p>
        <div class="sh-kaki"><b>${SNA_PLAT[a.p] || ''} ${aman(a.l)}</b><span>→ ${aman(b.l)}</span>
          ${e.src === 's' ? `<span class="lencana ${kelasSentimen(e.s)}">${e.s}</span>` : '<span class="chip">berita</span>'}
          <span class="sh-jenis">${SNA_JENIS[e.j] || e.j}</span></div></article>`;
    }).join('')}</div>
    ${baris.length > tampil.length ? '<button type="button" class="tombol hantu kecil" id="sh-lagi">Tampilkan 30 lagi</button>' : ''}`;
  el.querySelectorAll('.sh-item').forEach(x => x.onclick = () => {
    snaPilih(+x.dataset.i, true);
    document.getElementById('sna-layar').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  const lagi = document.getElementById('sh-lagi');
  if (lagi) lagi.onclick = () => { S.hasilN = (S.hasilN || 30) + 30; snaHasil(); };
}

/* ---------- kesimpulan & kartu klaster ---------- */
function snaKesimpulan() {
  const G = S.g;
  const w = document.getElementById('sna-wawasan');
  const kk = document.getElementById('sna-klaster');
  if (!G) { w.innerHTML = kk.innerHTML = ''; return; }
  w.innerHTML = G.wawasan.length ? G.wawasan.map(x => `
      <div class="ws ${x.k != null ? 'bisa' : ''}" ${x.k != null ? `data-k="${x.k}"` : ''}>
        <p class="ws-judul"><i style="${x.k != null ? `background:${snaWarnaKlaster(x.k)}` : ''}"></i>${aman(x.judul)}</p>
        <p>${aman(x.isi)}</p></div>`).join('')
    : `<div class="ws"><p style="margin:0">${G.hanyaBerita
        ? 'Graf media ↔ aktor: edge menghubungkan media dengan lembaga atau tokoh yang disebut di artikelnya. Graf ini tidak memakai label sentimen.'
        : 'Belum ada ringkasan.'}</p></div>`;

  const kl = G.klaster.slice(0, 10);
  const daftar = `<nav class="kk-daftar">${kl.map(c => `<a href="#klaster-${c.k}">
      <i style="background:${snaWarnaKlaster(c.k)}"></i>K${c.k + 1} · ${aman(snaNamaPendek(c))}</a>`).join('')}</nav>`;
  kk.innerHTML = daftar + kl.map(c => {
    const warna = snaWarnaKlaster(c.k);
    const butir = (c.butir && c.butir.length ? c.butir : c.butir_auto) || [];
    const plat = Object.entries(c.platform || {}).map(([p, v]) => `${SNA_PLAT_NAMA[p] || p} ${angka(v)}`).join(' · ');
    const s = c.sentimen;
    const emo = (c.emosi_utama || []).map(e => `<div class="kk-emo-baris">
        <span>${SNA_EMO_NAMA[e]}</span>
        <div class="kk-emo-trek"><i style="width:${Math.min(100, c.emosi[e] * 2.5)}%;background:${SNA_EMO[e]}"></i></div>
        <b>${pk(c.emosi[e])}%</b></div>`).join('');
    const contoh = (c.contoh || []).slice(0, 3).map(x => `<blockquote class="kk-kutip">
        <p>${aman(x.t)}</p>
        <div class="kutip-kaki"><b>${SNA_PLAT[x.p] || ''} ${aman(x.oleh)}</b>
          ${x.l ? `<span>♥ ${angka(x.l)}</span>` : ''}
          <span class="lencana ${kelasSentimen(x.s)}">${x.s}</span>
          <span class="chip"><i style="background:${SNA_EMO[x.e]}"></i>${SNA_EMO_NAMA[x.e]}</span>
          ${x.u ? `<a href="${aman(x.u)}" target="_blank" rel="noopener" style="margin-left:auto">buka<svg class="ik" style="width:12px;height:12px"><use href="#ik-keluar"/></svg></a>` : ''}</div>
      </blockquote>`).join('');
    return `<article class="kk" id="klaster-${c.k}" data-k="${c.k}" style="--warna:${warna}">
      <header class="kk-kepala">
        <span class="kk-no">K${c.k + 1}</span>
        <div class="kk-judul"><h3>${aman(c.nama || c.nama_auto)}</h3>
          <p>${angka(c.simpul)} akun · ${angka(c.interaksi)} interaksi · ${plat} ·
             <em title="${c.nama ? 'butir ditulis setelah membaca isi unggahan klaster' : 'butir dihasilkan dari angka'}">${c.nama ? 'dikurasi ' + (c.kurasi || '') : 'ringkasan otomatis'}</em></p></div>
        <button class="kk-sorot tombol hantu kecil" data-k="${c.k}"><svg class="ik"><use href="#ik-sorot"/></svg>Sorot di peta</button>
      </header>
      <div class="kk-badan">
        <div class="kk-kiri">
          ${`<div class="kk-label">Komposisi sentimen</div>
          <div class="kk-sent"><i style="width:${s.negatif}%;background:${SNA_SENT.negatif}"></i><i
            style="width:${s.netral}%;background:${SNA_SENT.netral}"></i><i
            style="width:${s.positif}%;background:${SNA_SENT.positif}"></i></div>
          <div class="kk-sent-ket">
            <span><i style="background:${SNA_SENT.negatif}"></i>Negatif <b>${pk(s.negatif)}%</b></span>
            <span><i style="background:${SNA_SENT.netral}"></i>Netral <b>${pk(s.netral)}%</b></span>
            <span><i style="background:${SNA_SENT.positif}"></i>Positif <b>${pk(s.positif)}%</b></span></div>
          ${emo ? `<div class="kk-label">Emosi menonjol</div><div class="kk-emo">${emo}</div>` : ''}`}
          <div class="kk-label">Temuan</div>
          <ul class="kk-butir">${butir.map(b => `<li>${aman(b)}</li>`).join('')}</ul>
          ${c.kata && c.kata.length ? `<div class="kk-label">Kata khas</div>
            <p class="kk-kata">${c.kata.map(aman).join(' · ')}</p>` : ''}
        </div>
        <div class="kk-kanan">
          <div class="kk-label">Contoh unggahan paling disukai</div>
          ${contoh || '<p class="memuat">Belum ada contoh.</p>'}
        </div>
      </div>
    </article>`;
  }).join('');

  document.querySelectorAll('.kk-sorot').forEach(d => d.onclick = () => snaSorot(+d.dataset.k));
  document.querySelectorAll('.ws.bisa').forEach(d => d.onclick = () => snaSorot(+d.dataset.k));
  snaBanding();
  snaPeran();
}

/* ---------- perbandingan antar-klaster ---------- */
function snaBanding() {
  const G = S.g;
  const kl = G.klaster.slice(0, 10);
  const label = kl.map(c => `K${c.k + 1} · ${snaNamaPendek(c).slice(0, 32)}`);
  if (G.hanyaBerita) {
    gambar('g-klaster-sent', { type: 'bar', data: { labels: [], datasets: [] } });
    document.getElementById('sna-emo-matriks').innerHTML =
      '<p class="memuat">Graf media ↔ aktor tidak dilabeli sentimen/emosi.</p>';
    return;
  }
  grafikTumpuk100('g-klaster-sent', label, ['negatif', 'netral', 'positif'].map(k => ({
    nama: k, warna: SNA_SENT[k], data: kl.map(c => Math.round(c.sentimen[k] * c.interaksi / 100)) })),
    { onClick: (_, el) => { if (el.length) snaSorot(kl[el[0].index].k); } });
  const emo = ['sedih', 'antisipasi', 'marah', 'jijik', 'percaya', 'senang', 'takut', 'terkejut'];
  const maks = Math.max(1, ...kl.flatMap(c => emo.map(e => c.emosi[e] || 0)));
  document.getElementById('sna-emo-matriks').innerHTML = `<table class="matriks"><thead><tr><th></th>
    ${emo.map(e => `<th title="${SNA_EMO_EN[e]}"><i style="background:${SNA_EMO[e]}"></i>${SNA_EMO_NAMA[e]}</th>`).join('')}
    </tr></thead><tbody>${kl.map((c, i) => `<tr data-k="${c.k}"><td>${label[i]}</td>
    ${emo.map(e => {
      const v = c.emosi[e] || 0;
      return `<td style="background:${SNA_EMO[e]}${Math.round(14 + 190 * v / maks).toString(16).padStart(2, '0')};
               color:${v / maks > 0.55 ? '#161614' : INK[1]}">${v ? v.toFixed(0) : '·'}</td>`;
    }).join('')}</tr>`).join('')}</tbody></table>`;
  document.querySelectorAll('.matriks tbody tr').forEach(r => r.onclick = () => snaSorot(+r.dataset.k));
}

/* ---------- peran aktor ---------- */
function snaPeran() {
  const G = S.g;
  const el = document.getElementById('sna-peran');
  if (!el || !G) return;
  // peran dihitung di percakapan sosial; simpul berita hanya dipakai bila
  // hanya berita yang tampak (aktor berita punya derajat masuk sangat besar)
  const kandidat = G.vis.filter(n => G.hanyaBerita || n.grp !== 'berita');
  // hub = 20 akun penerima interaksi terbanyak; di jaringan berbentuk bintang
  // merekalah jembatan terbesar, sehingga daftar jembatan hanya mengulang
  // daftar hub. Yang lebih informatif: warganet biasa yang menyambungkan klaster.
  const hub = new Set([...kandidat].sort((a, b) => b.i - a.i).slice(0, 20).map(n => n.idx));
  const kolom = [
    { judul: 'In-degree tertinggi', ket: 'paling banyak dikomentari, dibalas, atau di-mention', kunci: n => n.i, fmt: n => `${angka(n.i)} masuk` },
    { judul: 'Out-degree tertinggi', ket: 'paling banyak mengirim komentar, balasan, atau mention', kunci: n => n.o, fmt: n => `${angka(n.o)} keluar` },
    { judul: 'Betweenness tertinggi', ket: 'di luar 20 akun dengan in-degree tertinggi; akun yang paling sering menghubungkan klaster berbeda',
      kunci: n => hub.has(n.idx) ? 0 : n.b, fmt: n => n.b.toFixed(4) },
  ];
  el.innerHTML = kolom.map(k => {
    const top = [...kandidat].sort((a, b) => k.kunci(b) - k.kunci(a)).slice(0, 8).filter(n => k.kunci(n) > 0);
    return `<div><h3>${k.judul}</h3><p class="ket">${k.ket}</p>${top.map((n, i) => `
      <div class="peran" data-i="${n.idx}"><span class="no">${i + 1}</span>
        <span class="nm"><i style="background:${n.grp === 'berita' ? SNA_BERITA_WARNA[n.p] : SNA_SENT[n.s]}"></i>${SNA_PLAT[n.p] || ''} ${aman(n.l)}</span>
        <span class="kl" style="color:${snaWarnaKlaster(n.k)}">${snaLabelK(n)}</span><b>${k.fmt(n)}</b></div>`).join('')
      || '<p class="memuat">Tidak ada.</p>'}</div>`;
  }).join('');
  el.querySelectorAll('.peran').forEach(d => d.onclick = () => {
    snaPilih(+d.dataset.i, true);
    document.getElementById('sna-layar').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
}

function snaSorot(k) {
  S.sorotK = S.sorotK === k ? null : k; S.pilih = null;
  snaDetail();
  if (S.sorotK != null) {
    const anggota = S.g.vis.filter(n => n.k === S.sorotK).map(n => n.idx);
    snaPasKe(anggota);
  } else { S.view = { x: 0, y: 0, z: 1 }; snaGambar(); }
  document.querySelectorAll('.kk').forEach(d => d.classList.toggle('aktif', +d.dataset.k === S.sorotK));
  document.getElementById('sna-layar').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ---------- interaksi kanvas ---------- */
function snaCariSimpul(ox, oy) {
  const c = document.getElementById('graf');
  const { px, py } = snaSkala(c.clientWidth, c.clientHeight);
  let dekat = null, jarak = 1e9;
  for (const n of S.g.vis) {
    const d = Math.hypot(px(n.x) - ox, py(n.y) - oy);
    if (d < Math.max(6, n.r + 3) && d < jarak) { jarak = d; dekat = n; }
  }
  return dekat;
}

function snaZoom(f, ox, oy) {
  const c = document.getElementById('graf');
  if (!S.g) return;
  const nz = Math.max(0.3, Math.min(14, S.view.z * f));
  const k = nz / S.view.z;
  const p = snaSkala(c.clientWidth, c.clientHeight);
  const cx = ox == null ? 0 : ox - p.ox, cy = oy == null ? 0 : oy - p.oy;
  // zoom ke arah kursor (atau ke tengah kanvas untuk tombol)
  S.view.x = (S.view.x - cx) * k + cx;
  S.view.y = (S.view.y - cy) * k + cy;
  S.view.z = nz; snaGambar();
}

/* layar penuh: Fullscreen API, dengan cadangan CSS bila peramban menolak */
function snaPenuhAktif() { return !!(document.fullscreenElement || document.webkitFullscreenElement); }

function snaLayarPenuh() {
  const el = document.getElementById('sna-layar');
  if (snaPenuhAktif()) { (document.exitFullscreen || document.webkitExitFullscreen).call(document); return; }
  if (el.classList.contains('penuh')) { snaSetPenuh(false); return; }       // cadangan CSS
  const minta = el.requestFullscreen || el.webkitRequestFullscreen;
  if (minta) {
    const p = minta.call(el);
    if (p && p.catch) p.catch(() => snaSetPenuh(true));
  } else snaSetPenuh(true);
}

function snaWidget(nama, tampil) {
  const l = document.getElementById('sna-layar');
  const kelas = nama === 'saring' ? 'tanpa-saring' : 'tanpa-info';
  const on = tampil == null ? l.classList.contains(kelas) : tampil;
  l.classList.toggle(kelas, !on);
  const b = document.getElementById(nama === 'saring' ? 'sna-tgl-saring' : 'sna-tgl-info');
  if (b) { b.classList.toggle('aktif', on); b.setAttribute('aria-pressed', String(on)); }
  if (snaPenuh()) requestAnimationFrame(snaGambar);
}

function snaSetPenuh(on) {
  const el = document.getElementById('sna-layar');
  const berubah = el.classList.contains('penuh') !== on;
  el.classList.toggle('penuh', on);
  document.body.classList.toggle('sna-penuh', on);
  if (on && berubah) { snaWidget('saring', true); snaWidget('info', S.pilih != null); }
  if (berubah) S.view = { x: 0, y: 0, z: 1 };
  const b = document.getElementById('sna-penuh');
  b.innerHTML = on ? '<svg class="ik"><use href="#ik-penuh-keluar"/></svg><span>Keluar layar penuh</span>'
    : '<svg class="ik"><use href="#ik-penuh"/></svg><span>Layar penuh</span>';
  requestAnimationFrame(() => requestAnimationFrame(snaGambar));
}

function snaPasang() {
  const c = document.getElementById('graf');
  if (!c) return;
  const tip = document.getElementById('sna-tip');
  let seret = false, geser = false, ax = 0, ay = 0;
  c.onmousedown = e => { seret = true; geser = false; ax = e.offsetX; ay = e.offsetY; };
  window.addEventListener('mouseup', () => { seret = false; });
  c.onmousemove = e => {
    if (seret) {
      if (Math.abs(e.offsetX - ax) + Math.abs(e.offsetY - ay) > 2) geser = true;
      S.view.x += e.offsetX - ax; S.view.y += e.offsetY - ay;
      ax = e.offsetX; ay = e.offsetY; tip.style.display = 'none'; snaGambar(); return;
    }
    if (!S.g) return;
    const n = snaCariSimpul(e.offsetX, e.offsetY);
    if (!n) { tip.style.display = 'none'; c.style.cursor = 'grab'; return; }
    c.style.cursor = 'pointer';
    tip.style.display = 'block';
    tip.style.left = Math.min(e.offsetX + 14, c.clientWidth - 230) + 'px'; tip.style.top = (e.offsetY + 10) + 'px';
    tip.innerHTML = n.grp === 'berita'
      ? `<b>${SNA_PLAT[n.p]} ${aman(n.l)}</b><br>${n.p === 'media' ? `menyebut ${angka(n.o)} kali` : `disebut ${angka(n.i)} kali`} · berita`
      : `<b>${SNA_PLAT[n.p] || ''} ${aman(n.l)}</b><br>${angka(n.i)} masuk · ${angka(n.o)} keluar<br>
        <span style="color:${SNA_SENT[n.s]}">${n.s}</span> ·
        <span style="color:${SNA_EMO[n.e]}">${SNA_EMO_NAMA[n.e]}</span> · ${snaLabelK(n)}`;
  };
  c.onmouseleave = () => { tip.style.display = 'none'; };
  c.onwheel = e => { e.preventDefault(); snaZoom(e.deltaY < 0 ? 1.15 : 0.87, e.offsetX, e.offsetY); };
  c.onclick = e => {
    if (geser || !S.g) return;
    const n = snaCariSimpul(e.offsetX, e.offsetY);
    snaPilih(n ? n.idx : null);
  };
  document.getElementById('sna-zoom-masuk').onclick = () => snaZoom(1.35);
  document.getElementById('sna-zoom-keluar').onclick = () => snaZoom(0.74);
  document.getElementById('sna-zoom-pas').onclick = () => {
    if (S.g && S.g.cocokN && S.g.cocokN.size) snaPasKe(S.g.cocokN);
    else { S.view = { x: 0, y: 0, z: 1 }; snaGambar(); }
  };
  document.getElementById('sna-reset').onclick = () => {
    S.view = { x: 0, y: 0, z: 1 }; S.pilih = null; S.sorotK = null;
    document.querySelectorAll('.kk').forEach(d => d.classList.remove('aktif'));
    snaDetail(); snaGambar();
  };
  document.getElementById('sna-label').oninput = snaGambar;
  document.getElementById('sna-tagklaster').onchange = snaGambar;
  document.querySelectorAll('#sna-tab button').forEach(b => b.onclick = () => {
    S.mode = b.dataset.mode;
    document.querySelectorAll('#sna-tab button').forEach(x => x.classList.toggle('aktif', x === b));
    snaLegenda(); snaTemuan(); snaInsight(); snaIsiTop(); snaGambar();
  });
  document.getElementById('sna-penuh').onclick = snaLayarPenuh;
  document.getElementById('sna-tgl-saring').onclick = () => snaWidget('saring');
  document.getElementById('sna-tgl-info').onclick = () => snaWidget('info');
  document.getElementById('sna-layar').addEventListener('click', e => {
    const t = e.target.closest('[data-tutup]');
    if (t) snaWidget(t.dataset.tutup, false);
  });
  const ubah = () => snaSetPenuh(snaPenuhAktif());
  document.addEventListener('fullscreenchange', ubah);
  document.addEventListener('webkitfullscreenchange', ubah);
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && document.getElementById('sna-layar').classList.contains('penuh') && !snaPenuhAktif()
        && !e.target.closest('input')) snaSetPenuh(false);
  });
  snaPasangFilter();
  let t = null;
  window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(snaGambar, 120); });
}

function snaSegarkan() {
  snaSiapkan(); snaLegenda(); snaTemuan(); snaInsight(); snaRingkas(); snaKesimpulan(); snaHasil(); snaGambar();
}

async function muatSNA() {
  if (!S.data) {
    const r = await fetch(api('/api/sna') + snaRentang());
    S.data = await r.json();
    const dibuat = document.getElementById('sna-dibuat');
    if (dibuat && S.data.dibuat) dibuat.textContent = 'diperbarui ' + S.data.dibuat;
    snaGabung();
    snaBangunKontrol();
  }
  // filter platform di bilah atas ikut menyetel sumber peta (hanya saat berubah,
  // agar pilihan di panel peta tidak ditimpa setiap kali filter lain berganti)
  const platform = (document.getElementById('f-platform') || {}).value || 'semua';
  if (platform !== S.platGlobal) {
    S.platGlobal = platform;
    S.f.plat = SNA_FILTER[platform] ? new Set([SNA_FILTER[platform]]) : new Set(SNA_SOSIAL);
    S.view = { x: 0, y: 0, z: 1 };
    snaSinkronKontrol();
  }
  snaSegarkan();
}

snaPasang();
