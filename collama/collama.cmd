@echo off
setlocal EnableExtensions
set "COLLAMA_VERSION=dev"
if exist "%~dp0VERSION" set /p "COLLAMA_VERSION="<"%~dp0VERSION"
if "%COLLAMA_VERSION%"=="dev" if exist "%~dp0..\VERSION" set /p "COLLAMA_VERSION="<"%~dp0..\VERSION"

if /I "%~1"=="--cofer-version" goto cofer_version
if /I "%~1"=="launch" goto launch

if "%COFER_PHYSICAL_OLLAMA_HOST%"=="" (
  set "OLLAMA_HOST=http://127.0.0.1:11435"
) else (
  set "OLLAMA_HOST=%COFER_PHYSICAL_OLLAMA_HOST%"
)
where ollama >nul 2>nul
if errorlevel 1 (
  echo collama: ollama was not found in PATH 1>&2
  exit /b 127
)
ollama %*
exit /b %ERRORLEVEL%

:launch
if not exist "%~dp0collama_launch.py" (
  echo collama: launcher helper not found: %~dp0collama_launch.py 1>&2
  exit /b 2
)

rem Do not trust ERRORLEVEL alone here. Windows App Execution Aliases can
rem masquerade as python/python3 and still not execute the supplied code.
rem A candidate is valid only when stdout is exactly COFER_PYTHON_OK.
call :probe_py_launcher
if defined COFER_PY_CMD (
  %COFER_PY_CMD% "%~dp0collama_launch.py" %*
  exit /b %ERRORLEVEL%
)
call :probe_python3
if defined COFER_PY_CMD (
  %COFER_PY_CMD% "%~dp0collama_launch.py" %*
  exit /b %ERRORLEVEL%
)
call :probe_python
if defined COFER_PY_CMD (
  %COFER_PY_CMD% "%~dp0collama_launch.py" %*
  exit /b %ERRORLEVEL%
)

echo collama: a working Python 3 interpreter was not found. 1>&2
echo collama: tried py -3, python3, and python; Windows Store aliases are rejected unless they execute the probe. 1>&2
exit /b 127

:probe_py_launcher
set "COFER_PY_CMD="
where py >nul 2>nul || exit /b 0
call :probe_output py -3
if /I "%COFER_PY_PROBE%"=="COFER_PYTHON_OK" set "COFER_PY_CMD=py -3"
exit /b 0

:probe_python3
set "COFER_PY_CMD="
where python3 >nul 2>nul || exit /b 0
call :probe_output python3
if /I "%COFER_PY_PROBE%"=="COFER_PYTHON_OK" set "COFER_PY_CMD=python3"
exit /b 0

:probe_python
set "COFER_PY_CMD="
where python >nul 2>nul || exit /b 0
call :probe_output python
if /I "%COFER_PY_PROBE%"=="COFER_PYTHON_OK" set "COFER_PY_CMD=python"
exit /b 0

:probe_output
set "COFER_PY_PROBE="
set "COFER_PY_PROBE_FILE=%TEMP%\cofer-python-%RANDOM%-%RANDOM%.txt"
%* -c "print('COFER_PYTHON_OK')" >"%COFER_PY_PROBE_FILE%" 2>nul
if exist "%COFER_PY_PROBE_FILE%" set /p "COFER_PY_PROBE="<"%COFER_PY_PROBE_FILE%"
del /q "%COFER_PY_PROBE_FILE%" >nul 2>nul
exit /b 0

:cofer_version
echo collama %COLLAMA_VERSION%
echo wrapper: %~f0
echo launcher: %~dp0collama_launch.py
exit /b 0
