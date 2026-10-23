@echo off
title Office Telco - Painel de TI
cd /d "%~dp0"
echo A iniciar o painel central de TI na rede...
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
pause
