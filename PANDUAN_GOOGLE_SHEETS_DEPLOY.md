# Google Sheets dan deploy gratis

Dashboard tetap menggunakan Python + Streamlit + Plotly. Excel lokal masih tersedia sebagai alternatif. Setelah konfigurasi Google Sheets diisi, sumber awal dashboard otomatis menjadi **Google Sheets**.

## 1. Siapkan spreadsheet kolaborasi

1. Upload `Sales.xls` atau `.xlsx` ke Google Drive.
2. Buka dengan Google Sheets, kemudian pilih **File > Save as Google Sheets / Simpan sebagai Google Spreadsheet**. Upload Excel saja belum cukup: gunakan dokumen hasil konversi, bukan file Excel yang masih berada dalam mode Office.
3. Pastikan tab `template bider (okt)` tersedia. Jika namanya berbeda, isi `worksheet` di konfigurasi sesuai nama tab sebenarnya.
4. Pertahankan kolom **C** (Cabang), **K/L/M** (MPP Total/Reguler/Mitra), **P/Q/R** (Actual Total/Reguler/Mitra). Jangan sisipkan atau pindahkan kolom tersebut tanpa menyesuaikan adapter.
5. Bagikan dokumen kepada rekan yang mengerjakan data sebagai **Editor**. Selanjutnya lakukan pembaruan bersama pada dokumen Google Sheets yang sama.
6. Salin URL dokumen hasil konversi. ID terletak di antara `/d/` dan `/edit`, misalnya `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`. Konfigurasi menerima URL lengkap maupun ID saja.

Mengubah Excel asli di komputer tidak otomatis mengubah dokumen hasil konversi. Setelah migrasi, Google Sheets menjadi sumber kerja bersama. Jika membuat dokumen baru dari upload ulang, ID berubah dan perlu diperbarui di Secrets. Jika mengimpor ke dokumen yang sama, pastikan nama tab dan posisi kolom tetap sesuai.

## 2. Aktifkan Google Sheets API

1. Buka [Google Cloud Console](https://console.cloud.google.com/) dan buat/pilih project.
2. Buka **APIs & Services > Library**, cari **Google Sheets API**, lalu klik **Enable**.
3. Buka **IAM & Admin > Service Accounts > Create service account**. Contoh nama: `dashboard-mpp-reader`. Untuk membaca spreadsheet yang dibagikan langsung, tidak perlu memberi role project seperti Owner/Editor dan tidak perlu domain-wide delegation.
4. Pada service account, buka **Keys > Add key > Create new key > JSON**. Simpan JSON asli di tempat privat di luar repository proyek. Jika organisasi melarang pembuatan key atau berbagi ke service account, minta administrator menyiapkan akses yang diizinkan.
5. Salin `client_email` dari JSON. Pada Google Sheets, klik **Share / Bagikan**, tambahkan alamat tersebut sebagai **Viewer**. Hak Editor hanya diperlukan oleh rekan yang mengubah data.

Dashboard hanya meminta scope `spreadsheets.readonly` dan hanya memanggil API pembacaan. Tidak perlu Publish to web, API key publik, Google Drive API, atau membuat dokumen dapat diakses siapa pun.

Referensi: [kredensial service account](https://developers.google.com/workspace/guides/create-credentials), [pembacaan nilai Sheets API](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/get).

## 3. Hubungkan dashboard lokal

1. Salin `.streamlit/secrets.example.toml` menjadi `.streamlit/secrets.toml`.
2. Isi `spreadsheet_id` dan `worksheet` pada `[google_sheets]`.
3. Isi `[gcp_service_account]` dengan nilai dari JSON pada langkah sebelumnya. Gunakan `private_key` lengkap, termasuk baris BEGIN dan END. Pada contoh TOML, private key memakai blok multiline dengan baris baru asli; baris baru asli dianjurkan. Adapter juga otomatis merapikan escape `\n`, escape ganda, dan baris PEM yang menyatu saat disalin, tanpa mengubah isi key. Jangan tempel keseluruhan JSON sebagai TOML.
4. Klik `JALANKAN_DASHBOARD.bat`; launcher memasang dependency dari `requirements.txt`.
5. Buka `http://localhost:8501`. Sumber awal akan menjadi **Google Sheets**. Jika dashboard sudah berjalan saat Secrets dibuat/diubah, hentikan lalu jalankan ulang.

Alternatif terminal dari folder proyek:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

`secrets.toml`, private key, JSON kredensial, dan workbook sumber tidak boleh diunggah ke GitHub. `.gitignore` sudah mengecualikan Secrets, workbook di `Excell/`, dan beberapa pola nama kredensial; tetap simpan JSON unduhan Google di luar repository karena nama otomatisnya dapat berbeda.

## 4. Cara pembaruan otomatis bekerja

```text
Rekan mengedit Google Sheets
          ↓ perubahan tersimpan dan formula dihitung Google
Google Sheets API (akses baca saja)
          ↓ polling dashboard dan cache bersama 5 detik
KPI, grafik, tabel, dan unduhan CSV mengikuti data
```

- Interval tercepat sekaligus default **5 detik**, dapat diubah menjadi 10, 15, 30, atau 60 detik dari sidebar. Ini pembaruan mendekati real time melalui polling, bukan push langsung setiap ketikan.
- Pembacaan API disimpan pada cache memori bersama selama 5 detik untuk mengurangi permintaan dari banyak pengunjung. Dalam kondisi normal dengan interval default, perubahan umumnya terlihat dalam sekitar **5–10 detik**, ditambah waktu koneksi/perhitungan Google. Angka ini bukan jaminan latensi.
- Hanya satu rentang `'<nama tab>'!C:R` dibaca per pengambilan. Nilai formula dibaca sebagai hasil angka tanpa format tampilan agar locale Indonesia tidak mengubah interpretasi angka.
- **Sinkronkan sekarang** melewati cache sumber saat ini dan segera meminta pembacaan baru. Hindari menekannya berulang kali bersamaan dari banyak browser.
- Waktu yang ditampilkan adalah **waktu pembacaan data oleh dashboard (WIB)**, bukan waktu edit terakhir Google Sheets. Waktu cache tetap ditampilkan apa adanya.
- Jika gagal, dashboard menampilkan peringatan dan mempertahankan data sukses terakhir untuk sumber yang sama dalam sesi browser. Pembacaan dicoba lagi dengan jeda 10, 20, 40, hingga 60 detik, mengikuti interval pemeriksaan. Jika sesi baru belum pernah berhasil membaca, grafik belum ditampilkan.
- Saat kembali ke sumber lain atau konfigurasi berubah, data lama tidak dipakai sebagai data sumber baru.
- Polling berlangsung selama dashboard terbuka dan sesi aktif. Tidak ada proses latar yang wajib berjalan ketika semua pengunjung menutup dashboard. Saat dibuka kembali, dashboard mengambil data terbaru.

Penggunaan standar Sheets API tersedia tanpa biaya tambahan dengan kuota. Dokumentasi saat diperiksa mencantumkan 60 pembacaan/menit/pengguna/project dan 300/menit/project; service account dihitung sebagai satu akun. Satu sumber pada satu proses aplikasi dengan cache 5 detik memakai sekitar 12 pembacaan/menit saat aktif, di luar sinkronisasi manual dan kegagalan. Proses/replika hosting lain memiliki cache masing-masing. Lihat [kuota dan ketentuan biaya terbaru](https://developers.google.com/workspace/sheets/api/limits).

## 5. Deploy gratis dengan Streamlit Community Cloud

Pilihan yang sesuai untuk proyek ini adalah **Streamlit Community Cloud**: hosting gratis, terhubung ke GitHub, dan memperoleh subdomain `*.streamlit.app`. Anda tidak perlu membeli domain. Lihat [dokumentasi Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud).

1. Buat repository **private** di GitHub, misalnya `dashboard-mpp-sales`.
2. Upload kode proyek dengan struktur folder tetap terjaga:

   ```text
   app.py
   data_loader.py
   google_sheets_loader.py
   requirements.txt
   .gitignore
   .streamlit/
     secrets.example.toml  # contoh kosong, bukan secrets.toml asli
   ```

   README, panduan, dan folder `tests` boleh disertakan. Jangan upload `.venv`, Excel sumber, atau kredensial. Mode Google Sheets tidak membutuhkan file `Sales.xls` di server.

3. Login ke [share.streamlit.io](https://share.streamlit.io/) menggunakan GitHub. Berikan akses ke repository private yang dipilih.
4. Klik **Create app**, pilih repository, branch yang berisi kode (umumnya `main`), dan **Main file path: `app.py`**.
5. Pilih subdomain yang masih tersedia. Contoh nama: `nasmoco-mpp-sales`; alamat akan mengikuti pola `https://<subdomain>.streamlit.app` (contoh, belum diterbitkan).
6. Buka **Advanced settings**, pilih **Python 3.12**, lalu isi **Secrets** dengan isi `.streamlit/secrets.toml` yang sudah lengkap. Simpan Secrets di pengaturan hosting, bukan dalam source code GitHub.
7. Klik **Deploy**. Tunggu instalasi dan startup selesai.
8. Untuk berbagi dashboard internal, pastikan pengaturan sharing aplikasi **private**, tambahkan email rekan sebagai **viewer**, lalu bagikan URL. Repository private dan akses dokumen Google tidak menggantikan pengaturan akses dashboard. Viewer dashboard dapat melihat data yang diambil service account meski tidak memiliki akses langsung ke spreadsheet.
9. Uji dari browser lain: login sebagai viewer, ubah angka Actual di Google Sheets, tunggu pembaruan, lalu pastikan grafik dan KPI berubah. Laptop lokal tidak perlu menyala setelah aplikasi berjalan di cloud.

Perubahan kode berikutnya diunggah ke branch GitHub yang sama. Perubahan data cukup dilakukan di Google Sheets, tanpa deploy ulang. Untuk mengganti dokumen/tab atau service account, perbarui Secrets hosting dan reboot aplikasi jika diperlukan.

Panduan resmi: [deploy, subdomain dan Secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [akses private dan viewer](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app).

### Batas hosting gratis

Community Cloud menidurkan aplikasi setelah **12 jam tanpa trafik**. Pengunjung yang memiliki akses dapat membangunkannya lagi. Saat tidur, dashboard tidak melakukan polling; data akan dibaca ketika aplikasi aktif kembali. Hosting gratis ini sesuai untuk dashboard kolaborasi yang dibuka saat dibutuhkan, dengan batas sumber daya bersama. Lihat [hibernasi aplikasi](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app).

## 6. Pemeriksaan jika gagal

| Gejala | Yang diperiksa |
| --- | --- |
| Spreadsheet ID belum diisi | Isi `[google_sheets]` di Secrets lokal/hosting, bukan hanya file contoh. |
| 400 / tab tidak valid | Dokumen sudah dikonversi ke Google Sheets; nama tab dan kapital/spasi sesuai. |
| 403 | Sheets API aktif pada project service account; dokumen dibagikan ke `client_email` sebagai Viewer; kebijakan organisasi mengizinkan akses tersebut. |
| 404 | ID berasal dari dokumen hasil konversi; service account memiliki akses. |
| Kredensial tidak valid | Private key harus lengkap dari JSON service account. Format baris dirapikan otomatis; pesan sekarang membedakan field kosong, nilai contoh, format PEM tidak lengkap, dan isi key rusak. |
| 429 | Tunggu percobaan ulang otomatis; kurangi sinkronisasi manual atau tambah interval. |
| Data kosong / cabang tidak dikenali | Kolom C masih berisi nama cabang yang didaftarkan, tidak bergeser. |
| Angka belum mengikuti Excel lokal | Edit dokumen Google Sheets yang terhubung; Excel lokal dan dokumen hasil konversi tidak disinkronkan oleh aplikasi. |
| Total berbeda dengan Reguler + Mitra | Periksa formula hasil konversi dan buka bagian Validasi dan kualitas data di dashboard. |
| Halaman tidur | Buka URL lalu pilih tombol untuk membangunkan aplikasi. |

## 7. Verifikasi kode

Dari folder proyek:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Pengujian memakai data buatan dan mock API, sehingga tidak memerlukan private key atau akses spreadsheet sungguhan. Pengujian koneksi akhir tetap dilakukan setelah Spreadsheet ID dan Secrets asli tersedia.
