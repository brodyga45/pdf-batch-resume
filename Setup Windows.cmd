@echo off
setlocal
cd /d "%~dp0"
echo PDF Batch Resume - first-time setup
echo This downloads the pinned Python packages from PyPI into this folder's .venv.
echo No PDF files are uploaded. Python 3.10 or newer with Tcl/Tk must already be installed.
where py >nul 2>nul
if errorlevel 1 (
  echo Install Python from https://www.python.org/downloads/windows/ then run this setup again.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Could not create the Python environment. Check your Python installation and folder permissions.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Setup did not finish. Check the message above and your internet connection.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -c "import tkinter, pypdf, PIL"
if errorlevel 1 (
  echo This Python installation needs Tcl/Tk support. Modify the official Python installation to include it.
  pause
  exit /b 1
)
echo Ready. Double-click Start Windows.cmd to choose your folders.
pause
