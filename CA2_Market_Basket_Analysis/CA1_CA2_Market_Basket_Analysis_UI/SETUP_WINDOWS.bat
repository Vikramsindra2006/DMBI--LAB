@echo off
setlocal
cd /d "%~dp0"
echo Market Basket Analysis - setup
echo Python 3.12 is tested. Python 3.13 is also allowed by this launcher.
if exist ".venv\Scripts\python.exe" goto install_packages
py -3.12 --version >nul 2>nul
if not errorlevel 1 (
  py -3.12 -m venv .venv
  if errorlevel 1 goto failed
  goto install_packages
)
py -3.13 --version >nul 2>nul
if not errorlevel 1 (
  py -3.13 -m venv .venv
  if errorlevel 1 goto failed
  goto install_packages
)
python -c "import sys; assert sys.version_info[:2] in [(3,12),(3,13)]" >nul 2>nul
if errorlevel 1 goto missing_python
python -m venv .venv
if errorlevel 1 goto failed
:install_packages
".venv\Scripts\python.exe" --version
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Setup completed. Double-click RUN_APP_WINDOWS.bat.
pause
exit /b 0
:missing_python
echo Install Python 3.12 or 3.13 and enable Add to PATH or the Python launcher.
pause
exit /b 1
:failed
echo Setup could not finish. Read the messages above and check the internet connection.
pause
exit /b 1
