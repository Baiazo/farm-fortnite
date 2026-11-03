@echo off
rem Abre o Farm Automatico sem janela de console.
rem Para rodar como administrador: botao direito neste arquivo > Executar como administrador.
cd /d "%~dp0"
where pythonw >nul 2>nul && (start "" pythonw farm.py & exit /b)
where pyw >nul 2>nul && (start "" pyw -3 farm.py & exit /b)
echo Python nao encontrado. Instale o Python 3.10 ou mais novo em python.org e marque "Add python.exe to PATH".
pause
