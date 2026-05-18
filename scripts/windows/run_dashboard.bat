@echo off
setlocal
set "ROOT=%~dp0..\.."
pushd "%ROOT%" >nul

if not exist "venv\Scripts\streamlit.exe" (
  echo Missing venv\Scripts\streamlit.exe
  echo Create the virtual environment and install dependencies first.
  popd >nul
  exit /b 1
)

venv\Scripts\streamlit.exe run story_dashboard.py
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
exit /b %EXIT_CODE%
