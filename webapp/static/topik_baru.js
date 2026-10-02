/* Wizard topik baru dan ubah konfigurasi topik JSON (lihat topik/_umum.py). */
const TB = window.TOPIK_BARU;
const q = id => document.getElementById(id);
const escTB = t => String(t == null ? '' : t).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

async function mintaTB(url, data) {
  const r = await fetch(url, data === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.galat || `HTTP ${r.status}`);
  return d;
}
function statusTB(id, teks, jenis) { const el = q(id); el.textContent = teks || ''; el.className = 'kel-status' + (jenis ? ' ' + jenis : ''); }
function langkah(n) {
  q('tb-1').hidden = n !== 1; q('tb-2').hidden = n !== 2;
  document.querySelectorAll('#tb-langkah span').forEach(s => s.classList.toggle('aktif', Number(s.dataset.l) === n));
}
const slugDari = nama => {
  let s = nama.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  if (!/^[a-z]/.test(s)) s = 't_' + s;
  return s.slice(0, 30);
};

/* ---------------------------------------------------------------- konversi form <-> konfigurasi */
const baris = v => (v || []).join('\n');
const koma = v => (v || []).join(', ');
const pecahBaris = s => s.split('\n').map(x => x.trim()).filter(Boolean);
const pecahKoma = s => s.split(',').map(x => x.trim()).filter(Boolean);
const DAFTAR = ['kueri_berita', 'kueri_yt', 'kueri_x', 'tagar_ig', 'kueri_threads', 'situs_lokal', 'wajib', 'kecuali', 'stop'];

function isiForm(c) {
  for (const k of ['slug', 'nama', 'judul', 'judul_laporan', 'lede', 'dari']) q('k-' + k).value = c[k] || '';
  q('k-sampai').value = c.sampai || '';
  for (const k of DAFTAR) q('k-' + k).value = baris(c[k]);
  q('k-pasangan').value = (c.pasangan || []).map(p => `${koma(p.jika)} => ${koma(p.dan)}`).join('\n');
  q('k-narasi').value = Object.entries(c.narasi || {}).map(([n, v]) => `${n}: ${koma(v)}`).join('\n');
  q('k-aktor').value = Object.entries(c.aktor || {}).map(([n, v]) => `${n}: ${koma(v)}`).join('\n');
  const a = c.aturan || {};
  for (const k of ['pihak', 'didukung', 'abaikan', 'samarkan']) q('k-' + k).value = koma(a[k]);
  const f = c.fokus || {};
  q('k-fokus_nama').value = f.nama || ''; q('k-fokus_ket').value = f.ket || ''; q('k-fokus_narasi').value = koma(f.narasi);
  q('k-preset').value = (c.preset || []).map(p => `${p.label} | ${p.dari} | ${p.sampai}`).join('\n');
}
function bacaForm() {
  const c = {};
  for (const k of ['slug', 'nama', 'judul', 'judul_laporan', 'lede', 'dari', 'sampai']) c[k] = q('k-' + k).value.trim();
  c.sampai = c.sampai || null;
  for (const k of DAFTAR) c[k] = pecahBaris(q('k-' + k).value);
  c.pasangan = pecahBaris(q('k-pasangan').value).map(b => {
    const [jika, dan] = b.split('=>');
    return { jika: pecahKoma(jika || ''), dan: pecahKoma(dan || '') };
  }).filter(p => p.jika.length && p.dan.length);
  const kamus = s => Object.fromEntries(pecahBaris(s).map(b => {
    const i = b.indexOf(':');
    return i > 0 ? [b.slice(0, i).trim(), pecahKoma(b.slice(i + 1))] : [b.trim(), [b.trim().toLowerCase()]];
  }));
  c.narasi = kamus(q('k-narasi').value);
  c.aktor = kamus(q('k-aktor').value);
  c.aturan = Object.fromEntries(['pihak', 'didukung', 'abaikan', 'samarkan'].map(k => [k, pecahKoma(q('k-' + k).value)]));
  const fn = pecahKoma(q('k-fokus_narasi').value);
  c.fokus = fn.length ? { nama: q('k-fokus_nama').value.trim() || 'Fokus', ket: q('k-fokus_ket').value.trim(), narasi: fn } : null;
  c.preset = pecahBaris(q('k-preset').value).map(b => {
    const [label, dari, sampai] = b.split('|').map(x => (x || '').trim());
    return { label, dari, sampai };
  }).filter(p => p.label && /^\d{4}-\d{2}-\d{2}$/.test(p.dari) && /^\d{4}-\d{2}-\d{2}$/.test(p.sampai));
  return c;
}

/* ---------------------------------------------------------------- langkah 1 */
function brief() {
  return { nama: q('b-nama').value.trim(), deskripsi: q('b-deskripsi').value.trim(), wilayah: q('b-wilayah').value.trim(),
    pihak: q('b-pihak').value.trim(), dari: q('b-dari').value, sampai: q('b-sampai').value, catatan: q('b-catatan').value.trim() };
}
const pctTB = x => `${Math.round((x || 0) * 100)}%`;
function contohUji(judul, daftar, n, ket) {
  if (!daftar || !daftar.length) return '';
  n = Math.max(n || 0, daftar.length);
  return `<details class="tb-contoh"><summary>${escTB(judul)} <span class="kel-redup">(${n} judul${n > daftar.length ? `, ${daftar.length} contoh` : ''})</span></summary>
    <p class="kel-kecil">${escTB(ket)}</p><ul>${daftar.map(t => `<li>${escTB(t)}</li>`).join('')}</ul></details>`;
}
/* Ringkasan uji otomatis dari ai_topik.susun: aturan draf dicocokkan dengan penilaian AI atas judul hasil riset. */
function tampilkanUji(isi) {
  const u = isi && isi.uji;
  q('tb-hasil').hidden = !u;
  if (!u) return;
  const a = u.awal, z = u.akhir, berubah = JSON.stringify(a) !== JSON.stringify(z);
  const nRiset = (isi.riset || []).length;
  q('tb-hasil-ket').textContent = `AI mengumpulkan ${z.dinilai} judul berita dan video dari periode ini, menilai mana yang benar-benar `
    + `membahas topik, lalu mencocokkannya dengan aturan relevansi di bawah. ${z.relevan_ai} dari ${z.dinilai} judul dinilai relevan.`;
  const sel = (nama, ket, k) => `<div><small>${nama}</small><b>${pctTB(z[k])}</b>`
    + `<em>${berubah ? `awal ${pctTB(a[k])} · ` : ''}${ket}</em></div>`;
  q('tb-hasil-isi').innerHTML = `<div class="kel-ringkas">
      ${sel('Ketepatan', 'yang terjaring aturan memang relevan', 'presisi')}
      ${sel('Kelengkapan', 'yang relevan ikut terjaring aturan', 'recall')}
      ${sel('Cakupan isu', 'judul relevan yang tertandai isu', 'cakupan_isu')}
      ${z.jangkauan != null ? sel('Jangkauan kueri', 'judul relevan yang memuat kata salah satu kueri', 'jangkauan') : ''}
    </div>
    ${berubah ? '<p class="kel-kecil">Aturan sudah diperbaiki sekali atau lebih berdasarkan contoh yang meleset. Angka besar adalah hasil akhir.</p>' : ''}
    ${contohUji('Relevan tetapi belum terjaring', z.terlewat, z.n_terlewat, 'Tambahkan istilah wajib atau pasangan bila judul-judul ini memang perlu dihitung.')}
    ${contohUji('Terjaring tetapi bukan topik ini', z.salah_tangkap, z.n_salah_tangkap, 'Tambahkan frasa pengecualian atau persempit istilah yang terlalu umum.')}
    ${(z.isu_terlalu_umum || []).length ? `<details class="tb-contoh" open><summary>Isu yang terlalu umum <span class="kel-redup">(${z.isu_terlalu_umum.length})</span></summary>
      <p class="kel-kecil">Isu ini menandai sebagian besar konten, jadi pembagian isu kurang bermakna. Ganti kata pemicunya dengan frasa yang lebih khas.</p>
      <ul>${z.isu_terlalu_umum.map(u => `<li>${escTB(u.isu)}: ${pctTB(u.porsi)} judul relevan · kata pemicu ${escTB(u.kata.join(', '))}</li>`).join('')}</ul></details>` : ''}
    ${contohUji('Relevan tetapi tidak memuat kata kueri mana pun', z.tak_terjangkau, z.n_tak_terjangkau, 'Perkiraan kasar karena mesin pencari juga membaca isi artikel. Bila banyak, tambahkan kueri yang lebih pendek atau nama lain topik ini.')}
    ${contohUji('Relevan tetapi belum bertanda isu', z.tanpa_isu, z.n_tanpa_isu ?? Math.round(z.relevan_ai * (1 - z.cakupan_isu)), 'Tambahkan kata kunci isu bila judul-judul ini mewakili isu yang ingin dipantau.')}`;
  if (nRiset && !q('tb-uji-teks').value.trim()) q('tb-uji-teks').value = isi.riset.slice(0, 80).map(x => x.judul).join('\n');
}
function keLangkah2(draf, isi) {
  const b = brief();
  const d = draf || {};
  isiForm({ ...d, slug: slugDari(b.nama), nama: b.nama, dari: b.dari, sampai: b.sampai || null,
    judul: d.judul || b.nama, judul_laporan: d.judul_laporan || d.judul || b.nama, lede: d.lede || b.deskripsi });
  tampilkanUji(isi);
  langkah(2);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
if (q('tb-ai')) q('tb-ai').onclick = async () => {
  const b = brief();
  if (!b.nama || !b.deskripsi || !b.dari) { statusTB('tb-status1', 'Isi nama, deskripsi, dan tanggal mulai dulu.', 'galat'); return; }
  q('tb-ai').disabled = true;
  try {
    const r = await mintaTB('/api/kelola/topik/draf', b);
    const mulai = Date.now();
    const tunggu = async () => {
      const d = await mintaTB(`/api/kelola/topik/draf/${r.draf}`);
      if (d.siap) { statusTB('tb-status1', ''); q('tb-ai').disabled = false; keLangkah2(d.isi.draf, d.isi); return; }
      const p = d.pekerjaan;
      if (p && ['gagal', 'batal'].includes(p.status)) {
        statusTB('tb-status1', `Draf gagal dibuat (${p.pesan || p.status}). Coba lagi atau isi manual.`, 'galat');
        q('tb-ai').disabled = false; return;
      }
      const dtk = Math.round((Date.now() - mulai) / 1000);
      const tahap = p && p.status === 'antre' ? 'menunggu antrean AI' : (p && p.baris_akhir ? p.baris_akhir.replace(/^\[[^\]]+\]\s*/, '') : 'memulai');
      statusTB('tb-status1', `AI meriset judul berita dan video, menyusun draf, lalu mengujinya (biasanya 4–8 menit) · `
        + `${Math.floor(dtk / 60)}:${String(dtk % 60).padStart(2, '0')} · ${tahap.slice(0, 90)}`, 'jalan');
      setTimeout(tunggu, 2000);
    };
    tunggu();
  } catch (e) { statusTB('tb-status1', e.message, 'galat'); q('tb-ai').disabled = false; }
};
q('tb-manual').onclick = () => {
  if (!q('b-nama').value.trim() || !q('b-dari').value) { statusTB('tb-status1', 'Isi nama dan tanggal mulai dulu.', 'galat'); return; }
  keLangkah2(null, null);
};
if (q('tb-kembali')) q('tb-kembali').onclick = () => langkah(1);

/* ---------------------------------------------------------------- uji & simpan */
q('tb-uji').onclick = async () => {
  try {
    const d = await mintaTB('/api/kelola/topik/uji', { konfig: bacaForm(), teks: q('tb-uji-teks').value });
    const ya = d.hasil.filter(h => h.relevan).length;
    q('tb-uji-hasil').innerHTML = !d.hasil.length ? '<p class="memuat">Tempel contoh teks dulu.</p>'
      : `<p class="kel-kecil">${ya} dari ${d.hasil.length} contoh dihitung relevan.</p><ul>${d.hasil.map(h =>
        `<li class="${h.relevan ? 'ya' : 'tidak'}">${h.relevan ? '✓' : '✗'} ${escTB(h.teks)}${h.isu.length ? ` <small>· isu: ${escTB(h.isu.join(', '))}</small>` : ''}${h.aktor.length ? ` <small>· aktor: ${escTB(h.aktor.join(', '))}</small>` : ''}</li>`).join('')}</ul>`;
  } catch (e) { q('tb-uji-hasil').innerHTML = `<p class="memuat">${escTB(e.message)}</p>`; }
};
q('tb-simpan').onclick = async () => {
  const c = bacaForm();
  q('tb-simpan').disabled = true;
  try {
    const d = await mintaTB('/api/kelola/topik' + (TB.ubah ? '?ubah=1' : ''), c);
    statusTB('tb-status2', 'Tersimpan. Membuka halaman panen…', 'ok');
    setTimeout(() => { location.href = `/${d.slug}/kelola#panen`; }, 600);
  } catch (e) { statusTB('tb-status2', e.message, 'galat'); q('tb-simpan').disabled = false; }
};

if (q('tb-hapus')) q('tb-hapus').onclick = async () => {
  if (!confirm('Hapus topik ini dari daftar? Konfigurasinya disimpan di data/_bersama/topik_terhapus/, data panennya tidak dihapus.')) return;
  try { const d = await mintaTB(`/api/${TB.ubah}/kelola/hapus-topik`, {}); location.href = `/${d.berikut}/`; }
  catch (e) { statusTB('tb-status2', e.message, 'galat'); }
};

/* ---------------------------------------------------------------- mulai */
if (TB.ubah) {
  langkah(2);
  mintaTB(`/api/${TB.ubah}/kelola/konfigurasi`).then(d => d.konfig && isiForm(d.konfig))
    .catch(e => statusTB('tb-status2', e.message, 'galat'));
} else {
  langkah(1);
  q('b-dari').value = new Date().toISOString().slice(0, 10);
}
