# Excel masing-masing pengguna pada satu website

## Website online bersama: koneksi otomatis dari browser

1. Buka website menggunakan **Chrome atau Microsoft Edge desktop**, melalui alamat **HTTPS**. `localhost` juga didukung untuk pengujian lokal.
2. Pilih **Sumber data > Excel lokal**.
3. Pilih **Dari browser (otomatis)**.
4. Isi **Nama sheet Excel**. Nama bawaan adalah `template bider (okt)`; ganti sesuai tab workbook Anda.
5. Klik **Hubungkan Excel dari perangkat**, lalu pilih satu file `.xls` atau `.xlsx` melalui dialog browser. Ukuran maksimum **20 MB**.
6. Setelah file dibaca, angka KPI, grafik, tabel, dan CSV mengikuti workbook tersebut.
7. Edit file menggunakan Excel, lalu **Save / Ctrl+S**. Selama halaman tetap terbuka dan izin file tersedia, browser memeriksa file setiap **5 detik** secara default. Interval mengikuti pengaturan **Pembaruan & sumber**.
8. Klik **Putuskan koneksi** untuk menghentikan pemantauan dan menghapus file aktif dari tampilan sesi. Pilih file kembali setelah refresh halaman atau browser ditutup.

Satu website dapat dibuka banyak orang: pengguna A memilih workbook A dan pengguna B memilih workbook B. File browser, path aktif, hasil parsing/cache Excel, dan pilihan filter disimpan per sesi; tidak dijadikan sumber bersama untuk pengunjung lain. Isi workbook dikirim ke backend website untuk perhitungan dashboard dalam sesi tersebut, sehingga pengelola hosting tetap bertanggung jawab atas server pemroses data. Aplikasi tidak mengubah workbook asli dan tidak menyimpan unggahan ke berkas permanen server.

Browser membaca ulang file hanya ketika metadata file berubah atau sinkronisasi manual diminta. Tab di latar belakang dapat mengalami pembatasan timer oleh browser. Waktu pembaruan mencakup penyimpanan file, pengiriman, dan pengolahan; interval 5 detik bukan jaminan latensi tepat 5 detik.

Jika Excel menyimpan file ketika sedang dibaca, data terakhir tetap ditampilkan dengan peringatan. Jika izin dicabut, file diganti nama/dipindahkan, atau handle file tidak lagi valid setelah penyimpanan, hubungkan file kembali.

### Mengapa tidak cukup menempelkan path laptop?

Path `C:\Users\Nama\Documents\Sales.xlsx` yang diketik ke website online adalah teks. Server hosting tidak memiliki disk C: laptop Anda. Browser juga tidak dapat mengubah path teks menjadi izin membaca file; pengguna harus memilih file melalui dialog. Koneksi otomatis menggunakan izin baca atas file yang dipilih itu saja, tanpa meminta akses seluruh folder atau disk.

Referensi: [arsitektur client-server Streamlit](https://docs.streamlit.io/develop/concepts/architecture/architecture), [pemilih file browser](https://developer.mozilla.org/en-US/docs/Web/API/Window/showOpenFilePicker).

## Alternatif: unggah satu salinan Excel

Pilih **Sumber data > Unggah Excel**, isi nama sheet, lalu pilih workbook. Cara ini tersedia untuk browser yang tidak mendukung koneksi file otomatis. Unggahan adalah snapshot: jika workbook di laptop berubah, unggah ulang. File tidak berubah otomatis hanya karena file aslinya disimpan.

## Dashboard lokal: tempel path dari Explorer

Jika dashboard dijalankan pada laptop yang sama dengan workbook:

1. Jalankan `JALANKAN_DASHBOARD.bat` dan buka `http://localhost:8501`.
2. Di Windows Explorer, **Shift + klik kanan** workbook > **Salin sebagai jalur / Copy as path**.
3. Pilih **Excel lokal > Tempel path (server lokal)**.
4. Tempel ke **Path file Excel**, termasuk tanda kutip jika ada. Klik **Hubungkan path**.
5. Isi nama sheet sesuai workbook, lalu simpan setiap perubahan Excel. Dashboard membaca perubahan waktu modifikasi/ukuran file setiap interval pembaruan.

Path yang dipilih pengguna tidak perlu dipindahkan ke folder proyek atau diubah menjadi `Sales.xls`. Gunakan path lengkap ke berkas `.xls`/`.xlsx`, bukan folder atau shortcut.

Launcher lokal mengaktifkan `DASHBOARD_ALLOW_LOCAL_PATHS=1` dan menjalankan server pada `localhost`. Input path juga tersedia pada server yang secara eksplisit mengikat alamat loopback. **Jangan mengaktifkan flag tersebut pada website online bersama.** Pada hosting biasa fitur path server dinonaktifkan; gunakan koneksi browser agar setiap orang membaca file laptopnya sendiri.

## Format workbook

Semua metode memakai format data yang sama: **C = Cabang**, **K/L/M = MPP Total/Reguler/Mitra**, **P/Q/R = Actual Total/Reguler/Mitra**. Cabang di luar daftar 22 cabang tidak dihitung. Untuk rumus Excel, hasil terakhir harus sudah dihitung dan disimpan oleh Excel; aplikasi membaca nilainya dan tidak menghitung ulang rumus workbook.

## File yang perlu ikut diperbarui di hosting

Selain `app.py`, `data_loader.py`, dan konfigurasi tema, sertakan **`browser_excel.py`**, **`excel_sources.py`**, **`table_styles.py`**, **`dashboard.css`**, serta **`Assets/Logo-Nasmoco.png`**. Pertahankan Secrets Google Sheets di pengaturan hosting. Tidak ada private key, workbook pribadi, atau folder `.venv` yang perlu diunggah ke repository.
