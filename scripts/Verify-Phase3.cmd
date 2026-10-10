@echo off
setlocal
set "REPO=%~dp0.."
cd /d "%REPO%" || exit /b 1
if not exist ".venv\Scripts\python.exe" (
  echo Missing .venv. Follow outputs/CROSS_DEVICE_SETUP.md.
  exit /b 1
)
where node >nul 2>&1
if errorlevel 1 (
  echo Install Node.js and add it to PATH.
  exit /b 1
)
if not exist outputs mkdir outputs
set "LOG=%CD%\outputs\phase3-host-verification.log"
set "RESULT=0"
set "GROWTH_LIVE_EVAL=0"
echo Phase 3 verification: no live model calls > "%LOG%"
".venv\Scripts\python.exe" -X utf8 -m pytest tests skills/openclaw/skill-wechat-publisher/tests -q --tb=short -p no:cacheprovider >> "%LOG%" 2>&1
set "CHECK=%ERRORLEVEL%"
echo PYTEST_EXIT=%CHECK% >> "%LOG%"
if not "%CHECK%"=="0" set "RESULT=1"
cd web\frontend || exit /b 1
node node_modules\typescript\bin\tsc -b >> "%LOG%" 2>&1
set "CHECK=%ERRORLEVEL%"
echo TSC_EXIT=%CHECK% >> "%LOG%"
if not "%CHECK%"=="0" set "RESULT=1"
node node_modules\oxlint\bin\oxlint >> "%LOG%" 2>&1
set "CHECK=%ERRORLEVEL%"
echo LINT_EXIT=%CHECK% >> "%LOG%"
if not "%CHECK%"=="0" set "RESULT=1"
node node_modules\vite\bin\vite.js build --configLoader native >> "%LOG%" 2>&1
set "CHECK=%ERRORLEVEL%"
echo BUILD_EXIT=%CHECK% >> "%LOG%"
if not "%CHECK%"=="0" set "RESULT=1"
type "%LOG%"
echo Log saved to: %LOG%
exit /b %RESULT%
