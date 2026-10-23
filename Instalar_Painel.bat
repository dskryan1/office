@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado. Instale Python 3.11 ou 3.12 do site oficial e marque "Add Python to PATH".
  pause
  exit /b 1
)
py -3 -m venv .venv
if errorlevel 1 (
  echo Falha ao criar ambiente virtual.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Falha ao instalar dependencias. Verifique internet/proxy e tente novamente.
  pause
  exit /b 1
)
echo.
echo Instalacao concluida. Agora execute Iniciar_Painel.bat
pause
