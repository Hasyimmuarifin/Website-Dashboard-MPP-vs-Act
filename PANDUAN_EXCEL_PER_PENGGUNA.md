# Unggah Excel untuk masing-masing pengguna

1. Buka dashboard, lalu pilih **Sumber data > Unggah Excel** (pilihan awal).
2. Isi **Nama sheet Excel** sesuai nama tab workbook. Bawaan: `template bider (okt)`.
3. Pada **Pilih file Excel**, unggah satu file `.xls` atau `.xlsx`, maksimum **20 MB**.
4. KPI, grafik, tabel, dan CSV akan mengikuti workbook tersebut. Gunakan filter **Jenis sales** dan **Area** sesuai kebutuhan.
5. Setelah mengedit workbook di Excel, simpan lalu **unggah ulang** agar dashboard membaca perubahan.
6. Hapus file dari pengunggah untuk mengosongkan data sesi, atau unggah workbook lain untuk mengganti sumber.

Unggahan adalah snapshot per sesi. Pengguna A dapat mengunggah workbook A dan pengguna B workbook B; hasil tidak dijadikan sumber bersama. File diproses di server, tanpa mengubah workbook asli atau menyimpan unggahan ke berkas permanen. Tombol **Sinkronkan** membaca ulang salinan yang sudah diunggah, bukan file terbaru di laptop.

Untuk pembaruan otomatis pada sumber bersama, pilih **Google Sheets** dan ikuti [panduan Google Sheets](PANDUAN_GOOGLE_SHEETS_DEPLOY.md).

## Format workbook

**C = Cabang**, **K/L/M = MPP Total/Reguler/Mitra**, **P/Q/R = Actual Total/Reguler/Mitra**. Hanya 22 cabang terdaftar yang dihitung. Untuk rumus Excel, hasil terakhir harus sudah dihitung dan disimpan oleh Excel; aplikasi membaca nilainya dan tidak menghitung ulang rumus workbook.

## File hosting

Sertakan `app.py`, `data_loader.py`, `google_sheets_loader.py`, `table_styles.py`, `dashboard.css`, `requirements.txt`, `.streamlit/config.toml`, dan `Assets/Logo-Nasmoco.png`. Pertahankan Secrets Google Sheets di pengaturan hosting. Workbook pribadi, private key, dan `.venv` tidak perlu diunggah ke repository.
