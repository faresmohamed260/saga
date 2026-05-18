@echo off
setlocal EnableDelayedExpansion
set "ROOT=%~dp0..\.."
pushd "%ROOT%" >nul

if not exist "venv\Scripts\python.exe" (
  echo Missing venv\Scripts\python.exe
  echo Create the virtual environment and install dependencies first.
  popd >nul
  exit /b 1
)

echo.
echo SAGA Task Launcher
echo ------------------
echo 1. inspect-corpus
echo 2. encode-store
echo 3. rebuild-corpus
echo 4. generate-blueprint-neo4j
echo 5. generate-sequel-neo4j
echo 6. audit-corpus
echo 7. custom saga_tools command
echo.
set /p "CHOICE=Choose a task number: "

set "COMMAND="
if "%CHOICE%"=="1" set "COMMAND=inspect-corpus"
if "%CHOICE%"=="2" set "COMMAND=encode-store"
if "%CHOICE%"=="3" set "COMMAND=rebuild-corpus"
if "%CHOICE%"=="4" set "COMMAND=generate-blueprint-neo4j"
if "%CHOICE%"=="5" set "COMMAND=generate-sequel-neo4j"
if "%CHOICE%"=="6" set "COMMAND=audit-corpus"
if "%CHOICE%"=="7" (
  set /p "COMMAND=Enter the full saga_tools subcommand: "
)

if not defined COMMAND (
  echo Invalid selection.
  popd >nul
  exit /b 1
)

echo.
echo Selected command: !COMMAND!
echo Enter the rest of the arguments exactly as you want them passed.
echo Example: --series-id acotar --output-dir analysis_outputs\generated_narratives\acotar_book6
set /p "ARGS=Arguments: "

echo.
echo Running: venv\Scripts\python.exe saga_tools.py !COMMAND! !ARGS!
venv\Scripts\python.exe saga_tools.py !COMMAND! !ARGS!
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
exit /b %EXIT_CODE%
