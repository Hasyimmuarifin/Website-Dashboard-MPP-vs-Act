# Dashboard MPP vs MP Actual Sales — Nasmoco HCM

Dashboard Python + Streamlit + Plotly untuk memantau kebutuhan dan realisasi tenaga Sales di 22 cabang.

## Sumber data

- **Google Sheets:** kolaborasi pada spreadsheet privat; KPI, grafik, tabel, dan CSV mengikuti perubahan melalui Sheets API. Polling default 5 detik, cache bersama 5 detik, waktu sinkronisasi WIB, tombol sinkronisasi manual, dan data terakhir tetap terlihat saat koneksi gagal.
- **Excel lokal:** membaca `Excell/Sales.xls` setelah disimpan; sumber tidak pernah diubah oleh dashboard. Letak alternatif dapat diatur melalui `SALES_EXCEL_PATH`.

Untuk menghubungkan Google Sheets dan menerbitkan dashboard gratis tanpa domain, ikuti **[PANDUAN_GOOGLE_SHEETS_DEPLOY.md](PANDUAN_GOOGLE_SHEETS_DEPLOY.md)**. Contoh konfigurasi tersedia di **[.streamlit/secrets.example.toml](.streamlit/secrets.example.toml)**.

## Jalankan lokal

1. Pasang Python 3.11–3.13 dengan opsi Add Python to PATH.
2. Untuk Excel lokal, letakkan `Sales.xls` di folder `Excell` dalam proyek ini. Untuk Google Sheets, isi `.streamlit/secrets.toml` sesuai panduan.
3. Klik dua kali `JALANKAN_DASHBOARD.bat`. Instalasi pertama membutuhkan internet.
4. Buka `http://localhost:8501` dan biarkan terminal berjalan.
5. Pilih sumber data, jenis Sales, area, dan interval pembaruan di sidebar. Jika konfigurasi spreadsheet sudah diisi, Google Sheets dipilih otomatis.

Alternatif terminal dari folder proyek:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Logika bisnis

- Nama tab bawaan: `template bider (okt)`; dapat dikonfigurasi untuk Google Sheets.
- **C:** Cabang; **K/L/M:** MPP Total/Reguler/Mitra; **P/Q/R:** Actual Total/Reguler/Mitra.
- Gap = Actual − MPP. Pemenuhan = Actual / MPP × 100% jika MPP tidak nol.
- Hanya nama cabang terdaftar yang dihitung; subtotal area dan Grand Total tidak dihitung ganda. Cabang duplikat ditolak; cabang hilang, angka tidak valid, dan total yang berbeda dari Reguler + Mitra ditampilkan dalam validasi.
- Area 1: Kaligawe, Pemuda, Gombel, Majapahit, Siliwangi, Pati, Demak, Karangjati.
- Area 2: Bantul, Janti, Mlati, Purwokerto, Magelang, Cilacap, Wonosobo.
- Area 3: Solo Baru, Slamet Riyadi, Ring Road, Pekalongan, Tegal, Klaten, Salatiga.

Google Sheets dibaca sebagai hasil angka/formula melalui `UNFORMATTED_VALUE`, tanpa mengandalkan pemisah ribuan tampilan. Excel dibaca dari hasil formula terakhir yang disimpan; aktifkan kalkulasi otomatis dan simpan workbook.

## Deploy gratis

Gunakan **Streamlit Community Cloud**, repository GitHub private, entry point `app.py`, Python 3.12, dan Secrets pada pengaturan hosting. Alamat tersedia sebagai `https://<subdomain>.streamlit.app`. Detail langkah, akses viewer, dan batas hibernasi dijelaskan di panduan. Hosting belum diterbitkan oleh perubahan kode ini.

## Tampilan dashboard

- Pilih **Light / Dark / System** melalui menu kanan atas. Tema utama, sidebar, dropdown, tabel, dan teks grafik mengikuti pilihan tersebut.
- Empat KPI menggunakan tinggi yang sama, 136 px, dengan grid 4, 2, atau 1 kolom sesuai lebar area dashboard, termasuk ketika sidebar terbuka.
- Judul dan status sinkronisasi diringkas. Interval dan informasi sumber tersedia di **Pembaruan & sumber** pada sidebar; waktu pembacaan lengkap tersedia di **Validasi dan kualitas data**.
- Pembacaan Google Sheets berkala menggunakan cache yang diperbarui di latar belakang setelah data pertama dimuat. Sinkronisasi manual tetap membaca ulang langsung.
- Sertakan `dashboard.css` dan `.streamlit/config.toml` ketika memperbarui kode hosting. File CSS hanya mengatur grid KPI; warna diatur oleh tema native Streamlit.

## Verifikasi

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Pengujian menggunakan data buatan dan mock API. Koneksi Google asli perlu diuji setelah spreadsheet dan kredensial tersedia.

## Struktur proyek

```text
app.py                           # UI, cache, refresh, status sinkronisasi
dashboard.css                    # grid KPI responsif, tanpa override warna
data_loader.py                   # adapter Excel, parser bersama, agregasi
google_sheets_loader.py           # adapter Sheets API, service account read-only
requirements.txt
JALANKAN_DASHBOARD.bat
PANDUAN_GOOGLE_SHEETS_DEPLOY.md
.streamlit/secrets.example.toml   # contoh konfigurasi
.streamlit/config.toml            # tema terang/gelap dan sidebar
.streamlit/secrets.toml           # lokal saja, tidak masuk Git
tests/
Excell/Sales.xls                  # sumber privat, tidak masuk Git
```
