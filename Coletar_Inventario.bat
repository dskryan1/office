@echo off
title Office Telco - Coletor de Inventario
cd /d "%~dp0"
rem Edite a linha abaixo UMA vez com o IP do computador da TI (onde roda o painel)
set SERVIDOR=10.70.2.118
python coletor.py %SERVIDOR%
pause
