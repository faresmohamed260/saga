@echo off
setlocal
set "ROOT=%~dp0..\.."
pushd "%ROOT%" >nul

if not exist "dashboard_app\node_modules" (
  echo Installing dashboard dependencies...
  pushd "%ROOT%\dashboard_app" >nul
  call npm install
  popd >nul
  if errorlevel 1 (
    echo npm install failed.
    popd >nul
    exit /b 1
  )
)

echo Building S.A.G.A. dashboard...
pushd "%ROOT%\dashboard_app" >nul
call npm run build
set "BUILD_CODE=%ERRORLEVEL%"
popd >nul
if not "%BUILD_CODE%"=="0" (
  echo Dashboard build failed.
  popd >nul
  exit /b %BUILD_CODE%
)

echo Starting S.A.G.A. local web runtime at http://127.0.0.1:8675 ...
call "%ROOT%\venv\Scripts\python.exe" -m dashboard_runtime.app
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
exit /b %EXIT_CODE%
