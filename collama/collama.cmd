@echo off
setlocal
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
