@echo off
rem Gera dist\Farm\Farm.exe a partir do codigo. O Python so e preciso aqui: o exe roda sem ele.
cd /d "%~dp0"
where python >nul 2>nul || (
    echo Python nao encontrado. Instale o Python 3.10 ou mais novo em python.org e marque "Add python.exe to PATH".
    pause
    exit /b 1
)
python -c "import numpy, PIL, PyInstaller" 2>nul || (
    echo Instalando numpy, Pillow e PyInstaller...
    python -m pip install -r requirements.txt pyinstaller || (pause & exit /b 1)
)
python gerar_exe.py
pause
