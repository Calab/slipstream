@echo off
rem Build a single-file Slipstream executable on Windows:  dist\slipstream.exe
rem Double-click this file, or run it from a Command Prompt.
rem Needs Python 3.9-3.14 to BUILD (players of the finished .exe don't need Python).
rem
rem Uses the virtual environment .win_venv (so it can share the project folder
rem with a Linux .venv).  To use a different one:  set VENV=myvenv  first.
setlocal
cd /d "%~dp0\.."
if "%VENV%"=="" set "VENV=.win_venv"

if not exist "%VENV%\Scripts\python.exe" (
    echo Creating a Python environment in %VENV% ...
    py -3 -m venv "%VENV%" 2>nul || python -m venv "%VENV%" || goto :nopython
)

echo Installing build requirements into %VENV% ...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip >nul
"%VENV%\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller || goto :fail

"%VENV%\Scripts\python.exe" tools\build_binary.py || goto :fail

echo.
echo Done: dist\slipstream.exe
pause
exit /b 0

:nopython
echo.
echo Python was not found. Install Python 3.13 from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" during setup, then run this again.
pause
exit /b 1

:fail
echo.
echo The build failed - see the messages above.
pause
exit /b 1
