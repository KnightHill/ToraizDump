@echo off
setlocal
set "launcher=%~dp0.venv\Scripts\toraiz-dump.exe"

if not exist "%launcher%" (
    echo toraiz-dump: project launcher not found; run: .venv\Scripts\python.exe -m pip install -e . 1>&2
    exit /b 1
)

"%launcher%" %*
exit /b %errorlevel%
