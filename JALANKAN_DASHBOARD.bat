@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [1/2] Membuat Python virtual environment...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Python belum terinstall / belum masuk PATH.
    pause
    exit /b 1
  )
)
echo [2/2] Memastikan library Python terpasang...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Instalasi library gagal. Cek koneksi Internet.
  pause
  exit /b 1
)
echo Membuka dashboard...
".venv\Scripts\python.exe" -m streamlit run app.py --server.address localhost --server.port 8501
pause
