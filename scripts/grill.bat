@echo off
REM Bangumi Grillmaster launcher script
REM Activates the virtual environment and runs main.py with all arguments

"%~dp0.venv\Scripts\python.exe" "%~dp0main.py" %*
