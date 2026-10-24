@echo off
REM ============================================================
REM  VozComanda - launcher (qualquer PC Windows)
REM  1. Acha um interpretador Python (py launcher ou python no PATH)
REM  2. Roda vozComanda_bootstrap.py, que instala dependencias faltantes via pip
REM  3. So entao abre o app de voz
REM ============================================================
cd /d "%~dp0"
setlocal

set "PY_CMD="

REM Tenta o py launcher (Python 3.8+). Especifica 3.10+ para ter faster-whisper.
where py >nul 2>nul
if not errorlevel 1 (
  py -3 --version >nul 2>nul
  if not errorlevel 1 set "PY_CMD=py -3"
)

REM Fallback: python no PATH
if not defined PY_CMD (
  where python >nul 2>nul
  if not errorlevel 1 set "PY_CMD=python"
)

if not defined PY_CMD (
  echo.
  echo [rodar] Python NAO encontrado neste computador.
  echo [rodar] Instale o Python 3.10+ de https://www.python.org/downloads/
  echo [rodar] MARQUE a opcao "Add python.exe to PATH" na instalacao.
  echo.
  pause
  exit /b 1
)

echo [rodar] Usando: %PY_CMD%
%PY_CMD% vozComanda_bootstrap.py
if errorlevel 1 (
  echo.
  echo [rodar] Falha no bootstrap. Veja mensagens acima.
  pause
  exit /b 1
)

endlocal
