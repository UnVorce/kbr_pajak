# tests/fixtures

Folder untuk sampel nyata (HTML/teks) dari sumber peraturan.

Diisi pada **Fase 1** saat inspeksi struktur halaman `peraturan.bpk.go.id`,
`jdih.kemenkeu.go.id`, dan portal DJP (spec Bagian 0 aturan 2: jangan menulis
parser berdasarkan asumsi). Pada Fase 3 ditambah fixture teks dari tiap jenis
dokumen untuk parser pasal/ayat (S4).

Konvensi penamaan (usulan):
- `<sumber>__<document_id>__metadata.html`   (contoh: bpk__UU-1983-7__metadata.html)
- `<sumber>__<document_id>__detail.html`
- `<sumber>__<document_id>.txt`              (teks bersih untuk tes parser)

Sampel harus dari sumber asli yang sah; jangan memuat data pribadi.
