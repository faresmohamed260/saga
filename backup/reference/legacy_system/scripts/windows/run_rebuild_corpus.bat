@echo off
setlocal
set "ROOT=%~dp0..\.."
pushd "%ROOT%" >nul

if not exist "venv\Scripts\python.exe" (
  echo Missing venv\Scripts\python.exe
  echo Create the virtual environment and install dependencies first.
  popd >nul
  exit /b 1
)

venv\Scripts\python.exe saga_tools.py rebuild-corpus %*
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
exit /b %EXIT_CODE%
