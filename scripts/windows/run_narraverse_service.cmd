@echo off
setlocal
set "ROOT=%~dp0..\.."
set "APP_DIR=%ROOT%\apps\narraverse_web"
pushd "%APP_DIR%" >nul

if not exist "node_modules\next\dist\bin\next" (
  echo Missing Next.js runtime. Run npm install in apps\narraverse_web first.
  popd >nul
  exit /b 1
)

if not defined PORT set "PORT=8676"
if not defined HOSTNAME set "HOSTNAME=127.0.0.1"

"C:\Program Files\nodejs\node.exe" "node_modules\next\dist\bin\next" start --hostname %HOSTNAME% --port %PORT%
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
exit /b %EXIT_CODE%
