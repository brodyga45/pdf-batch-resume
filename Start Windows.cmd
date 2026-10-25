@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run Setup Windows.cmd in this extracted folder.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -c "import tkinter, pypdf, PIL" >nul 2>nul
if errorlevel 1 (
  echo Required packages or Tcl/Tk are missing. Run Setup Windows.cmd and check its result.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" pdfbatch_gui.py
if errorlevel 1 pause
