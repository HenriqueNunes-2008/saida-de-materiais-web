@echo off
title Iniciando o Sistema de Almoxarifado
cd /d %~dp0

:: Verifica se o Python está instalado
where python >nul 2>nul
if errorlevel 1 (
    echo Python não encontrado. Por favor, instale o Python e tente novamente.
    pause
    exit
)

:: Cria ambiente virtual se não existir
if not exist venv (
    echo Criando ambiente virtual...
    python -m venv venv
)

:: Ativa o ambiente virtual
call venv\Scripts\activate.bat

:: Instala dependências
echo Instalando dependências...
pip install -r requirements.txt

:: Inicia o sistema Flask
echo Iniciando o servidor...
python app.py

pause
