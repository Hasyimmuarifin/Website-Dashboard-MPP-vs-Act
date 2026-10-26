# Dashboard MPP vs MP Actual Sales — Nasmoco HCM

Dashboard web internal dengan **Python + Streamlit + Plotly**, tanpa lisensi berbayar.

## Lokasi target di Windows

`E:\Nasmoco\2. RECRUITMENT\1. HR End-to-End Recruitment Process\Dashboard MPP vs Actual`

File sumber yang dibaca (tanpa diubah):

`E:\Nasmoco\2. RECRUITMENT\1. HR End-to-End Recruitment Process\Dashboard MPP vs Actual\Excell\Sales.xls`

Nama sheet: `template bider (okt)`.

## Langkah pertama

1. Ekstrak seluruh isi ZIP ke **folder target di atas**; jangan membuat folder `Dashboard MPP vs Actual` ganda.
2. Buat folder `Excell` (sudah disediakan) lalu salin file asli `Sales.xls` ke dalamnya.
3. Pasang Python 3.11–3.13 bila belum tersedia, dengan opsi **Add python.exe to PATH**.
4. Klik dua kali `JALANKAN_DASHBOARD.bat`. Proses pertama membutuhkan internet untuk memasang package gratis.
5. Di browser, buka **http://localhost:8501**. Biarkan jendela terminal hidup selama dashboard dipakai.
6. Ubah angka di Excel, **Save (Ctrl+S)**; dashboard akan membaca ulang saat terdeteksi waktu modifikasi file berubah (polling 10 detik). Pastikan Excel menghitung rumus otomatis.

Alternatif terminal:

```powershell
cd 'E:\Nasmoco\2. RECRUITMENT\1. HR End-to-End Recruitment Process\Dashboard MPP vs Actual'
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Logika bisnis

- Kolom **C**: Cabang.
- Kolom **K**: MPP Total = **L (Reguler)** + **M (Mitra)**.
- Kolom **P**: MP Actual Total = **Q (Reguler)** + **R (Mitra)**.
- Gap = Actual − MPP; negatif = kekurangan.
- Pemenuhan = Actual / MPP × 100%, jika MPP lebih dari 0.
- Pembacaan menggunakan **nama cabang yang sudah didaftarkan**, sehingga baris subtotal Area 1–3 dan Grand Total tidak dihitung ganda.
- Area 1 (8 cabang): Kaligawe, Pemuda, Gombel, Majapahit, Siliwangi, Pati, Demak, Karangjati.
- Area 2 (7 cabang): Bantul, Janti, Mlati, Purwokerto, Magelang, Cilacap, Wonosobo.
- Area 3 (7 cabang): Solo Baru, Slamet Riyadi, Ring Road, Pekalongan, Tegal, Klaten, Salatiga.

## Penting

- Streamlit refresh **setelah workbook disimpan ke disk**, bukan saat perubahan sel belum disimpan.
- File `.xls` menyimpan hasil formula terakhir yang dihitung Excel. Untuk rumus, pastikan kalkulasi Excel otomatis dan file telah disimpan. Saat workbook sedang disimpan, dashboard dapat menampilkan pesan error sesaat; pembacaan berikutnya akan mencoba lagi.
- Dashboard untuk penggunaan pribadi / lokal pada tahap ini, belum ada sistem autentikasi; **jangan ekspos ke Internet publik**.
- Untuk migrasi Google Sheets nantinya, gunakan adapter baru untuk mengganti fungsi `load_sales` saja, tanpa harus mengubah desain grafik.
- Jika file lebih besar atau banyak pengguna, pertimbangkan cache / staging data tersendiri.
- Untuk mengubah letak sumber, atur environment variable `SALES_EXCEL_PATH`.
- Karena sumber asli besar dan privat, **Sales.xls sengaja tidak dikemas** bersama source code project.

## Struktur proyek

```text
Dashboard MPP vs Actual/
  app.py
  data_loader.py
  requirements.txt
  JALANKAN_DASHBOARD.bat
  README.md
  Excell/
    Sales.xls               <-- pengguna menyalin file sendiri
```
