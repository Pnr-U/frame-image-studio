@echo off
cd /d "%~dp0"
py -3 --version >nul 2>&1
if errorlevel 1 (
  echo Python was not found. Install Python 3 and try again.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto error
)
.venv\Scripts\python.exe -c "import PIL" >nul 2>&1
if errorlevel 1 (
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto error
)
.venv\Scripts\python.exe app.py
if errorlevel 1 goto error
exit /b 0
:error
echo The operation failed. Please share the error message above.
pause
exit /b 1
