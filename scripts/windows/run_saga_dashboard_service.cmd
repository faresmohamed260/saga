@echo off
setlocal
set "ROOT=%~dp0..\.."
pushd "%ROOT%" >nul

if not exist "venv\Scripts\python.exe" (
  echo Missing venv\Scripts\python.exe
  popd >nul
  exit /b 1
)

if not exist "dashboard_app\node_modules" (
  pushd "dashboard_app" >nul
  call npm install
  set "NPM_INSTALL_CODE=%ERRORLEVEL%"
  popd >nul
  if not "%NPM_INSTALL_CODE%"=="0" (
    echo npm install failed
    popd >nul
    exit /b %NPM_INSTALL_CODE%
  )
)

if not exist "dashboard_app\dist\index.html" (
  pushd "dashboard_app" >nul
  call npm run build
  set "BUILD_CODE=%ERRORLEVEL%"
  popd >nul
  if not "%BUILD_CODE%"=="0" (
    echo dashboard build failed
    popd >nul
    exit /b %BUILD_CODE%
  )
)

set "SAGA_DASHBOARD_NO_BROWSER=1"
if not defined SAGA_DASHBOARD_HOST set "SAGA_DASHBOARD_HOST=127.0.0.1"
if not defined SAGA_DASHBOARD_PORT set "SAGA_DASHBOARD_PORT=8675"
if not defined SAGA_DASHBOARD_LOG_LEVEL set "SAGA_DASHBOARD_LOG_LEVEL=info"

call "venv\Scripts\python.exe" -m dashboard_runtime.app
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
exit /b %EXIT_CODE%
