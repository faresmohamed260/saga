@echo off
setlocal
set "ROOT=%~dp0..\.."
pushd "%ROOT%" >nul

if not exist "venv\Scripts\python.exe" (
  echo Missing venv\Scripts\python.exe
  popd >nul
  exit /b 1
)

set "SAGA_DASHBOARD_NO_BROWSER=1"
if not defined SAGA_DASHBOARD_HOST set "SAGA_DASHBOARD_HOST=127.0.0.1"
if not defined SAGA_DASHBOARD_PORT set "SAGA_DASHBOARD_PORT=8675"
if not defined SAGA_DASHBOARD_LOG_LEVEL set "SAGA_DASHBOARD_LOG_LEVEL=info"

"venv\Scripts\python.exe" -m dashboard_runtime.app
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
exit /b %EXIT_CODE%
